# LTS4AI API Contract

## Production Addresses

| Purpose | Address |
|---|---|
| Service origin | `https://api.lts4ai.com` |
| OpenAI-compatible Base URL | `https://api.lts4ai.com/v1` |
| Public health/status | `GET https://api.lts4ai.com/api/status` |
| Public pricing catalog | `GET https://api.lts4ai.com/api/pricing` |
| Authenticated model catalog | `GET https://api.lts4ai.com/v1/models` |

Normalize a configured Base URL by removing trailing slashes. Do not append `/v1` twice.

## Authentication

Relay endpoints use:

```http
Authorization: Bearer ${LTS4AI_API_KEY}
```

Use a token created for the application with the least practical scope and budget. Store it in the deployment platform's secret manager or a server-only environment variable. Never accept a provider key from an end user as part of the normal product flow.

## Supported OpenAI-Compatible Routes

| Capability | Method and route |
|---|---|
| Models | `GET /v1/models` |
| Chat Completions | `POST /v1/chat/completions` |
| Responses | `POST /v1/responses` |
| Response compaction | `POST /v1/responses/compact` |
| Image generation | `POST /v1/images/generations` |
| Image editing | `POST /v1/images/edits` |
| Embeddings | `POST /v1/embeddings` |
| Speech | `POST /v1/audio/speech` |
| Transcription | `POST /v1/audio/transcriptions` |
| Translation | `POST /v1/audio/translations` |

Endpoint exposure does not mean every model supports every route. Match the selected model's advertised capability and treat a model/endpoint mismatch as a configuration error rather than retrying another model.

## Model Discovery

Call `GET /v1/models` with the same application token used for inference. Select the exact `data[].id` value. Provider-prefixed IDs such as `openai/...` are valid and must not be stripped.

Recommended website selector pattern:

1. Backend loads `/v1/models` and caches the non-secret result briefly.
2. Backend intersects live IDs with a product-owned allowlist.
3. Frontend receives only safe display fields and exact IDs.
4. Inference route validates the submitted ID against the same allowlist.

Do not scrape UI labels or copy a static catalog into source. If the catalog cannot be queried because the key is missing or rejected, stop and request correct server-side configuration.

## Endpoint Choice

- Prefer Responses for a new text or tool-calling integration only if the exact model advertises it. Use Chat Completions for chat-only models.
- Keep Chat Completions when the existing application already uses its message schema or its library does not support Responses.
- Do not translate between schemas unless the target application requires it; the fields and streaming events are not interchangeable.
- Use image endpoints only for models confirmed to support image generation or editing.

## Pricing and Billing

- Read model pricing from the public `GET /api/pricing` catalog. It requires no authentication and exposes per-model fields such as `model_name`, `quota_type`, `model_ratio`, `completion_ratio`, `enable_groups`, and `supported_endpoint_types`. Expression-billed models additionally expose `billing_mode` and `billing_expr`. Do not derive a price from a model name or description.
- Inspect `billing_mode` and `billing_expr` before interpreting `quota_type`; expression billing can coexist with `quota_type: 0` and does not necessarily mean token billing. Text prices may depend on input/output/cache usage. Image requests use fixed per-request prices or pixel-tier expressions, independent of usage tokens.
- `billing_expr` is authoritative for expression-billed models. Treat it as opaque configuration: evaluate or display it server-side, do not port the current expression constants into client code, and re-read the catalog when prices change instead of caching forever.
- `pricing_version` is a compatibility marker for the pricing list as a whole. Compare prices by model ID and per-model fields, not by which record carries the version marker.
- For balance display, `GET /api/status` exposes the current quota presentation settings, including `quota_display_type`, `custom_currency_symbol`, `custom_currency_exchange_rate`, and `quota_per_unit`. When rendering an authenticated user's balance in the site's display currency, convert from the raw quota value using those status fields rather than a fixed local multiplier. With the current `CUSTOM` display, the conversion is `displayed_credits = raw_quota / quota_per_unit * custom_currency_exchange_rate`.
- Prices, multipliers, and display-currency settings are operational values that can change. Applications should show live values from these endpoints or clearly label a cached price with its refresh time.

## Reliability and Errors

- Configure a finite timeout and propagate caller cancellation. Cancelling the HTTP connection does not guarantee cancellation at the provider or prevent billing.
- Treat `401`/`403` as credential or permission problems; do not retry.
- Treat `400`/`404` model errors as model/endpoint configuration problems; refresh the model list and report clearly.
- Treat `429` as rate or quota pressure. Honor `Retry-After` when present, but bound retries and avoid silently multiplying paid requests.
- Treat `5xx` as transient only when the target application's retry policy permits it. Avoid automatic retries for a paid non-idempotent request unless duplicate charging is acceptable.
- Generate an application request ID for tracing, but never include the API key or full sensitive prompt in logs.
- Return a stable application error shape to browsers; keep sanitized upstream details only in protected server logs.

## Images Contract (verified 2026-11-16)

- Use `n: 1`. A batch is multiple independent single-image requests; do not replace the application's concurrency with an arbitrary lower limit. Other image-count fields must also equal1.
- The gateway reserves funds before submission and charges after actual upstream submission whether the request succeeds, fails or times out. Authentication, insufficient funds and validation rejection before submission are not charged. Polling/retrieval is not a new generation; explicitly retrying generation is a new potentially billable request.
- Public pricing may expose `image_request_billing: submitted_attempt` and `max_images_per_request: 1`. These optional fields supplement the contract; their absence does not authorize multi-image batches or free failure retries.
- Disable automatic paid POST retries in SDKs, application proxies and job queues. One user request can already include the route's bounded retry; do not add another retry loop. Preserve opaque request/recovery IDs without recording credentials or full image payloads in logs.
- `gpt-image-2.6` is available through `/v1/images/generations` and multipart `/v1/images/edits`. The dedicated route rejects `/v1/chat/completions`, even if generic channel capability inference also lists `openai`. It sends the actual upstream model `gpt-image-2.6`. It does not downgrade to2.5. 1K makes one upstream attempt; 2K/4K retain at most one same-model Weason retry. Do not generalize these route-specific rules to every image model.
- At this verification date, ordinary2.5 and2.6 share 1K/2K/4K prices of3/4/5 displayed credits. This is a dated example, not a price table to embed in code. Read the live expression, request `size`, group ratio and display settings. A `4K` tier label does not guarantee a4096-pixel side; show actual returned dimensions and preserve aspect ratio.
- Allow long image requests end to end: an example client timeout is570seconds under the existing600second gateway response-header allowance. Align the application's host/proxy timeout and payload limit. Persist the job server-side so a browser disconnect does not discard a completed result; a30second generic text timeout is unsuitable for this image route.
- Accept `data[].b64_json` or `data[].url` as applicable; preserve exact bytes, decode Base64 before saving, and retrieve signed/temporary URLs promptly using protected server-side code. Do not expose supplier credentials or log signed URLs.
- Unknown outcome, missing image, download failure and resolution mismatch must not trigger another generation automatically. A failure message does not imply no charge. Reconcile the existing application's task/result records first; there is no generic `/v1/images/tasks/...` API promised by this skill.

## Cost and Data Boundaries

- Model prices and billing expressions can change. Do not calculate or promise price from hardcoded multipliers in application code.
- Usage is charged against the LTS4AI account associated with the token.
- User prompts and uploaded media traverse LTS4AI and the selected upstream route. Ensure the application's privacy notice and data-handling policy reflect that flow.
- Never run a live inference solely as a smoke test without explicit approval because even a minimal request can consume balance.
