---
name: lts4ai-api-integration
description: Use when integrating a selected LTS4AI-hosted model into a website, backend, CLI, or application through its OpenAI-compatible API, including model discovery, chat, Responses API, streaming, images, embeddings, or integration troubleshooting. Do not use for LTS4AI infrastructure administration or billing changes.
---

# LTS4AI API Integration

Integrate LTS4AI through its OpenAI-compatible API while preserving the target project's conventions and keeping credentials server-side.

## Required Invariants

- Use `https://api.lts4ai.com/v1` as the production Base URL unless the user explicitly supplies another LTS4AI deployment.
- Read the API key from a server-side secret such as `LTS4AI_API_KEY`. Never print, commit, return, log, embed in browser code, or put it in a URL.
- A browser or desktop renderer calls the application's backend or serverless route; it must not call LTS4AI with the real key.
- Preserve the exact model ID selected by the user. Do not silently substitute a nearby model.
- Discover or validate models with authenticated `GET /v1/models`; do not hardcode the changing catalog, provider, price, or future model IDs.
- Read live prices and quota-display settings from the public `GET /api/pricing` and `GET /api/status` endpoints when an application shows cost or balance; do not hardcode the current multipliers or display currency.
- Do not send a paid inference request merely to test connectivity without explicit approval. Health and model-list checks are read-only.
- Do not deploy, rotate secrets, alter balances, or change LTS4AI configuration unless separately authorized.

## Workflow

1. Read the target repository instructions and identify its runtime, existing AI client, API routes, secret handling, and tests.
2. Determine the exact model ID and capability needed. If no model was selected, expose a server-side-backed selector or ask for one; never guess.
3. Choose an endpoint advertised for the exact model. Prefer `/responses` for new text integrations only when that model supports it; retain `/chat/completions` for chat-only models or existing chat-compatible code. Do not infer audio, embedding, or image capability from a route existing on the gateway.
4. Reuse the project's OpenAI-compatible client when practical. Change only the Base URL, server-side API key source, and selected model.
5. For user-selectable models, validate the submitted model against a server-side allowlist intersected with `/v1/models`. Do not trust a browser-supplied model ID directly.
6. Preserve streaming end to end, propagate cancellation, add a finite timeout, and handle SSE as a stream rather than JSON.
7. Sanitize errors before returning them to clients. Never expose authorization headers, upstream response headers, secret-bearing request objects, or internal stack traces.
8. Add scope-matched tests with mocked HTTP responses. Run the read-only checker before any approved minimal live inference.

## Image Requests

- Read the image contract in `references/api-contract.md` before integrating image generation or editing. Submit one image per request (`n: 1`); implement batches as independent requests while preserving the application's concurrency setting.
- Images are charged per submitted upstream attempt regardless of success, failure, or timeout. Disable SDK/proxy automatic retries. Cancellation or a missing image does not prove that generation stopped or that no charge occurred.
- Use a separate long timeout for images, preserve returned image bytes or temporary URLs promptly, and retain application task IDs/results across client disconnects. Do not invent a gateway task-recovery endpoint.
- `gpt-image-2.6` uses Images generation/edit endpoints; its dedicated route rejects Chat Completions. Preserve the exact ID and do not silently downgrade to 2.5. Treat this as a verified contract example, not a replacement for live discovery.

## References

- Read `references/api-contract.md` for endpoints, authentication, model discovery, and operational rules.
- Read `references/integration-recipes.md` for TypeScript, Python, cURL, streaming, and website-backend examples.
- Run `python scripts/check_lts4ai.py --help` for read-only health and model availability checks.

## Completion Checklist

- The selected model is exact and available to the configured key.
- No secret appears in source, client bundles, logs, screenshots, test fixtures, or output.
- Browser requests terminate at an application-owned backend route.
- Tests cover success, authorization failure, upstream failure, timeout, and invalid/disallowed model.
- No paid live call or deployment occurred without explicit authorization.
