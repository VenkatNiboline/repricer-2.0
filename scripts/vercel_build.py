#!/usr/bin/env python3
"""Build React UI into public/ for Vercel static + FastAPI deployment."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB = ROOT / "web"
PUBLIC = ROOT / "public"


def main() -> None:
    subprocess.run(["npm", "install"], cwd=WEB, check=True)
    subprocess.run(["npm", "run", "build"], cwd=WEB, check=True)

    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    shutil.copytree(WEB / "dist", PUBLIC)
    print(f"Built UI into {PUBLIC}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
