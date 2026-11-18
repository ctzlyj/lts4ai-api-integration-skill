#!/usr/bin/env python3
"""Live LTS4AI catalog and single-request client (Python 3.10+, standard library)."""

import argparse
import base64
import binascii
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

from check_lts4ai import DEFAULT_BASE_URL, NoRedirect, model_ids, request_json, service_origin


ROUTES = {
    "openai": "/v1/chat/completions",
    "openai-response": "/v1/responses",
    "anthropic": "/v1/messages",
    "gemini": "/v1beta/models/{model}:generateContent",
    "image-generation": "/v1/images/generations",
    "image-edit": "/v1/images/edits",
    "embeddings": "/v1/embeddings",
    "speech": "/v1/audio/speech",
    "transcription": "/v1/audio/transcriptions",
    "translation": "/v1/audio/translations",
}
IMAGE_ROUTES = {"image-generation", "image-edit"}
MULTIPART_ROUTES = {"image-edit", "transcription", "translation"}
REQUEST_LIMIT = 50 * 1024 * 1024
PRICING_FIELDS = (
    "quota_type", "model_price", "model_ratio", "completion_ratio",
    "billing_mode", "billing_expr", "image_request_billing", "max_images_per_request",
)


def endpoints_for(model, row, advertised_routes):
    endpoints = {}
    for endpoint in row.get("supported_endpoint_types") or []:
        route = advertised_routes.get(endpoint, {})
        path = ROUTES.get(endpoint)
        if path is None and isinstance(route, dict) and route.get("method") == "POST":
            candidate = route.get("path", "")
            if isinstance(candidate, str) and re.fullmatch(r"/v1/[\w-]+(?:/[\w-]+)*", candidate):
                path = candidate
        if path:
            endpoints[endpoint] = path

    # Production generic-channel inference omits the GPT 2.5 Images routes
    # and adds a Chat route that the dedicated GPT 2.6 router rejects.
    if model in {"gpt-image-2.5", "gpt-image-2.6", "GPT-image-2"}:
        endpoints.update({name: ROUTES[name] for name in IMAGE_ROUTES})
    if model == "gpt-image-2.6":
        endpoints.pop("openai", None)
    return dict(sorted(endpoints.items()))


def catalog(origin, key):
    pricing = request_json(origin + "/api/pricing", None, 20)
    if not isinstance(pricing, dict) or pricing.get("success") is not True or not isinstance(pricing.get("data"), list):
        raise ValueError("Model Square returned an unexpected response")
    routes = pricing.get("supported_endpoint", {})
    entries = {row["model_name"]: row for row in pricing["data"] if isinstance(row, dict) and isinstance(row.get("model_name"), str)}
    visible = set(model_ids(request_json(origin + "/v1/models", key, 20))) if key else None
    ids = entries.keys() if visible is None else visible
    result = []
    for name in sorted(ids):
        row = entries.get(name, {})
        endpoints = endpoints_for(name, row, routes)
        is_image = row.get("image_request_billing") == "submitted_attempt" or bool(IMAGE_ROUTES & endpoints.keys())
        capabilities = ["image"] if is_image else []
        if not is_image and {"openai", "openai-response", "anthropic", "gemini"} & endpoints.keys():
            capabilities.append("text")
        if "embeddings" in endpoints:
            capabilities.append("embedding")
        if {"speech", "transcription", "translation"} & endpoints.keys():
            capabilities.append("audio")
        result.append({
            "id": name, "available": True if key else None, "capabilities": capabilities,
            "endpoints": endpoints, "advertised_endpoint_types": row.get("supported_endpoint_types", []),
            "groups": row.get("enable_groups", []), "description": row.get("description", ""),
            "pricing": {field: row[field] for field in PRICING_FIELDS if field in row},
        })
    return result


