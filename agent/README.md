# ReqEngineer

ReqEngineer is a FastAPI agent that turns a chat conversation into structured
software requirements.

The frontend can send typed text or transcribed audio text. ReqEngineer stores
the conversation, replies conversationally through an OpenAI-compatible Exo
endpoint, and only creates requirements when the model requests the backend
tool `create_requirements_from_conversation`.

There is no offline fallback.

For the detailed conversation/tool flow and latency notes, see [FLOW.md](FLOW.md).

## Installation

Create the project environment and install dependencies:

```bash
uv sync
```

Configure Exo. Defaults are already set for the current Exo endpoint, but these
environment variables make the runtime explicit:

```bash
export EXO_BASE_URL="http://192.168.10.68:52415/v1"
export EXO_MODEL="mlx-community/gpt-oss-20b-MXFP4-Q8"
export REQENGINEER_TEMPERATURE="0.2"
export REQENGINEER_TIMEOUT_SECONDS="300"
export REQENGINEER_REVIEW_ITERATIONS="0"
```

Start the API:

```bash
uv run uvicorn reqengineer.api:app --reload
```

The health endpoint is:

```bash
curl -s http://127.0.0.1:8000/health
```

Open the quick UI:

```text
http://127.0.0.1:8000/
```

## Usage For Other Systems

Use this section when integrating ReqEngineer from another backend or frontend.
The frontend can send typed text or transcribed audio text in the same `content`
field.

Create a conversation:

```bash
curl -s -X POST http://127.0.0.1:8000/conversations
```

Example response:

```json
{
  "conversation_id": "session_abc123"
}
```

Send user text to the conversation:

```bash
curl -s http://127.0.0.1:8000/conversations/session_abc123/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "I want to keep statistics of the world cup, goals, assists, etc. to predict next match stuff"
  }'
```

Full request body with every supported option:

```json
{
  "content": "I want to keep statistics of the world cup, goals, assists, etc. to predict next match stuff",
  "model": "mlx-community/gpt-oss-20b-MXFP4-Q8",
  "base_url": "http://192.168.10.68:52415/v1",
  "temperature": 0.2,
  "timeout_seconds": 300,
  "review_iterations": 0
}
```

Field notes:

- `content` is required. It can be typed text or transcribed audio text.
- `model` overrides `EXO_MODEL` for this request.
- `base_url` overrides `EXO_BASE_URL` for this request.
- `temperature` overrides `REQENGINEER_TEMPERATURE` for this request.
- `timeout_seconds` overrides `REQENGINEER_TIMEOUT_SECONDS` for this request.
- `review_iterations` controls draft critique/revision passes when requirements are created. Use `0` for faster interactive chat and `1` or `2` when you want slower self-review.

The assistant replies normally and does not create requirements yet:

```json
{
  "conversation_id": "session_abc123",
  "message": {
    "role": "assistant",
    "content": "Sounds interesting. Which statistics do you want to track, and what predictions should the system produce?"
  },
  "actions_performed": [],
  "tool_calls": [],
  "draft_id": null,
  "requirements": []
}
```

When the user is satisfied, send a normal chat message:

```bash
curl -s http://127.0.0.1:8000/conversations/session_abc123/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "yes, create the requirements"}'
```

If the model requests the backend tool, requirements are created and returned:

```json
{
  "conversation_id": "session_abc123",
  "message": {
    "role": "assistant",
    "content": "Sure, generating the requirements now."
  },
  "actions_performed": ["create_requirements_from_conversation"],
  "tool_calls": [
    {
      "name": "create_requirements_from_conversation",
      "arguments": {}
    }
  ],
  "draft_id": "draft_abc123",
  "requirements": [
    {
      "id": "req_abc123",
      "name": "Track player statistics",
      "description": "The system shall store goals, assists, and match participation for each player.",
      "priority": "high",
      "status": "pending"
    }
  ]
}
```

The frontend only needs to render:

- `message.content` as the assistant chat reply
- `requirements` as cards when the array is non-empty

## Direct Requirement Generation

For testing or backend-only use, you can bypass conversation and generate
requirements directly:

```bash
curl -s http://127.0.0.1:8000/requirements \
  -H "Content-Type: application/json" \
  -d '{
    "user_text": "A mobile app that helps field technicians document equipment inspections",
    "review_iterations": 1
  }'
```

Full request body:

```json
{
  "user_text": "A mobile app that helps field technicians document equipment inspections",
  "idea": "Compatibility alias for user_text",
  "model": "mlx-community/gpt-oss-20b-MXFP4-Q8",
  "base_url": "http://192.168.10.68:52415/v1",
  "temperature": 0.2,
  "timeout_seconds": 300,
  "review_iterations": 1
}
```

Use either `user_text` or `idea`; `user_text` is preferred.

## Embeddings

After requirements are created, use a returned requirement ID:

```bash
curl -s http://127.0.0.1:8000/requirements/req_abc123/embedding \
  -H "Content-Type: application/json" \
  -d '{"model": "your-embedding-model"}'
```

Full request body:

```json
{
  "model": "your-embedding-model",
  "base_url": "http://192.168.10.68:52415/v1",
  "timeout_seconds": 300
}
```

This endpoint expects an OpenAI-compatible `/v1/embeddings` endpoint at
`EXO_BASE_URL`. If the Exo server does not provide embeddings, this endpoint
will return an upstream error.

## CLI

The CLI still supports direct generation:

```bash
uv run python -m reqengineer.cli \
  --model mlx-community/gpt-oss-20b-MXFP4-Q8 \
  --review-iterations 1 \
  "A portal for customers to request refunds"
```
