---
title: "Autonomous research"
description: "Run multi-agent Deep Research that gathers web sources, validates every citation, and writes a cited markdown report into your vault."
---

## What Deep Research does

Deep Research is the autonomous, multi-agent research capability in horus-os. You hand it a question, it plans a set of subtopics, dispatches a small team of specialist agents to search the web and read the pages they find, and then it synthesizes a structured markdown report with numbered citations. The finished report is written into your vault under `research/<task_id>.md`, so every run leaves a durable, reviewable artifact alongside the rest of your notes.

Three guarantees define a run:

- **Hard budget caps.** A single shared iteration budget bounds the whole delegation tree, and a source registry caps the number of distinct pages fetched. Neither can be silently exceeded.
- **Source de-duplication.** Every fetched page funnels through a registry that keys on a normalized URL, so the same source is never counted or cited twice.
- **Zero hallucinated citations.** As the report renders, every cited URL is validated against the set of pages the team actually fetched this session. A citation that points at a URL nobody fetched is removed from the prose and recorded under a `## Flagged citations` block, so a fabricated citation never survives into the body.

> [!NOTE]
> Deep Research is exposed through the dashboard and the HTTP API, not a standalone CLI command. Start the dashboard with `horus-os serve` and use the research surface there. The routes are loopback-only: a non-local client cannot start or cancel a run.

## The research team

A run is executed by a four-role agent team. Only the coordinator can delegate; the specialists cannot, which makes a recursive research run impossible.

| Role | Job |
| --- | --- |
| Research Coordinator | Plans subtopics, delegates to the specialists, and synthesizes the cited report. The only role permitted to delegate. |
| Research Searcher | Runs focused web searches and surfaces candidate result URLs and titles. Does not fetch full pages. |
| Research Fetcher | Reads each candidate page (including PDFs and images) and records the key facts plus the exact source URL into notes. |
| Research Synthesizer | Reads the gathered notes and drafts the report body, attaching a citation to every factual claim. |

The team profiles are persisted to your database on the first run and upserted on every run after, so they stay in sync without duplicating rows. They appear alongside your other agents. See [Your agent team](/concepts/agent-team/) for how profiles work in general.

## How a run flows

1. **Plan.** The coordinator splits the question into a few focused subtopics. The plan step runs no search and no fetch, so the dashboard can show you the plan and let you cancel before any tokens are spent.
2. **Confirm.** You confirm the plan to start the run. Without an explicit confirm, nothing executes.
3. **Search and fetch.** The Searcher finds candidate URLs; the Fetcher reads the pages and writes their key facts to notes, recording the source URL for each. Every fetched URL is registered (de-duplicated by normalized URL).
4. **Synthesize.** The Synthesizer drafts the report body with inline citations; the coordinator assembles the final report.
5. **Write the report.** The cited markdown is written to `research/<task_id>.md` in your vault through the audited note-write path, the generating trace is recorded, and the task is marked complete.

Throughout a run the dashboard shows live progress: the current phase, the number of sources found, the iterations used, and the iteration budget.

### Status outcomes

A run always leaves a trace row, even when it does not finish cleanly.

- **success** : the run completed and the full report was written.
- **partial** : the source cap was reached mid-run. The run degrades gracefully to a partial report built from the sources gathered so far, and the report title is suffixed with `(partial)`.
- **cancelled** : you cancelled the run, either at the plan stage or mid-run. The orchestrator polls the cancel flag between delegation turns and halts before the next turn.
- **error** : an unexpected failure. A trace row with the error message is still recorded.

## The report and citations

The report is structured markdown with a title, a findings body, and a numbered `## References` list. Each reference entry shows the source title (or URL when no title was captured), the URL, and the date the page was fetched.

Inline citations are validated, not trusted. The synthesis prompt instructs the model to cite only URLs the team actually fetched in this session, and the report builder enforces it. Every run, successful or partial, renders under the same flag policy: a citation pointing at a URL nobody fetched is stripped from the report body and listed under a `## Flagged citations` block. This never aborts a run, and it guarantees that a fabricated citation never reaches the prose, while a stray marker can never crash the render.

Because the report lands in your vault as a normal markdown file, you can read, edit, search, and link it like any other note. See [The vault](/concepts/the-vault/) for how notes are stored and [Editing your vault](/guides/editing-your-vault/) for working with them.

> [!TIP]
> The report is written through the audited note path, so the write appears in your note-write audit trail and the task's trace resolves under the same id you see in the trace viewer. See [Traces and observability](/concepts/traces-and-observability/).

## Setup: bring your own web search

Deep Research needs a way to reach the web, and that is opt-in. There is no built-in search provider and no bundled crawler. Web access ships in the `web` extra and is off by default.

Install the web extra (or the `research` meta-extra, which pulls the full local-first and web stack at once):

```bash
pip install 'horus-os[web]'
# or the full Deep Research stack:
pip install 'horus-os[research]'
```

The `research` extra installs `local-llm`, `local-memory`, `mcp`, `web`, `pdf`, and `vision` together, which gives you web search, PDF and image reading, and the local-first stack in one command.

### Configure a search provider

The `web_search` tool is absent from the agent registry until you configure a provider. Add a `[tools.web_search]` block to `config.toml` in your data directory:

```toml
[tools.web_search]
provider = "searxng"                # one of: searxng, brave, tavily
base_url = "http://localhost:8888"  # required for searxng (your instance)
```

The three supported providers:

- **searxng** (default and recommended): a self-hosted SearXNG instance. Set `base_url` to your instance URL. No API key.
- **brave**: the Brave Search API. `base_url` is optional and defaults to the public endpoint. Provide the key via the `HORUS_OS_WEB_SEARCH_KEY` environment variable.
- **tavily**: the Tavily API. `base_url` is optional and defaults to the public endpoint. Provide the key via `HORUS_OS_WEB_SEARCH_KEY`.

The API key is read from `HORUS_OS_WEB_SEARCH_KEY` at runtime and is never written to `config.toml`:

```bash
export HORUS_OS_WEB_SEARCH_KEY=your-web-search-key
```

> [!IMPORTANT]
> With no `[tools.web_search]` block, the registry has no `web_search` entry at all (default-deny), so the research team cannot search and a run produces no sources. Configure a provider before running Deep Research.

For the full web access model, including optional browsing and screenshots via the Playwright MCP server and the SSRF protections on the fetch path, see [Web access](/integrations/web-access/).

## Budget caps

Deep Research is bounded by two hard caps from the `[research]` section of `config.toml`. Both are real limits the coordinator can never silently exceed:

```toml
[research]
max_sources = 10
max_iterations = 5
```

- `max_sources` caps how many distinct URLs the source registry will accept. Registering a new source past this cap stops the run early and degrades it to a partial report. Re-registering an already-known URL never trips the cap, since it adds no new entry.
- `max_iterations` sizes the shared iteration budget that bounds the entire delegation tree across all four roles.

The defaults are 10 sources and 5 iterations. The `[research]` block is only written to `config.toml` when your caps differ from those defaults, so a config without a `[research]` section is running at the defaults.

> [!WARNING]
> Raising these caps increases token usage and run time, and a deeper run can take noticeably longer before it produces a report. Increase them deliberately.

## See also

- [Web access](/integrations/web-access/) : configure search, browsing, and the security posture.
- [The vault](/concepts/the-vault/) : where reports are stored and how notes work.
- [Traces and observability](/concepts/traces-and-observability/) : inspect what a run fetched and synthesized.
- [Configuration](/reference/configuration/) : the full `config.toml` reference.
