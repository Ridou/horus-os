---
phase: 08-web-chat-and-dashboard
plan: "01"
subsystem: dashboard-ui
tags: [dashboard, html, vanilla-js, serve, uvicorn]

# Dependency graph
requires:
  - phase: "08-00"
provides:
  - "Single-page HTML dashboard at /"
  - "Functional horus-os serve subcommand using uvicorn"
  - "package-data wiring so the static HTML ships in wheels"

# Tech tracking
tech-stack:
  added: []  # uses extras already declared in 08-00
  patterns:
    - "Single-file dashboard: HTML + CSS + JS in one file with no build step."
    - "Tab-based section navigation via show/hide and a small DOM helper, no framework."
    - "Fetch helpers wrap /api/* with consistent error rendering."
    - "Lazy uvicorn import inside the serve subcommand keeps the [dashboard] extra truly optional."

key-files:
  created:
    - "src/horus_os/server/static/index.html, 152 lines, full dashboard"
    - "tests/test_server_static.py, 19 lines, 1 test"
  modified:
    - "src/horus_os/server/api.py, mount StaticFiles + serve index.html at /"
    - "src/horus_os/cli/serve_cmd.py, real uvicorn invocation + missing-extra error path"
    - "src/horus_os/__main__.py, --host / --port / --data-dir flags on serve"
    - "tests/test_cli_serve.py, replaced stub test with uvicorn-mock + missing-extra tests"
    - "pyproject.toml, package-data so static/ ships in wheels"

key-decisions:
  - "Single-file dashboard for v0.1. No Node, no npm, no build step. The maintainer types `pip install` and gets a working dashboard."
  - "Tab UI in vanilla JS. The full v0.1 UX is three views (chat, traces, writes); a framework would be overkill. A v0.x Next.js phase can replace this if richer UX is needed."
  - "Default port 8765. Avoids the common 8000/8080 collisions on developer machines."
  - "Dark theme only. The maintainer's other surfaces are dark; matching it keeps the project visually consistent."

requirements-completed:
  - DASH-01  # dashboard lists recent runs and their traces
  - DASH-02  # dashboard hosts a chat surface that sends prompts to the runtime
  - DASH-03  # dashboard renders each trace with input, output, tool log

known-limitations:
  - "No live streaming of agent responses. The page waits for the full response. Streaming lands when the underlying loop gains an async/streaming variant."
  - "No keyboard shortcuts. Send is button-only."
  - "No pagination on traces/writes lists. Limit 50, no scroll-to-load."
  - "No filter/search on traces. Future phase."

# Metrics
duration: 32m
completed: 2026-05-23
test-count: 2 net (165 cumulative)
new-cli-subcommands-upgraded: 1 (serve)
