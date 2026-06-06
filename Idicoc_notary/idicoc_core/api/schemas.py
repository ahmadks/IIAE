from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class SessionContext(BaseModel):
    user_prompt: str = Field(..., description="El prompt original inyectado por el usuario")
    rag_context: str = Field(default="", description="El contexto extraído de la base de conocimiento (RAG)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class NotaryAuditResult(BaseModel):
    is_admitted: bool = Field(..., description="Veredicto de paso (True) o contención/rechazo (False)")
    integrity_score: float = Field(..., ge=0.0, le=1.0, description="1.0 equivale a Invarianza Coálgebraica Terminal")
    dissonance_ds: float = Field(..., description="D_s absoluto (puede ser infinito (inf) si hay ruptura 'Hard')")
    allowed_epsilon: float = Field(..., description="Tolerancia paramétrica configurada (épsilon)")
    violated_policies: List[str] = Field(default_factory=list, description="IDs o textos de los axiomas quebrantados")
    session_context: SessionContext
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Desglose matemático y penalizaciones")
