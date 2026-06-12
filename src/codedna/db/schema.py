"""Database schema management for CodeDNA."""
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)
CURRENT_SCHEMA_VERSION = 1

def get_config_dir() -> Path:
    home = Path.home()
    config_dir = home / ".codedna"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_db_path() -> Path:
    return get_config_dir() / "codedna.db"

def get_migrations_dir() -> Path:
    """Get the path to the migrations directory.
    
    Handles both editable installs and wheel installs by checking multiple possible locations.
    """
    # Start from the codedna package location
    package_dir = Path(__file__).parent.parent
    
    # Try multiple possible locations for migrations
    possible_paths = [
        # 1. Next to the package (for editable installs from project root)
        package_dir.parent / "migrations",
        # 2. In src/ parent (when package is at src/codedna)
        package_dir.parent.parent / "migrations",
        # 3. Installed location (when pip installed from wheel)
        package_dir / "migrations",
        # 4. Fallback: check if it's a package resource
        Path(__file__).parent / "migrations",
    ]
    
    for path in possible_paths:
        if path.exists() and path.is_dir():
            return path
    
    # Last resort: return the expected path (will fail with clear error later)
    logger.warning(f"Migrations directory not found in any expected location")
    return possible_paths[0]  # Return the first path for error message

def init_db(engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()
        run_migrations(conn)

def run_migrations(conn) -> None:
    migrations_dir = get_migrations_dir()
    if not migrations_dir.exists():
        logger.warning(f"Migrations directory not found: {migrations_dir}")
        return
    current_version = get_schema_version(conn)
    for migration_file in sorted(migrations_dir.glob("*.sql")):
        try:
            version = int(migration_file.stem.split("_")[0])
        except (ValueError, IndexError):
            continue
        if version <= current_version:
            continue
        logger.info(f"Applying migration {version}: {migration_file.name}")
        try:
            sql_content = migration_file.read_text()
            for statement in sql_content.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(text(statement))
            conn.commit()
            logger.info(f"Migration {version} applied successfully")
        except Exception as e:
            logger.error(f"Migration {version} failed: {e}")
            conn.rollback()
            raise

def get_schema_version(conn) -> int:
    result = conn.execute(text("PRAGMA user_version"))
    row = result.fetchone()
    return int(row[0]) if row else 0

def get_active_fingerprint_for_repo(conn, repo_id: str) -> Optional[dict]:
    """Get the active fingerprint for a repository, including the feature vector.
    
    Returns the fingerprint with deserialized model_blob (feature vector) for baseline comparison.
    """
    import msgpack
    
    result = conn.execute(text("""
        SELECT id, version, vector_dims, model_blob, commit_hash, commit_count, file_count, build_duration_s, created_at
        FROM fingerprints WHERE repo_id = :repo_id AND is_active = 1 AND deleted_at IS NULL
        ORDER BY created_at DESC LIMIT 1"""), {"repo_id": repo_id})
    row = result.fetchone()
    if row:
        # Deserialize the msgpack model_blob to get the feature vector
        feature_vector = None
        if row[3]:  # model_blob
            try:
                unpacked_bytes = msgpack.unpackb(row[3], raw=False)
                if isinstance(unpacked_bytes, bytes):
                    import struct
                    # Unpack first 32 float32 values (128 bytes) representing the mean vector
                    feature_vector = list(struct.unpack(f"{32}f", unpacked_bytes[:128]))
                else:
                    feature_vector = unpacked_bytes
            except Exception as e:
                logger.error(f"Failed to deserialize model_blob: {e}")
        
        return {
            "id": row[0], 
            "version": row[1], 
            "vector_dims": row[2], 
            "model_blob": row[3],
            "feature_vector": feature_vector,  # The actual 32-dim vector for comparison
            "commit_hash": row[4],
            "commit_count": row[5], 
            "file_count": row[6], 
            "build_duration_s": row[7], 
            "created_at": row[8]
        }
    return None

def list_tracked_repos(conn) -> list:
    result = conn.execute(text("SELECT id, path, name, language, created_at, updated_at FROM repos WHERE deleted_at IS NULL ORDER BY created_at DESC"))
    return [{"id": row[0], "path": row[1], "name": row[2], "language": row[3], "created_at": row[4], "updated_at": row[5]} for row in result.fetchall()]

def add_repo(conn, path: str, name: str, language: str = "python") -> str:
    from codedna.db.models import generate_uuid, utc_now
    repo_id = generate_uuid()
    now = utc_now()
    conn.execute(text("INSERT INTO repos (id, path, name, language, created_at, updated_at) VALUES (:id, :path, :name, :language, :created_at, :updated_at)"),
                 {"id": repo_id, "path": path, "name": name, "language": language, "created_at": now, "updated_at": now})
    conn.commit()
    conn.execute(text("INSERT INTO audit_log (id, event_type, entity_type, entity_id, detail, created_at) VALUES (:id, :event_type, :entity_type, :entity_id, :detail, :created_at)"),
                 {"id": generate_uuid(), "event_type": "repo_added", "entity_type": "repo", "entity_id": repo_id, "detail": f'{{"path": "{path}"}}', "created_at": now})
    conn.commit()
    return repo_id

def remove_repo(conn, repo_id: str) -> bool:
    now = utc_now()
    result = conn.execute(text("UPDATE repos SET deleted_at = :deleted_at, updated_at = :updated_at WHERE id = :repo_id AND deleted_at IS NULL"),
                         {"deleted_at": now, "updated_at": now, "repo_id": repo_id})
    conn.commit()
    return result.rowcount > 0

def erase_repo_data(conn, repo_id: str) -> dict:
    results = {}
    for table in ["scan_results", "feature_vectors", "fingerprints", "jobs"]:
        result = conn.execute(text(f"DELETE FROM {table} WHERE repo_id = :repo_id"), {"repo_id": repo_id})
        results[f"{table}_deleted"] = result.rowcount
    conn.commit()
    return results

def prune_old_data(engine, scan_retention_days: int = 90, job_retention_days: int = 30) -> dict:
    from codedna.db.models import utc_now
    cutoff_time = utc_now() - (scan_retention_days * 86400)
    job_cutoff = utc_now() - (job_retention_days * 86400)
    results = {}
    with engine.connect() as conn:
        result = conn.execute(text("DELETE FROM scan_results WHERE created_at < :cutoff"), {"cutoff": cutoff_time})
        results["scan_results_deleted"] = result.rowcount
        result = conn.execute(text("DELETE FROM jobs WHERE created_at < :cutoff AND status IN ('COMPLETE', 'FAILED')"), {"cutoff": job_cutoff})
        results["jobs_deleted"] = result.rowcount
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        conn.commit()
    return results
