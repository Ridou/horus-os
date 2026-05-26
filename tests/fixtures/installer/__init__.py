"""Synthetic wheel fixtures for Phase 44 installer tests.

The four template directories under ``tests/fixtures/installer/`` are
turned into real ``.whl`` / ``.tar.gz`` files by
``build_fixture_wheels.build_fixture_wheels(tmp_dir)`` at test-session
start. The synthetic wheels are byte-exact zips of the template
``horus-plugin.toml`` + ``RECORD`` + ``METADATA`` contents, laid out in
the standard ``<dist-info>`` directory layout that
``read_wheel_record`` / ``read_wheel_metadata`` /
``extract_horus_plugin_toml`` parse.

Keeping the templates as plain text files (rather than building a
wheel via ``setuptools`` or ``build``) avoids a real ``pip wheel``
dependency in CI and keeps the per-test wheel construction
deterministic.
"""
