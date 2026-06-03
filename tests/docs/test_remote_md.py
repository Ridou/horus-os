"""docs/REMOTE.md content gates (REMOTE-02 / REMOTE-03).

These tests pin the documentation contracts Plan 04 ships: the serve --host
security warning alongside the loopback default, the Tailscale serve happy
path (the tailnet is the auth boundary), the hard do-not warning for tailscale
funnel (public internet, no auth), and the Windows OpenSSH note. A fifth check
enforces CLAUDE.md rule 3 (no em-dash) on the doc itself.

The doc is read once via pathlib into a module-scoped fixture; each test
asserts the required substrings (case-insensitive where appropriate),
mirroring tests/docs/test_plugins_md_anatomy.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REMOTE_MD_PATH = REPO_ROOT / "docs" / "REMOTE.md"

EM_DASH = chr(8212)  # U+2014, forbidden by CLAUDE.md rule 3


@pytest.fixture(scope="module")
def remote_md_text() -> str:
    if not REMOTE_MD_PATH.is_file():
        pytest.fail(
            "docs/REMOTE.md does not exist. Plan 66-04 must ship the remote "
            "access and always-on service guide."
        )
    return REMOTE_MD_PATH.read_text(encoding="utf-8")


def test_remote_md_documents_serve_host_warning(remote_md_text: str) -> None:
    """REMOTE.md explains --host 0.0.0.0 exposes an unauthenticated dashboard (REMOTE-02)."""
    lower = remote_md_text.lower()
    assert "--host" in remote_md_text, "REMOTE.md must document the serve --host flag"
    assert "0.0.0.0" in remote_md_text, "REMOTE.md must document the 0.0.0.0 bind address"
    assert "127.0.0.1" in remote_md_text, "REMOTE.md must document the loopback default"
    # The no-auth implication of binding to a routable interface.
    assert "no app-level auth" in lower or "no authentication" in lower, (
        "REMOTE.md must state that horus-os ships no app-level authentication"
    )


def test_remote_md_documents_tailscale_serve_happy_path(remote_md_text: str) -> None:
    """REMOTE.md gives the tailscale serve happy path with the tailnet as auth boundary."""
    lower = remote_md_text.lower()
    assert "tailscale serve" in lower, "REMOTE.md must document the tailscale serve path"
    assert "tailnet" in lower, "REMOTE.md must name the tailnet"
    # The tailnet-as-auth-boundary framing (D-10).
    assert (
        "auth boundary" in lower or "authentication boundary" in lower or "auth layer" in lower
    ), "REMOTE.md must state the tailnet is the authentication boundary"


def test_remote_md_documents_funnel_do_not_warning(remote_md_text: str) -> None:
    """REMOTE.md carries the hard do-not warning for tailscale funnel (REMOTE-03)."""
    lower = remote_md_text.lower()
    assert "tailscale funnel" in lower, "REMOTE.md must mention tailscale funnel"
    assert "public internet" in lower, "REMOTE.md must warn that funnel is the public internet"
    # The do-not framing with the no-auth rationale.
    assert "do not" in lower or "do-not" in lower, (
        "REMOTE.md must carry a do-not warning for tailscale funnel"
    )
    assert "no authentication" in lower or "no auth" in lower, (
        "REMOTE.md must state funnel exposes the dashboard with no authentication"
    )


def test_remote_md_documents_windows_openssh_note(remote_md_text: str) -> None:
    """REMOTE.md notes Windows remote management uses OpenSSH, not Tailscale SSH."""
    lower = remote_md_text.lower()
    assert "openssh" in lower, "REMOTE.md must document Windows OpenSSH for remote management"
    assert "windows" in lower, "REMOTE.md must scope the OpenSSH note to Windows"


def test_remote_md_has_no_em_dash(remote_md_text: str) -> None:
    """REMOTE.md contains no em-dash character (CLAUDE.md rule 3)."""
    assert EM_DASH not in remote_md_text, (
        "docs/REMOTE.md contains an em-dash (U+2014). CLAUDE.md rule 3 forbids "
        "em-dashes in committed prose; use commas, periods, or hyphens."
    )
