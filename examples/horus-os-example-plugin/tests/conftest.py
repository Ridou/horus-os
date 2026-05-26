"""Local conftest for the reference plugin's tier-1 tests.

When the host repo's ``pytest`` invocation collects this directory via
``[tool.pytest.ini_options].testpaths``, the plugin's ``src/`` is NOT
on ``sys.path`` because the plugin is not pip-installed into the host
``.venv`` — installing it would pollute the host's plugin-discovery
tests (the entry-point walk would find it). Pre-pending the plugin's
``src/`` to ``sys.path`` here makes ``horus_os_example_plugin`` an
ordinary import without ever touching ``importlib.metadata``.

The Phase 48 installer-e2e smoke test in
``tests/plugins/test_reference_plugin_install_local.py`` uses the
``clean_venv`` fixture so an isolated venv DOES pip-install the
plugin; that path exercises the entry-point seam end-to-end. This
conftest covers the in-process tier-1 path only.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PLUGIN_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_PLUGIN_SRC) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_SRC))
