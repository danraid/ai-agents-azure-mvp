from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Agent-Policy (stub)")

class Authz(BaseModel):
    user_id: str
    scope: str

@app.get("/healthz")
def healthz():
    return {"status":"ok"}

@app.post("/authorize")
def authorize(a: Authz):
    # TODO: validar JWT/Entra ID + consentimentos
    if a.scope.startswith("read:"):
        return {"ok": True}
    return {"ok": False}
