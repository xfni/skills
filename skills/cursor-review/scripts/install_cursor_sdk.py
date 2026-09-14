import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path


DEFAULT_RUNTIME = Path.home() / ".codex" / "runtime" / "cursor-review"


def runtime_python(runtime):
    if os.name == "nt":
        return runtime / "Scripts" / "python.exe"
    return runtime / "bin" / "python"


def main():
    parser = argparse.ArgumentParser(description="Install the pinned Cursor SDK in its dedicated runtime.")
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    args = parser.parse_args()

    runtime = args.runtime.expanduser().resolve()
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
    venv.EnvBuilder(with_pip=True).create(runtime)
    python = runtime_python(runtime)
    subprocess.run(
        [str(python), "-m", "pip", "install", "--requirement", str(requirements)],
        check=True,
    )
    subprocess.run(
        [str(python), "-c", "import cursor_sdk; print('READY: cursor_sdk dedicated runtime is installed')"],
        check=True,
    )
    print(f"runtime_python={python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
