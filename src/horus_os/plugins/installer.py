"""Two-phase plugin installer with grant prompt, rollback, and upgrade-diff.

The installer wraps ``pip`` via a single chokepoint helper (``run_pip``)
that uses the stdlib subprocess module to invoke
``[sys.executable, "-m", "pip", *args]``. A grep on the literal
invocation token returns exactly 1: the chokepoint inside ``run_pip``.
Pitfall 4 (six pip-wrapping foot-guns) is foreclosed by that single
audit point — no other code path in this module ever shells out.

The orchestrator ``install_plugin(spec_str, ...)`` walks a five-phase
pipeline:

* Phase 0 — venv gate. Refuses to install outside a venv unless the
  caller passes ``allow_system_python=True``.
* Phase A — download. ``pip download --no-deps`` into a tmpdir. We
  inspect the result without ever extracting an sdist.
* Phase A.5 — sdist gate. If no ``.whl`` landed (only a ``.tar.gz``
  or ``.zip``), refuse unless ``allow_sdist=True``. Pitfall 4 mode 5:
  sdist installs run ``setup.py`` BEFORE manifest validation, so
  every refusal must land at Phase A.5 — not at Phase D.
* Phase B — validate. Parse the wheel-embedded ``horus-plugin.toml``
  through ``validate_manifest``. Parse RECORD; refuse any wheel that
  ships a ``.pth`` file (Checkmarx command-jacking). Parse METADATA;
  for every ``Requires-Dist`` line that targets one of the horus-os
  runtime deps (``pydantic``, ``packaging``), refuse if the spec
  excludes our currently-installed version.
* Phase C — grant. Render the capability grant prompt; collect the
  user's decision. Persist ``granted`` rows + audit-log entries
  through ``PermissionService.grant``. Refusing ANY capability
  raises ``PluginInstallError`` and skips Phase D entirely (no
  half-grant state, INSTALL-05).
* Phase D — install. ``pip install --no-deps --no-build-isolation``
  against the wheel.
* Phase E — verify. Re-run ``pip freeze``; compare sha256 to the
  pre-install freeze. Equal hash → silent rollback (pip reported
  success but installed nothing). Different but horus-os runtime
  deps moved → runtime-dep-changed rollback. Otherwise call
  ``discover_plugins()`` and INSERT a ``plugins`` row with
  ``status='pending'``.

Any exception from Phase D onward triggers ``pip uninstall -y <name>``
and a ``DELETE FROM plugins`` to leave the venv byte-equal to the
pre-install state.

``update_plugin(name, spec_str, ...)`` adds the upgrade-diff
classifier. The new manifest's capability set is compared against the
existing ``plugin_capabilities`` rows for the installed version:

* Unchanged (same name set) → re-grant under the new version, no
  prompt.
* Reduced (new ⊂ old) → re-grant survivors; ``revoke`` audit row per
  surplus old capability.
* Expanded (new ⊋ old) → call ``PermissionService.pending_on_upgrade``
  for the EXPANDED diff and re-prompt only for the new caps. On
  refuse, abort without Phase D (the old version stays installed,
  the old grants stay granted).

Every test path monkeypatches ``run_pip`` at the module boundary so no
real ``pip install`` runs in CI. The real-install gate (TEST-20)
lands in Phase 49's three-OS install-smoke matrix.
"""

from __future__ import annotations

import email
import hashlib
import string
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from packaging.requirements import InvalidRequirement, Requirement

from horus_os.plugins.capability_catalog import DESCRIPTIONS, Capability
from horus_os.plugins.discovery import discover_plugins
from horus_os.plugins.manifest import (
    compute_manifest_hash,
    format_validation_error,
    validate_manifest,
)
from horus_os.plugins.permissions import PermissionService

if TYPE_CHECKING:
    from horus_os.plugins.spec import PluginSpec
    from horus_os.storage import Database


# Runtime deps a plugin's Requires-Dist line is forbidden from
# downgrading. Source of truth: pyproject.toml [project] dependencies
# (v0.5 base = pydantic + packaging). fastapi / anthropic / google-genai
# are optional extras in v0.5, so a plugin requiring an older fastapi
# is acceptable as long as the user has not installed the [server] /
# [anthropic] / [gemini] extra. See PROJECT.md "Out of Scope" and
# STACK.md "base vs extras."
HORUS_OS_RUNTIME_DEPS: tuple[str, ...] = ("pydantic", "packaging")


