"""FastAPI backend.  Run:  pip install -r requirements.txt  &&  uvicorn api:app --reload
Open http://127.0.0.1:8000 (app) or http://127.0.0.1:8000/docs (API docs).
Every endpoint and its access level lives in deservia/routes.py.
In /docs, call POST /api/auth/signin, copy the token, click "Authorize" and paste it."""
from pathlib import Path

from fastapi import Body, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from deservia import routes, service

app = FastAPI(title="Deservia matching API",
              description="We match on how you live, never on who you are. "
                          "Access: public / user (tenant or landlord) / agent (website owner).")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
STATIC = Path(__file__).parent / "static"
bearer = HTTPBearer(auto_error=False)


@app.on_event("startup")
def _startup():
    service.load_users_into_pool()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/static/{name}", include_in_schema=False)
def static(name: str):
    if name not in ("app.js", "style.css"):
        return JSONResponse({"detail": "Not found"}, 404)
    return FileResponse(STATIC / name)


def _make(method, path, handler, level):
    def endpoint(body: dict = Body(default={}),
                 cred: HTTPAuthorizationCredentials | None = Depends(bearer)):
        status, payload = routes.dispatch(method, path, body, cred.credentials if cred else None)
        return JSONResponse(payload, status)

    def get_endpoint(cred: HTTPAuthorizationCredentials | None = Depends(bearer)):
        status, payload = routes.dispatch(method, path, {}, cred.credentials if cred else None)
        return JSONResponse(payload, status)

    fn = endpoint if method == "POST" else get_endpoint
    fn.__name__ = path.strip("/").replace("/", "_").replace("-", "_") + "_" + method.lower()
    app.add_api_route(path, fn, methods=[method], summary=f"[{level}] {path}",
                      description=(handler.__doc__ or "").strip(), tags=[level])


for (m, p), (h, lvl) in routes.ROUTES.items():
    _make(m, p, h, lvl)
