"""FastAPI backend.  Run:  pip install -r requirements.txt  &&  uvicorn api:app --reload
Then open http://127.0.0.1:8000  (demo page)  or  http://127.0.0.1:8000/docs  (API docs)."""
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from deservia import service

app = FastAPI(title="Deservia matching API",
              description="Lifestyle matching for landlords and tenants. "
                          "We match on how you live, never on who you are.")
# Lets the existing deservia.netlify.app front end call this API during development.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATIC = Path(__file__).parent / "static"


class MatchRequest(BaseModel):
    tenant_id: Optional[str] = None
    tenant: Optional[dict] = None     # full questionnaire answers (see deservia/options.py)
    limit: int = 10


class TextRequest(BaseModel):
    text: str


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/tenants")
def tenants():
    return service.list_tenants()


@app.get("/api/listings")
def listings():
    return service.list_listings()


@app.post("/api/match")
def match(req: MatchRequest):
    try:
        return service.match(req.model_dump())
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/check-text")
def check_text(req: TextRequest):
    return service.check(req.model_dump())


@app.get("/api/admin/metrics")
def metrics():
    return service.metrics()


@app.get("/api/admin/audit")
def audit():
    return service.audit()


@app.get("/api/admin/model")
def model_card():
    return service.model_card()


# ---------------- swipe deck + learning loop
def _call(fn, body):
    try:
        return fn(body)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/profiles")
def profiles(body: dict = Body(...)):
    """Who you can swipe as. body: {"role": "tenant" | "landlord"}"""
    return service.profiles(body.get("role", "tenant"))


@app.post("/api/deck")
def deck(body: dict = Body(...)):
    """Next 10 flashcards. body: {"role": "tenant", "user_id": "t_demo"} or {"role": "landlord", "user_id": "l01"}"""
    return _call(service.deck, body)


@app.post("/api/swipe")
def swipe(body: dict = Body(...)):
    """Record a like/pass. body: {"user_id": "t_demo", "item_id": "l01", "liked": true}"""
    return _call(service.swipe, body)


@app.post("/api/retrain")
def retrain():
    """Retrain the AI model with all swipes, in the background."""
    return service.retrain()


@app.get("/api/learning")
def learning():
    return service.learning_status()


@app.post("/api/feedback/reset")
def reset(body: dict = Body(default={})):
    return service.reset_feedback(body)
