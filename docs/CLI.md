# horus-os CLI reference

Every subcommand exposes `run_<name>(args, *, stdout, stderr) -> int`.
Tests pass StringIO buffers and assert on captured text. All numeric
output respects the precision contract documented under `horus-os
usage` below.

## Command overview

| Command | What it does |
| ------- | ------------ |
| `init` | Initialize a new horus-os installation (seeds a starter team, an example vault, and a demo trace; `--interactive` walks through API keys). |
| `run` | Run a single agent prompt with the configured tools (streams by default; `--no-stream` buffers). |
| `serve` | Start the local web dashboard and JSON API on `127.0.0.1:8765`. |
| `traces` | List recent agent traces. |
| `agents` | Manage agent profiles. |
| `schedule` | Manage recurring agent schedules (cron). |
| `service` | Install and manage the always-on service (systemd, launchd, NSSM). |
| `skills` | List and show discoverable skills. |
| `plugins` | Manage installed plugins (install, list, info, enable, disable, grant, revoke). |
| `usage` | Print a usage report: cost, latency, tool reliability. Documented in detail below. |
| `doctor` | Check integration health and configuration (`--service`, `--supabase`, `--local`, `--memory`, `--mcp`). |
| `memory` | Manage on-device vector memory (model download, index status). |

Run `horus-os <command> --help` for per-command flags. The complete
per-command reference lives on the documentation site at
[docs.horus-demo.com](https://docs.horus-demo.com). The rest of this
file documents the `usage` subcommand's output contract.

## horus-os usage

Print a usage report (cost, latency, tool reliability) over a window
in JSON, CSV, or a table.

```
horus-os usage [--data-dir PATH] [--since WINDOW] [--format FORMAT] [--by SLICE]
```

### Flags

| Flag         | Default | Meaning                                                                        |
| ------------ | ------- | ------------------------------------------------------------------------------ |
| `--data-dir` | platform | Override the data directory containing the SQLite database.                   |
| `--since`    | `7d`    | Window. Accepts `24h`, `7d`, `30d`, and any positive `Nh` or `Nd` form.        |
| `--format`   | `table` | Output shape: `json`, `csv`, or `table`.                                       |
| `--by`       | `agent` | Slice the report: `agent`, `tool`, or `model`.                                 |

Invalid windows exit non-zero with `invalid window: ...` on stderr.
A missing database exits with `No database at PATH. Run` `horus-os init`
on stderr; run `horus-os init` first.

### JSON output schema

Every JSON response carries the envelope shape:

```
{
  "by":    "agent" | "tool" | "model",
  "since": "<the original --since arg verbatim>",
  "rows":  [ ...slice-specific row dicts... ]
}
```

`rows` is an empty list when the window contains no matching data.
`sort_keys=True` keeps the output diff-stable so consumer scripts and
test fixtures can pin against an exact byte representation.

Per-row shape for `--by agent` (mirrors `cost_by_agent` in
`horus_os.observability.queries`):

| Field                                | Type         | Notes                                    |
| ------------------------------------ | ------------ | ---------------------------------------- |
| `agent`                              | string       | Agent profile name.                      |
| `total_cost_usd`                     | float        | SUM rounded to 6 decimals.               |
| `total_input_tokens`                 | integer      | SUM across in-window traces.             |
| `total_output_tokens`                | integer      | SUM across in-window traces.             |
| `total_cache_read_input_tokens`      | integer      | SUM from llm_calls.                      |
| `total_cache_creation_input_tokens`  | integer      | SUM from llm_calls.                      |
| `run_count`                          | integer      | Every in-window trace row.               |
| `uncosted_runs`                      | integer      | Rows with `total_cost_usd IS NULL`.      |

Per-row shape for `--by tool` (mirrors `tool_reliability`):

| Field                       | Type           | Notes                                                  |
| --------------------------- | -------------- | ------------------------------------------------------ |
| `tool_name`                 | string         | Tool registered name.                                  |
| `call_count`                | integer        | Every in-window invocation.                            |
| `success_count`             | integer        | Status in (`success`, `retry_then_success`).           |
| `error_count`               | integer        | Status = `error`.                                      |
| `retry_then_success_count`  | integer        | Surfaced separately from success.                      |
| `expected_no_result_count`  | integer        | Excluded from `success_rate` denominator.              |
| `success_rate`              | float or null  | success / (success + error) rounded to 4dp.            |
| `last_error_type`           | string or null | Exception class name only, never error text content.   |
| `last_error_at`             | string or null | ISO timestamp of the most recent error row.            |

Per-row shape for `--by model` (mirrors `cost_by_model`):

| Field                                | Type    | Notes                                       |
| ------------------------------------ | ------- | ------------------------------------------- |
| `model`                              | string  | The `llm_calls.model` value.                |
| `provider`                           | string  | `anthropic` or `gemini`.                    |
| `total_cost_usd`                     | float   | SUM rounded to 6 decimals.                  |
| `total_input_tokens`                 | integer | SUM across in-window llm_calls.             |
| `total_output_tokens`                | integer | SUM across in-window llm_calls.             |
| `total_cache_read_input_tokens`      | integer | SUM across in-window llm_calls.             |
| `total_cache_creation_input_tokens`  | integer | SUM across in-window llm_calls.             |
| `call_count`                         | integer | Every in-window llm_calls row.              |
| `uncosted_calls`                     | integer | Rows where `cost_usd IS NULL`.              |

The matching HTTP route `/api/observability/cost-by-model?since=<window>`
returns the SAME row shape under a `{"models": [...]}` envelope. CLI
`--by model --format json` output and the HTTP route body are
byte-for-byte identical over the same window where data overlaps
(USAGE-03 contract; pinned by `tests/test_cli_usage.py`).

### Precision contract

Costs round to 6 decimal places via Python's `round(value, 6)` BEFORE
JSON serialization. Durations cast to integer ms. The same numeric
values appear across `--format json|csv|table`. The 6-decimal rounding
eliminates the float-precision noise that breaks `jq` and `column`
pipes (for example, `0.04200000000000001` becomes `0.042`).

The canonical PRICE-02 cost is hand-derived from the bundled
`pricing.json`:

```
claude-sonnet-4-6 with 1000 input + 200 output + 500 cache_read
-> (1000 * 3 + 200 * 15 + 500 * 0.30) / 1_000_000
-> 0.006150
```

That value is the load-bearing fixture cost pinned by the schema test;
any drift from `0.006150` in either the JSON, CSV, or table output for
this seed indicates a regression in the rounding contract.

### Example

```json
{
  "by": "agent",
  "rows": [
    {
      "agent": "default",
      "run_count": 1,
      "total_cache_creation_input_tokens": 0,
      "total_cache_read_input_tokens": 500,
      "total_cost_usd": 0.006150,
      "total_input_tokens": 1000,
      "total_output_tokens": 200,
      "uncosted_runs": 0
    }
  ],
  "since": "7d"
}
```
