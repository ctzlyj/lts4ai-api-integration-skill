---
name: lts4ai-api-integration
description: Discover, choose, and call models from the LTS4AI Model Square, including text and multiple image models, or integrate selected LTS4AI models into a program, website, backend, or CLI. Use for live model access, model selectors, text, image generation and edits, streaming, and integration troubleshooting. Gateway administration is out of scope.
---

# LTS4AI models

Use the production base URL `https://api.lts4ai.com/v1` and an LTS4AI API Key in the runtime's `LTS4AI_API_KEY` secret. The commands below are relative to this Skill directory. Python 3.10 or later is sufficient. Use your agent's HTTP tool or runtime and the same API contract if Python is unavailable.

## Choose a model

1. Run `python scripts/lts4ai.py catalog --kind image` for image choices, `--kind text` for text, or omit the filter for all models. The command combines the Model Square's `GET /api/pricing` and the key's authenticated `GET /v1/models`. With no key it previews the public catalog and reports access as unverified. A model granted to the key but missing compatible endpoint data stays listed. Resolve its API contract before calling it.
2. If the user supplied an ID, validate it with `catalog --model EXACT_ID` and retain it exactly, including prefixes. Otherwise offer relevant accessible choices. For images, distinguish generation, editing, reference-image support, and the exact endpoint. Show size and price only if verified. Do not silently switch models or default to an expensive model.
3. If a key is missing, continue public discovery or project setup and tell the user where to configure the secret. They can sign in to LTS4AI and open API Tokens to copy their initial token or create an app-specific token. Never ask them to paste a key into chat, put it in a URL, or expose it to browser code.

## Call from an agent

Read [direct invocation](references/direct-invocation.md). Use `python scripts/lts4ai.py call --model EXACT_ID --endpoint ENDPOINT --payload request.json` to verify the selected pair and prepare the request. Add `--execute` only when the user has asked for a real call or given a budget that covers it. A request for integration, installation, or connectivity checks alone does not authorize billed inference. The command sends one inference POST per execution without redirects or automatic retries.

Use the request schema for the selected endpoint. For example, an Images request uses `prompt` and `n: 1`, while a native Gemini request uses `contents`. Prefer saving image bytes or the raw result to a file and returning the resulting artifact. Reference images go through the matching edit or native input schema. Preserve the request ID after an ambiguous failure. Do not regenerate to recover a lost response.

## Integrate into an app or website

Read [API contract](references/api-contract.md) and [integration recipes](references/integration-recipes.md). Reuse the app's existing SDK and runtime. Put the key and paid API calls on the server, and expose a safe model list to the browser from live metadata. Intersect accessible model IDs with any project allowlist, then validate both model and endpoint at submission. Use separate request adapters when choices have different schemas. Keep the account's actual billing and permissions in force.

Preserve streaming where requested. For long image jobs, keep task and result state on the server, allow the appropriate timeout through proxies, and use independent single-image requests for batches. Test request mapping, media upload and result saving with mocks. Run read-only catalog checks with the app's configured key. Verify any new model only against its actual published or tested capabilities.
