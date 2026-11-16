# Integration Recipes

Use the target repository's package manager, framework conventions, and error format. These examples contain placeholders only.

## TypeScript / Node.js

Install the official OpenAI SDK only if the project does not already have an OpenAI-compatible client:

```bash
npm install openai
```

Create one server-only client:

```ts
import OpenAI from 'openai'

function requiredEnv(name: string): string {
  const value = process.env[name]
  if (!value) throw new Error(`${name} is not configured`)
  return value
}

export const lts4ai = new OpenAI({
  apiKey: requiredEnv('LTS4AI_API_KEY'),
  baseURL: (process.env.LTS4AI_BASE_URL ?? 'https://api.lts4ai.com/v1').replace(/\/+$/, ''),
  timeout: 30_000,
  maxRetries: 0,
})
```

Validate an exact selected model:

```ts
export async function requireLts4aiModel(model: string): Promise<string> {
  const page = await lts4ai.models.list()
  const available = new Set(page.data.map((item) => item.id))
  if (!available.has(model)) throw new Error(`LTS4AI model is unavailable: ${model}`)
  return model
}
```

Responses API:

```ts
const model = await requireLts4aiModel(selectedModel)
const response = await lts4ai.responses.create({ model, input: userInput })
console.log(response.output_text)
```

Chat Completions compatibility:

```ts
const completion = await lts4ai.chat.completions.create({
  model: selectedModel,
  messages: [{ role: 'user', content: userInput }],
})
const text = completion.choices[0]?.message?.content ?? ''
```

Streaming Responses:

```ts
const stream = await lts4ai.responses.create({
  model: selectedModel,
  input: userInput,
  stream: true,
})

for await (const event of stream) {
  if (event.type === 'response.output_text.delta') process.stdout.write(event.delta)
}
```

## Website Backend Boundary

Never instantiate the client above in a browser component. A server route must authenticate the application user, validate request size, validate the selected model against a server-owned allowlist, call LTS4AI with the server-side key, and return sanitized JSON or an SSE stream.

Minimal Next.js route shape:

```ts
import { lts4ai } from '@/server/lts4ai'

const allowedModels = new Set(
  (process.env.LTS4AI_ALLOWED_MODELS ?? '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean),
)

export async function POST(request: Request) {
  const body = await request.json()
  if (typeof body.model !== 'string' || !allowedModels.has(body.model)) {
    return Response.json({ error: 'Unsupported model' }, { status: 400 })
  }
  if (typeof body.input !== 'string' || body.input.length === 0 || body.input.length > 20_000) {
    return Response.json({ error: 'Invalid input' }, { status: 400 })
  }

  try {
    const response = await lts4ai.responses.create({ model: body.model, input: body.input })
    return Response.json({ text: response.output_text })
  } catch {
    return Response.json({ error: 'AI request failed' }, { status: 502 })
  }
}
```

Add the framework's normal authentication, rate limiting, CSRF protection, timeout/cancellation, observability, and streaming primitives rather than inventing parallel infrastructure.

## Python

```python
import os
from openai import OpenAI

api_key = os.environ.get("LTS4AI_API_KEY")
if not api_key:
    raise RuntimeError("LTS4AI_API_KEY is not configured")

client = OpenAI(
    api_key=api_key,
    base_url=os.environ.get("LTS4AI_BASE_URL", "https://api.lts4ai.com/v1").rstrip("/"),
    timeout=30.0,
    max_retries=0,
)

response = client.responses.create(model=selected_model, input=user_input)
print(response.output_text)
```

## Raw HTTP / cURL

List models without exposing the key in source:

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $LTS4AI_API_KEY" \
  https://api.lts4ai.com/v1/models
```

Responses request:

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $LTS4AI_API_KEY" \
  -H "Content-Type: application/json" \
  https://api.lts4ai.com/v1/responses \
  -d '{"model":"MODEL_ID_FROM_V1_MODELS","input":"Hello"}'
```

Do not paste a real token into documentation, shell history, screenshots, issue reports, or chat. Prefer the environment-variable form even for local testing.

## Image Generation

After confirming that the exact selected model supports Images API generation, use a separate timeout and disable paid POST retries:

```ts
const imageClient = lts4ai.withOptions({ timeout: 570_000, maxRetries: 0 })
const image = await imageClient.images.generate({
  model: selectedModel,
  prompt,
  size: '1024x1024',
  n: 1,
  response_format: 'b64_json',
})
```

Treat returned URLs as temporary unless the contract explicitly says otherwise. Persist results server-side according to the application's storage policy; never log temporary signed URLs.

For GPT Image2.6, use the exact ID `gpt-image-2.6` after discovery; do not route it through Chat Completions or rename it2.5. For image edits, send the original reference file bytes as multipart `image` with `n: 1`. A batch consists of independent requests, not `n > 1`.

Python image calls can override the text client's timeout without enabling retries:

```python
image = client.with_options(timeout=570.0, max_retries=0).images.generate(
    model=selected_model, prompt=prompt, size="1024x1024", n=1,
    response_format="b64_json",
)
```

Run image work in a durable application task when the hosting platform cannot hold a long connection. Save the task ID before submission and preserve returned images on completion. Do not automatically repeat generation after timeout, cancellation or download failure: the original request can still be charged and can still complete.

## Test Matrix

| Scenario | Expected behavior |
|---|---|
| Valid allowed model | Returns or streams the model response |
| Missing server key | Fails during server startup/configuration, not in the browser |
| Browser submits unapproved model | Returns application `400` without calling LTS4AI |
| LTS4AI returns `401`/`403` | Returns sanitized configuration error |
| LTS4AI returns `429` | Returns a rate-limit response or follows a bounded policy |
| Timeout/cancellation | Propagates cancellation and closes the response; does not claim provider cancellation or no charge |
| Image batch | Sends independent `n: 1` requests, retaining each task's result and failure separately |
| Image failure/unknown outcome | Does not automatically repeat generation or assume a refund |
| Malformed stream event | Fails safely without exposing headers or secrets |

After mocked tests pass, run the read-only checker. Run one minimal paid inference only when the user explicitly authorizes it and identifies the model.
