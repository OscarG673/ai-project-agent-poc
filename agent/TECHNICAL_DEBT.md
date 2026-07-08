# Technical Debt

This file tracks known technical debt and pragmatic next steps for ReqEngineer.

## In-Memory Storage

Current state:

- Conversations are stored in process memory.
- Messages are stored in process memory.
- Drafts and requirements are stored in process memory.
- Embeddings are stored in process memory.

Impact:

- Restarting Uvicorn loses all sessions and generated requirements.
- Running multiple workers would create separate isolated stores.
- Retrying failed requests can duplicate user messages.

Recommended fix:

- Add SQLite for local/single-host usage.
- Move to Postgres when multi-user or multi-worker deployment is needed.
- Add message IDs and idempotency keys.

## Request Atomicity

Current state:

- A user message is saved before the model call is made.
- If the model request times out or fails, the user message remains without an assistant reply.

Impact:

- Retrying the same frontend request can duplicate the user message.
- Conversation history may contain failed turns with no status metadata.

Recommended fix:

- Add message status: `pending`, `completed`, `failed`.
- Accept a frontend-provided `idempotency_key`.
- On retry, return the existing turn instead of appending a duplicate.

## Tool Calling

Current state:

- The model outputs JSON with a `tool_calls` array.
- The backend validates and executes `create_requirements_from_conversation`.
- There is a backend fallback for explicit phrases like `yes, create the requirements`.

Impact:

- This is not using formal OpenAI tool/function-calling protocol.
- Model behavior depends heavily on prompt compliance.
- The fallback is useful but phrase-based.

Recommended fix:

- If Exo supports OpenAI-compatible tools, migrate to formal `tools` / `tool_calls`.
- Keep backend validation as the source of truth.
- Add tests for tool-call parsing and fallback behavior.

## Latency

Current state:

- Normal chat is one model call.
- Requirement creation is one model call when `review_iterations = 0`.
- Each review iteration adds two model calls: critique and revise.

Impact:

- Requirement generation can feel slow, especially on LAN-hosted or smaller local models.
- Timeouts can happen under load or unstable network conditions.

Recommended fix:

- Keep `review_iterations = 0` for interactive UI.
- Run requirement generation as a background job for longer review pipelines.
- Add request timing logs per model call.
- Return progress events with WebSockets or Server-Sent Events.

## Error Handling

Current state:

- Model failures return `502`.
- The frontend displays the error as an assistant message.
- There is no structured error code taxonomy.

Impact:

- Frontend cannot easily distinguish timeout, invalid JSON, network failure, or model validation failure.
- Failed turns are not represented in persistent state.

Recommended fix:

- Return structured error payloads with stable `code` values.
- Add retry guidance for timeout and transient network failures.
- Store failed assistant turns if persistence is added.

## JSON Robustness

Current state:

- Prompts instruct the model to return JSON.
- The backend rejects invalid JSON.
- There is no JSON repair or retry pass.

Impact:

- A single malformed model response causes a failed request.
- User has to retry manually.

Recommended fix:

- Add one automatic repair/retry pass for invalid JSON.
- Consider schema-constrained decoding if Exo supports it.
- Add tests with malformed model responses.

## Embeddings

Current state:

- The embedding endpoint expects an OpenAI-compatible `/v1/embeddings` endpoint.
- It stores vectors in memory.
- It does not expose search yet.

Impact:

- Embeddings are not useful beyond confirming storage.
- Restarting the process loses vectors.
- Exo may not expose embeddings with the selected model.

Recommended fix:

- Decide on an embedding provider/model.
- Persist vectors in SQLite or Postgres with a vector extension when needed.
- Add semantic search endpoints only after persistence is in place.

## UI

Current state:

- The UI is a single static HTML file.
- It supports chat and renders requirement cards.
- It has no audio upload, auth, persistence warning, or retry controls.

Impact:

- Good for local testing, not production.
- Users can lose session state on server restart.
- Failed model calls are displayed but not recoverable cleanly.

Recommended fix:

- Add upload/transcription integration when the backend endpoint exists.
- Add retry without duplicating messages after idempotency is implemented.
- Show session persistence warnings in development mode.

## Security

Current state:

- No authentication.
- No authorization.
- No rate limits.
- No input size limits beyond basic Pydantic validation.

Impact:

- Not safe to expose outside a trusted LAN.
- A user can create expensive long-running model calls.

Recommended fix:

- Add auth before exposing outside trusted local networks.
- Add request size limits.
- Add rate limits and per-user/session quotas.
- Add CORS policy for known frontend origins.

## Testing

Current state:

- Verification has been manual through curl and compile checks.
- There are no automated tests.

Impact:

- Regressions in tool calling, JSON parsing, or storage behavior are easy to miss.

Recommended fix:

- Add unit tests for:
  - requirement parsing
  - chat response parsing
  - explicit requirements fallback
  - in-memory store behavior
- Add integration tests with a fake OpenAI-compatible model server.