def payload_for(path, model, values, is_image):
    if not isinstance(values, dict):
        raise ValueError("Payload must be a JSON object")
    if "model" in values and values["model"] != model:
        raise ValueError("Payload model differs from the selected model")
    body = {**values, "model": model}
    if "{model}" in path:
        path = path.replace("{model}", urllib.parse.quote(model, safe=""))
        body.pop("model")
    if is_image:
        if "n" in body and (type(body["n"]) is not int or body["n"] != 1):
            raise ValueError("Image requests must use n=1")
        if path in IMAGE_ROUTES_PATHS:
            if body.get("stream") is True:
                raise ValueError("This client expects a single JSON image result")
            body["n"] = 1
    return path, body


IMAGE_ROUTES_PATHS = {ROUTES[name] for name in IMAGE_ROUTES}


def multipart(values, files):
    boundary = uuid4().hex
    parts = []
    size = 0
    for name, value in values.items():
        if not re.fullmatch(r"[A-Za-z0-9_.\[\]-]+", name) or isinstance(value, (dict, list)):
            raise ValueError("Multipart JSON fields must be named scalar fields")
        content = value if isinstance(value, str) else json.dumps(value)
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{content}\r\n'.encode())
    for spec in files:
        field, sep, filename = spec.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z0-9_.\[\]-]+", field):
            raise ValueError("Use --file FIELD=PATH")
        source = Path(filename)
        mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", source.name)
        with source.open("rb") as stream:
            chunk = stream.read(REQUEST_LIMIT - size + 1)
        size += len(chunk)
        if size > REQUEST_LIMIT:
            raise ValueError("Multipart files exceed 50 MiB")
        parts.extend([
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{safe_name}"\r\nContent-Type: {mime}\r\n\r\n'.encode(),
            chunk, b"\r\n",
        ])
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), "multipart/form-data; boundary=" + boundary


def image_from_json(data):
    if not isinstance(data, dict):
        raise ValueError("Image reply is not an object")
    for image in data.get("data") or []:
        if isinstance(image, dict) and isinstance(image.get("b64_json"), str) and image["b64_json"]:
            return base64.b64decode(image["b64_json"], validate=True)
    for candidate in data.get("candidates") or []:
        for item in candidate.get("content", {}).get("parts", []):
            inline = item.get("inlineData") or item.get("inline_data") or {}
            if inline.get("data") and str(inline.get("mimeType", inline.get("mime_type", ""))).startswith("image/"):
                return base64.b64decode(inline["data"], validate=True)
    for choice in data.get("choices") or []:
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            match = re.search(r"data:image/[A-Za-z0-9.+-]+;base64,([A-Za-z0-9+/=]+)", content)
            if match:
                return base64.b64decode(match[1], validate=True)
        for part in (content if isinstance(content, list) else []) + (message.get("images") or []):
            url = part.get("image_url") if isinstance(part, dict) else None
            url = url.get("url") if isinstance(url, dict) else url
            if isinstance(url, str) and re.fullmatch(r"data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=]+", url):
                return base64.b64decode(url.split(",", 1)[1], validate=True)
    return None


