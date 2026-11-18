# Call LTS4AI from an agent

Run commands from the Skill directory. Set `LTS4AI_API_KEY` through your runtime's secret storage. The optional `LTS4AI_BASE_URL` accepts the service origin or that origin followed by `/v1`.

```text
python scripts/lts4ai.py catalog --kind image
python scripts/lts4ai.py catalog --model gpt-image-2.6
python scripts/lts4ai.py call --model gpt-image-2.6 --endpoint image-generation --payload request.json
```

The catalog contains exact IDs, access, capabilities, endpoint names and live pricing fields. `available: null` means no key was supplied. When a key can see a model but its endpoint metadata is missing, consult that model's API documentation and apply the HTTP contract directly. A generic Chat endpoint does not make a text model an image model, and an image model's Chat support must be confirmed separately.

## Pick the endpoint and payload

| Endpoint flag | Minimal JSON example | Response |
| --- | --- | --- |
| `openai-response` | `{"input":"Summarize this text"}` | Responses output, or SSE with `"stream":true` |
| `openai` | `{"messages":[{"role":"user","content":"Summarize this text"}]}` | Chat choices, or SSE |
| `anthropic` | `{"max_tokens":256,"messages":[{"role":"user","content":"Hello"}]}` | Messages content, or SSE |
| `gemini` | `{"contents":[{"parts":[{"text":"Hello"}]}]}` | Native Gemini candidates |
| `image-generation` | `{"prompt":"A blue ceramic mug","size":"1024x1024","n":1,"response_format":"b64_json"}` | Image data, inline Base64 or URLs |
| `image-edit` | `{"prompt":"Make the mug blue","n":1}` with `--file image=reference.png` | Image data |
| `embeddings` | `{"input":"Search text"}` | Embedding vectors |
| `speech` | `{"input":"Hello","voice":"alloy"}` with `--output speech.mp3` | Audio bytes |
| `transcription` or `translation` | `{}` with `--file file=clip.wav` | Transcript |

Use only the routes available for the selected model. Voices, sizes, output modalities, and request fields are model dependent. The command inserts the exact `model` into JSON or multipart form data. For Gemini it goes in the request path instead. Native Gemini reference images use `inlineData` with `mimeType` and Base64 `data` inside a `contents[].parts[]` element. When the image model requires it, set `generationConfig.responseModalities` to include `"IMAGE"`.

To send one real request, select the exact ID and add `--execute`. For example, after the user has selected an image model and asked to generate:

```text
python scripts/lts4ai.py call --model gpt-image-2.6 --endpoint image-generation --payload request.json --save-image result.png --execute
python scripts/lts4ai.py call --model gpt-image-2.6 --endpoint image-edit --payload edit.json --file image=reference.png --save-image edit.png --execute
```

`--output` saves the original response. `--save-image` decodes the first inline image in supported Images, Gemini, or Chat response formats without converting it. Choose the extension to match the returned bytes. If an upstream returns a temporary URL, use its original response and retrieve it without the LTS4AI bearer token. The helper does not follow media URLs.

Pass `--payload -` to read JSON from stdin. Text defaults to a 120-second socket timeout and image requests to 570 seconds. Use `--timeout` when the selected model and runtime require different limits. If a request fails after submission, keep the request ID or existing job receipt and check that request before considering another charge.

## HTTP tools instead of Python

Send the same GET discovery requests and intersect the Model Square entries with the key's model IDs. Use the exact endpoint path and payload schema above with `Authorization: Bearer <secret>` over HTTPS. Keep the secret out of tool output and disable redirects and automatic inference retries. Before any billable call, verify the user asked for the invocation and the selected model.
