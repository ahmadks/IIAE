"""
IIAE Demo UI + Chatbot con Standard-Zero (sin Llama gateado)
Simula respuestas del LLM pero preserva auditoría en tiempo real del IDICOC Notary
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Idicoc_notary"))

import streamlit as st
import json
from datetime import datetime
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient

# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="IIAE Chatbot + Standard-Zero",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .chat-user {
        background-color: #334155; padding: 12px; border-radius: 8px;
        margin: 8px 0; border-left: 4px solid #3b82f6;
    }
    .chat-assistant {
        background-color: #1e3a5f; padding: 12px; border-radius: 8px;
        margin: 8px 0; border-left: 4px solid #10b981;
    }
    .audit-admitted {
        background-color: #10b98122; border: 1px solid #10b981; padding: 12px;
        border-radius: 8px; margin: 8px 0; border-left: 4px solid #10b981;
    }
    .audit-rejected {
        background-color: #ef444422; border: 1px solid #ef4444; padding: 12px;
        border-radius: 8px; margin: 8px 0; border-left: 4px solid #ef4444;
    }
    .audit-badge {
        display: inline-block; padding: 4px 8px; border-radius: 4px;
        background-color: #10b981; color: white; font-size: 12px; font-weight: bold;
    }
    .audit-badge.rejected {
        background-color: #ef4444;
    }
    .metric-card {
        background-color: #0f172a; padding: 12px; border-radius: 8px;
        border: 1px solid #334155; margin: 8px 0;
    }
    code { background-color: #0f172a; color: #38bdf8; padding: 2px 6px; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Inicializar sesión ────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "notary_client" not in st.session_state:
    with st.spinner("🔧 Inicializando IDICOC Notary + Standard-Zero..."):
        try:
            config = AuditConfig(
                policy_file_path=os.path.join(
                    os.path.dirname(__file__), "policies.txt"
                ),
                compile_policies_on_init=True,
                instance_name="demo_chatbot",
            )
            st.session_state.notary_client = IDICOCNotaryClient(config)
            st.session_state.config = config
            st.session_state.notary_ready = True
            st.success("✓ IDICOC Notary listo (Fase 1 + Fase 2)")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.session_state.notary_ready = False

# ── Interfaz Principal ────────────────────────────────────────────────────────
st.title("🛡️ IIAE Chatbot + Standard-Zero Auditoría")
st.caption("Chatbot con auditoría determinística en tiempo real")

# ── Barra lateral ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración")

    # Contexto RAG
    context_mode = st.radio(
        "📋 Contexto de la sesión", ["Sin contexto", "Bancario", "Técnico"]
    )

    context_input = []
    if context_mode == "Bancario":
        context_input = [
            "El cliente tiene 5 años de antigüedad",
            "Saldo disponible: USD 2,500",
            "Límite diario de transferencia: USD 50,000",
            "Última transacción: hace 3 días",
        ]
    elif context_mode == "Técnico":
        context_input = [
            "Sistema IIAE v2.0 (Standard-Zero)",
            "Runtime: Python 3.10+",
            "Modelos: embeddings + NLI",
            "Auditoría: Fase 1 + Fase 2 activas",
        ]

    st.session_state.context_input = context_input

    st.markdown("---")
    if context_mode != "Sin contexto":
        st.markdown("**📌 Contexto Activo:**")
        for i, ctx in enumerate(context_input, 1):
            st.caption(f"{i}. {ctx}")

    st.markdown("---")

    # Controles
    show_audit = st.checkbox("🔍 Mostrar detalles de auditoría", value=True)
    st.session_state.show_audit = show_audit

    epsilon = st.slider("Umbral de tolerancia (ε)", 0.01, 1.0, 0.20, 0.01)
    st.session_state.epsilon = epsilon

    st.markdown("---")

    if st.button("🗑️ Limpiar historial"):
        st.session_state.chat_history = []
        st.rerun()

# ── Historial de chat ─────────────────────────────────────────────────────────
st.markdown("### 💬 Conversación")

for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(
            f'<div class="chat-user"><b>👤 Tú:</b> {msg["content"]}</div>',
            unsafe_allow_html=True,
        )
    elif msg["role"] == "audit":
        status = msg.get("status", "?")
        badge_class = "audit-badge" if status == "ADMITTED" else "audit-badge rejected"
        d_s = msg.get("d_s", 0.0)
        hash_val = msg.get("hash", "?")[:12]

        audit_class = "audit-admitted" if status == "ADMITTED" else "audit-rejected"
        st.markdown(
            f'<div class="{audit_class}">'
            f"<b>🔍 Auditoría IDICOC:</b> "
            f'<span class="{badge_class}">{status}</span><br>'
            f"<small>D_s: {d_s:.6f} | Hash: {hash_val}... | Phase: 2 (Interacción)</small>"
            f"</div>",
            unsafe_allow_html=True,
        )
    elif msg["role"] == "assistant":
        st.markdown(
            f'<div class="chat-assistant"><b>🤖 Assistant:</b> {msg["content"]}</div>',
            unsafe_allow_html=True,
        )

# ── Input de usuario ──────────────────────────────────────────────────────────
st.markdown("---")

col1, col2 = st.columns([0.85, 0.15])
with col1:
    user_input = st.text_input(
        "Escribe tu pregunta...",
        placeholder="Ej: ¿Cuál es el saldo de mi cuenta?",
        label_visibility="collapsed",
    )
with col2:
    send_button = st.button("📤 Enviar", use_container_width=True)

# ── Procesar entrada ──────────────────────────────────────────────────────────
if (send_button or user_input) and user_input.strip() and st.session_state.notary_ready:

    # Agregar entrada del usuario
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # ═════════════════════════════════════════════════════════════════════════
    # FASE 2: AUDITORÍA EN TIEMPO REAL (IDICOC Notary)
    # ═════════════════════════════════════════════════════════════════════════

    with st.spinner("🔍 Auditando entrada con IDICOC Notary (Fase 2)..."):
        try:
            from idicoc_notary_core.audit import SemanticPayload
            audit_result = st.session_state.notary_client.process_interaction(
                audit_input=SemanticPayload(""),
                context_input=st.session_state.context_input,
                user_input=user_input,
                epsilon_override=st.session_state.epsilon,
            )

            # Extraer resultados de auditoría
            audit_status = "ADMITTED"
            if audit_result.metadata.get("admission_breach"):
                audit_status = "REJECTED"

            d_s = audit_result.metadata.get("d_s", 0.0)
            hash_str = (
                str(audit_result.integrity_hash)
                if hasattr(audit_result, "integrity_hash")
                else "N/A"
            )

            # Guardar en historial
            st.session_state.chat_history.append(
                {
                    "role": "audit",
                    "content": f"[Fase 2 completada]",
                    "status": audit_status,
                    "d_s": d_s,
                    "hash": hash_str,
                    "timestamp": (
                        audit_result.timestamp
                        if hasattr(audit_result, "timestamp")
                        else str(datetime.now())
                    ),
                    "metadata": audit_result.metadata,
                }
            )

            # Mostrar detalles si está habilitado
            if st.session_state.show_audit:
                with st.expander("📊 Detalles de Auditoría (Fase 2)", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    col1.metric(
                        "Estado",
                        audit_status,
                        delta="✓" if audit_status == "ADMITTED" else "✗",
                    )
                    col2.metric("Disonancia (D_s)", f"{d_s:.6f}")
                    col3.metric(
                        "Timestamp",
                        (
                            audit_result.timestamp[:10]
                            if hasattr(audit_result, "timestamp")
                            else "N/A"
                        ),
                    )

                    st.markdown("**Metadata de Auditoría:**")
                    with st.expander("Ver JSON", expanded=False):
                        st.json(audit_result.metadata)

        except Exception as e:
            st.error(f"❌ Error en auditoría: {str(e)}")

    # ═════════════════════════════════════════════════════════════════════════
    # RESPUESTA SIMULADA DEL ASISTENTE
    # ═════════════════════════════════════════════════════════════════════════

    mock_response = f"""Analicé tu pregunta sobre: **"{user_input[:50]}..."**