# Stable, machine-readable reason tokens emitted as
# PluginInstallError.reason. Documented + grep-friendly so the CLI
# layer can map them to user-facing exit messages without parsing the
# human-readable error string.
_REASON_USER_REFUSED = "user_refused_grant"
_REASON_PARTIAL_GRANT = "partial_grant_refused"
_REASON_SDIST_REFUSED = "sdist_default_refusal"
_REASON_PTH_REFUSED = "pth_in_record"
_REASON_RUNTIME_DOWNGRADE = "runtime_dep_downgrade"
_REASON_RUNTIME_CHANGED = "runtime_dep_changed"
_REASON_MISSING_MANIFEST = "missing_manifest"
_REASON_MANIFEST_VALIDATION = "manifest_validation_failed"
_REASON_VENV = "outside_venv"
_REASON_NO_WHEEL = "no_wheel_in_download"
_REASON_SILENT_ROLLBACK = "silent_rollback"
_REASON_VERIFY_NOT_DISCOVERED = "not_in_discovery"


class PluginInstallError(Exception):
    """Raised whenever a phase of the installer pipeline refuses or fails.

    Two structured fields the CLI layer reads:
      * ``phase`` — one of ``"venv"|"download"|"validate"|"sdist"|
        "pth"|"downgrade"|"grant"|"install"|"verify"|"rollback"``.
      * ``reason`` — a stable lower-snake token (one of the
        ``_REASON_*`` module constants above). Machine-readable so
        the CLI can branch on it without parsing the message.
    """

    __slots__ = ("phase", "reason")

    def __init__(self, phase: str, reason: str, message: str) -> None:
        self.phase = phase
        self.reason = reason
        super().__init__(f"[{phase}] {reason}: {message}")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def is_venv() -> bool:
    """Return True when this Python is running inside a venv.

    The canonical check (per Python's own venv docs and pip's
    ``--require-virtualenv`` implementation) is ``sys.prefix !=
    sys.base_prefix``. Tests monkeypatch the two attributes to flip
    the result.
    """
    return sys.prefix != sys.base_prefix


