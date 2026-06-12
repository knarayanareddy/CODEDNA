"""FastAPI application for CodeDNA daemon."""
import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from codedna.config import get_daemon_config, setup_logging
from codedna.db.session import init_database, close_engine
from codedna.db.schema import get_schema_version, CURRENT_SCHEMA_VERSION

logger = logging.getLogger(__name__)

# Global job queue
job_queue = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global job_queue
    
    logger.info("CodeDNA daemon starting...")
    
    try:
        init_database()
        
        from codedna.db.session import get_raw_connection
        from codedna.daemon.job_queue import JobQueue, set_job_queue
        
        with get_raw_connection() as conn:
            db_version = get_schema_version(conn)
        
        if db_version > CURRENT_SCHEMA_VERSION:
            logger.error(f"FATAL: Database schema version ({db_version}) is newer than this CodeDNA binary supports ({CURRENT_SCHEMA_VERSION}).")
            print(f"\nERROR: Database schema version ({db_version}) is newer than this CodeDNA binary supports ({CURRENT_SCHEMA_VERSION}).\n")
            sys.exit(1)
        
        # Initialize job queue
        from codedna.db.session import get_engine
        job_queue = JobQueue(get_engine())
        await job_queue.start()
        set_job_queue(job_queue)
        
        logger.info(f"Database initialized, schema version: {db_version}")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    logger.info("CodeDNA daemon shutting down...")
    
    if job_queue:
        await job_queue.stop()
    
    close_engine()


from pathlib import Path

def get_dashboard_dir() -> Path:
    package_dir = Path(__file__).parent.parent
    possible_paths = [
        package_dir / "dashboard",
        package_dir.parent / "dashboard",
        package_dir.parent.parent / "dashboard",
    ]
    for path in possible_paths:
        if path.exists() and path.is_dir():
            return path
    return possible_paths[0]


def create_app() -> FastAPI:
    setup_logging()
    
    app = FastAPI(
        title="CodeDNA API",
        description="Local-first, privacy-preserving developer identity API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    
    from codedna.daemon.middleware import (
        ClientValidationMiddleware,
        LocalhostOnlyMiddleware,
        RateLimitMiddleware,
    )
    # Add security middleware (order matters - first added is outermost)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(ClientValidationMiddleware)
    app.add_middleware(LocalhostOnlyMiddleware)
    
    from codedna.daemon.routes import router
    app.include_router(router, prefix="/api/v1")
    
    @app.get("/")
    async def root():
        from fastapi.responses import FileResponse
        index_file = get_dashboard_dir() / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"name": "CodeDNA", "version": "0.1.0", "status": "running", "docs": "/docs"}
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.detail.get("code") if isinstance(exc.detail, dict) else f"HTTP_{exc.status_code}",
                    "message": exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred"}}
        )
    
    return app


def run_daemon() -> None:
    config = get_daemon_config()
    app = create_app()
    
    server_config = uvicorn.Config(
        app=app,
        host=config["host"],
        port=config["port"],
        log_level="info",
        access_log=True,
    )
    
    server = uvicorn.Server(server_config)
    
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        server.should_exit = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info(f"Starting CodeDNA daemon on {config['host']}:{config['port']}")
    asyncio.run(server.serve())


if __name__ == "__main__":
    run_daemon()
