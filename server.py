"""Zero-dependency server (Python 3.10+ standard library; the AI model needs scikit-learn).
Run:  python server.py   then open http://127.0.0.1:8000
Same routes as api.py; see deservia/routes.py for every endpoint and who may call it."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from deservia import routes, service

STATIC = Path(__file__).parent / "static"
FILES = {"/": ("index.html", "text/html; charset=utf-8"),
         "/static/app.js": ("app.js", "application/javascript; charset=utf-8"),
         "/static/style.css": ("style.css", "text/css; charset=utf-8")}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _token(self):
        h = self.headers.get("Authorization", "")
        return h[7:] if h.startswith("Bearer ") else None

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in FILES:
            name, ctype = FILES[path]
            return self._send(200, (STATIC / name).read_bytes(), ctype)
        self._send(*routes.dispatch("GET", path, {}, self._token()))

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self._send(400, {"detail": "Body must be JSON"})
        self._send(*routes.dispatch("POST", self.path.split("?")[0], body, self._token()))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    from deservia import auth
    host = os.environ.get("HOST", "127.0.0.1")          # Render: HOST=0.0.0.0
    port = int(os.environ.get("PORT", "8000"))          # Render provides PORT
    service.load_users_into_pool()
    print(f"Deservia on http://{host}:{port}", flush=True)
    if auth.owner_password_is_default():
        print("  Owner:     owner@deservia.ca / admin1234   (set DESERVIA_ADMIN_PASSWORD before going public)")
    else:
        print("  Owner:     owner@deservia.ca / (password from DESERVIA_ADMIN_PASSWORD)")
    print("  Tenants:   alex@demo.ca, sam@demo.ca         / demo1234")
    print("  Landlords: maple@demo.ca, sandalwood@demo.ca / demo1234", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
