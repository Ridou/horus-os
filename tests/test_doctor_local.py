"""Tests for `horus-os doctor --local` (LP-4 base-URL validation + probe).

The prober is injected so no live local server is contacted. The 0.0.0.0 case
pins LP-4: the wildcard base URL is rejected as invalid with a nonzero exit and
the prober is never called.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from horus_os.cli.doctor_cmd import run_doctor
from horus_os.config import Config


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(local=True, supabase=False, data_dir=tmp_path)


def _write_config(tmp_path: Path, base_url: str) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.local_base_url = base_url
    cfg.save()


class _RecordingProber:
    """A prober that records its calls and returns a canned result."""

    def __init__(self, result: tuple[bool, int | None, str | None]) -> None:
        self.result = result
        self.calls: list[str] = []

    def __call__(self, base_url: str) -> tuple[bool, int | None, str | None]:
        self.calls.append(base_url)
        return self.result


def test_wildcard_base_url_rejected_without_probing(tmp_path: Path) -> None:
    """LP-4: a 0.0.0.0 base URL is invalid and the prober is never called."""
    _write_config(tmp_path, "http://0.0.0.0:11434/v1")
    prober = _RecordingProber((True, 3, None))

    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(_args(tmp_path), stdout=out, stderr=err, probe=prober)

    assert code != 0
    assert prober.calls == [], "the invalid base URL must not be probed (LP-4)"
    assert "invalid" in err.getvalue().lower()
    # The fix-it suggestion must point at a loopback host, never the wildcard.
    assert "localhost" in err.getvalue()


def test_empty_host_base_url_rejected(tmp_path: Path) -> None:
    _write_config(tmp_path, "not-a-url")
    prober = _RecordingProber((True, 1, None))

    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(_args(tmp_path), stdout=out, stderr=err, probe=prober)

    assert code != 0
    assert prober.calls == []


def test_loopback_reachable_returns_zero(tmp_path: Path) -> None:
    _write_config(tmp_path, "http://localhost:11434/v1")
    prober = _RecordingProber((True, 3, None))

    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(_args(tmp_path), stdout=out, stderr=err, probe=prober)

    assert code == 0
    assert prober.calls == ["http://localhost:11434/v1"]
    output = out.getvalue()
    assert "reachable" in output
    assert "3 models" in output


def test_loopback_unreachable_returns_nonzero(tmp_path: Path) -> None:
    _write_config(tmp_path, "http://127.0.0.1:11434/v1")
    prober = _RecordingProber((False, None, "ConnectError"))

    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(_args(tmp_path), stdout=out, stderr=err, probe=prober)

    assert code != 0
    assert "unreachable" in err.getvalue()


def test_non_loopback_host_warns_but_probes(tmp_path: Path) -> None:
    """A LAN IP is a warning (not a hard reject); a reachable one still passes."""
    _write_config(tmp_path, "http://192.168.1.50:11434/v1")
    prober = _RecordingProber((True, 2, None))

    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(_args(tmp_path), stdout=out, stderr=err, probe=prober)

    assert code == 0
    assert prober.calls == ["http://192.168.1.50:11434/v1"]
    output = out.getvalue()
    assert "WARNING" in output
    assert "reachable" in output


def test_local_never_prints_when_no_flag(tmp_path: Path) -> None:
    """Without --local (and without --supabase), doctor prints usage and exits 0."""
    args = argparse.Namespace(local=False, supabase=False, data_dir=tmp_path)
    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(args, stdout=out, stderr=err)
    assert code == 0
    assert "--local" in out.getvalue()
