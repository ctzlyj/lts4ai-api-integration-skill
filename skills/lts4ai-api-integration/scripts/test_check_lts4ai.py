import contextlib
import io
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
import check_lts4ai as checker


class Tests(unittest.TestCase):
    def test_rejects_credential_bearing_or_insecure_remote_urls(self):
        for url in ("https://user:secret@example.org/v1", "https://example.org/v1?key=secret", "https://example.org/v1#secret", "http://example.org/v1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                checker.service_origin(url)

    def test_production_and_local_urls(self):
        self.assertEqual(checker.service_origin("https://api.lts4ai.com/v1"), "https://api.lts4ai.com")
        self.assertEqual(checker.service_origin("http://127.0.0.1:8000/v1"), "http://127.0.0.1:8000")

    def test_exact_model_ids_and_invalid_shapes(self):
        self.assertEqual(checker.model_ids({"data": [{"id": "gpt-image-2.6"}, {"id": "vendor/model"}]}), ["gpt-image-2.6", "vendor/model"])
        with self.assertRaises(ValueError):
            checker.model_ids({"error": "denied"})

    def test_redirect_never_reaches_target_with_bearer(self):
        target_hits = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302); self.send_header("Location", "/target"); self.end_headers()
                else:
                    target_hits.append(self.headers.get("Authorization")); self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with self.assertRaises(urllib.error.HTTPError) as error:
                checker.request_json(f"http://127.0.0.1:{server.server_port}/redirect", "fixture-only", 2)
            self.assertEqual(error.exception.code, 302); self.assertEqual(target_hits, [])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_pricing_and_authentication_checks_never_send_inference(self):
        urls = []
        def fake(url, key, timeout):
            urls.append(url)
            if url.endswith("/api/status"): return {"success": True}
            if url.endswith("/api/pricing"): return {"success": True, "data": [{"model_name": "gpt-image-2.6", "max_images_per_request": 1}]}
            if url.endswith("/v1/models"): return {"data": [{"id": "gpt-image-2.6"}]}
            raise AssertionError("Unexpected endpoint")
        with patch("sys.argv", ["check", "--pricing", "--model", "gpt-image-2.6"]), patch.dict("os.environ", {"LTS4AI_API_KEY": "fixture-only", "LTS4AI_BASE_URL": checker.DEFAULT_BASE_URL}), patch.object(checker, "request_json", fake), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(checker.main(), 0)
        self.assertEqual(len(urls), 3); self.assertNotIn("fixture-only", output.getvalue())


if __name__ == "__main__": unittest.main()
