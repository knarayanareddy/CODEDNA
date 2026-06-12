"""API routes for CodeDNA daemon."""
import logging
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_conn():
    from codedna.db.session import get_raw_connection
    return get_raw_connection()


class StatusResponse(BaseModel):
    status: str = "running"
    db_version: int
    expected_schema_version: int
    rebuild_required: bool
    active_repos: list = []
    interrupted_jobs: list = []


class RepoCreateRequest(BaseModel):
    path: str
    language: str = "python"


class ScanFileRequest(BaseModel):
    repo_id: str
    file_path: str
    language: str = "python"
    content_hash: str | None = None


class ExportRequest(BaseModel):
    repo_id: str
    format: str = Field(default="json")
    include: list[str] = Field(default=["fingerprint", "evolution", "scan_history"])
    confirmed: bool


@router.get("/status", response_model=StatusResponse)
async def get_status():
    from codedna.db.schema import get_schema_version, list_tracked_repos
    from sqlalchemy import text
    
    conn = _get_conn()
    db_version = get_schema_version(conn)
    repos = list_tracked_repos(conn)
    result = conn.execute(text("SELECT id, repo_id, type, error FROM jobs WHERE status = 'RUNNING'"))
    interrupted_jobs = [{"id": row[0], "repo_id": row[1], "type": row[2], "error": row[3]} for row in result.fetchall()]
    conn.close()
    
    return StatusResponse(
        status="running",
        db_version=db_version,
        expected_schema_version=1,
        rebuild_required=False,
        active_repos=repos,
        interrupted_jobs=interrupted_jobs,
    )


@router.get("/repos")
async def list_repos():
    from codedna.db.schema import list_tracked_repos
    conn = _get_conn()
    repos = list_tracked_repos(conn)
    conn.close()
    return repos


@router.post("/repos", status_code=201)
async def create_repo(request: RepoCreateRequest):
    from pathlib import Path
    from codedna.db.schema import add_repo
    from sqlalchemy import text
    
    repo_path = Path(request.path)
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail={"code": "INVALID_PATH", "message": f"Path does not exist"})
    if not (repo_path / ".git").exists():
        raise HTTPException(status_code=400, detail={"code": "NOT_A_GIT_REPO", "message": "Not a git repository"})
    
    conn = _get_conn()
    existing = conn.execute(text("SELECT id FROM repos WHERE path = :path AND deleted_at IS NULL"), {"path": str(repo_path)}).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail={"code": "REPO_ALREADY_TRACKED", "message": "Repository already tracked"})
    
    name = repo_path.name
    repo_id = add_repo(conn, str(repo_path), name, request.language)
    conn.close()
    return {"id": repo_id, "path": str(repo_path), "name": name, "language": request.language}


@router.delete("/repos/{repo_id}", status_code=204)
async def delete_repo(repo_id: str):
    from codedna.db.schema import remove_repo
    conn = _get_conn()
    if not remove_repo(conn, repo_id):
        conn.close()
        raise HTTPException(status_code=404, detail={"code": "REPO_NOT_FOUND", "message": "Repository not found"})
    conn.close()


@router.delete("/repos/{repo_id}/data", status_code=200)
async def erase_repo_data(repo_id: str):
    """Erase all data for a repository (fingerprints, scan results, jobs) without deleting the repo."""
    from codedna.db.schema import erase_repo_data
    conn = _get_conn()
    
    # Verify repo exists
    existing = conn.execute(text("SELECT id FROM repos WHERE id = :id AND deleted_at IS NULL"), {"id": repo_id}).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail={"code": "REPO_NOT_FOUND", "message": "Repository not found"})
    
    results = erase_repo_data(conn, repo_id)
    conn.close()
    
    return {"repo_id": repo_id, "erased": results}


@router.post("/repos/{repo_id}/build")
async def enqueue_build(repo_id: str):
    from codedna.db.models import generate_uuid, utc_now
    from sqlalchemy import text
    from codedna.daemon.job_queue import get_job_queue
    
    conn = _get_conn()
    existing = conn.execute(text("SELECT id FROM repos WHERE id = :id AND deleted_at IS NULL"), {"id": repo_id}).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail={"code": "REPO_NOT_FOUND", "message": "Repository not found"})
    
    existing_job = conn.execute(text("SELECT id FROM jobs WHERE repo_id = :repo_id AND status IN ('QUEUED', 'RUNNING')"), {"repo_id": repo_id}).fetchone()
    if existing_job:
        conn.close()
        raise HTTPException(status_code=409, detail={"code": "BUILD_ALREADY_RUNNING", "message": "Build already running"})
    
    job_id = generate_uuid()
    now = utc_now()
    conn.execute(text("INSERT INTO jobs (id, repo_id, type, status, created_at) VALUES (:id, :repo_id, :type, :status, :created_at)"),
                 {"id": job_id, "repo_id": repo_id, "type": "FULL_BUILD", "status": "QUEUED", "created_at": now})
    conn.commit()
    conn.close()
    
    job_queue = get_job_queue()
    if job_queue:
        await job_queue.enqueue(job_id)
    
    return {"job_id": job_id, "status": "QUEUED"}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    from sqlalchemy import text
    conn = _get_conn()
    result = conn.execute(text("SELECT id, repo_id, type, status, progress, started_at, completed_at, error, created_at FROM jobs WHERE id = :id"), {"id": job_id}).fetchone()
    conn.close()
    if not result:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": "Job not found"})
    return {"id": result[0], "repo_id": result[1], "type": result[2], "status": result[3], "progress": result[4], "started_at": result[5], "completed_at": result[6], "error": result[7], "created_at": result[8]}


