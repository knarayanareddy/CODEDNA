"""CodeDNA CLI - Main entry point and command definitions."""
import argparse
import logging
import sys
from pathlib import Path
from codedna import __version__
from codedna.config import get_daemon_config, get_config_dir
from codedna.db.session import init_database, get_raw_connection
from codedna.db.schema import CURRENT_SCHEMA_VERSION, prune_old_data

logger = logging.getLogger(__name__)

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codedna", description="CodeDNA - Local-first developer identity and code intelligence")
    parser.add_argument("--version", action="version", version=f"CodeDNA {__version__}")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    init_parser = subparsers.add_parser("init", help="Initialize CodeDNA")
    init_parser.add_argument("path", nargs="?", help="Path to repository")
    init_parser.add_argument("--language", default="python", help="Primary language")
    
    build_parser = subparsers.add_parser("build", help="Build baseline fingerprint")
    build_parser.add_argument("--repo", help="Repository path")
    build_parser.add_argument("--async", dest="async_mode", action="store_true", help="Run build asynchronously")
    
    scan_parser = subparsers.add_parser("scan", help="Scan files or diff")
    scan_parser.add_argument("target", help="File or diff to scan")
    scan_parser.add_argument("--type", choices=["file", "diff"], default="file", help="Scan type")
    scan_parser.add_argument("--repo", help="Repository ID")
    scan_parser.add_argument("--language", default="python", help="Language")
    
    status_parser = subparsers.add_parser("status", help="Show status")
    status_parser.add_argument("--slo", action="store_true", help="Show SLO summary")
    
    export_parser = subparsers.add_parser("export", help="Export data")
    export_parser.add_argument("--repo", required=True, help="Repository ID")
    export_parser.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")
    export_parser.add_argument("--output", help="Output file path")
    export_parser.add_argument("--confirmed", action="store_true", help="Confirm export")
    
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("action", choices=["get", "set", "list"], help="Config action")
    config_parser.add_argument("key", nargs="?", help="Config key")
    config_parser.add_argument("value", nargs="?", help="Config value")
    
    daemon_parser = subparsers.add_parser("daemon", help="Manage the daemon")
    daemon_parser.add_argument("action", choices=["start", "stop", "restart", "status"], help="Daemon action")
    
    db_parser = subparsers.add_parser("db", help="Database management")
    db_parser.add_argument("action", choices=["prune", "repair", "reset", "backup"], help="DB action")
    db_parser.add_argument("--repo", help="Repository ID for partial operations")
    
    return parser

def cmd_init(args) -> int:
    from codedna.db.schema import add_repo
    if not args.path:
        args.path = str(Path.cwd())
    repo_path = Path(args.path).resolve()
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}")
        return 1
    if not (repo_path / ".git").exists():
        print(f"Error: Not a git repository: {repo_path}")
        return 1
    init_database()
    conn = get_raw_connection()
    try:
        repo_id = add_repo(conn, str(repo_path), repo_path.name, args.language)
        print(f"Repository added: {repo_path}")
        print(f"Repository ID: {repo_id}")
        print(f"\nTo build a baseline fingerprint, run: codedna build --repo {repo_id}")
    except Exception as e:
        if "UNIQUE" in str(e):
            print("Error: Repository is already being tracked.")
            return 1
        raise
    finally:
        conn.close()
    return 0

def cmd_build(args) -> int:
    import requests
    repo_id = args.repo
    if not repo_id:
        print("Error: --repo is required")
        return 1
    config = get_daemon_config()
    try:
        response = requests.get(f"http://{config['host']}:{config['port']}/health", timeout=2)
        if response.status_code != 200:
            print("Error: Daemon is not running. Start it with: codedna daemon start")
            return 1
    except requests.exceptions.ConnectionError:
        print("Error: Daemon is not running. Start it with: codedna daemon start")
        return 1
    try:
        response = requests.post(f"http://{config['host']}:{config['port']}/api/v1/repos/{repo_id}/build", headers={"X-CodeDNA-Client": "cli"}, timeout=5)
        response.raise_for_status()
        result = response.json()
        print(f"Build job enqueued: {result['job_id']}")
        print(f"Status: {result['status']}")
        if not args.async_mode:
            print("\nWaiting for build to complete...")
            import time
            while True:
                job_response = requests.get(f"http://{config['host']}:{config['port']}/api/v1/jobs/{result['job_id']}", headers={"X-CodeDNA-Client": "cli"}, timeout=5)
                job_result = job_response.json()
                if job_result["status"] == "COMPLETE":
                    print("Build completed successfully!")
                    break
                elif job_result["status"] == "FAILED":
                    print(f"Build failed: {job_result['error']}")
                    return 1
                else:
                    progress = job_result.get("progress", 0) or 0
                    print(f"\rProgress: {progress * 100:.1f}%", end="", flush=True)
                time.sleep(2)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return 1
    return 0

def cmd_scan(args) -> int:
    import requests
    config = get_daemon_config()
    try:
        requests.get(f"http://{config['host']}:{config['port']}/health", timeout=2)
    except requests.exceptions.ConnectionError:
        print("Error: Daemon is not running. Start it with: codedna daemon start")
        return 1
    file_path = Path(args.target)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return 1
    try:
        response = requests.post(f"http://{config['host']}:{config['port']}/api/v1/scan/file", headers={"X-CodeDNA-Client": "cli"}, json={"repo_id": args.repo or "", "file_path": str(file_path), "language": args.language}, timeout=10)
        response.raise_for_status()
        result = response.json()
        print(f"Scan completed in {result['latency_ms']:.0f}ms")
        if result.get("degraded"):
            print("Warning: Scan degraded")
        if result.get("dna_score") is not None:
            print(f"DNA Score: {result['dna_score']:.2f}")
            print(f"Explanation: {result['explanation']['summary']}")
        else:
            print("No fingerprint available for comparison.")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return 1
    return 0

