"""docs/DEPLOY-VERCEL.md content gates (VERCEL-02 / VERCEL-04).

These tests pin the documentation contracts Plan 67-04 ships: the no-auth
red-banner warning that leads the doc (any reachable backend URL is usable by
anyone who can reach it, given wide-open CORS plus no-auth /api), the
"add a real authentication layer first" prerequisite, the Vercel project
config (root directory frontend, build command next build, output directory
out), the NEXT_PUBLIC_API_BASE wiring, and the anon-key-only caveat. A final
check enforces CLAUDE.md rule 3 (no em-dash) on the doc itself.

The doc is read once via pathlib into a module-scoped fixture; each test
asserts the required substrings (case-insensitive where appropriate),
mirroring tests/docs/test_remote_md.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_MD_PATH = REPO_ROOT / "docs" / "DEPLOY-VERCEL.md"

EM_DASH = chr(8212)  # U+2014, forbidden by CLAUDE.md rule 3


@pytest.fixture(scope="module")
def deploy_md_text() -> str:
    if not DEPLOY_MD_PATH.is_file():
        pytest.fail(
            "docs/DEPLOY-VERCEL.md does not exist. Plan 67-04 must ship the "
            "Vercel deploy walkthrough leading with the no-auth red-banner warning."
        )
    return DEPLOY_MD_PATH.read_text(encoding="utf-8")


def test_deploy_md_leads_with_no_auth_warning(deploy_md_text: str) -> None:
    """DEPLOY-VERCEL.md states /api has no app-level auth and is reachable by anyone (D-11, D-13)."""
    lower = deploy_md_text.lower()
    assert "no app-level auth" in lower or "no authentication" in lower, (
        "DEPLOY-VERCEL.md must state that horus-os ships no app-level authentication"
    )
    # The anyone-with-the-URL reach implication of the wide-open CORS plus no-auth /api.
    assert "anyone who can reach" in lower or "anyone with the url" in lower, (
        "DEPLOY-VERCEL.md must warn that any reachable backend URL is usable by "
        "anyone who can reach it"
    )


def test_deploy_md_makes_auth_a_prerequisite(deploy_md_text: str) -> None:
    """DEPLOY-VERCEL.md makes adding a real auth layer a prerequisite step (D-11)."""
    lower = deploy_md_text.lower()
    assert "prerequisite" in lower, (
        "DEPLOY-VERCEL.md must frame adding auth as a prerequisite step, not an afterthought"
    )
    assert (
        "real authentication layer" in lower
        or "auth layer first" in lower
        or "authentication layer in front" in lower
    ), "DEPLOY-VERCEL.md must tell the reader to put a real authentication layer in front first"


def test_deploy_md_documents_next_public_api_base(deploy_md_text: str) -> None:
    """DEPLOY-VERCEL.md documents the NEXT_PUBLIC_API_BASE env var (VERCEL-01 cross-ref)."""
    lower = deploy_md_text.lower()
    assert "next_public_api_base" in lower, (
        "DEPLOY-VERCEL.md must document the NEXT_PUBLIC_API_BASE env var"
    )
    # The no-trailing-slash note from Plan 01's trailing-slash strip.
    assert "trailing slash" in lower, (
        "DEPLOY-VERCEL.md must carry the no-trailing-slash note for NEXT_PUBLIC_API_BASE"
    )


def test_deploy_md_documents_vercel_project_config(deploy_md_text: str) -> None:
    """DEPLOY-VERCEL.md documents the Vercel root/build/output config (VERCEL-02)."""
    lower = deploy_md_text.lower()
    assert "frontend" in lower, "DEPLOY-VERCEL.md must document the frontend root directory"
    assert "next build" in lower, "DEPLOY-VERCEL.md must document the next build command"
    # The static export output directory.
    assert "out" in lower, "DEPLOY-VERCEL.md must document the out output directory"


def test_deploy_md_documents_anon_key_only_caveat(deploy_md_text: str) -> None:
    """DEPLOY-VERCEL.md states the anon key only, never the service key (VERCEL-02, D-05)."""
    lower = deploy_md_text.lower()
    assert "anon" in lower, "DEPLOY-VERCEL.md must document the Supabase anon key"
    # Never the service key in a browser-facing surface.
    assert "service key" in lower or "service role" in lower or "service-role" in lower, (
        "DEPLOY-VERCEL.md must warn never to use the Supabase service key in the browser env"
    )
    # The server-side tokens must not be NEXT_PUBLIC_* (D-05, D-08).
    assert "next_public_" in lower, (
        "DEPLOY-VERCEL.md must forbid setting server-side tokens as NEXT_PUBLIC_* vars"
    )


def test_deploy_md_has_no_em_dash(deploy_md_text: str) -> None:
    """DEPLOY-VERCEL.md contains no em-dash character (CLAUDE.md rule 3)."""
    assert EM_DASH not in deploy_md_text, (
        "docs/DEPLOY-VERCEL.md contains an em-dash (U+2014). CLAUDE.md rule 3 forbids "
        "em-dashes in committed prose; use commas, periods, or hyphens."
    )
