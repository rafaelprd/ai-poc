from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR
FRONTEND_DIR = ROOT_DIR / "frontend"


def start_process(name: str, command: list[str], cwd: Path) -> subprocess.Popen:
    print(f"Starting {name}...")
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=os.environ.copy(),
    )


def stop_process(name: str, process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    print(f"Stopping {name}...")
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def main() -> int:
    backend_path = ROOT_DIR / "backend"
    frontend_path = ROOT_DIR / "frontend"

    if not backend_path.exists() or not frontend_path.exists():
        print(
            "Expected `backend/` and `frontend/` directories next to this script.",
            file=sys.stderr,
        )
        return 1

    backend_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]

    frontend_command = [
        "npm",
        "run",
        "dev",
    ]

    backend_process = start_process("backend", backend_command, BACKEND_DIR)
    frontend_process = start_process("frontend", frontend_command, FRONTEND_DIR)

    processes = [
        ("backend", backend_process),
        ("frontend", frontend_process),
    ]

    try:
        while True:
            for name, process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"{name} exited with code {exit_code}.")
                    return exit_code

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0
    finally:
        for name, process in processes:
            stop_process(name, process)


if __name__ == "__main__":
    raise SystemExit(main())
