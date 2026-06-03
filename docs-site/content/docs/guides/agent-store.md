---
title: "Agent store"
description: "Install ready-made agent bundles from the store, or build your own from scratch. Installed agents join your team and show up in chat."
---

## What the agent store is

An agent bundle is a portable, installable agent definition: a persona (the system prompt), a recommended model, the tools the agent wants, and the adapters it pairs with. The store ships a few featured bundles you can install in one click, and a form for building a custom agent from scratch.

Installing a bundle creates an agent profile in your local database. From that point the agent is on your team and available in [Chat](/getting-started/chat/), just like any agent you built by hand. Everything in the store is generic and owns no personal data; the featured personas are reusable archetypes, not a port of anyone's private assistant.

Open the store with `horus-os serve` (default http://127.0.0.1:8765) and go to the Agent store page. It has two tabs: **Browse** for the featured bundles and **Create** for building your own.

> [!NOTE]
> Installing and creating both need a running local backend. In the hosted demo both are disabled. Run horus-os locally to add agents to your team.

## Featured bundles

The store ships three featured bundles. Each card shows the agent's role, a short description, its recommended tools, and the adapters it pairs with.

### Atlas, the travel planner

Atlas plans trips, finds places worth your time, and works out travel logistics: transit, entry rules, local payment norms, and weather. It builds day plans that respect travel time and energy, and it is told to look things up with its tools rather than guess, and to never invent an address, a price, an opening time, or a booking detail.

Atlas recommends the `web_search`, `list_calendar_events_today`, `create_calendar_event`, `search_notes`, and `create_note` tools, and pairs with the calendar and [voice](/integrations/voice/) adapters. Enable the `[web]` extra for web search and the [Calendar](/integrations/calendar/) adapter for the calendar tools. Pair it with the voice adapter to let Atlas place reservation calls.

### Vitriol, the wellness researcher

Vitriol helps you understand health and integrative-medicine topics by gathering evidence and explaining it plainly. It is not a doctor and does not give medical advice, diagnose, or prescribe. The persona is written to open with that framing whenever a question edges toward a personal medical decision, to steer you toward a qualified professional for anything diagnostic or urgent, to prefer and cite primary sources, and to never fabricate a citation or a study. Education, not treatment.

Vitriol recommends the `web_search`, `search_notes`, and `create_note` tools, and pairs with the web adapter. Enable the `[web]` extra for web search.

### Sol, the reflective companion

Sol is a reflective conversational companion and journaling partner. It holds space for you to think out loud: it listens, asks open questions, reflects back what it hears, and offers gentle journaling prompts. It is not a therapist and makes no clinical claims; if someone is in crisis, it encourages them to reach real human support. When a conversation lands on something worth keeping, Sol offers to save a short reflection to your notes.

Sol recommends the `search_notes`, `create_note`, and `append_note` tools and needs no extra services, since it journals to your notes store.

> [!NOTE]
> Recommended tools and adapters are advisory. Installing a bundle sets the agent's allowed tools to its recommended list, but the tools only do anything once you enable the matching pip extras and adapters. Each bundle's setup notes spell out which extras to turn on.

## Installing a bundle

On the Browse tab, click **Install** on a bundle card. The dashboard posts to `POST /api/store/{slug}/install`, which creates an agent profile from the bundle. Once installed, the card flips to an **Installed** badge, and the new agent appears on your team and in the chat agent picker.

A bundle installs under its display name, which is the unique profile key. If a profile with that name already exists, install returns a conflict and the agent is not duplicated.

> [!TIP]
> You can list the catalog from the API directly. `GET /api/store` returns every bundle flagged with its installed state, and `GET /api/store/{slug}` returns one bundle in full, including its persona.

## Building a custom agent

The **Create** tab is a form for defining your own agent. Fill in:

- **Name**: the display name and unique key for the agent.
- **Role / description**: a one-line summary of what the agent does.
- **Accent color**: a hex color for the agent's dot on the team view.
- **Default model** (optional): leave blank to inherit the configured model.
- **Tools** (optional): a comma-separated list of tool names the agent is allowed to call.
- **System prompt**: the persona. This and the name are the only required fields.

Submitting posts to `POST /api/agents` to create the profile. On success the new agent is on your team and available in chat right away.

## Exporting an agent to share

Any installed agent can be exported back into a shareable bundle. Call `GET /api/agents/{name}/export` and you get a bundle dict, the inverse of install, that you can hand to someone else or publish. The export carries the agent's persona, recommended tools, color, and description, so the recipient can recreate the same agent.

## Next steps

- [Chat](/getting-started/chat/): talk to an installed agent and watch its replies stream.
- [The agent team](/concepts/agent-team/): how your team is structured and how work is delegated.
- [Calendar](/integrations/calendar/): the adapter behind Atlas's calendar tools.
- [Voice](/integrations/voice/): the adapter that lets Atlas place reservation calls.