def invoke(args, origin, key, entries):
    selected = next((entry for entry in entries if entry["id"] == args.model), None)
    if not selected or args.endpoint not in selected["endpoints"]:
        raise ValueError("This exact model and endpoint pair is unavailable to the configured key")
    is_image = "image" in selected["capabilities"]
    source = sys.stdin if args.payload == "-" else Path(args.payload)
    values = json.load(source) if source is sys.stdin else json.loads(source.read_text(encoding="utf-8"))
    path, values = payload_for(selected["endpoints"][args.endpoint], args.model, values, is_image)
    if args.file and args.endpoint not in MULTIPART_ROUTES:
        raise ValueError("Use --file with image-edit, transcription, or translation")
    if args.endpoint in MULTIPART_ROUTES and not args.file:
        raise ValueError("This endpoint requires a --file FIELD=PATH attachment")
    if args.save_image and not is_image:
        raise ValueError("--save-image requires an image model")
    for output in (args.output, args.save_image):
        if output and (output.exists() or not output.parent.is_dir()):
            raise ValueError("Output must be a new file in an existing directory")
    if args.output and args.save_image and args.output.resolve() == args.save_image.resolve():
        raise ValueError("Raw response and decoded image require separate paths")
    body, mime = multipart(values, args.file) if args.file else (json.dumps(values).encode(), "application/json")
    if len(body) > REQUEST_LIMIT:
        raise ValueError("Request exceeds 50 MiB")
    timeout = args.timeout if args.timeout is not None else (570 if is_image else 120)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be finite and positive")
    if not args.execute:
        print(json.dumps({"method": "POST", "path": path, "model": args.model, "timeout_seconds": timeout,
                          "pricing": selected["pricing"], "request_sent": False}, ensure_ascii=True))
        return 0
    req = urllib.request.Request(origin + path, body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": mime,
        "Accept": "text/event-stream" if values.get("stream") is True else "*/*",
    })
    # Inference uses exactly one request. Do not follow redirects or retry it.
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
        rid = response.headers.get("x-oneapi-request-id") or response.headers.get("x-request-id")
        print("HTTP " + str(response.status) + safe_request_id(rid), file=sys.stderr)
        if args.save_image:
            raw = response.read(64 * 1024 * 1024 + 1)
            if len(raw) > 64 * 1024 * 1024:
                raise ValueError("Image response exceeds 64 MiB")
            if args.output:
                with args.output.open("xb") as out:
                    out.write(raw)
            image = image_from_json(json.loads(raw))
            if image is None:
                if not args.output:
                    sys.stdout.buffer.write(raw)
                raise ValueError("No inline image found. Check the original response for a result URL or other format")
            with args.save_image.open("xb") as out:
                out.write(image)
        elif args.output:
            with args.output.open("xb") as out:
                shutil.copyfileobj(response, out)
        elif response.headers.get_content_type() == "text/event-stream":
            for line in response:
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
        else:
            shutil.copyfileobj(response, sys.stdout.buffer)
    return 0


def safe_request_id(value):
    return " request ID " + value if value and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) else ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("catalog", help="List Model Square entries and current token access")
    listing.add_argument("--kind", choices=("image", "text", "embedding", "audio"))
    listing.add_argument("--model", help="Exact model ID")
    call = commands.add_parser("call", help="Validate a request, or send once with --execute")
    call.add_argument("--model", required=True)
    call.add_argument("--endpoint", required=True, help="Endpoint name shown in catalog")
    call.add_argument("--payload", required=True, help="JSON file, or - to read JSON from stdin")
    call.add_argument("--file", action="append", default=[], help="Multipart attachment FIELD=PATH (repeatable)")
    call.add_argument("--output", type=Path, help="New file for the raw response")
    call.add_argument("--save-image", type=Path, help="New file for decoded original image bytes")
    call.add_argument("--timeout", type=float)
    call.add_argument("--execute", action="store_true", help="Send one potentially billable inference request")
    args = parser.parse_args()
    base = os.environ.get("LTS4AI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    key = os.environ.get("LTS4AI_API_KEY") or None
    try:
        origin = service_origin(base)
        if base not in {origin, origin + "/v1"}:
            raise ValueError("LTS4AI_BASE_URL must be the service origin or end in /v1")
        if args.command == "call" and not key:
            raise ValueError("Set LTS4AI_API_KEY to use the authenticated catalog and send requests")
        entries = catalog(origin, key)
        if args.command == "call":
            return invoke(args, origin, key, entries)
        entries = [row for row in entries if (not args.kind or args.kind in row["capabilities"])
                   and (not args.model or row["id"] == args.model)]
        print(json.dumps({"source": "authenticated" if key else "public", "models": entries}, ensure_ascii=True, indent=2))
        return 0 if entries or not args.model else 3
    except urllib.error.HTTPError as error:
        print("HTTP " + str(error.code) + safe_request_id(error.headers.get("x-oneapi-request-id") or
              error.headers.get("x-request-id")), file=sys.stderr)
    except (json.JSONDecodeError, binascii.Error, UnicodeError, OSError, TypeError, KeyError, AttributeError):
        print("LTS4AI request or file processing failed. Check input and original request status.", file=sys.stderr)
    except ValueError as error:
        print(str(error), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
