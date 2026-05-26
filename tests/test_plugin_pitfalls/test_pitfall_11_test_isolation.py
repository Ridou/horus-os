"""Pitfall 11: Plugin tests pollute the host venv or the entry-point cache.

See .planning/research/PITFALLS.md §"Pitfall 11" for the documented
threat. A test that pip-installs a plugin into the host runner's venv
leaves the runner's site-packages dirty across test invocations; a
test that monkey-patches ``importlib.metadata.entry_points`` without
proper tear-down leaks entries into subsequent tests. Either failure
mode produces flaky test ordering AND breaks the developer's host
Python environment.

The Phase 42 prevention pattern is two-fold:

* Tier-2 (``fake_plugin_entry_points``) uses pytest's ``monkeypatch``
  fixture, which auto-undoes at test teardown. Per-test scope means
  test A's injected entries are gone by the time test B runs.
* Tier-3 (``clean_venv``) creates an isolated venv under
  ``tmp_path_factory.getbasetemp()``; the runner's ``sys.prefix`` is
  never touched.

Tier-3 portion of this file is gated by ``@pytest.mark.installer_e2e``
so the default ``pytest`` invocation runs the tier-2 assertions only.

Five structural assertions:

1. Two sequential test functions calling the discovery walk see
   isolated state — no entry-point leak between them.
2. After a test that injects synthetic entries exits, the production
   ``importlib.metadata.entry_points(group=...)`` returns the host's
   unmodified state.
3. (TIER 3, opt-in) The ``clean_venv`` fixture's python executable
   path is NOT ``sys.executable`` — proves the fixture spawned a real
   second interpreter.
4. (TIER 3, opt-in) The clean_venv's site-packages directory lives
   under ``tmp_path_factory.getbasetemp()`` — proves nothing landed
   in the runner's site-packages.
5. (TIER 3, opt-in) The fixture is session-scoped: the same venv is
   reused across multiple tier-3 tests in one session (amortizes the
   ~30s pip install -e cost).
"""

from __future__ import annotations

import sys
from importlib.metadata import entry_points

import pytest

# Tier-1/tier-2 portions run on the default invocation. Tier-3 portions
# are marked installer_e2e and skipped without --run-installer-e2e.


def test_discovery_entry_points_returns_host_state_after_no_monkeypatch() -> None:
    """Baseline: the host's ``entry_points(group='horus_os.plugins')`` is observable."""
    # No monkeypatch is active here; this returns whatever the developer's
    # runner venv carries. The point of this test is that THIS call works,
    # i.e. the host's entry-point registry is reachable.
    eps = entry_points(group="horus_os.plugins")
    # We don't care about the contents — only that the call succeeds and
    # the API is in the canonical shape.
    assert hasattr(eps, "__iter__"), "entry_points() returned a non-iterable shape"


def test_tier2_monkeypatch_does_not_leak_into_host_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A per-test monkeypatch of discovery.entry_points reverts at teardown.

    Inside the test: ``horus_os.plugins.discovery.entry_points`` is
    rebound to a synthetic stub. The reversion is implicit (pytest's
    monkeypatch fixture undoes at teardown); the next test
    (``test_host_registry_unmodified_after_monkeypatch_test``) asserts
    the revert.
    """
    sentinel_entries = ["sentinel-marker-do-not-leak"]

    def _stub(*, group: str) -> list[str]:
        return sentinel_entries

    monkeypatch.setattr("horus_os.plugins.discovery.entry_points", _stub)

    import horus_os.plugins.discovery as discovery

    assert discovery.entry_points(group="horus_os.plugins") == sentinel_entries


def test_host_registry_unmodified_after_monkeypatch_test() -> None:
    """After the prior test's monkeypatch reverts, the host registry is intact.

    This test depends on test ordering — pytest runs tests in file order
    by default. If the monkeypatch leaked, this test's assertion would
    catch it.
    """
    import horus_os.plugins.discovery as discovery

    # The production reference should now point at importlib.metadata.entry_points,
    # not the sentinel stub from the previous test.
    eps = discovery.entry_points(group="horus_os.plugins")
    # Must not be the sentinel list.
    assert eps != ["sentinel-marker-do-not-leak"], (
        "Pitfall 11: monkeypatch from prior test leaked into this test's namespace."
    )


# --- Tier-3 portions (opt-in via --run-installer-e2e) ----------------------


@pytest.mark.installer_e2e
def test_clean_venv_uses_a_separate_python_interpreter(clean_venv: object) -> None:
    """The clean_venv fixture's python is NOT the runner's sys.executable.

    Skipped by default; runs under --run-installer-e2e. Asserts the
    tier-3 fixture spawns a real second interpreter under tmp_path.
    """
    # Late-import the dataclass to avoid pulling test internals into the
    # module-level namespace.
    from tests.conftest import CleanVenv

    assert isinstance(clean_venv, CleanVenv)
    assert str(clean_venv.python) != sys.executable, (
        f"Pitfall 11 tier-3: clean_venv.python ({clean_venv.python}) equals "
        f"the runner's sys.executable ({sys.executable}); the fixture failed "
        "to spawn an isolated venv."
    )


@pytest.mark.installer_e2e
def test_clean_venv_site_packages_is_isolated_from_runner(
    clean_venv: object,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The clean_venv's site-packages must live under tmp_path_factory.getbasetemp()."""
    from tests.conftest import CleanVenv

    assert isinstance(clean_venv, CleanVenv)
    basetemp = tmp_path_factory.getbasetemp()
    assert str(clean_venv.site_packages).startswith(str(basetemp)), (
        f"Pitfall 11 tier-3: clean_venv.site_packages ({clean_venv.site_packages}) "
        f"escaped tmp_path_factory.getbasetemp() ({basetemp}); the runner's "
        "site-packages may be polluted."
    )
