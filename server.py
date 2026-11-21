"""Zero-dependency backup server (Python 3.10+ standard library only). Same endpoints as api.py.
Run:  python server.py   then open http://127.0.0.1:8000
Use this if pip / FastAPI isn't working on demo day."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from deservia import service

STATIC = Path(__file__).parent / "static"
GET = {"/api/tenants": service.list_tenants, "/api/listings": service.list_listings,
       "/api/admin/metrics": service.metrics, "/api/admin/audit": service.audit,
       "/api/admin/model": service.model_card, "/api/learning": service.learning_status}
POST = {"/api/match": service.match, "/api/check-text": service.check,
        "/api/profiles": lambda b: service.profiles(b.get("role", "tenant")),
        "/api/deck": service.deck, "/api/swipe": service.swipe, "/api/retrain": service.retrain,
        "/api/feedback/reset": service.reset_feedback}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path in GET:
            return self._send(200, GET[self.path]())
        self._send(404, {"detail": "Not found"})

    def do_POST(self):
        if self.path not in POST:
            return self._send(404, {"detail": "Not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            self._send(200, POST[self.path](body))
        except KeyError as e:
            self._send(404, {"detail": str(e)})
        except (ValueError, TypeError) as e:
            self._send(400, {"detail": f"Bad request: {e}"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("Deservia matching demo on http://127.0.0.1:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
