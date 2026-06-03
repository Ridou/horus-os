---
title: "The vault"
description: "Your vault is a folder of plain markdown files that agents read from and write to. Learn how memory works, where it lives, and how the optional on-device vector search fits in."
---

The **vault** is horus-os's knowledge base: a folder of plain markdown (`.md`)
files that your agents read from and write to. It is the long-term memory of your
command center. Because it is just markdown on disk, you own it completely, you
can edit it in any editor, and you can back it up, version it, or sync it however
you like.

## Where the vault lives

The vault is the `notes/` folder inside your [data
directory](/getting-started/installation/#where-horus-os-stores-its-data):

| Platform | Default vault path |
|----------|--------------------|
| macOS | `~/Library/Application Support/horus-os/notes` |
| Linux | `~/.local/share/horus-os/notes` (or `$XDG_DATA_HOME/horus-os/notes`) |
| Windows | `%APPDATA%\horus-os\notes` |

You can point the vault somewhere else with the `[notes]` section of
`config.toml`:

```toml
[notes]
notes_dir = "/Users/you/Documents/horus-vault"
```

This is the key setting for editor integration: set `notes_dir` to a folder you
already keep notes in (for example an existing Obsidian vault) and horus-os and
your editor share the same files. See [Editing your
vault](/guides/editing-your-vault/) for the full walkthrough.

## How agents use the vault

Agents read and write the vault through a small set of tools:

- `search_notes` finds notes by keyword (case-insensitive substring, ranked by
  hit count). When on-device vector memory is enabled, results are merged with
  semantic matches.
- `read_note` returns the full text of one note.
- `list_notes` lists every note in the vault.
- `create_note` writes a new note.
- `append_note` adds to the end of an existing note.

Notes are addressed by their path relative to the vault root, so an agent can
organize work into folders, for example `projects/website.md` or
`research/retrieval.md`.

## Writes are append-only and audited

horus-os never silently overwrites your notes. Writes are **append-only**:
`create_note` makes a new file and `append_note` adds to the end of an existing
one. Every write is recorded in an audit log (the `note_writes` table in
`horus.sqlite`) with the operation, the path, and the content, so you can review
exactly what each agent wrote and when from the dashboard.

> [!NOTE]
> Because horus-os only ever appends, your own edits are safe. You remain the
> only writer that can change or delete existing text in a note.

## Titles and structure

A note's title is the first level-one heading (`# Title`) in the file. If a note
has no heading, horus-os falls back to the filename. A good habit is to start
each note with a clear `# Title` line and keep one topic per note.

There is no required structure beyond that. The vault is a flat-or-nested folder
of markdown; horus-os reads every `.md` file it finds, at any depth.

## Optional: on-device vector search

By default, vault search is keyword-based and runs with zero configuration. You
can additionally enable **on-device vector memory** so agents can find notes by
meaning, not just exact words. It runs entirely on your machine with a local
embedding model, so nothing is sent to a cloud service.

Vector memory is **off by default** and ships as an optional extra:

```bash
pip install 'horus-os[local-memory]'
horus-os memory download-model
```

Once the model is downloaded, enable it in `config.toml`:

```toml
[memory]
vector_enabled = true
```

The vector index is a rebuildable cache stored separately in
`vectors.sqlite`, never in your authoritative `horus.sqlite`. If you edit notes
in bulk outside horus-os, rebuild the index with:

```bash
horus-os memory reindex
```

Keyword search always reflects the current files on disk, so it works even
before you reindex. See [Autonomous research](/guides/autonomous-research/) for
how the Researcher writes its findings back into the vault as cited reports.

## Next steps

- [Editing your vault](/guides/editing-your-vault/) shows how to use Obsidian,
  VS Code, or any editor alongside horus-os.
- [The agent team](/concepts/agent-team/) explains which agents read and write
  the vault.
