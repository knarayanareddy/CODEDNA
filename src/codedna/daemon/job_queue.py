"""
Job queue for CodeDNA build jobs.
"""

import asyncio
import logging
from typing import Optional
from sqlalchemy import text

from codedna.db.models import generate_uuid, utc_now

logger = logging.getLogger(__name__)

_job_queue: Optional["JobQueue"] = None


class JobQueue:
    """
    Background job queue for processing build jobs.
    Per design doc §6.4: Daemon spawns job worker thread pool (default: 2 workers).
    Emits SSE events for job state changes.
    """
    
    def __init__(self, engine):
        self.engine = engine
        self.workers: list[asyncio.Task] = []
        self.num_workers = 2
        self.running = False
    
    async def start(self) -> None:
        """Start the job queue workers."""
        self.running = True
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker(i))
            self.workers.append(task)
        logger.info(f"Job queue started with {self.num_workers} workers")
    
    async def stop(self) -> None:
        """Stop the job queue workers gracefully."""
        logger.info("Stopping job queue...")
        self.running = False
        for task in self.workers:
            try:
                await asyncio.wait_for(task, timeout=30)
            except asyncio.TimeoutError:
                task.cancel()
        self.workers.clear()
        logger.info("Job queue stopped")
    
    async def enqueue(self, job_id: str) -> None:
        """Enqueue a job for processing."""
        from codedna.daemon.events import emit_job_event, EventType
        
        logger.info(f"Enqueuing job: {job_id}")
        
        # Emit job.queued event
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT repo_id FROM jobs WHERE id = :id"), {"id": job_id})
                row = result.fetchone()
            if row:
                await emit_job_event(EventType.JOB_QUEUED, job_id, row[0])
        except Exception as e:
            logger.error(f"Failed to emit job.queued event: {e}")
    
    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine that processes jobs."""
        from codedna.daemon.events import emit_job_event, EventType
        
        logger.info(f"Worker {worker_id} started")
        
        while self.running:
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT id, repo_id, type
                        FROM jobs
                        WHERE status = 'QUEUED'
                        ORDER BY created_at ASC
                        LIMIT 1
                    """))
                    row = result.fetchone()
                
                if row:
                    job_id, repo_id, job_type = row[0], row[1], row[2]
                    
                    now = utc_now()
                    with self.engine.connect() as conn:
                        conn.execute(text("UPDATE jobs SET status = 'RUNNING', started_at = :started_at WHERE id = :job_id"),
                                     {"started_at": now, "job_id": job_id})
                        conn.commit()
                    
                    # Emit job.started event
                    await emit_job_event(EventType.JOB_STARTED, job_id, repo_id, job_type=job_type)
                    
                    logger.info(f"Worker {worker_id} processing job {job_id}")
                    
                    try:
                        await self._process_job(job_id, repo_id, job_type)
                        
                        with self.engine.connect() as conn:
                            now = utc_now()
                            conn.execute(text("UPDATE jobs SET status = 'COMPLETE', progress = 1.0, completed_at = :completed_at WHERE id = :job_id"),
                                         {"completed_at": now, "job_id": job_id})
                            conn.commit()
                        
                        logger.info(f"Job {job_id} completed")
                        
                        # Emit job.complete and build.complete events
                        await emit_job_event(EventType.JOB_COMPLETE, job_id, repo_id)
                        await emit_job_event(EventType.BUILD_COMPLETE, job_id, repo_id, success=True)
                        
                    except Exception as e:
                        logger.error(f"Job {job_id} failed: {e}")
                        
                        with self.engine.connect() as conn:
                            now = utc_now()
                            conn.execute(text("UPDATE jobs SET status = 'FAILED', error = :error, completed_at = :completed_at WHERE id = :job_id"),
                                         {"error": str(e), "completed_at": now, "job_id": job_id})
                            conn.commit()
                        
                        # Emit job.failed event
                        await emit_job_event(EventType.JOB_FAILED, job_id, repo_id, error=str(e))
                else:
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(5)
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _process_job(self, job_id: str, repo_id: str, job_type: str) -> None:
        """Process a build job."""
        from codedna.harvester.harvester import Harvester
        from codedna.db.schema import get_active_fingerprint_for_repo
        from codedna.daemon.events import emit_job_event, EventType
        
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT path FROM repos WHERE id = :id"), {"id": repo_id})
            row = result.fetchone()
        
        if not row:
            raise ValueError(f"Repository not found: {repo_id}")
        
        repo_path = row[0]
        
        harvester = Harvester(repo_path)
        
        async def progress_callback(p: float):
            # Emit progress updates
            with self.engine.connect() as conn:
                conn.execute(text("UPDATE jobs SET progress = :progress WHERE id = :job_id"), {"progress": p, "job_id": job_id})
                conn.commit()
            await emit_job_event(EventType.JOB_PROGRESS, job_id, repo_id, progress=p)
        
        fingerprint_data = await harvester.build_baseline(progress_callback=progress_callback)
        
        await self._save_fingerprint(repo_id, job_id, fingerprint_data)
    
    async def _save_fingerprint(self, repo_id: str, job_id: str, fingerprint_data: dict) -> None:
        """Save the computed fingerprint to the database."""
        import msgpack
        
        with self.engine.connect() as conn:
            conn.execute(text("UPDATE fingerprints SET is_active = 0, updated_at = :updated_at WHERE repo_id = :repo_id AND is_active = 1"),
                         {"updated_at": utc_now(), "repo_id": repo_id})
            
            now = utc_now()
            conn.execute(text("""
                INSERT INTO fingerprints 
                (id, repo_id, version, vector_dims, model_blob, commit_hash,
                 commit_count, file_count, build_duration_s, created_at, updated_at, is_active)
                VALUES (:id, :repo_id, :version, :vector_dims, :model_blob, :commit_hash,
                        :commit_count, :file_count, :build_duration_s, :created_at, :updated_at, :is_active)
            """), {
                "id": generate_uuid(),
                "repo_id": repo_id,
                "version": 1,
                "vector_dims": fingerprint_data.get("vector_dims", 32),
                "model_blob": msgpack.packb(fingerprint_data.get("model", [])),
                "commit_hash": fingerprint_data.get("commit_hash", ""),
                "commit_count": fingerprint_data.get("commit_count", 0),
                "file_count": fingerprint_data.get("file_count", 0),
                "build_duration_s": fingerprint_data.get("duration_s"),
                "created_at": now,
                "updated_at": now,
                "is_active": 1,
            })
            conn.commit()


def get_job_queue() -> Optional[JobQueue]:
    """Get the global job queue instance."""
    return _job_queue


def set_job_queue(queue: JobQueue) -> None:
    """Set the global job queue instance."""
    global _job_queue
    _job_queue = queue
