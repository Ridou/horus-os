"""Build the four synthetic installer fixture archives from text templates.

Called by ``tests/plugins/conftest.py`` (or a per-test fixture) to
materialize the template directories into real ``.whl`` / ``.tar.gz``
files in a session-scoped tmp dir. The output is a dict keyed by the
template directory name (``wheel_clean``, ``wheel_with_pth``,
``wheel_downgrades_pydantic``, ``sdist_only``) → ``Path`` of the
built artifact.

Each ``.whl`` is a zip with three files at the layout the installer's
parsers expect:

  horus-plugin.toml                            (at the wheel root)
  <dist_name>-<version>.dist-info/RECORD       (the wheel RECORD)
  <dist_name>-<version>.dist-info/METADATA     (the wheel METADATA)

The ``dist_name`` and ``version`` are read from the template's
``horus-plugin.toml`` ``name`` and ``version`` fields. The dist
filename uses underscore-normalized name + the version per PEP 427.

``sdist_only`` is special: it produces a ``.tar.gz`` (not a ``.whl``)
so ``detect_sdist`` trips on the dirs that lack a sibling ``.whl``.
"""

from __future__ import annotations

import re
import tarfile
import tomllib
import zipfile
from pathlib import Path

FIXTURES_ROOT = Path(__file__).resolve().parent


def _read_template_files(template_dir: Path) -> tuple[bytes, bytes, bytes]:
    """Return (horus_plugin_toml, RECORD, METADATA) bytes for a template dir.

    Templates that lack a RECORD / METADATA file return empty bytes for
    the missing slot (only the ``sdist_only`` template skips them).
    """
    toml_path = template_dir / "horus-plugin.toml"
    record_path = template_dir / "RECORD"
    metadata_path = template_dir / "METADATA"
    toml_bytes = toml_path.read_bytes() if toml_path.exists() else b""
    record_bytes = record_path.read_bytes() if record_path.exists() else b""
    metadata_bytes = metadata_path.read_bytes() if metadata_path.exists() else b""
    return toml_bytes, record_bytes, metadata_bytes


def _parse_name_version(toml_bytes: bytes) -> tuple[str, str]:
    """Parse the ``name`` + ``version`` fields out of a manifest payload."""
    payload = tomllib.loads(toml_bytes.decode("utf-8"))
    return payload["name"], payload["version"]


def _wheel_dist_name(plugin_name: str) -> str:
    """Normalize a plugin name to the PEP 427 dist-name component.

    Replaces ``-`` with ``_`` per the underscore-normalization rule
    used by wheel filenames.
    """
    return re.sub(r"-", "_", plugin_name)


def _build_one_wheel(template_dir: Path, dest_dir: Path) -> Path:
    """Build one ``.whl`` from a wheel_* template directory."""
    toml_bytes, record_bytes, metadata_bytes = _read_template_files(template_dir)
    plugin_name, version = _parse_name_version(toml_bytes)
    dist_name = _wheel_dist_name(plugin_name)
    wheel_filename = f"{dist_name}-{version}-py3-none-any.whl"
    wheel_path = dest_dir / wheel_filename
    dist_info_dir = f"{dist_name}-{version}.dist-info"
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("horus-plugin.toml", toml_bytes)
        if record_bytes:
            zf.writestr(f"{dist_info_dir}/RECORD", record_bytes)
        if metadata_bytes:
            zf.writestr(f"{dist_info_dir}/METADATA", metadata_bytes)
    return wheel_path


def _build_one_sdist(template_dir: Path, dest_dir: Path) -> Path:
    """Build one ``.tar.gz`` from the sdist_only template directory.

    The sdist carries just the horus-plugin.toml manifest at its root.
    """
    toml_bytes, _record, _metadata = _read_template_files(template_dir)
    plugin_name, version = _parse_name_version(toml_bytes)
    dist_name = _wheel_dist_name(plugin_name)
    sdist_filename = f"{dist_name}-{version}.tar.gz"
    sdist_path = dest_dir / sdist_filename
    inner_dir = f"{dist_name}-{version}"
    import io

    with tarfile.open(sdist_path, "w:gz") as tf:
        info = tarfile.TarInfo(name=f"{inner_dir}/horus-plugin.toml")
        info.size = len(toml_bytes)
        tf.addfile(info, io.BytesIO(toml_bytes))
    return sdist_path


def build_fixture_wheels(dest_dir: Path) -> dict[str, Path]:
    """Build every fixture archive into ``dest_dir`` and return the path map.

    Returns a dict keyed by template directory name. Wheel templates
    produce ``.whl`` files; the sdist template produces ``.tar.gz``.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for template_name in ("wheel_clean", "wheel_with_pth", "wheel_downgrades_pydantic"):
        template_dir = FIXTURES_ROOT / template_name
        if not template_dir.is_dir():
            continue
        out[template_name] = _build_one_wheel(template_dir, dest_dir)
    sdist_dir = FIXTURES_ROOT / "sdist_only"
    if sdist_dir.is_dir():
        out["sdist_only"] = _build_one_sdist(sdist_dir, dest_dir)
    return out


__all__ = ["build_fixture_wheels"]
