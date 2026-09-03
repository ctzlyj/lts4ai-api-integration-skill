#!/usr/bin/env python3
"""Read-only LTS4AI health and model availability checker."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_BASE_URL = "https://api.lts4ai.com/v1"


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def service_origin(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("LTS4AI_BASE_URL must be an absolute HTTP(S) URL")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def request_json(url: str, api_key: str | None, timeout: float) -> object:
    headers = {"Accept": "application/json", "User-Agent": "lts4ai-skill-check/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def model_ids(payload: object) -> list[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("unexpected /v1/models response shape")
    values = []
    for item in payload["data"]:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            values.append(item["id"])
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check LTS4AI health and optionally validate an exact model ID. No inference is sent."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LTS4AI_BASE_URL", DEFAULT_BASE_URL),
        help="OpenAI-compatible Base URL (default: LTS4AI_BASE_URL or production)",
    )
    parser.add_argument("--model", help="Exact model ID to validate through GET /v1/models")
    parser.add_argument("--list", action="store_true", help="Print available model IDs")
    parser.add_argument("--timeout", type=float, default=15.0, help="Request timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        base_url = normalize_base_url(args.base_url)
        status = request_json(f"{service_origin(base_url)}/api/status", None, args.timeout)
        healthy = isinstance(status, dict) and status.get("success") is True
        if not healthy:
            print("LTS4AI public status returned an unexpected response", file=sys.stderr)
            return 1
        print("LTS4AI public status: healthy")

        api_key = os.environ.get("LTS4AI_API_KEY")
        if not api_key:
            if args.model or args.list:
                print("Set LTS4AI_API_KEY in the environment to query models", file=sys.stderr)
                return 2
            print("Authenticated model check: skipped (LTS4AI_API_KEY is not set)")
            return 0

        models = model_ids(request_json(f"{base_url}/models", api_key, args.timeout))
        print(f"Authenticated model check: {len(models)} models available")
        if args.list:
            for model in sorted(models):
                print(model)
        if args.model:
            if args.model not in models:
                print(f"Selected model is unavailable: {args.model}", file=sys.stderr)
                return 3
            print(f"Selected model is available: {args.model}")
        return 0
    except urllib.error.HTTPError as error:
        print(f"LTS4AI check failed with HTTP {error.code}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        print(f"LTS4AI check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
