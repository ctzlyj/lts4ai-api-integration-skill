import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import lts4ai


class CatalogTests(unittest.TestCase):
    def test_only_authorized_image_models_are_offered_with_verified_endpoints(self):
        pricing = {"success": True, "data": [
            {"model_name": "gpt-image-2.6", "supported_endpoint_types": ["openai"]},
            {"model_name": "gemini-image-fixture", "supported_endpoint_types": ["gemini"],
             "image_request_billing": "submitted_attempt"},
            {"model_name": "private-image", "supported_endpoint_types": ["image-generation"]},
        ]}
        models = {"data": [{"id": key} for key in (
            "gpt-image-2.6", "gemini-image-fixture", "token-only-id",
        )]}
        with patch.object(lts4ai, "request_json", side_effect=[pricing, models]) as get:
            entries = {row["id"]: row for row in lts4ai.catalog("https://lts4ai.test", "fixture")}
        self.assertNotIn("private-image", entries)
        self.assertEqual(set(entries["gpt-image-2.6"]["endpoints"]), {"image-generation", "image-edit"})
        self.assertEqual(entries["gemini-image-fixture"]["capabilities"], ["image"])
        self.assertEqual(entries["token-only-id"]["endpoints"], {})
        self.assertIsNone(get.call_args_list[0].args[1])

    def test_gemini_and_chat_inline_outputs_keep_original_bytes(self):
        gemini = {"candidates": [{"content": {"parts": [
            {"inlineData": {"mimeType": "image/png", "data": "AAEC"}},
        ]}}]}
        chat = {"choices": [{"message": {"images": [
            {"image_url": {"url": "data:image/png;base64,AAEC"}},
        ]}}]}
        for response in (gemini, chat):
            self.assertEqual(lts4ai.image_from_json(response), bytes([0, 1, 2]))

    def test_prepared_native_request_uses_the_exact_model_in_the_path(self):
        path, payload = lts4ai.payload_for(lts4ai.ROUTES["gemini"], "vendor/image", {"contents": []}, True)
        self.assertEqual(path, "/v1beta/models/vendor%2Fimage:generateContent")
        self.assertNotIn("model", payload)
        with self.assertRaises(ValueError):
            lts4ai.payload_for(lts4ai.ROUTES["image-generation"], "model", {"n": 2}, True)


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.posts = []
        self.status = 200
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send_json(self, status, body):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("x-request-id", "fixture-id")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def do_GET(self):
                if self.path == "/api/pricing":
                    self.send_json(200, {"success": True, "data": [{"model_name": "gpt-image-2.6"}]})
                elif self.path == "/v1/models" and self.headers["Authorization"] == "Bearer fixture-key":
                    self.send_json(200, {"data": [{"id": "gpt-image-2.6"}]})
                else:
                    self.send_json(404, {})

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                owner.posts.append((self.path, self.headers["Content-Type"], body))
                self.send_json(owner.status, {"data": [{"b64_json": "AAEC"}]})

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.output = self.directory / "image.png"
        self.reference = self.directory / "reference.png"
        self.reference.write_bytes(b"fixture-reference")

    def stop_server(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def run_call(self, endpoint, *args):
        command = [sys.executable, str(Path(lts4ai.__file__)), "call", "--model", "gpt-image-2.6",
                   "--endpoint", endpoint, "--payload", "-", *args]
        env = {**os.environ, "LTS4AI_BASE_URL": f"http://127.0.0.1:{self.server.server_port}/v1",
               "LTS4AI_API_KEY": "fixture-key"}
        result = subprocess.run(command, input='{"prompt":"fixture"}', text=True, capture_output=True,
                                timeout=10, env=env)
        self.assertNotIn("fixture-key", result.stdout + result.stderr)
        return result

    def test_dry_run_then_single_billable_edit_and_original_output(self):
        args = ["--file", f"image={self.reference}", "--save-image", str(self.output)]
        self.assertEqual(self.run_call("image-edit", *args).returncode, 0)
        self.assertEqual(self.posts, [])
        result = self.run_call("image-edit", *args, "--execute")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.posts), 1)
        path, content_type, body = self.posts[0]
        self.assertEqual(path, "/v1/images/edits")
        self.assertIn("multipart/form-data", content_type)
        self.assertIn(b"fixture-reference", body)
        self.assertIn(b"gpt-image-2.6", body)
        self.assertEqual(self.output.read_bytes(), bytes([0, 1, 2]))

    def test_timeout_like_response_sends_no_second_post(self):
        self.status = 504
        result = self.run_call("image-generation", "--execute")
        self.assertEqual(result.returncode, 1)
        self.assertIn("504", result.stderr)
        self.assertEqual(len(self.posts), 1)
