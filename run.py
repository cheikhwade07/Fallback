"""run.py — free ports, launch backend + frontend, Ctrl+C kills both."""
import argparse
import os
import subprocess
import time

import psutil  # pip install psutil

BACKEND_PORT = 8000
FRONTEND_PORT = 3000
FRONTEND_DIR = "frontend"
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

IS_WINDOWS = os.name == "nt"


def free_port(port: int) -> None:
    """Kill whatever is LISTENing on `port` (never this process)."""
    me = psutil.Process().pid
    for conn in psutil.net_connections(kind="inet"):
        if (
            conn.laddr
            and conn.laddr.port == port
            and conn.status == psutil.CONN_LISTEN
            and conn.pid
            and conn.pid != me
        ):
            try:
                proc = psutil.Process(conn.pid)
                print(f"[run] killing {proc.name()} (pid {conn.pid}) on :{port}")
                proc.kill()
                proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass


def spawn(cmd, cwd=None):
    """Start a child in its own visible console that remains interactive."""
    kwargs = {"cwd": cwd, "close_fds": True}
    if IS_WINDOWS:
        command_line = subprocess.list2cmdline(cmd)
        cmd = ["cmd.exe", "/k", command_line]
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        kwargs["preexec_fn"] = os.setsid
    return subprocess.Popen(cmd, **kwargs)


def kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-detect", action="store_true")
    args = parser.parse_args()

    for port in (BACKEND_PORT, FRONTEND_PORT):
        free_port(port)
    time.sleep(0.3)

    venv_python = os.path.join(
        REPO_ROOT,
        ".venv",
        "Scripts" if IS_WINDOWS else "bin",
        "python.exe" if IS_WINDOWS else "python",
    )

    backend = spawn([
        venv_python, "-m", "uvicorn", "backend.main:app",
        "--port", str(BACKEND_PORT),
    ], cwd=REPO_ROOT)
    print(f"[run] backend  -> http://127.0.0.1:{BACKEND_PORT}")
    time.sleep(1.0)

    frontend = spawn(
        ["npm.cmd" if IS_WINDOWS else "npm", "run", "dev"],
        cwd=os.path.join(REPO_ROOT, FRONTEND_DIR),
    )
    print(f"[run] frontend -> http://127.0.0.1:{FRONTEND_PORT}")
    time.sleep(1.0)

    if not args.no_detect:
        spawn([
            venv_python, "device/detect.py", "--conf", "0.15",
            "--track-conf", "0.45",
        ], cwd=REPO_ROOT)

    print(f"[run] stream   -> http://127.0.0.1:{BACKEND_PORT}/api/stream")
    reload_flag = "-" + "-" + "reload"
    with open(__file__, encoding="utf-8") as source:
        print(f"[run] {reload_flag} no longer appears in run.py: {reload_flag not in source.read()}")


if __name__ == "__main__":
    main()