**Información procesada:**
- 🎯 Contexto: {len(st.session_state.context_input)} fragmentos cargados
- 📋 Modo: {context_mode}
- ✓ Auditoría: **{audit_status}** (D_s={d_s:.4f})

**Respuesta:** Este es un ejemplo de respuesta simulada. En producción, se usaría Llama-3-8B-Instruct con contención sub-simbólica (Fase 3 Hot Loop).

---
*ℹ️ Sistema Standard-Zero: Fase 1 (Cold Loop) ✓ | Fase 2 (Interacción) ✓ | Fase 3 (Generación) ⏸️*"""

    st.session_state.chat_history.append(
        {"role": "assistant", "content": mock_response}
    )

    st.rerun()

elif not st.session_state.notary_ready:
    st.warning("⚠️ IDICOC Notary no está disponible. Revisa los logs de configuración.")

# ── Panel de estadísticas ─────────────────────────────────────────────────────
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Mensajes procesados",
        len([m for m in st.session_state.chat_history if m["role"] == "user"]),
    )

with col2:
    audit_count = len(
        [m for m in st.session_state.chat_history if m["role"] == "audit"]
    )
    admitted = len(
        [
            m
            for m in st.session_state.chat_history
            if m["role"] == "audit" and m.get("status") == "ADMITTED"
        ]
    )
    st.metric("Auditorías completadas", audit_count, delta=f"{admitted} ADMITTED")

with col3:
    st.caption(f"**Versión:** Standard-Zero | **Fase activa:** 2 (Interacción)")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
---
**IIAE Standard-Zero Demo** | Auditoría determinística en Fase 2
- ✓ Fase 1 (Cold Loop): Compilación de políticas
- ✓ Fase 2 (Interacción): Auditoría de entrada del usuario
- ⏸️ Fase 3 (Hot Loop): Generación con contención (Requiere Llama autorizado)
- ⏸️ Fase 4 (Consolidación): Trazabilidad en CTM WAL

[📚 Docs](https://github.com/iiae) | [🐛 Issues](https://github.com/iiae/issues) | [⭐ Star](https://github.com/iiae)
""")
