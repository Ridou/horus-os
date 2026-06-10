# Voice / reservations adapter

The Voice adapter lets an agent place an outbound phone call to a
venue to request or confirm a reservation. Like the Calendar
adapter it is a tool provider: it registers agent-callable tools
onto the horus-os tool registry rather than routing inbound
events. Your agent can decide to call a restaurant, the adapter
dials out through Twilio, and the outcome is recorded and (on a
confirmed booking) written to your calendar.

Two tools ship:

- `request_reservation_call(venue_name, to_number, reservation_datetime, ...)`
  places one outbound call. Registered when the adapter binds
  successfully (the `[voice]` extra installed and the three
  `HORUS_OS_TWILIO_*` vars set); the tool refuses to dial until
  outbound calling is armed via `HORUS_OS_VOICE_CALLS_ALLOWED`.
- `get_reservation_calls(status="")` lists recorded calls and
  their outcomes.

Two safety gates apply, both re-checked at call time:

1. `HORUS_OS_VOICE_CALLS_ALLOWED` must equal `true` before any
   call is placed. This is the ask-first rail: an agent can never
   autonomously dial out unless you have armed calling.
2. A reservation is only written to the calendar when the call
   outcome classifies as `confirmed` AND the Calendar adapter's
   `create_calendar_event` tool is registered.

## 1. Install the optional extra

```
pip install 'horus-os[voice]'
```

This pulls in the `twilio` REST client. Without it the adapter
loads cleanly but `bind` marks itself in error and registers no
tools.

## 2. Get a Twilio account and number

Create an account at https://www.twilio.com and buy a
voice-capable phone number. From the Twilio console note your
Account SID, your Auth Token, and the number you bought (the
caller id). Set them as environment variables:

```
export HORUS_OS_TWILIO_ACCOUNT_SID=ACxxxxxxxx
export HORUS_OS_TWILIO_AUTH_TOKEN=your-auth-token
export HORUS_OS_TWILIO_FROM_NUMBER=+14155550000
```

With these three set, the adapter binds and registers its tools.
Until you arm calling (step 4) the call tool refuses to dial.

## 3. Expose a public URL

Twilio fetches call instructions (TwiML) over HTTP and opens the
two-way audio stream over a websocket, so it needs a public URL
it can reach. In local development a tunnel works well:

```
# example with cloudflared
cloudflared tunnel --url http://localhost:8765
```

Point the adapter at the public origin:

```
export HORUS_OS_VOICE_PUBLIC_BASE_URL=https://your-tunnel.example
```

The adapter serves `GET /api/adapters/voice/twiml`, which returns
TwiML that connects the answered call to the media stream at
`wss://<public-base>/api/adapters/voice/media`.

## 4. Arm outbound calling (ask-first)

Calling is off by default. Turn it on deliberately:

```
export HORUS_OS_VOICE_CALLS_ALLOWED=true
```

Leave this unset (or set to anything other than `true`) and the
`request_reservation_call` tool returns a clear refusal instead
of dialing. This is intentional: it keeps a misbehaving or
over-eager agent from placing real phone calls on your account.

## 5. The live audio bridge

Placing the call, recording it, classifying the outcome, and the
calendar / notify side effects all work with the steps above. The
live, two-way conversation (the agent actually talking to whoever
answers) runs over the `/api/adapters/voice/media` websocket,
which bridges Twilio Media Streams to a realtime voice model.

This is the one piece that is deployment-bound: it needs the
public URL from step 3 plus a realtime voice provider (for
example an OpenAI or Gemini realtime endpoint) configured with
your own key. Wire your realtime provider into the media route
for your deployment. The reservation pipeline around it does not
depend on which provider you choose.

## 6. Completing a call

When a call ends, post the transcript to the complete endpoint so
the outcome is classified and any side effects run:

```
curl -X POST \
  "$HORUS_OS_VOICE_PUBLIC_BASE_URL/api/adapters/voice/calls/<record_id>/complete" \
  -H "Content-Type: application/json" \
  -d '{"transcript": "Your table is confirmed for two at seven."}'
```

The adapter classifies the transcript into `confirmed`,
`declined`, `callback`, or `unclear`. You can override the
classification by passing an explicit `"outcome"` field (useful
when an upstream model has already judged the call). On a
confirmed outcome with the Calendar adapter's
`create_calendar_event` tool available, the reservation is added
to your calendar; if `HORUS_OS_VOICE_NOTIFY_WEBHOOK` is set, a
short notification is posted there too.

## 7. Calendar write-through (optional)

To have confirmed reservations land on your calendar, install and
configure the Calendar adapter (see `docs/adapters/CALENDAR.md`)
with `HORUS_OS_CALENDAR_WRITE_ALLOWED=true`. The Voice adapter
looks up the registered `create_calendar_event` tool at
completion time; if it is absent, the call is still recorded and
classified, it just does not write an event.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `HORUS_OS_TWILIO_ACCOUNT_SID` | yes | Twilio account SID |
| `HORUS_OS_TWILIO_AUTH_TOKEN` | yes | Twilio auth token |
| `HORUS_OS_TWILIO_FROM_NUMBER` | yes | Caller id number (E.164) |
| `HORUS_OS_VOICE_PUBLIC_BASE_URL` | to place calls | Public URL Twilio can reach |
| `HORUS_OS_VOICE_CALLS_ALLOWED` | to place calls | Set to `true` to arm calling |
| `HORUS_OS_VOICE_NOTIFY_WEBHOOK` | no | URL that receives a completion notification |

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/adapters/voice/status` | Configuration and pending-call summary |
| GET | `/api/adapters/voice/twiml` | TwiML that connects a call to the media stream |
| POST | `/api/adapters/voice/calls/{record_id}/complete` | Record a transcript and run side effects |
| WS | `/api/adapters/voice/media` | Two-way audio bridge. Not mounted by the adapter; your deployment implements this route (see section 5) |
