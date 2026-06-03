"""TEST-29: Supabase service-key isolation (SUPA-02).

These tests are CI-runnable, require no network, and use no live Supabase
connection. They assert two hard security properties:

1. The service key is never accessed as a browser environment variable in the
   static bundle. Specifically, `process.env.SUPABASE_SERVICE_KEY` and
   `process.env.NEXT_PUBLIC_SUPABASE_SERVICE_KEY` must never appear in
   frontend/out/**/*.js. The test skips gracefully when the bundle has not
   been built (fresh checkout), so CI does not fail on bare pytest runs.
   Run `npm run build` in frontend/ first to activate the grep.

   Note: the string "SUPABASE_SERVICE_KEY" may legitimately appear as
   documentation metadata (e.g. in the integrations fixture's `required_vars`
   list, which tells the user what to set). What must never appear is any
   pattern that reads or evaluates the secret as a process env var in
   browser code.

2. No environment variable whose name starts with NEXT_PUBLIC_SUPABASE_SERVICE
   is present in the current process. This catches the Pitfall-6 mistake of
   accidentally setting NEXT_PUBLIC_SUPABASE_SERVICE_KEY in Vercel, which
   would bake the secret into the static export.

3. When both SUPABASE_SERVICE_KEY and NEXT_PUBLIC_SUPABASE_ANON_KEY are set,
   they must not share the same value (key-swap guard).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_OUT = REPO_ROOT / "frontend" / "out"

# Patterns that indicate the service key is being read as a browser env var.
# These are the dangerous forms - not mere string metadata (like required_vars docs).
_DANGEROUS_PATTERNS = [
    # Reading via process.env in bundled client code
    "process.env.SUPABASE_SERVICE_KEY",
    "process.env.NEXT_PUBLIC_SUPABASE_SERVICE_KEY",
    # Baked NEXT_PUBLIC_ form (Next.js inlines these at build time)
    "NEXT_PUBLIC_SUPABASE_SERVICE_KEY",
]


def test_service_key_not_in_static_bundle() -> None:
    """The service key must not be accessed as a browser env var in the bundle.

    Checks for patterns that indicate the service key is being read or baked
    into the static export as a browser-accessible value (SUPA-02 / TEST-29).

    Skips gracefully when frontend/out has not been built.
    """
    if not FRONTEND_OUT.exists():
        pytest.skip("frontend/out not built; run 'npm run build' in frontend/ first")

    offending: list[tuple[str, str]] = []
    for js_file in sorted(FRONTEND_OUT.rglob("*.js")):
        content = js_file.read_text(encoding="utf-8", errors="replace")
        for pattern in _DANGEROUS_PATTERNS:
            if pattern in content:
                offending.append((str(js_file.relative_to(FRONTEND_OUT)), pattern))

    assert offending == [], (
        "Service key exposed as browser env var in static bundle:\n"
        + "\n".join(f"  {p} -> pattern: '{pat}'" for p, pat in offending)
        + "\n\nThe service key must never appear as a process.env reference or "
        "NEXT_PUBLIC_* variable in frontend code. Only NEXT_PUBLIC_SUPABASE_ANON_KEY "
        "is safe for browser/Vercel exposure (SUPA-02 / TEST-29)."
    )


def test_service_key_not_in_env_surface() -> None:
    """No NEXT_PUBLIC_SUPABASE_SERVICE* env var name must exist in the process.

    This assertion is meaningful: if a developer sets
    NEXT_PUBLIC_SUPABASE_SERVICE_KEY=... in their shell or Vercel dashboard,
    this test catches it. The assertion fails on any such env var name
    regardless of its value (even an empty value is a naming violation).
    """
    violations: list[str] = []
    for key in os.environ:
        if key.startswith("NEXT_PUBLIC_SUPABASE_SERVICE"):
            violations.append(key)

    assert violations == [], (
        "Service key exposed via NEXT_PUBLIC_* env var(s): "
        + ", ".join(violations)
        + "\n\nOnly NEXT_PUBLIC_SUPABASE_ANON_KEY is safe for browser "
        "exposure. The service key must use the server-only name "
        "SUPABASE_SERVICE_KEY (no NEXT_PUBLIC_ prefix)."
    )


def test_anon_key_naming_not_swapped() -> None:
    """When Supabase is configured, the service key and anon key must differ.

    Guards against the copy-paste mistake of assigning the same JWT to both
    SUPABASE_SERVICE_KEY and NEXT_PUBLIC_SUPABASE_ANON_KEY.
    """
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    anon_key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

    if service_key and anon_key:
        assert service_key != anon_key, (
            "SUPABASE_SERVICE_KEY and NEXT_PUBLIC_SUPABASE_ANON_KEY must not "
            "share the same value. The service key bypasses RLS and must never "
            "reach the browser. Only the anon key is safe for NEXT_PUBLIC_* "
            "(SUPA-02 / TEST-29)."
        )
