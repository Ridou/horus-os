"""v0.7 starter-team seeding: a fresh init bootstraps agents, notes, a trace.

Drives ``horus-os init`` against a temp data dir and asserts the seeded
content lands correctly:
  - The five starter agents exist with the right colors and soul_path.
  - Each agent's SOUL.md exists in the notes dir with the placeholder
    substituted (no literal {{USER_NAME}}) and carries the required
    frontmatter keys plus the five canonical H2 sections in order.
  - Around twelve example vault notes exist.
  - Exactly one demo trace exists.
"""

from __future__ import annotations

import io
from pathlib import Path

from horus_os.__main__ import main
from horus_os.cli.init_cmd import _seed_starter_content
from horus_os.config import Config
from horus_os.seed import SOUL_SECTIONS, STARTER_TEAM
from horus_os.storage import Database

REQUIRED_FRONTMATTER_KEYS = ("name", "description", "agent", "plugin", "updated")


def _init(tmp_path: Path) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(["init", "--data-dir", str(tmp_path)], stdout=stdout, stderr=stderr)
    assert code == 0, stderr.getvalue()


def _frontmatter_block(text: str) -> str:
    assert text.startswith("---\n"), "SOUL.md must open with a YAML frontmatter fence"
    end = text.index("\n---", 4)
    return text[4:end]


def test_starter_agents_seeded_with_color_and_soul_path(tmp_path: Path) -> None:
    _init(tmp_path)
    db = Database(tmp_path / "horus.sqlite")
    by_name = {entry["name"]: entry for entry in STARTER_TEAM}

    for name, entry in by_name.items():
        profile = db.load_profile(name)
        assert profile is not None, f"{name} was not seeded"
        assert profile.color == entry["color"]
        assert profile.soul_path == f"agents/{name}/SOUL.md"
        assert profile.description == entry["description"]
        # default_model is intentionally unset so the profile inherits the
        # configured provider/model.
        assert profile.default_model is None


def test_soul_files_written_with_placeholder_substituted(tmp_path: Path) -> None:
    _init(tmp_path)
    notes_dir = tmp_path / "notes"
    for entry in STARTER_TEAM:
        name = entry["name"]
        soul = notes_dir / "agents" / name / "SOUL.md"
        assert soul.exists(), f"SOUL.md missing for {name}"
        text = soul.read_text(encoding="utf-8")
        assert "{{USER_NAME}}" not in text


def test_soul_files_have_frontmatter_and_sections_in_order(tmp_path: Path) -> None:
    _init(tmp_path)
    notes_dir = tmp_path / "notes"
    for entry in STARTER_TEAM:
        name = entry["name"]
        text = (notes_dir / "agents" / name / "SOUL.md").read_text(encoding="utf-8")

        front = _frontmatter_block(text)
        for key in REQUIRED_FRONTMATTER_KEYS:
            assert f"{key}:" in front, f"{name} SOUL.md missing frontmatter key {key!r}"

        # The five canonical H2 sections appear in the documented order.
        positions = [text.find(section) for section in SOUL_SECTIONS]
        assert all(pos != -1 for pos in positions), f"{name} SOUL.md missing a section"
        assert positions == sorted(positions), f"{name} SOUL.md sections out of order"


def test_example_vault_notes_seeded(tmp_path: Path) -> None:
    _init(tmp_path)
    notes_dir = tmp_path / "notes"
    top_level_notes = list(notes_dir.glob("*.md"))
    # Around a dozen example notes ship in the vault.
    assert 10 <= len(top_level_notes) <= 14
    assert (notes_dir / "welcome-to-horus-os.md").exists()


def test_exactly_one_demo_trace(tmp_path: Path) -> None:
    _init(tmp_path)
    db = Database(tmp_path / "horus.sqlite")
    traces = db.list_traces()
    assert len(traces) == 1
    trace = traces[0]
    assert trace.agent_profile_name == "Coordinator"
    assert trace.provider == "example"


def test_demo_tasks_seeded(tmp_path: Path) -> None:
    _init(tmp_path)
    db = Database(tmp_path / "horus.sqlite")
    tasks = db.list_tasks()
    assert len(tasks) == 5, f"expected 5 demo tasks, got {len(tasks)}"
    statuses = {t.status for t in tasks}
    assert statuses == {"pending", "running", "completed", "error"}, (
        f"unexpected statuses: {statuses}"
    )
    agent_names = {t.agent_profile_name for t in tasks}
    assert agent_names == {"Coordinator", "Engineer", "Researcher", "Writer", "Operator"}
    assert all(t.is_demo_seed for t in tasks)


def test_demo_tasks_seed_is_idempotent(tmp_path: Path) -> None:
    _init(tmp_path)
    db = Database(tmp_path / "horus.sqlite")
    cfg = Config.with_defaults(tmp_path)
    _seed_starter_content(cfg)
    tasks_after = db.list_tasks()
    assert len(tasks_after) == 5, (
        f"second _seed_starter_content call duplicated tasks: got {len(tasks_after)}"
    )
