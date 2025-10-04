from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Agent-RAG-Docs (stub)")

class RetrieveReq(BaseModel):
    query: str

@app.get("/healthz")
def healthz():
    return {"status":"ok"}

@app.post("/retrieve")
def retrieve(r: RetrieveReq):
    return {"evidence":[{"doc_id":"demo-doc","page":1,"snippet":"Exemplo de evidência"}]}
