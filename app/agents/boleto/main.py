from fastapi import FastAPI, UploadFile, File, HTTPException
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import os, uuid, datetime

app = FastAPI(title="Agent-Boleto (MVP)")

STORAGE_CONN = os.getenv("STORAGE_CONN", "")
CONTAINER = os.getenv("BOLETO_CONTAINER", "boletos")

@app.get("/healthz")
def healthz():
    return {"status":"ok"}

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    if not STORAGE_CONN:
        raise HTTPException(status_code=500, detail="Missing STORAGE_CONN")
    data = await file.read()
    doc_id = str(uuid.uuid4())
    blob = BlobServiceClient.from_connection_string(STORAGE_CONN)
    container = blob.get_container_client(CONTAINER)
    container.upload_blob(f"{doc_id}.pdf", data, overwrite=True, content_type="application/pdf")
    return {"doc_id": doc_id, "filename": file.filename}

@app.get("/search")
def search(range: str = "this_week"):
    if not STORAGE_CONN:
        raise HTTPException(status_code=500, detail="Missing STORAGE_CONN")
    blob = BlobServiceClient.from_connection_string(STORAGE_CONN)
    container = blob.get_container_client(CONTAINER)
    items = [{"doc_id": b.name.replace(".pdf","")} for b in container.list_blobs() if b.name.endswith(".pdf")]
    return {"range": range, "items": items}

@app.get("/pdf/{doc_id}")
def get_pdf(doc_id: str):
    if not STORAGE_CONN:
        raise HTTPException(status_code=500, detail="Missing STORAGE_CONN")
    blob = BlobServiceClient.from_connection_string(STORAGE_CONN)
    container = blob.get_container_client(CONTAINER)
    name = f"{doc_id}.pdf"
    if not container.get_blob_client(name).exists():
        raise HTTPException(status_code=404, detail="not found")
    # Atenção: para produção, use Managed Identity; aqui é demo com chave na conn string.
    sas = generate_blob_sas(
        account_name=blob.account_name,
        container_name=CONTAINER,
        blob_name=name,
        account_key=blob.credential.account_key if hasattr(blob.credential, "account_key") else None,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
    )
    url = f"https://{blob.account_name}.blob.core.windows.net/{CONTAINER}/{name}?{sas}"
    return {"url": url}
