"""Daemon process management for CodeDNA.

Handles background daemon lifecycle: start, stop, restart, and status checking.
Uses PID file at ~/.codedna/daemon.pid for process tracking.

Cross-platform support: Uses subprocess on Windows, fork on Unix.
Per constraint C10: Native Windows support required.
"""
import os
import sys
import signal
import time
import subprocess
from pathlib import Path
from typing import Optional

from codedna.config import get_config_dir


def get_daemon_pid() -> Optional[int]:
    """Read the current daemon PID from lockfile."""
    pid_file = get_config_dir() / "daemon.pid"
    if not pid_file.exists():
        return None
    
    try:
        pid = int(pid_file.read_text().strip())
        # Verify process is actually running
        if _is_process_running(pid):
            return pid
        else:
            # Stale PID file - remove it
            pid_file.unlink()
            return None
    except (ValueError, IOError):
        return None


def _is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    try:
        # On Unix, signal 0 checks if process exists without sending signal
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_daemon_running() -> bool:
    """Check if the CodeDNA daemon is currently running."""
    return get_daemon_pid() is not None


def write_pid_file(pid: int) -> None:
    """Write the PID to the lockfile."""
    pid_file = get_config_dir() / "daemon.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid))


def remove_pid_file() -> None:
    """Remove the PID lockfile."""
    pid_file = get_config_dir() / "daemon.pid"
    if pid_file.exists():
        pid_file.unlink()


def _get_daemon_command() -> list:
    """Get the command to run the daemon."""
    # Find the Python executable
    python_exe = sys.executable
    
    # Find the codedna module path
    import codedna.daemon.app
    app_path = Path(codedna.daemon.app.__file__).parent / "app.py"
    
    return [str(python_exe), "-m", "codedna.daemon.app"]


def start_daemon(background: bool = True) -> bool:
    """
    Start the CodeDNA daemon as a background process.
    
    Cross-platform: Uses subprocess.Popen on Windows, os.fork on Unix.
    Per constraint C10: Native Windows support required.
    
    Args:
        background: If True, run as background process. If False, run in foreground.
    
    Returns:
        True if daemon started successfully, False otherwise.
    """
    # Check if already running
    if is_daemon_running():
        print("Daemon is already running.")
        return False
    
    if sys.platform == "win32":
        # Windows: Use subprocess.Popen for background process
        return _start_daemon_windows(background)
    else:
        # Unix: Use os.fork for background process
        return _start_daemon_unix(background)


def _start_daemon_windows(background: bool) -> bool:
    """Start daemon on Windows using subprocess."""
    import threading
    
    # Write current PID as placeholder (will be updated by daemon)
    daemon_pid = os.getpid()
    
    if background:
        # Create a detached process on Windows
        # Use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS flags
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        
        try:
            # Start the daemon as a detached subprocess
            # Redirect stdin/stdout/stderr to DEVNULL
            process = subprocess.Popen(
                _get_daemon_command(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
                cwd="/"
            )
            
            # Wait briefly for the daemon to start and write its PID
            time.sleep(0.5)
            
            # Check if the daemon wrote its PID file
            actual_pid = get_daemon_pid()
            if actual_pid:
                print(f"Daemon started with PID {actual_pid}")
                return True
            else:
                # If no PID file, the subprocess might have been created but not daemonized
                # Store the subprocess PID (the daemon will create its own PID file)
                write_pid_file(process.pid)
                print(f"Daemon started with PID {process.pid}")
                return True
                
        except Exception as e:
            print(f"Failed to start daemon: {e}")
            return False
    else:
        # Run in foreground
        print("Starting CodeDNA daemon in foreground...")
        write_pid_file(os.getpid())
        try:
            process = subprocess.run(
                _get_daemon_command(),
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Daemon exited with error: {e}")
            return False
        finally:
            remove_pid_file()


def _start_daemon_unix(background: bool) -> bool:
    """Start daemon on Unix using os.fork."""
    from codedna.daemon.app import run_daemon
    
    if background:
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process - wait briefly and check if child started successfully
                time.sleep(0.5)
                if is_daemon_running():
                    print(f"Daemon started with PID {get_daemon_pid()}")
                    return True
                else:
                    print("Failed to start daemon")
                    return False
        except OSError as e:
            print(f"Fork failed: {e}")
            return False
        
        # Child process - close stdin/stdout/stderr and daemonize
        try:
            # Create new session
            os.setsid()
            
            # Redirect standard file descriptors to /dev/null
            devnull = os.open(os.devnull, os.O_RDWR)
            os.dup2(devnull, 0)  # stdin
            os.dup2(devnull, 1)  # stdout
            os.dup2(devnull, 2)  # stderr
            os.close(devnull)
            
            # Change working directory to prevent holding onto mounted filesystems
            os.chdir("/")
            
            # Write PID file
            write_pid_file(os.getpid())
            
            # Import and run the daemon
            from codedna.daemon.app import run_daemon
            sys.argv = ["codedna-daemon"]
            run_daemon()
            
        except Exception as e:
            print(f"Daemon startup failed: {e}")
            remove_pid_file()
            sys.exit(1)
    else:
        # Run in foreground (for development/debugging)
        print("Starting CodeDNA daemon in foreground...")
        write_pid_file(os.getpid())
        try:
            run_daemon()
        finally:
            remove_pid_file()
        return True


def stop_daemon(timeout: int = 10) -> bool:
    """
    Stop the CodeDNA daemon gracefully.
    
    Args:
        timeout: Maximum seconds to wait for graceful shutdown.
    
    Returns:
        True if daemon stopped successfully, False otherwise.
    """
    pid = get_daemon_pid()
    if pid is None:
        print("Daemon is not running.")
        return True  # Not running is considered "stopped"
    
    try:
        if sys.platform == "win32":
            # Windows: Use taskkill or signal.CTRL_C_EVENT
            try:
                # Try to gracefully terminate with CTRL_C_EVENT first
                os.kill(pid, signal.CTRL_C_EVENT)
            except (OSError, AttributeError):
                # Fall back to SIGTERM equivalent
                subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
        else:
            # Unix: Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)
        
        # Wait for process to exit
        start_time = time.time()
        while _is_process_running(pid):
            if time.time() - start_time > timeout:
                print(f"Daemon did not stop after {timeout}s, forcing...")
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
                break
            time.sleep(0.1)
        
        remove_pid_file()
        print("Daemon stopped.")
        return True
        
    except OSError as e:
        print(f"Failed to stop daemon: {e}")
        return False


def restart_daemon() -> bool:
    """Restart the CodeDNA daemon."""
    print("Stopping daemon...")
    if not stop_daemon():
        return False
    
    time.sleep(1)  # Brief pause before restart
    
    print("Starting daemon...")
    return start_daemon(background=True)


def get_daemon_status() -> dict:
    """Get the current status of the daemon."""
    pid = get_daemon_pid()
    status = {
        "running": pid is not None,
        "pid": pid,
        "pid_file_exists": (get_config_dir() / "daemon.pid").exists(),
        "platform": sys.platform,
    }
    
    if pid:
        try:
            import psutil
            proc = psutil.Process(pid)
            status["memory_mb"] = proc.memory_info().rss / 1024 / 1024
            status["cpu_percent"] = proc.cpu_percent()
            status["uptime_seconds"] = time.time() - proc.create_time()
        except ImportError:
            pass  # psutil not available
    
    return status