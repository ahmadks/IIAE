from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class SessionContext(BaseModel):
    user_prompt: str
    rag_context: str
    metadata: Optional[Dict[str, Any]] = None

class NotaryAuditResult(BaseModel):
    is_admitted: bool
    integrity_score: float = Field(ge=0.0, le=1.0, description="1.0 is terminal coalgebraic zero-dissonance")
    dissonance_ds: float = Field(description="Raw D_s value")
    allowed_epsilon: float
    violated_policies: List[str]
    session_context: SessionContext
    metrics: Dict[str, Any]
