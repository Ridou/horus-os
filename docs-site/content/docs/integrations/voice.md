---
title: "Voice"
description: "The optional voice adapter lets an agent place an outbound phone call to a venue to request or confirm a reservation, through Twilio, with an ask-first safety rail."
---

## Overview

The Voice adapter lets an agent place an outbound phone call to a venue to request or confirm a reservation. Like the [Calendar](/integrations/calendar/) adapter it is a tool provider: it registers agent-callable tools onto the horus-os tool registry rather than routing inbound events. Your agent can decide to call a restaurant, the adapter dials out through Twilio, the call is recorded, the outcome is classified from the transcript, and a confirmed booking can be written to your calendar.

Two tools ship with the adapter:

- `request_reservation_call(venue_name, to_number, reservation_datetime, ...)` places one outbound call. It is registered only when the adapter is fully configured and outbound calling is armed.
- `get_reservation_calls(status="")` lists recorded calls and their outcomes.

> [!IMPORTANT]
> Calling is off by default. The `request_reservation_call` tool refuses to dial until you explicitly arm calling with `HORUS_OS_VOICE_CALLS_ALLOWED=true`. This ask-first rail is re-checked at call time, so an agent can never autonomously place a real phone call unless you have armed it.

## Install the optional extra

```bash
pip install 'horus-os[voice]'
```

This pulls in the `twilio` REST client. Without it the adapter loads cleanly but `bind` marks itself in error and registers no tools.

## What you need

- A Twilio account and a voice-capable phone number. Set `HORUS_OS_TWILIO_ACCOUNT_SID`, `HORUS_OS_TWILIO_AUTH_TOKEN`, and `HORUS_OS_TWILIO_FROM_NUMBER` (the caller id, in E.164). All three are required for the tools to register.
- A public URL Twilio can reach to fetch call instructions and open the audio stream, set as `HORUS_OS_VOICE_PUBLIC_BASE_URL`. A tunnel works in local development.
- The ask-first flag, `HORUS_OS_VOICE_CALLS_ALLOWED=true`, set deliberately when you are ready to place real calls.

## The two safety gates

Two gates apply, both re-checked at call time:

1. `HORUS_OS_VOICE_CALLS_ALLOWED` must equal `true` before any call is placed.
2. A reservation is written to the calendar only when the call outcome classifies as `confirmed` AND the Calendar adapter's `create_calendar_event` tool is registered (which itself requires `HORUS_OS_CALENDAR_WRITE_ALLOWED=true`).

## Recording and classifying a call

When a call ends, post the transcript to `POST /api/adapters/voice/calls/{record_id}/complete`. The adapter classifies the transcript into `confirmed`, `declined`, `callback`, or `unclear` with a deterministic keyword scan, so the result is reproducible and testable without a model. You can override the classification by passing an explicit `outcome` field, which is useful when an upstream model has already judged the call.

On a confirmed outcome with the Calendar adapter's `create_calendar_event` tool available, the reservation is added to your calendar; if `HORUS_OS_VOICE_NOTIFY_WEBHOOK` is set, a short notification is posted there too. Both side effects are best-effort: a missing calendar tool or a failed notification never turns a confirmed call into an error.

## The live audio bridge

Placing the call, recording it, classifying the outcome, and the calendar and notify side effects all work with the steps above and are tested without any live telephony. The live, two-way conversation, where the agent actually talks to whoever answers, runs over the `/api/adapters/voice/media` websocket, which bridges Twilio Media Streams to a realtime voice model. That piece is deployment-bound: it needs the public URL plus a realtime voice provider configured with your own key.

## Full setup guide

This page is a summary. The deeper walkthrough, including the Twilio setup, exposing a public URL, the TwiML route, completing a call, the calendar write-through, and the full table of environment variables and endpoints, lives in the adapter guide at `docs/adapters/VOICE.md`.

## See also

- [Integrations overview](/integrations/overview/)
- [Calendar integration](/integrations/calendar/): the adapter that writes confirmed reservations to your calendar.
- [Agent store](/guides/agent-store/): the Atlas travel planner pairs with this adapter to place reservation calls.
