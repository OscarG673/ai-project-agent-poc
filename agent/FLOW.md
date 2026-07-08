# ReqEngineer Flow

This document explains how the chat-first requirements flow works and why
requirement generation can take time.

## High-Level Flow

```text
frontend/backend sends text
-> ReqEngineer stores it as a conversation message
-> model returns a normal chat reply
-> user keeps chatting until satisfied
-> user asks to create requirements
-> backend runs create_requirements_from_conversation
-> structured requirements are returned
```

The input text may come from typed chat or from audio transcription. ReqEngineer
does not need to know which one it was.

## Main Endpoints

Create a conversation:

```http
POST /conversations
```

Send a chat message:

```http
POST /conversations/{conversation_id}/messages
```

The message body is:

```json
{
  "content": "User text or transcribed audio text",
  "model": "mlx-community/gpt-oss-20b-MXFP4-Q8",
  "base_url": "http://192.168.10.68:52415/v1",
  "temperature": 0.2,
  "timeout_seconds": 300,
  "review_iterations": 0
}
```

Only `content` is required. The other fields override environment defaults for
that request.

## When Requirements Are Created

Requirements are not created on the first product idea by default. The agent
first chats with the user to gather context.

Requirements are created when the user says something explicit such as:

- `create the requirements`
- `generate requirements`
- `yes, create the requirements`
- `go ahead`
- `proceed`

When that happens, the backend runs:

```text
create_requirements_from_conversation
```

The model does not directly write to storage. It can request the tool, and the
backend validates and executes it.

## Why Generation Can Take Time

There are two different paths:

### Normal Chat Message

```text
1 model call:
conversation -> assistant reply
```

This is the fast path.

### Requirement Creation

```text
1 model call:
conversation transcript -> structured requirements JSON
```

This is slower because the model must produce validated JSON with 5 to 10
requirements.

If `review_iterations` is greater than `0`, each review pass adds two more model
calls:

```text
draft requirements
-> critique requirements
-> revise requirements
```

So the call count is:

```text
review_iterations = 0: 1 model call
review_iterations = 1: 3 model calls
review_iterations = 2: 5 model calls
```

For interactive use, keep:

```json
{
  "review_iterations": 0
}
```

Use `1` or `2` only when you want slower self-review and revision.

## Current Optimization

When the user explicitly asks to create requirements and the conversation
already has prior context, the backend skips an extra chat completion and runs
the tool directly.

This avoids:

```text
chat reply -> tool call -> requirement generation
```

and uses:

```text
explicit user request -> requirement generation
```

The quick UI sends `review_iterations: 0` for this reason.

## Session Persistence

Sessions, messages, drafts, requirements, and embeddings are currently stored in
memory. Restarting Uvicorn clears them.

For persistent sessions, the next step should be SQLite or Postgres storage.
