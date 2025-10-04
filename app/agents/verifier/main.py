from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Agent-Verifier (stub)")

class Evidence(BaseModel):
    doc_id: str
    page: Optional[int] = None
    snippet: Optional[str] = None

class CheckReq(BaseModel):
    answer: str
    evidence: List[Evidence] = []

@app.get("/healthz")
def healthz():
    return {"status":"ok"}

@app.post("/check")
def check(c: CheckReq):
    return {"ok": bool(c.answer)}
