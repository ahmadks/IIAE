"""
Chatbot con Llama + IDICOC Notary (Standard-Zero Integration)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Idicoc_notary"))

from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient


class LlamaChatbot:
    """Chatbot con auditoría en tiempo real."""

    def __init__(self, policies_file="policies.txt"):
        self.notary = None
        self.tokenizer = None
        self.model = None

        try:
            # Inicializar Notary con políticas
            print("[Init] Cargando config...")
            self.config = AuditConfig(
                policy_file_path=policies_file,
                compile_policies_on_init=True,
                instance_name="demo_chatbot",
            )
            self.notary = IDICOCNotaryClient(self.config)
            print(
                f"[Init] ✓ Notary listo con {len(self.config.w_bank or {})} tokens prohibidos"
            )
        except Exception as e:
            print(f"[Init] ⚠️ Sin auditoría disponible: {e}")

    def chat(self, user_input: str, context: list = None) -> dict:
        """
        Procesa entrada del usuario con auditoría.

        Returns:
            {
                "user_input": str,
                "audit_result": dict,
                "metadata": dict,
            }
        """
        context = context or []

        result = {
            "user_input": user_input,
            "audit_result": None,
            "metadata": {},
        }

        # Auditoría
        if self.notary:
            try:
                audit_output = self.notary.process_interaction(
                    audit_input="",
                    context_input=context,
                    user_input=user_input,
                    epsilon_override=0.0,
                )

                result["audit_result"] = {
                    "d_s": audit_output.metadata.get("d_s", 0.0),
                    "status": (
                        "ADMITTED"
                        if not audit_output.metadata.get("admission_breach")
                        else "REJECTED"
                    ),
                    "integrity_hash": str(audit_output.integrity_hash)[:20] + "...",
                }
                result["metadata"]["audit_timestamp"] = audit_output.timestamp
            except Exception as e:
                result["metadata"]["audit_error"] = str(e)

        return result
