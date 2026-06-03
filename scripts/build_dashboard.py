"""Build the Next.js dashboard and stage its static export for packaging.

Runs ``npm ci`` (or ``npm install``) and ``npm run build`` in ``frontend/``,
then copies the static export (``frontend/out/``) into
``src/horus_os/server/dashboard_dist/`` so the Python wheel can bundle it.

Node is required to RUN this script, but the resulting wheel needs no Node:
end users get the prebuilt assets and ``horus-os serve`` serves them. When the
``dashboard_dist`` directory is absent (for example an editable install with no
Node build), the server falls back to the legacy single-page HTML dashboard.

Usage:
    python scripts/build_dashboard.py

Run this before ``python -m build`` when producing a release wheel.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
OUT = FRONTEND / "out"
DIST = ROOT / "src" / "horus_os" / "server" / "dashboard_dist"


def _npm() -> str:
    npm = shutil.which("npm")
    if npm is None:
        print(
            "npm was not found on PATH. Install Node.js (which provides npm) to "
            "build the dashboard. Node is only needed to build, not to run.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return npm


def _run(npm: str, *args: str) -> None:
    print(f"$ npm {' '.join(args)}  (in {FRONTEND})")
    subprocess.run([npm, *args], cwd=str(FRONTEND), check=True)


def main() -> int:
    if not FRONTEND.is_dir():
        print(f"frontend directory not found at {FRONTEND}", file=sys.stderr)
        return 1

    npm = _npm()
    install_cmd = "ci" if (FRONTEND / "package-lock.json").is_file() else "install"
    _run(npm, install_cmd)
    _run(npm, "run", "build")

    if not (OUT / "index.html").is_file():
        print(f"expected static export at {OUT} was not produced", file=sys.stderr)
        return 1

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(OUT, DIST)

    file_count = sum(1 for path in DIST.rglob("*") if path.is_file())
    print(f"staged {file_count} files into {DIST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
