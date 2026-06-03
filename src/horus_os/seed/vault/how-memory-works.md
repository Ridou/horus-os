# How Memory Works

A short explainer on how the agents remember things, so you know where to put
information you want them to use later.

## The vault is the memory

This folder of markdown notes is the long-lived memory. Anything you write
here, the agents can read. There is no hidden store: what you see in these
files is what they see.

## Reading

The agents search and read notes by filename and content. Clear titles and
plain markdown make a note easier to find. A note with a good `# Heading` is
easier to surface than an untitled wall of text.

## Writing

When an agent saves something, it writes a new note or appends to an existing
one. Each write is recorded so you can review what changed and when. Nothing
is overwritten silently.

## Tips for good memory

- Give each note a clear `# Title` on the first line.
- Keep one topic per note where you can.
- Use the example notes in this vault as starting templates.
- Delete notes you no longer need so search stays sharp.

## Traces are a different kind of memory

A trace records how a single answer was produced: the prompt, the response,
and the tools used. Notes are what the agents know; traces are what they did.
