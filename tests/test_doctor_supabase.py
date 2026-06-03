"""Tests for `horus-os doctor --supabase` CLI subcommand.

All tests mock httpx; no live Supabase connection is used.

Because run_doctor imports httpx lazily (inside the function), we inject a
fake module via sys.modules so the `import httpx` inside the function resolves
to our MagicMock. Each test class that needs the mock sets up sys.modules
before calling run_doctor and restores it after.
"""

from __future__ import annotations

import argparse
import io
import sys
from typing import ClassVar
from unittest.mock import MagicMock

import pytest


def _args(supabase: bool = True) -> argparse.Namespace:
    return argparse.Namespace(supabase=supabase, data_dir=None)


def _fake_response(rows: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = rows
    resp.raise_for_status.return_value = None
    return resp


def _make_fake_httpx(rows: list[dict]) -> MagicMock:
    """Return a fake httpx module whose .post() returns a response with rows."""
    fake = MagicMock()
    fake.post.return_value = _fake_response(rows)
    # Make HTTPStatusError and RequestError real exceptions so except clauses work
    fake.HTTPStatusError = type("HTTPStatusError", (Exception,), {})
    fake.RequestError = type("RequestError", (Exception,), {})
    return fake


class TestDoctorNoFlag:
    """Without --supabase, doctor prints usage and exits 0."""

    def test_no_flag_prints_usage_and_returns_0(self) -> None:
        from horus_os.cli.doctor_cmd import run_doctor

        out = io.StringIO()
        err = io.StringIO()
        code = run_doctor(_args(supabase=False), stdout=out, stderr=err)

        assert code == 0
        assert "horus-os doctor --supabase" in out.getvalue()
        assert err.getvalue() == ""


class TestDoctorMissingEnv:
    """Without env vars, doctor exits nonzero with a not-configured message."""

    def test_missing_both_vars_returns_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

        from horus_os.cli.doctor_cmd import run_doctor

        out = io.StringIO()
        err = io.StringIO()
        code = run_doctor(_args(), stdout=out, stderr=err)

        assert code != 0
        # Should mention what is missing, without echoing any key value
        assert "SUPABASE_URL" in err.getvalue() or "not configured" in err.getvalue().lower()
        assert "SUPABASE_SERVICE_KEY" not in out.getvalue()

    def test_missing_key_returns_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://your-project.supabase.co")
        monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

        from horus_os.cli.doctor_cmd import run_doctor

        out = io.StringIO()
        err = io.StringIO()
        code = run_doctor(_args(), stdout=out, stderr=err)

        assert code != 0


class TestDoctorAllRlsOn:
    """When all tables report rls_enabled=true, doctor returns 0 and lists them."""

    _ALL_ON: ClassVar[list[dict]] = [
        {"table_name": "traces", "rls_enabled": True, "policy_count": 2},
        {"table_name": "agent_profiles", "rls_enabled": True, "policy_count": 2},
        {"table_name": "tasks", "rls_enabled": True, "policy_count": 2},
        {"table_name": "sync_health", "rls_enabled": True, "policy_count": 2},
    ]

    def test_all_on_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://your-project.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

        fake_httpx = _make_fake_httpx(self._ALL_ON)
        old = sys.modules.get("httpx")
        sys.modules["httpx"] = fake_httpx  # type: ignore[assignment]
        try:
            from horus_os.cli.doctor_cmd import run_doctor

            out = io.StringIO()
            err = io.StringIO()
            code = run_doctor(_args(), stdout=out, stderr=err)
        finally:
            if old is None:
                sys.modules.pop("httpx", None)
            else:
                sys.modules["httpx"] = old

        assert code == 0
        output = out.getvalue()
        for row in self._ALL_ON:
            assert row["table_name"] in output
        assert "RLS=on" in output

    def test_all_on_service_key_not_in_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://your-project.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "super-secret-key-value")

        fake_httpx = _make_fake_httpx(self._ALL_ON)
        old = sys.modules.get("httpx")
        sys.modules["httpx"] = fake_httpx  # type: ignore[assignment]
        try:
            from horus_os.cli.doctor_cmd import run_doctor

            out = io.StringIO()
            err = io.StringIO()
            run_doctor(_args(), stdout=out, stderr=err)
        finally:
            if old is None:
                sys.modules.pop("httpx", None)
            else:
                sys.modules["httpx"] = old

        combined = out.getvalue() + err.getvalue()
        # The actual key value must never appear in output (T-65-09)
        assert "super-secret-key-value" not in combined


class TestDoctorOneRlsOff:
    """When any table has rls_enabled=false, doctor returns nonzero."""

    _ONE_OFF: ClassVar[list[dict]] = [
        {"table_name": "traces", "rls_enabled": True, "policy_count": 2},
        {"table_name": "agent_profiles", "rls_enabled": False, "policy_count": 0},
    ]

    def test_one_off_returns_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://your-project.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

        fake_httpx = _make_fake_httpx(self._ONE_OFF)
        old = sys.modules.get("httpx")
        sys.modules["httpx"] = fake_httpx  # type: ignore[assignment]
        try:
            from horus_os.cli.doctor_cmd import run_doctor

            out = io.StringIO()
            err = io.StringIO()
            code = run_doctor(_args(), stdout=out, stderr=err)
        finally:
            if old is None:
                sys.modules.pop("httpx", None)
            else:
                sys.modules["httpx"] = old

        assert code != 0
        output = out.getvalue()
        assert "agent_profiles" in output
        assert "RLS=OFF" in output


class TestDoctorEmptyResult:
    """An empty RPC result means nothing was verified -> unhealthy (WR-02)."""

    def test_empty_rows_returns_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://your-project.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

        fake_httpx = _make_fake_httpx([])
        old = sys.modules.get("httpx")
        sys.modules["httpx"] = fake_httpx  # type: ignore[assignment]
        try:
            from horus_os.cli.doctor_cmd import run_doctor

            out = io.StringIO()
            err = io.StringIO()
            code = run_doctor(_args(), stdout=out, stderr=err)
        finally:
            if old is None:
                sys.modules.pop("httpx", None)
            else:
                sys.modules["httpx"] = old

        assert code != 0, "an empty RPC result must be reported as unhealthy"
        assert "no rows" in err.getvalue().lower()


class TestDoctorMissingExpectedTable:
    """A result missing an expected synced table -> unhealthy (WR-03)."""

    _MISSING_TASKS: ClassVar[list[dict]] = [
        {"table_name": "traces", "rls_enabled": True, "policy_count": 2},
        {"table_name": "agent_profiles", "rls_enabled": True, "policy_count": 2},
        {"table_name": "sync_health", "rls_enabled": True, "policy_count": 2},
        # tasks is absent (migration not applied for this table).
    ]

    def test_missing_expected_table_returns_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://your-project.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

        fake_httpx = _make_fake_httpx(self._MISSING_TASKS)
        old = sys.modules.get("httpx")
        sys.modules["httpx"] = fake_httpx  # type: ignore[assignment]
        try:
            from horus_os.cli.doctor_cmd import run_doctor

            out = io.StringIO()
            err = io.StringIO()
            code = run_doctor(_args(), stdout=out, stderr=err)
        finally:
            if old is None:
                sys.modules.pop("httpx", None)
            else:
                sys.modules["httpx"] = old

        assert code != 0, "a missing expected synced table must be unhealthy"
        assert "tasks" in err.getvalue(), "the absent table must be named in stderr"

    def test_extra_non_horus_table_does_not_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All expected tables present with RLS on stays healthy even with extras."""
        rows = [
            {"table_name": "traces", "rls_enabled": True, "policy_count": 2},
            {"table_name": "agent_profiles", "rls_enabled": True, "policy_count": 2},
            {"table_name": "tasks", "rls_enabled": True, "policy_count": 2},
            {"table_name": "sync_health", "rls_enabled": True, "policy_count": 2},
            # An unrelated table the operator hosts in the same project.
            {"table_name": "some_other_app_table", "rls_enabled": False, "policy_count": 0},
        ]
        monkeypatch.setenv("SUPABASE_URL", "https://your-project.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

        fake_httpx = _make_fake_httpx(rows)
        old = sys.modules.get("httpx")
        sys.modules["httpx"] = fake_httpx  # type: ignore[assignment]
        try:
            from horus_os.cli.doctor_cmd import run_doctor

            out = io.StringIO()
            err = io.StringIO()
            code = run_doctor(_args(), stdout=out, stderr=err)
        finally:
            if old is None:
                sys.modules.pop("httpx", None)
            else:
                sys.modules["httpx"] = old

        assert code == 0, "an extra non-horus table must not flip the result to failure"
        assert "some_other_app_table" in out.getvalue(), "extra tables are still displayed"


class TestDoctorRpcUrl:
    """Doctor calls the correct PostgREST RPC endpoint."""

    def test_rpc_url_contains_check_rls_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://your-project.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")

        fake_httpx = _make_fake_httpx([])
        old = sys.modules.get("httpx")
        sys.modules["httpx"] = fake_httpx  # type: ignore[assignment]
        try:
            from horus_os.cli.doctor_cmd import run_doctor

            run_doctor(_args(), stdout=io.StringIO(), stderr=io.StringIO())
        finally:
            if old is None:
                sys.modules.pop("httpx", None)
            else:
                sys.modules["httpx"] = old

        call_args = fake_httpx.post.call_args
        # The first positional arg is the URL
        url_called = call_args[0][0]
        assert "rpc/check_rls_status" in url_called


class TestDoctorCliWiring:
    """doctor subparser must be wired in __main__ with set_defaults(func=run_doctor)."""

    def test_run_doctor_importable_from_cli_barrel(self) -> None:
        from horus_os.cli import run_doctor  # noqa: F401

    def test_doctor_in_cli_all(self) -> None:
        import horus_os.cli as cli_module

        assert "run_doctor" in cli_module.__all__

    def test_doctor_subcommand_parses(self) -> None:
        from horus_os.__main__ import build_parser
        from horus_os.cli.doctor_cmd import run_doctor

        parser = build_parser()
        args = parser.parse_args(["doctor", "--supabase"])
        assert args.supabase is True
        assert args.func is run_doctor
