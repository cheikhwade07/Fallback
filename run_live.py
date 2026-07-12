"""Launch the local detector against the deployed Fallback server."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_SERVER = "http://206.189.199.1"
HEALTH_TIMEOUT_SECONDS = 5.0
REPO_ROOT = Path(__file__).resolve().parent


def env_value(name: str) -> str | None:
    env_path = REPO_ROOT / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value or None
    return None


def health_check(server: str) -> None:
    health_url = f"{server}/api/health"
    request = Request(health_url, method="GET")
    with urlopen(request, timeout=HEALTH_TIMEOUT_SECONDS) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"HTTP status {response.status}")
        payload = json.loads(response.read().decode("utf-8"))
        if payload.get("ok") is not True:
            raise RuntimeError(f"unexpected health response: {payload!r}")


def detector_python() -> Path:
    executable = "python.exe" if os.name == "nt" else "python"
    return REPO_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / executable


def launch_detector(server: str, conf: float, track_conf: float) -> None:
    command = [
        str(detector_python()),
        "device/detect.py",
        "--conf",
        str(conf),
        "--track-conf",
        str(track_conf),
        "--server",
        server,
    ]
    options = {"cwd": REPO_ROOT}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        options["start_new_session"] = True
    subprocess.Popen(command, **options)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local detector against the deployed Fallback server.")
    parser.add_argument("--server", help="Override FALLBACK_SERVER from .env")
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--track-conf", type=float, default=0.45)
    args = parser.parse_args()

    server = (args.server or env_value("FALLBACK_SERVER") or DEFAULT_SERVER).rstrip("/")
    try:
        health_check(server)
    except (HTTPError, URLError, OSError, ValueError, RuntimeError) as error:
        print("!!! FALLBACK SERVER HEALTH CHECK FAILED !!!", file=sys.stderr)
        print(f"URL       : {server}/api/health", file=sys.stderr)
        print(f"EXCEPTION : {error}", file=sys.stderr)
        return 1

    python = detector_python()
    if not python.is_file():
        print("!!! VENV PYTHON NOT FOUND !!!", file=sys.stderr)
        print(f"PATH      : {python}", file=sys.stderr)
        return 1

    launch_detector(server, args.conf, args.track_conf)
    print(f"SERVER OK    : {server}")
    print(f"DASHBOARD    : {server}       <- open this on the phone")
    print("DETECTOR     : launched in a new window")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
