"""D-05: HORUS_OS_VERCEL_TOKEN isolation (VERCEL-02 / VERCEL-03).

These tests are CI-runnable, require no network, and use no live Vercel
connection. They assert two hard security properties:

1. The Vercel token is never accessed as a browser environment variable in
   the static bundle. Specifically, `process.env.HORUS_OS_VERCEL_TOKEN`,
   `process.env.NEXT_PUBLIC_VERCEL_TOKEN`, `NEXT_PUBLIC_VERCEL_TOKEN`, and
   `NEXT_PUBLIC_HORUS_OS_VERCEL_TOKEN` must never appear in
   frontend/out/**/*.js. The test skips gracefully when the bundle has not
   been built (fresh checkout), so CI does not fail on bare pytest runs.
   Run `npm run build` in frontend/ first to activate the grep.

   Note: the string "HORUS_OS_VERCEL_TOKEN" may legitimately appear as
   documentation metadata (e.g. in the integrations fixture's `required_vars`
   list, which tells the user what to set). What must never appear is any
   pattern that reads or evaluates the secret as a process env var in
   browser code.

2. No environment variable whose name starts with NEXT_PUBLIC_VERCEL (or
   NEXT_PUBLIC_HORUS_OS_VERCEL) is present in the current process. This
   catches the Pitfall-6 mistake of accidentally setting a
   NEXT_PUBLIC_VERCEL_TOKEN in Vercel, which would bake the secret into the
   static export.

3. When HORUS_OS_VERCEL_TOKEN is set, it must never equal any NEXT_PUBLIC_*
   environment value. The Vercel token has no browser-safe sibling (unlike
   the Supabase anon key), so any NEXT_PUBLIC_* var sharing its value is a
   leak.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_OUT = REPO_ROOT / "frontend" / "out"

# Patterns that indicate the Vercel token is being read as a browser env var.
# These are the dangerous forms - not mere string metadata (like required_vars docs).
_DANGEROUS_PATTERNS = [
    # Reading via process.env in bundled client code
    "process.env.HORUS_OS_VERCEL_TOKEN",
    "process.env.NEXT_PUBLIC_VERCEL_TOKEN",
    # Baked NEXT_PUBLIC_ forms (Next.js inlines these at build time)
    "NEXT_PUBLIC_VERCEL_TOKEN",
    "NEXT_PUBLIC_HORUS_OS_VERCEL_TOKEN",
]


def test_vercel_token_not_in_static_bundle() -> None:
    """The Vercel token must not be accessed as a browser env var in the bundle.

    Checks for patterns that indicate the token is being read or baked into
    the static export as a browser-accessible value (VERCEL-02 / D-05).

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
        "Vercel token exposed as browser env var in static bundle:\n"
        + "\n".join(f"  {p} -> pattern: '{pat}'" for p, pat in offending)
        + "\n\nThe Vercel token must never appear as a process.env reference or "
        "NEXT_PUBLIC_* variable in frontend code. It is server-side only and the "
        "browser only ever sees the derived deploy status (VERCEL-02 / D-05)."
    )


def test_vercel_token_not_in_env_surface() -> None:
    """No NEXT_PUBLIC_VERCEL* env var name must exist in the process.

    This assertion is meaningful: if a developer sets
    NEXT_PUBLIC_VERCEL_TOKEN=... (or NEXT_PUBLIC_HORUS_OS_VERCEL_TOKEN=...)
    in their shell or Vercel dashboard, this test catches it. The assertion
    fails on any such env var name regardless of its value (even an empty
    value is a naming violation).
    """
    violations: list[str] = []
    for key in os.environ:
        if key.startswith("NEXT_PUBLIC_VERCEL") or key.startswith("NEXT_PUBLIC_HORUS_OS_VERCEL"):
            violations.append(key)

    assert violations == [], (
        "Vercel token exposed via NEXT_PUBLIC_* env var(s): "
        + ", ".join(violations)
        + "\n\nThe Vercel token must use the server-only name "
        "HORUS_OS_VERCEL_TOKEN (no NEXT_PUBLIC_ prefix). There is no "
        "browser-safe Vercel token (VERCEL-02 / D-05)."
    )


def test_vercel_token_not_shared_with_any_public_value() -> None:
    """When set, HORUS_OS_VERCEL_TOKEN must not equal any NEXT_PUBLIC_* value.

    Guards against the copy-paste mistake of assigning the server-side Vercel
    token to a browser-exposed NEXT_PUBLIC_* variable. Unlike the Supabase
    anon key, the Vercel token has no browser-safe sibling, so any match is a
    leak.
    """
    token = os.environ.get("HORUS_OS_VERCEL_TOKEN", "")

    if token:
        public_matches = [
            key
            for key, value in os.environ.items()
            if key.startswith("NEXT_PUBLIC_") and value == token
        ]
        assert public_matches == [], (
            "HORUS_OS_VERCEL_TOKEN value also appears in NEXT_PUBLIC_* var(s): "
            + ", ".join(public_matches)
            + "\n\nThe Vercel token is server-side only and must never reach the "
            "browser. No NEXT_PUBLIC_* variable may carry its value (VERCEL-02 / D-05)."
        )