@router.post("/scan/file")
async def scan_file(request: ScanFileRequest):
    from codedna.db.models import generate_uuid, utc_now
    from codedna.db.schema import get_active_fingerprint_for_repo
    from codedna.daemon.scanner_client import invoke_scanner
    from sqlalchemy import text
    from codedna.explainer import Explainer
    from codedna.daemon.events import emit_scan_event
    
    start_time = time.time()
    scan_id = generate_uuid()
    degraded = False
    dna_score = None
    baseline_vector = None
    explanation = {"summary": "No fingerprint available"}
    
    try:
        conn = _get_conn()
        fingerprint = get_active_fingerprint_for_repo(conn, request.repo_id)
        conn.close()
        
        if not fingerprint:
            return {"scan_id": scan_id, "dna_score": None, "explanation": explanation, "latency_ms": (time.time() - start_time) * 1000, "degraded": True}
        
        # Get baseline vector for comparison
        baseline_vector = fingerprint.get("feature_vector")
        
        file_content = ""
        try:
            from pathlib import Path
            if Path(request.file_path).exists():
                file_content = Path(request.file_path).read_text(errors="replace")
        except:
            pass
        
        # Invoke scanner (uses Rust if available, falls back to Python baseline comparison)
        result = await invoke_scanner(
            "scan_file", request.language, file_content, request.file_path, baseline_vector
        )
        
        if result.error:
            degraded = True
        else:
            dna_score = result.score if result.score else 0.85
            explainer = Explainer()
            # Pass baseline_vector and dna_score for proper explanation generation
            explanation = explainer.explain(
                result.partial_vector, 
                baseline_vector=baseline_vector,
                dna_score=dna_score,
                verbosity="brief"
            )
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        degraded = True
    
    conn = _get_conn()
    fingerprint = get_active_fingerprint_for_repo(conn, request.repo_id)
    if fingerprint:
        now = utc_now()
        conn.execute(text("INSERT INTO scan_results (id, repo_id, fingerprint_id, scan_type, trigger, file_path, dna_score, latency_ms, degraded, created_at) VALUES (:id, :repo_id, :fingerprint_id, :scan_type, :trigger, :file_path, :dna_score, :latency_ms, :degraded, :created_at)"),
                     {"id": scan_id, "repo_id": request.repo_id, "fingerprint_id": fingerprint["id"], "scan_type": "file", "trigger": "ide_save", "file_path": request.file_path, "dna_score": dna_score, "latency_ms": (time.time() - start_time) * 1000, "degraded": 1 if degraded else 0, "created_at": now})
        conn.commit()
    conn.close()
    
    # Emit scan complete event
    if dna_score is not None:
        try:
            await emit_scan_event(scan_id, request.repo_id, dna_score, request.file_path)
        except Exception as e:
            logger.error(f"Failed to emit scan event: {e}")
    
    return {"scan_id": scan_id, "dna_score": dna_score, "explanation": explanation, "latency_ms": (time.time() - start_time) * 1000, "degraded": degraded}


@router.get("/evolution/{repo_id}")
async def get_evolution(repo_id: str):
    from sqlalchemy import text
    conn = _get_conn()
    result = conn.execute(text("SELECT created_at, dna_score, degraded FROM scan_results WHERE repo_id = :repo_id ORDER BY created_at DESC LIMIT 100"), {"repo_id": repo_id})
    scans = [{"timestamp": row[0], "score": row[1], "degraded": bool(row[2])} for row in result.fetchall()]
    conn.close()
    # Safely compute average score - avoid division by zero when all scores are None
    valid_scores = [s["score"] for s in scans if s["score"] is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else None
    trend = "insufficient_data" if len(scans) < 2 else "stable"
    return {"repo_id": repo_id, "scan_count": len(scans), "average_score": avg_score, "trend": trend, "scans": scans}


@router.get("/config")
async def get_config():
    from codedna.config import load_config_file
    return load_config_file()


@router.post("/export")
async def export_data(request: ExportRequest):
    if not request.confirmed:
        raise HTTPException(status_code=400, detail={"code": "EXPORT_NOT_CONFIRMED", "message": "Export requires confirmed: true"})
    from codedna.db.schema import get_active_fingerprint_for_repo
    from sqlalchemy import text
    import time
    conn = _get_conn()
    fingerprint = get_active_fingerprint_for_repo(conn, request.repo_id)
    scans_result = conn.execute(text("SELECT created_at, dna_score, scan_type, trigger, file_path FROM scan_results WHERE repo_id = :repo_id ORDER BY created_at DESC"), {"repo_id": request.repo_id})
    scans = [dict(row) for row in scans_result.fetchall()]
    conn.close()
    export_data = {"fingerprint": fingerprint} if "fingerprint" in request.include else {}
    if "evolution" in request.include or "scan_history" in request.include:
        export_data["scans"] = scans
    return {"format": request.format, "data": export_data, "exported_at": int(time.time())}


@router.get("/events")
async def events():
    from sse_starlette.sse import EventSourceResponse
    from codedna.daemon.events import get_event_bus, EventType
    
    async def event_generator():
        # Subscribe to all events
        event_bus = get_event_bus()
        queue = await event_bus.subscribe()
        
        # Also send periodic status updates
        import asyncio
        status_task = None
        
        async def send_periodic_status():
            while True:
                await asyncio.sleep(15)
                await event_bus.broadcast_status()
        
        status_task = asyncio.create_task(send_periodic_status())
        
        try:
            while True:
                # Wait for events with timeout
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield event.to_sse_format()
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield "event: keepalive\ndata: {}\n\n"
                    
        except asyncio.CancelledError:
            pass
        finally:
            if status_task:
                status_task.cancel()
            await event_bus.unsubscribe(queue)
    
    return EventSourceResponse(event_generator())
