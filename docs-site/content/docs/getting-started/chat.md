---
title: "Chat"
description: "Talk to your agents from the dashboard. The /chat surface streams replies live, picks an agent, shows tool calls inline, and links every turn to its trace."
---

## What the chat surface is

The dashboard ships a `/chat` page that lets you talk to your agent team in a browser. You type a prompt, pick which agent answers (or use the default), and the reply streams back token by token. Any tools the model calls appear inline as chips, and every assistant turn links to the trace it produced so you can inspect exactly what ran.

Chat is part of the local dashboard. Open it with `horus-os serve` (default http://127.0.0.1:8765) and go to the Chat page. Like the rest of the dashboard, it talks only to your local backend; there is no hosted service behind it.

> [!NOTE]
> Chat needs a running local backend. In the hosted demo the page is read-only, and the composer is disabled. Run horus-os locally to talk to your agents.

## Picking an agent

The page header has an **Agent** picker. Leave it on **Default** to use the configured default provider and model, or select one of your team members to route the prompt through that agent's persona, model, and tool set.

The picker is populated from your installed agents, so anything on your team, including agents you installed from the [agent store](/guides/agent-store/) or built yourself, shows up here. The picker is disabled while a reply is streaming; finish or stop the current turn before switching agents.

## Sending a prompt and streaming the reply

Type into the composer and press **Enter** to send, or **Shift+Enter** for a new line. The send button is disabled until you have typed something.

Under the hood the page posts to `POST /api/chat/stream` and reads the reply as Server-Sent Events. As the response arrives:

- **Tokens** append to the assistant message in place, so you watch the answer build word by word.
- A **Thinking** indicator shows while the assistant turn is still empty.
- When the run finishes, the turn is tagged with its trace id.

To stop a reply mid-stream, click **Stop**. This aborts the in-flight request; the partial answer stays on screen.

> [!TIP]
> You can deep-link a prompt with `/chat?q=your+prompt`. The page prefills the composer and auto-sends that one prompt, which is how the home quick-prompt and the command palette open a conversation. Auto-send is skipped in demo mode.

## Tool-call chips

When the model invokes a tool during a turn, the tool name appears as a small chip above that assistant message, marked with a wrench icon. Each tool the model calls adds another chip, in the order they ran, so you can see at a glance which tools the answer leaned on, for example a web search or a calendar lookup.

The chips show the tool name. For the full input and output of each call, open the trace.

## Per-turn trace links

Every completed assistant turn carries a **View trace** link. It opens the [Traces](/concepts/traces-and-observability/) explorer focused on that run's trace id, where you can read the full tool inputs and outputs, the provider and model, token usage, and latency.

This is the main reason chat is more than a chat box: nothing the model does is hidden. Each reply is a recorded trace you can audit after the fact.

## When a turn fails

If the backend is unreachable, or the run errors mid-stream, the assistant turn shows a short error message in place of the answer. A common cause is that no local horus-os server is running; start one with `horus-os serve`. Provider-side errors (for example a missing API key) surface here too, and the failed run is still recorded as a trace with an `error` status.

## Next steps

- [Quickstart](/getting-started/quickstart/): install, initialize, and open the dashboard.
- [Using the dashboard](/guides/dashboard/): a tour of every dashboard page.
- [Traces and observability](/concepts/traces-and-observability/): how each turn is recorded and what the trace explorer shows.
- [Agent store](/guides/agent-store/): install ready-made agents or build your own, then chat with them.