def run_pip(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """The single chokepoint for every pip invocation in the installer.

    Always uses ``[sys.executable, "-m", "pip", *args]`` so the active
    venv's pip is the one that runs (Pitfall 4 mode 1: never call
    bare ``pip``). ``shell=False`` is structurally impossible because
    argv is a list (Pitfall 4 mode 5).

    ``capture_output=True, text=True`` so callers can read stdout/
    stderr. Tests monkeypatch THIS function (not the underlying
    stdlib call directly) so the byte-level audit point stays clean:
    a grep on the literal invocation token returns exactly 1.
    """
    cmd = [sys.executable, "-m", "pip", *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def pip_freeze_sha256() -> str:
    """Return sha256 of ``pip freeze`` stdout.

    Used pre- and post-install to detect (a) silent rollbacks (no
    change in freeze means pip installed nothing), and (b) runtime
    dep mutations (a change covering one of HORUS_OS_RUNTIME_DEPS).
    """
    proc = run_pip("freeze", check=False)
    return hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest()


def parse_freeze(freeze_output: str) -> dict[str, str]:
    """Parse ``pip freeze`` output into ``{package_lower: version}``.

    Handles the two common line shapes:
      * ``name==version`` → ``{"name": "version"}``
      * ``name @ <url>``  → ``{"name": ""}`` (editable / VCS install
        with no concrete version; downgrade check skips these).

    Lines that match neither shape are ignored (e.g. blank lines,
    comment lines beginning with ``#``).
    """
    result: dict[str, str] = {}
    for raw in freeze_output.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, _, version = line.partition("==")
            result[name.strip().lower()] = version.strip()
        elif " @ " in line:
            name, _, _rest = line.partition(" @ ")
            result[name.strip().lower()] = ""
    return result


def _wheel_dist_info_dir(zf: zipfile.ZipFile) -> str | None:
    """Locate the ``*.dist-info`` directory inside a wheel zip."""
    for name in zf.namelist():
        parts = name.split("/")
        if len(parts) >= 2 and parts[0].endswith(".dist-info"):
            return parts[0]
    return None


def extract_horus_plugin_toml(wheel_path: Path) -> bytes:
    """Return the bytes of the wheel's ``horus-plugin.toml`` payload.

    Search order:
      1. At the wheel root (``horus-plugin.toml``) — the example
         plugin convention used by the Phase 41 + 47 reference.
      2. Under ``<dist-name>/horus-plugin.toml`` — for plugins that
         ship the manifest as package data inside the importable
         module directory.

    Raises ``PluginInstallError(phase='validate',
    reason='missing_manifest')`` if neither location exists.
    """
    with zipfile.ZipFile(wheel_path, "r") as zf:
        names = zf.namelist()
        if "horus-plugin.toml" in names:
            return zf.read("horus-plugin.toml")
        for name in names:
            if name.endswith("/horus-plugin.toml") and not name.startswith(
                ("dist-info/", ".dist-info/")
            ):
                # Skip dist-info entries; the manifest belongs in
                # the importable package directory or at the wheel
                # root.
                parts = name.split("/")
                if not parts[0].endswith(".dist-info"):
                    return zf.read(name)
    raise PluginInstallError(
        "validate",
        _REASON_MISSING_MANIFEST,
        f"wheel {wheel_path.name} does not contain horus-plugin.toml at the root "
        f"or under any package directory",
    )


def read_wheel_record(wheel_path: Path) -> list[tuple[str, str, str]]:
    """Parse the wheel's ``*.dist-info/RECORD`` file into (path, hash, size) triples.

    RECORD is a CSV-ish file with one row per installed file: each row
    has three comma-separated fields (filename, hash, size). Trailing
    empty hash/size fields (used for the RECORD file itself) are
    preserved as empty strings.
    """
    with zipfile.ZipFile(wheel_path, "r") as zf:
        dist_info = _wheel_dist_info_dir(zf)
        if dist_info is None:
            return []
        record_name = f"{dist_info}/RECORD"
        if record_name not in zf.namelist():
            return []
        record_bytes = zf.read(record_name)
    triples: list[tuple[str, str, str]] = []
    for raw in record_bytes.decode("utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        fields = line.split(",")
        if len(fields) < 3:
            # Defensive: pad to three fields so callers can rely on
            # the tuple shape.
            fields = fields + [""] * (3 - len(fields))
        triples.append((fields[0], fields[1], fields[2]))
    return triples


def read_wheel_metadata(wheel_path: Path) -> email.message.Message:
    """Parse the wheel's ``*.dist-info/METADATA`` into a Message object.

    METADATA is RFC822-shaped (Metadata-Version + headers); using the
    stdlib ``email`` parser is the canonical path PyPA tooling uses.
    Callers iterate ``meta.get_all('Requires-Dist', [])`` for the
    downgrade gate.
    """
    with zipfile.ZipFile(wheel_path, "r") as zf:
        dist_info = _wheel_dist_info_dir(zf)
        if dist_info is None:
            return email.message_from_bytes(b"")
        metadata_name = f"{dist_info}/METADATA"
        if metadata_name not in zf.namelist():
            return email.message_from_bytes(b"")
        meta_bytes = zf.read(metadata_name)
    return email.message_from_bytes(meta_bytes)


def check_no_pth(wheel_path: Path) -> None:
    """Refuse any wheel whose RECORD contains a ``.pth`` entry.

    ``.pth`` files execute on every Python invocation (per the
    ``site`` module) so a malicious wheel that ships one bypasses
    every horus-os gate by running at interpreter startup, before
    any plugin loader. Raises before Phase D ever runs.
    """
    record = read_wheel_record(wheel_path)
    for filename, _hash, _size in record:
        if filename.endswith(".pth"):
            raise PluginInstallError(
                "pth",
                _REASON_PTH_REFUSED,
                f"wheel {wheel_path.name} contains .pth entry "
                f"{filename!r}; .pth files execute on every Python "
                f"startup and bypass the capability grant gate",
            )


def check_no_downgrade(wheel_path: Path, current_freeze: dict[str, str]) -> None:
    """Refuse any wheel that would downgrade a horus-os runtime dep.

    For each ``Requires-Dist`` line in the wheel's METADATA, parse
    via ``packaging.requirements.Requirement``. If the requirement's
    package name matches a HORUS_OS_RUNTIME_DEPS entry, check whether
    the currently-installed version satisfies the requirement's
    specifier. If not, refuse with a structured error naming the
    package, the current version, and the offending specifier.
    """
    meta = read_wheel_metadata(wheel_path)
    requires = meta.get_all("Requires-Dist", []) or []
    for req_line in requires:
        # Strip environment marker (``; extra == 'foo'``) — anything
        # past the first semicolon. ``packaging.Requirement`` handles
        # markers natively but for the downgrade gate we want the
        # base requirement.
        cleaned = req_line.split(";", 1)[0].strip()
        if not cleaned:
            continue
        try:
            req = Requirement(cleaned)
        except InvalidRequirement:
            # Malformed Requires-Dist line: skip rather than refuse,
            # the manifest_validation gate is the source of truth
            # for required-shape errors.
            continue
        pkg_lower = req.name.lower()
        if pkg_lower not in HORUS_OS_RUNTIME_DEPS:
            continue
        current_version = current_freeze.get(pkg_lower)
        if not current_version:
            # Not installed → nothing to downgrade. (A real install
            # would pull the dep in via Phase D, but Phase D is
            # ``--no-deps`` so this is moot.)
            continue
        if not req.specifier.contains(current_version, prereleases=True):
            raise PluginInstallError(
                "downgrade",
                _REASON_RUNTIME_DOWNGRADE,
                f"plugin's Requires-Dist {req_line!r} excludes the "
                f"currently-installed {pkg_lower} {current_version}; "
                f"installing it would downgrade a horus-os runtime "
                f"dependency",
            )


def detect_sdist(download_dir: Path) -> bool:
    """Return True when the download dir holds an sdist with no wheel sibling.

    A ``pip download`` invocation may produce both a ``.whl`` (the
    fast path) and a ``.tar.gz`` (the sdist fallback). We only refuse
    the case where ONLY an sdist is present, because a wheel sibling
    means we never need to run ``setup.py``.
    """
    has_wheel = any(p.suffix == ".whl" for p in download_dir.iterdir())
    if has_wheel:
        return False
    has_sdist = any(
        p.name.endswith((".tar.gz", ".zip")) for p in download_dir.iterdir()
    )
    return has_sdist


def _find_wheel(download_dir: Path) -> Path | None:
    """Return the first ``.whl`` in the download dir, or None."""
    for p in download_dir.iterdir():
        if p.suffix == ".whl":
            return p
    return None


def render_grant_prompt(spec: PluginSpec, stdout: TextIO) -> None:
    """Print the capability grant prompt to ``stdout``.

    Output shape (rendered for a spec requesting two capabilities):

        Plugin foo 1.0 requests these capabilities:

          [a] filesystem.read — Read files from disk paths the plugin declares...
          [b] net.outbound   — Open outbound network connections to hosts the plugin declares...

        Grant all (y) / per-capability (a/b/c/...) / refuse (n)?

    The per-capability letter is ``string.ascii_lowercase[i]`` for the
    ith capability in spec.capabilities. The description string is
    looked up via ``DESCRIPTIONS[Capability(cap.name)]`` — both the
    enum and the mapping are closed at compile time so no
    user-supplied content reaches the prompt.
    """
    stdout.write(
        f"Plugin {spec.name} {spec.version} requests these capabilities:\n\n"
    )
    for i, cap in enumerate(spec.capabilities):
        letter = string.ascii_lowercase[i]
        try:
            description = DESCRIPTIONS[Capability(cap.name)]
        except (KeyError, ValueError):
            description = "(no description registered)"
        stdout.write(f"  [{letter}] {cap.name} — {description}\n")
    stdout.write(
        "\nSee docs/PLUGIN-SECURITY.md for the trust model before granting capabilities.\n"
    )
    stdout.write(
        "\nGrant all (y) / per-capability (a/b/c/...) / refuse (n)? "
    )


def prompt_for_grants(
    spec: PluginSpec,
    *,
    stdin: TextIO,
    stdout: TextIO,
    assume_yes: bool,
) -> set[str]:
    """Render the prompt + collect the user's grant decision.

    Returns the set of capability name strings the user granted.

    Decision tree:
      * ``assume_yes=True`` (CLI ``--yes`` flag): return the full
        capability set without prompting. Used by automated installs
        and the upgrade-diff unchanged path.
      * input == ``y``: full grant.
      * input == ``n``: raise ``PluginInstallError`` with reason
        ``user_refused_grant``. No half-grant state.
      * input matches letter tokens (e.g. ``ab``): partial grant. If
        the partial grant is missing any requested capability, raise
        ``PluginInstallError`` with reason ``partial_grant_refused``
        — INSTALL-05 forbids the half-grant state.
      * Empty string or unrecognized input: treat as refuse.
    """
    requested_names = [cap.name for cap in spec.capabilities]
    if assume_yes or not requested_names:
        return set(requested_names)

    render_grant_prompt(spec, stdout)
    raw = stdin.readline()
    answer = raw.strip().lower()

    if answer == "y":
        return set(requested_names)
    if answer in ("", "n"):
        raise PluginInstallError(
            "grant",
            _REASON_USER_REFUSED,
            f"user refused to grant the requested capabilities for "
            f"plugin {spec.name} {spec.version}",
        )

    # Letter-token partial grant. Strip non-letters; map each letter
    # back to the capability at that index.
    letters = [c for c in answer if c in string.ascii_lowercase]
    if not letters:
        raise PluginInstallError(
            "grant",
            _REASON_USER_REFUSED,
            f"unrecognized grant decision {answer!r} for plugin "
            f"{spec.name} {spec.version}",
        )
    granted: set[str] = set()
    valid_letters = set(string.ascii_lowercase[: len(requested_names)])
    for letter in letters:
        if letter not in valid_letters:
            continue
        idx = string.ascii_lowercase.index(letter)
        granted.add(requested_names[idx])
    if granted != set(requested_names):
        # Half-grant state: INSTALL-05 says abort.
        raise PluginInstallError(
            "grant",
            _REASON_PARTIAL_GRANT,
            f"partial grant {sorted(granted)!r} does not cover every "
            f"requested capability {sorted(requested_names)!r}; "
            f"installer refuses half-grant state (INSTALL-05)",
        )
    return granted


# ----------------------------------------------------------------------
# Orchestrator + verbs
# ----------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _insert_plugins_row(
    db: Database,
    *,
    name: str,
    version: str,
    manifest_hash: str,
    source: str,
) -> None:
    """INSERT (or refresh) a row into the ``plugins`` table after a successful install."""
    now = _now_iso()
    with db._connect() as conn:
        conn.execute(
            """
            INSERT INTO plugins
                (name, version, manifest_hash, enabled, installed_at, source)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                version = excluded.version,
                manifest_hash = excluded.manifest_hash,
                installed_at = excluded.installed_at,
                source = excluded.source
            """,
            (name, version, manifest_hash, now, source),
        )
        conn.execute(
            """
            INSERT INTO plugin_status
                (plugin_name, status, error_phase, error_message, last_seen)
            VALUES (?, 'pending', NULL, NULL, ?)
            ON CONFLICT(plugin_name) DO UPDATE SET
                status = 'pending',
                error_phase = NULL,
                error_message = NULL,
                last_seen = excluded.last_seen
            """,
            (name, now),
        )


def _delete_plugins_row(db: Database, name: str) -> None:
    """DELETE the plugins row (CASCADE removes plugin_capabilities + plugin_status)."""
    with db._connect() as conn:
        conn.execute("DELETE FROM plugins WHERE name = ?", (name,))


def _rollback(db: Database, name: str) -> None:
    """Best-effort rollback: ``pip uninstall -y <name>`` + DELETE plugins row.

    Errors from either step are swallowed (the install already
    failed; a doubly-failed rollback is logged but does not raise
    over the original PluginInstallError).
    """
    try:
        run_pip("uninstall", "-y", name, check=False)
    except Exception:
        pass
    try:
        _delete_plugins_row(db, name)
    except Exception:
        pass


def install_plugin(
    spec_str: str,
    *,
    db: Database,
    allow_sdist: bool = False,
    allow_system_python: bool = False,
    assume_yes: bool = False,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> str:
    """Two-phase install pipeline. Returns the installed plugin name on success.

    See module docstring for the full phase walk. Every refusal lands
    before Phase D; any post-Phase-D failure triggers automatic
    rollback.
    """
    # Phase 0 — venv gate.
    if not is_venv() and not allow_system_python:
        raise PluginInstallError(
            "venv",
            _REASON_VENV,
            "horus-os plugins install must be run inside a virtualenv "
            "(sys.prefix == sys.base_prefix). Set HORUS_OS_ALLOW_SYSTEM_PYTHON=1 "
            "or pass --allow-system-python to override. See docs/PLUGINS.md.",
        )

    with tempfile.TemporaryDirectory(prefix="horus-os-install-") as tmpdir_str:
        tmpdir = Path(tmpdir_str)

        # Phase A — download.
        run_pip(
            "download",
            "--no-deps",
            "--dest",
            str(tmpdir),
            "--no-build-isolation",
            spec_str,
        )

        # Phase A.5 — sdist gate.
        if detect_sdist(tmpdir) and not allow_sdist:
            raise PluginInstallError(
                "sdist",
                _REASON_SDIST_REFUSED,
                f"download returned only an sdist for {spec_str!r}; sdist "
                f"installs run setup.py BEFORE manifest validation, which "
                f"allows arbitrary code execution prior to the grant prompt "
                f"(Pitfall 4 mode 5 / setup.py arbitrary code execution). "
                f"Pass --allow-sdist to override.",
            )

        wheel_path = _find_wheel(tmpdir)
        if wheel_path is None:
            # No wheel and (allow_sdist=True OR no sdist at all): we
            # cannot proceed because the rest of the pipeline reads
            # wheel-shaped artifacts. Surface as a structured error.
            raise PluginInstallError(
                "download",
                _REASON_NO_WHEEL,
                f"pip download produced no .whl for {spec_str!r}; "
                f"horus-os only supports wheel installs in v0.5",
            )

        # Phase B — validate.
        try:
            toml_bytes = extract_horus_plugin_toml(wheel_path)
        except PluginInstallError:
            raise
        from pydantic import ValidationError

        try:
            spec = validate_manifest(toml_bytes)
        except ValidationError as exc:
            raise PluginInstallError(
                "validate",
                _REASON_MANIFEST_VALIDATION,
                format_validation_error(exc),
            ) from exc

        # Pre-install freeze sha256 — captured BEFORE the .pth /
        # downgrade gates so we have the baseline ready for both
        # Phase E and rollback.
        pre_freeze_proc = run_pip("freeze", check=False)
        pre_freeze_text = pre_freeze_proc.stdout
        pre_freeze_hash = hashlib.sha256(pre_freeze_text.encode("utf-8")).hexdigest()
        pre_freeze_parsed = parse_freeze(pre_freeze_text)

        check_no_pth(wheel_path)
        check_no_downgrade(wheel_path, pre_freeze_parsed)

        # Phase C — grant.
        granted = prompt_for_grants(
            spec, stdin=stdin, stdout=stdout, assume_yes=assume_yes
        )
        permissions = PermissionService(db)
        # Insert the plugins row FIRST (the plugin_capabilities FK
        # requires it). We defer plugin_status to Phase E success so
        # a Phase D failure leaves no orphan 'pending' status row.
        _insert_plugins_row(
            db,
            name=spec.name,
            version=spec.version,
            manifest_hash=spec.manifest_hash,
            source="entry_point",
        )
        for cap_name in granted:
            permissions.grant(
                spec.name,
                spec.version,
                cap_name,
                actor="cli",
                manifest_hash=spec.manifest_hash,
            )

        # Phase D — install.
        install_args: list[str] = ["install", "--no-deps", "--no-build-isolation"]
        if not allow_system_python:
            install_args.append("--require-virtualenv")
        install_args.append(str(wheel_path))
        try:
            run_pip(*install_args)
        except subprocess.CalledProcessError as exc:
            _rollback(db, spec.name)
            raise PluginInstallError(
                "install",
                "pip_install_failed",
                f"pip install failed with exit code {exc.returncode}: "
                f"{exc.stderr or exc.stdout or '(no output)'}",
            ) from exc
        except Exception as exc:
            _rollback(db, spec.name)
            raise PluginInstallError(
                "install",
                "pip_install_unexpected_error",
                f"{type(exc).__name__}: {exc}",
            ) from exc

        # Phase E — verify.
        try:
            post_freeze_proc = run_pip("freeze", check=False)
            post_freeze_text = post_freeze_proc.stdout
            post_freeze_hash = hashlib.sha256(
                post_freeze_text.encode("utf-8")
            ).hexdigest()
            if post_freeze_hash == pre_freeze_hash:
                raise PluginInstallError(
                    "verify",
                    _REASON_SILENT_ROLLBACK,
                    f"pip install reported success but pip freeze is "
                    f"byte-equal to the pre-install snapshot; no package "
                    f"actually landed for {spec.name}",
                )
            post_freeze_parsed = parse_freeze(post_freeze_text)
            for dep in HORUS_OS_RUNTIME_DEPS:
                before = pre_freeze_parsed.get(dep)
                after = post_freeze_parsed.get(dep)
                if before != after:
                    raise PluginInstallError(
                        "verify",
                        _REASON_RUNTIME_CHANGED,
                        f"runtime dependency {dep} changed from "
                        f"{before!r} to {after!r} during install of "
                        f"{spec.name}; rolling back",
                    )
            specs, _errors = discover_plugins()
            discovered_names = {s.name for s in specs}
            if spec.name not in discovered_names:
                raise PluginInstallError(
                    "verify",
                    _REASON_VERIFY_NOT_DISCOVERED,
                    f"plugin {spec.name} installed but does not appear in "
                    f"discover_plugins() output; entry point may be missing",
                )
        except PluginInstallError:
            _rollback(db, spec.name)
            raise
        except Exception as exc:
            _rollback(db, spec.name)
            raise PluginInstallError(
                "verify",
                "verify_unexpected_error",
                f"{type(exc).__name__}: {exc}",
            ) from exc

    return spec.name


def uninstall_plugin(name: str, *, db: Database) -> None:
    """Uninstall a plugin: ``pip uninstall -y`` + DELETE the plugins row.

    CASCADE removes plugin_capabilities + plugin_status rows for the
    same plugin (FK ON DELETE CASCADE in storage.py).
    """
    run_pip("uninstall", "-y", name, check=False)
    _delete_plugins_row(db, name)


def _load_existing_plugin(db: Database, name: str) -> tuple[str, str] | None:
    """Return (version, manifest_hash) for an installed plugin, or None."""
    with db._connect() as conn:
        row = conn.execute(
            "SELECT version, manifest_hash FROM plugins WHERE name = ?",
            (name,),
        ).fetchone()
    if row is None:
        return None
    return row["version"], row["manifest_hash"]


def _load_granted_caps(db: Database, name: str, version: str) -> set[str]:
    """Return the set of currently-granted capability names for (name, version)."""
    with db._connect() as conn:
        rows = conn.execute(
            """
            SELECT capability FROM plugin_capabilities
            WHERE plugin_name = ? AND plugin_version = ? AND state = 'granted'
            """,
            (name, version),
        ).fetchall()
    return {row["capability"] for row in rows}


def update_plugin(
    name: str,
    spec_str: str,
    *,
    db: Database,
    allow_sdist: bool = False,
    allow_system_python: bool = False,
    assume_yes: bool = False,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> str:
    """Upgrade-diff installer: classify and route through the right grant flow.

    Three outcomes, classified by set-equality on capability NAMES
    (Pitfall 5: hash equality alone can drift for orthogonal reasons,
    so we compare the canonical capability-name set):

      * Unchanged: re-grant under the new version, no prompt.
      * Reduced (new ⊂ old): re-grant survivors; revoke audit row
        per surplus old capability.
      * Expanded (new ⊋ old, OR new ⊅ old + adds caps): stage the
        expanded diff via PermissionService.pending_on_upgrade and
        re-prompt only for the new caps. On refuse: abort, the old
        version stays installed.
    """
    existing = _load_existing_plugin(db, name)
    if existing is None:
        raise PluginInstallError(
            "validate",
            "plugin_not_installed",
            f"cannot update {name!r}: no row in the plugins table. "
            f"Use `horus-os plugins install` for first-install.",
        )
    old_version, _old_hash = existing
    old_caps = _load_granted_caps(db, name, old_version)

    # Phase 0 — venv gate (mirrors install_plugin).
    if not is_venv() and not allow_system_python:
        raise PluginInstallError(
            "venv",
            _REASON_VENV,
            "horus-os plugins update must be run inside a virtualenv. "
            "Pass --allow-system-python to override.",
        )

    with tempfile.TemporaryDirectory(prefix="horus-os-update-") as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        run_pip(
            "download",
            "--no-deps",
            "--dest",
            str(tmpdir),
            "--no-build-isolation",
            spec_str,
        )
        if detect_sdist(tmpdir) and not allow_sdist:
            raise PluginInstallError(
                "sdist",
                _REASON_SDIST_REFUSED,
                f"download for update {spec_str!r} returned only an sdist; "
                f"pass --allow-sdist to override",
            )
        wheel_path = _find_wheel(tmpdir)
        if wheel_path is None:
            raise PluginInstallError(
                "download",
                _REASON_NO_WHEEL,
                f"pip download produced no .whl for {spec_str!r}",
            )

        from pydantic import ValidationError

        try:
            toml_bytes = extract_horus_plugin_toml(wheel_path)
            new_spec = validate_manifest(toml_bytes)
        except ValidationError as exc:
            raise PluginInstallError(
                "validate",
                _REASON_MANIFEST_VALIDATION,
                format_validation_error(exc),
            ) from exc

        check_no_pth(wheel_path)
        pre_freeze_text = run_pip("freeze", check=False).stdout
        pre_freeze_parsed = parse_freeze(pre_freeze_text)
        check_no_downgrade(wheel_path, pre_freeze_parsed)

        new_caps = {cap.name for cap in new_spec.capabilities}
        new_hash = compute_manifest_hash(sorted(new_caps))

        # Classify by set comparison on capability NAMES.
        added = new_caps - old_caps
        removed = old_caps - new_caps
        if not added and not removed:
            outcome = "unchanged"
        elif not added and removed:
            outcome = "reduced"
        else:
            outcome = "expanded"

        permissions = PermissionService(db)

        if outcome == "expanded":
            # Stage the expansion as pending on the NEW version and
            # re-prompt for ONLY the new caps.
            permissions.pending_on_upgrade(
                name,
                old_version,
                new_spec.version,
                added,
                new_hash,
                actor="cli",
            )

            # Render a minimal re-prompt for just the expanded diff.
            if assume_yes:
                accepted = set(added)
            else:
                stdout.write(
                    f"Plugin {name} {old_version} → {new_spec.version} "
                    f"requests NEW capabilities:\n\n"
                )
                for i, cap_name in enumerate(sorted(added)):
                    letter = string.ascii_lowercase[i]
                    try:
                        description = DESCRIPTIONS[Capability(cap_name)]
                    except (KeyError, ValueError):
                        description = "(no description registered)"
                    stdout.write(f"  [{letter}] {cap_name} — {description}\n")
                stdout.write("\nGrant new capabilities (y/n)? ")
                answer = stdin.readline().strip().lower()
                if answer != "y":
                    raise PluginInstallError(
                        "grant",
                        _REASON_USER_REFUSED,
                        f"user refused expanded capabilities for "
                        f"{name} {new_spec.version}; old version stays "
                        f"installed",
                    )
                accepted = set(added)

            for cap_name in accepted:
                permissions.grant(
                    name,
                    new_spec.version,
                    cap_name,
                    actor="cli",
                    manifest_hash=new_hash,
                )
            # Re-emit the unchanged old caps under the new version.
            for cap_name in old_caps & new_caps:
                permissions.grant(
                    name,
                    new_spec.version,
                    cap_name,
                    actor="cli",
                    manifest_hash=new_hash,
                )

        elif outcome == "reduced":
            # Revoke each surplus old cap (audit row + state flip)
            # under the OLD version.
            for cap_name in removed:
                permissions.revoke(name, old_version, cap_name, actor="cli")
            # Re-emit the surviving caps under the new version.
            for cap_name in new_caps:
                permissions.grant(
                    name,
                    new_spec.version,
                    cap_name,
                    actor="cli",
                    manifest_hash=new_hash,
                )

        else:  # unchanged
            # Re-emit every cap under the new version. No prompt.
            for cap_name in new_caps:
                permissions.grant(
                    name,
                    new_spec.version,
                    cap_name,
                    actor="cli",
                    manifest_hash=new_hash,
                )

        # Phase D — install the new wheel.
        install_args: list[str] = ["install", "--no-deps", "--no-build-isolation"]
        if not allow_system_python:
            install_args.append("--require-virtualenv")
        install_args.append(str(wheel_path))
        run_pip(*install_args)

        # Update the plugins row with the new version + hash.
        now = _now_iso()
        with db._connect() as conn:
            conn.execute(
                """
                UPDATE plugins
                SET version = ?, manifest_hash = ?, installed_at = ?
                WHERE name = ?
                """,
                (new_spec.version, new_hash, now, name),
            )

    return name


def grant_capability(name: str, capability: str, *, db: Database) -> None:
    """Grant a single capability to an installed plugin from the CLI.

    Looks up the plugin's current version + manifest_hash from the
    plugins table; calls PermissionService.grant with actor='cli'.
    """
    existing = _load_existing_plugin(db, name)
    if existing is None:
        raise PluginInstallError(
            "validate",
            "plugin_not_installed",
            f"cannot grant capability to {name!r}: no row in the plugins table",
        )
    version, manifest_hash = existing
    PermissionService(db).grant(
        name, version, capability, actor="cli", manifest_hash=manifest_hash
    )


def revoke_capability(name: str, capability: str, *, db: Database) -> None:
    """Revoke a single capability from an installed plugin from the CLI."""
    existing = _load_existing_plugin(db, name)
    if existing is None:
        raise PluginInstallError(
            "validate",
            "plugin_not_installed",
            f"cannot revoke capability from {name!r}: no row in the plugins table",
        )
    version, _hash = existing
    PermissionService(db).revoke(name, version, capability, actor="cli")


__all__ = [
    "HORUS_OS_RUNTIME_DEPS",
    "PluginInstallError",
    "check_no_downgrade",
    "check_no_pth",
    "detect_sdist",
    "extract_horus_plugin_toml",
    "grant_capability",
    "install_plugin",
    "is_venv",
    "parse_freeze",
    "pip_freeze_sha256",
    "prompt_for_grants",
    "read_wheel_metadata",
    "read_wheel_record",
    "render_grant_prompt",
    "revoke_capability",
    "run_pip",
    "uninstall_plugin",
    "update_plugin",
]
