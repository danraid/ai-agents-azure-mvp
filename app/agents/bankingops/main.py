from fastapi import FastAPI
from typing import Dict

app = FastAPI(title="Agent-BankingOps (stub)")

@app.get("/healthz")
def healthz():
    return {"status":"ok"}

@app.get("/transactions")
def transactions(range: str = "this_month") -> Dict:
    items = [
        {"date":"2025-10-02","desc":"Supermercado","amount":-25.90},
        {"date":"2025-10-03","desc":"Salário","amount":3500.00},
    ]
    return {"range": range, "items": items}