def cmd_status(args) -> int:
    init_database()
    config = get_daemon_config()
    try:
        import requests
        response = requests.get(f"http://{config['host']}:{config['port']}/api/v1/status", headers={"X-CodeDNA-Client": "cli"}, timeout=5)
        result = response.json()
        print("CodeDNA Status")
        print("=" * 40)
        print(f"Daemon: Running on {config['host']}:{config['port']}")
        print(f"Schema: {result['db_version']}/{CURRENT_SCHEMA_VERSION}")
        print(f"Rebuild Required: {result['rebuild_required']}")
        print(f"Active Repos: {len(result['active_repos'])}")
        if result['active_repos']:
            print("\nTracked Repositories:")
            for repo in result['active_repos']:
                print(f"  - {repo['name']} ({repo['path']})")
        if args.slo:
            import time
            from sqlalchemy import text
            conn = get_raw_connection()
            cutoff = time.time() - (86400 * 7)  # 7 days ago as Unix epoch
            row = conn.execute(text("SELECT COUNT(*), AVG(latency_ms), AVG(CASE WHEN degraded = 1 THEN 1 ELSE 0 END) FROM scan_results WHERE created_at > :cutoff"), {"cutoff": cutoff}).fetchone()
            conn.close()
            if row and row[0] > 0:
                print(f"\nSLO Summary (last 7 days):")
                print(f"  Total scans: {row[0]}")
                print(f"  Avg latency: {row[1]:.0f}ms (SLO: ≤500ms)")
                print(f"  Degraded rate: {row[2] * 100:.1f}% (SLO: ≤1%)")
    except requests.exceptions.ConnectionError:
        print("Daemon is not running. Start with: codedna daemon start")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

def cmd_export(args) -> int:
    import requests
    if not args.confirmed:
        print("Error: --confirmed flag is required for export")
        return 1
    config = get_daemon_config()
    try:
        response = requests.post(f"http://{config['host']}:{config['port']}/api/v1/export", headers={"X-CodeDNA-Client": "cli"}, json={"repo_id": args.repo, "format": args.format, "include": ["fingerprint", "evolution", "scan_history"], "confirmed": True}, timeout=30)
        response.raise_for_status()
        result = response.json()
        if args.output:
            import json
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"Data exported to: {args.output}")
        else:
            print(result)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return 1
    return 0

def cmd_config(args) -> int:
    from codedna.config import get_config_value, set_config_value, load_config_file
    import json
    if args.action == "list":
        print(json.dumps(load_config_file(), indent=2))
    elif args.action == "get":
        if not args.key:
            print("Error: key is required for get")
            return 1
        print(f"{args.key} = {get_config_value(args.key)}")
    elif args.action == "set":
        if not args.key or args.value is None:
            print("Error: key and value are required for set")
            return 1
        set_config_value(args.key, args.value)
        print(f"Set {args.key} = {args.value}")
    return 0

def cmd_daemon(args) -> int:
    from codedna.daemon.daemon_manager import (
        start_daemon, stop_daemon, restart_daemon,
        is_daemon_running, get_daemon_status
    )
    
    if args.action == "start":
        if is_daemon_running():
            print("Daemon is already running.")
            return 0
        success = start_daemon(background=True)
        return 0 if success else 1
    
    elif args.action == "status":
        status = get_daemon_status()
        if status["running"]:
            print(f"Daemon is running (PID: {status['pid']})")
            if "memory_mb" in status:
                print(f"  Memory: {status['memory_mb']:.1f} MB")
                print(f"  Uptime: {status['uptime_seconds']:.0f}s")
        else:
            print("Daemon is not running.")
        return 0
    
    elif args.action == "stop":
        success = stop_daemon()
        return 0 if success else 1
    
    elif args.action == "restart":
        success = restart_daemon()
        return 0 if success else 1
    
    return 0

def cmd_db(args) -> int:
    init_database()
    if args.action == "prune":
        print("Pruning old data...")
        from codedna.db.session import get_engine
        results = prune_old_data(get_engine())
        print(f"Deleted records: {results}")
    elif args.action == "reset":
        if not args.repo:
            print("Error: --repo is required for reset")
            return 1
        from codedna.db.schema import erase_repo_data
        conn = get_raw_connection()
        results = erase_repo_data(conn, args.repo)
        conn.close()
        print(f"Repository data erased: {results}")
    elif args.action == "backup":
        from codedna.db.schema import get_db_path
        import shutil
        from datetime import datetime
        db_path = get_db_path()
        backup_dir = get_config_dir() / "backup"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / f"codedna_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")
    return 0

def main():
    parser = create_parser()
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    if not args.command:
        parser.print_help()
        return 0
    commands = {"init": cmd_init, "build": cmd_build, "scan": cmd_scan, "status": cmd_status, "export": cmd_export, "config": cmd_config, "daemon": cmd_daemon, "db": cmd_db}
    handler = commands.get(args.command)
    if handler:
        try:
            return handler(args)
        except Exception as e:
            if args.verbose:
                raise
            print(f"Error: {e}")
            return 1
    else:
        parser.print_help()
        return 1

def cli():
    sys.exit(main())

if __name__ == "__main__":
    cli()
