"""Broken-plugin fixtures for TEST-19 (Phase 42 failure isolation).

Each subpackage is one synthetic plugin used to prove
``discover_plugins()`` + ``PluginLoader.load()`` contain failures at
the right error_phase without crashing the host:

* ``bad_toml`` — syntactically invalid horus-plugin.toml; surfaces as
  ``error_phase="discover"``.
* ``schema_fail`` — valid TOML, fails MANIFEST_V1_SCHEMA (unknown
  capability); surfaces as ``error_phase="validate"``.
* ``import_raises`` — valid manifest; module raises RuntimeError at
  import; surfaces as ``error_phase="load"``.
* ``tool_raises_registration`` — valid manifest; factory raises during
  registration; surfaces as ``error_phase="load"`` with rollback.
* ``healthy`` — control fixture that loads cleanly alongside the broken
  ones; proves the isolation guarantee.
"""
