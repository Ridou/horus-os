"""CI helper for the install-smoke-no-otel job (Phase 38, Pitfall 12).

Asserts that without the [otel] extra installed:

1. `from horus_os.adapters.otel_adapter import OtelAdapter` succeeds
   (the module top imports are stdlib + typing + horus_os only).
2. `await OtelAdapter().start(ctx)` raises a clean `RuntimeError`
   whose message contains the literal substring `pip install
   horus-os[otel]`. NEVER a bare `ModuleNotFoundError`.

Mirrors the pytest assertions in
`tests/test_adapters_otel_install_smoke.py` at the OS-level install
boundary; the OS-level assertion catches the case where the pytest
suite passes inside a venv that happened to have opentelemetry on
the path from a prior dev install.

Exits 0 on success, nonzero with a clear message on any failure.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from horus_os.adapters.base import AdapterContext, AdapterRegistry
from horus_os.adapters.otel_adapter import OtelAdapter
from horus_os.config import Config


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        cfg = Config.with_defaults(Path(td))
        cfg.save()
        reg = AdapterRegistry()
        reg.register("otel")
        ctx = AdapterContext(config=cfg, data_dir=Path(td), registry=reg)
        try:
            asyncio.run(OtelAdapter().start(ctx))
        except RuntimeError as exc:
            if "pip install horus-os[otel]" not in str(exc):
                print(
                    f"FAIL: RuntimeError missing install hint: {exc}",
                    file=sys.stderr,
                )
                return 1
            print(f"PASS: RuntimeError with install hint: {exc}")
            return 0
        except ModuleNotFoundError as exc:
            print(
                f"FAIL: got ModuleNotFoundError (Pitfall 12 leak), expected RuntimeError: {exc}",
                file=sys.stderr,
            )
            return 2
        except BaseException as exc:
            print(
                f"FAIL: got unexpected {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 3
        print(
            "FAIL: start did not raise; expected RuntimeError with install hint",
            file=sys.stderr,
        )
        return 4


if __name__ == "__main__":
    sys.exit(main())
