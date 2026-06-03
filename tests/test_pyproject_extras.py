"""Phase 76 REL-18/REL-19 lock for the v0.8 optional-dependency contract.

Asserts the seven v0.8 optional extras are declared in pyproject.toml with the
exact pins verified in .planning/research/STACK.md, that the package version is
0.8.0 in both pyproject and the module, that a bare install pulls none of the
v0.8 deps (REL-19 bare-install guarantee), and that the heavy local-memory
triplet stays out of the [all] extra (REL-17-style exclusion so a fresh
.[all] install stays cross-OS clean).

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import horus_os

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

EXPECTED_VERSION = "0.8.0"

# Exact STACK.md pins for the seven v0.8 extras. Each extra must contain at
# least these strings; the local-memory onnxruntime pin is verbatim because it
# guards Intel-macOS wheel coverage.
EXPECTED_EXTRA_PINS = {
    "local-llm": ["openai>=2.40.0"],
    "local-memory": [
        "fastembed>=0.8.0",
        "onnxruntime>=1.17.0,<1.19.0",
        "sqlite-vec>=0.1.9",
    ],
    "mcp": ["mcp>=1.27.2"],
    "web": ["readability-lxml>=0.8.4.1", "httpx>=0.27.0"],
    "pdf": ["pypdf>=6.12.2"],
    "vision": ["Pillow>=10.0"],
    "research": ["horus-os[local-llm,local-memory,mcp,web,pdf,vision]"],
}

# Distribution names that must never appear in [project.dependencies] (the
# bare-install set) so `pip install horus-os` pulls zero v0.8 infrastructure.
V0_8_DISTRIBUTIONS = (
    "openai",
    "fastembed",
    "onnxruntime",
    "sqlite-vec",
    "mcp",
    "readability-lxml",
    "pypdf",
    "Pillow",
)

# The local-memory triplet that must stay out of [all] (REL-17 precedent).
LOCAL_MEMORY_DISTRIBUTIONS = ("onnxruntime", "fastembed", "sqlite-vec")


def _load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_pyproject_exists() -> None:
    assert PYPROJECT_PATH.is_file(), f"{PYPROJECT_PATH} must exist"


def test_version_matches() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    project_version = data["project"]["version"]
    assert project_version == EXPECTED_VERSION, (
        f"REL-19: pyproject [project].version must be {EXPECTED_VERSION!r}; got {project_version!r}"
    )
    assert horus_os.__version__ == EXPECTED_VERSION, (
        f"REL-19: horus_os.__version__ must be {EXPECTED_VERSION!r}; got {horus_os.__version__!r}"
    )
    assert project_version == horus_os.__version__, (
        "REL-19: pyproject version and __version__ must agree; "
        f"got {project_version!r} vs {horus_os.__version__!r}"
    )


def test_v0_8_extras_declared() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    extras = data["project"]["optional-dependencies"]
    for name, expected_pins in EXPECTED_EXTRA_PINS.items():
        assert name in extras, (
            f"REL-18: optional extra [{name}] must be declared; got {sorted(extras)}"
        )
        declared = extras[name]
        for pin in expected_pins:
            assert pin in declared, (
                f"REL-18: extra [{name}] must pin {pin!r} exactly (STACK.md); got {declared}"
            )


def test_local_memory_onnxruntime_intel_pin() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    local_memory = data["project"]["optional-dependencies"]["local-memory"]
    assert "onnxruntime>=1.17.0,<1.19.0" in local_memory, (
        "REL-18: the Intel-macOS onnxruntime pin must live verbatim in [local-memory]; "
        f"got {local_memory}"
    )


def test_research_meta_extra_is_self_referential() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    research = data["project"]["optional-dependencies"]["research"]
    assert "horus-os[local-llm,local-memory,mcp,web,pdf,vision]" in research, (
        "REL-18: [research] must be a self-referential meta-extra installing the full "
        f"v0.8 infrastructure layer; got {research}"
    )


def test_base_dependencies_stay_minimal() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    base = data["project"]["dependencies"]
    for dist in V0_8_DISTRIBUTIONS:
        assert not any(dist in entry for entry in base), (
            f"REL-19: bare install must not pull {dist!r}; it leaked into "
            f"[project.dependencies]: {base}"
        )


def test_local_memory_excluded_from_all() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    all_extra = data["project"]["optional-dependencies"]["all"]
    for dist in LOCAL_MEMORY_DISTRIBUTIONS:
        assert not any(dist in entry for entry in all_extra), (
            f"REL-18/REL-17: heavy local-memory dep {dist!r} must stay out of [all] so a "
            f"fresh .[all] install stays cross-OS clean; it leaked into [all]: {all_extra}"
        )


def test_light_v0_8_extras_aggregated_in_all() -> None:
    data = _load_pyproject(PYPROJECT_PATH)
    all_extra = data["project"]["optional-dependencies"]["all"]
    for pin in (
        "openai>=2.40.0",
        "mcp>=1.27.2",
        "readability-lxml>=0.8.4.1",
        "pypdf>=6.12.2",
        "Pillow>=10.0",
    ):
        assert pin in all_extra, (
            f"REL-18: light cross-OS-wheel v0.8 pin {pin!r} must be aggregated into [all]; "
            f"got {all_extra}"
        )
