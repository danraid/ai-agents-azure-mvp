from pydantic import BaseModel
from typing import List, Optional

class Evidence(BaseModel):
    doc_id: str
    page: Optional[int] = None
    snippet: Optional[str] = None

class AskRequest(BaseModel):
    user_id: str
    text: str

class AskResponse(BaseModel):
    answer: str
    evidence: List[Evidence] = []
