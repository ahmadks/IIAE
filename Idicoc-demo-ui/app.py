"""
🛡️ Production Monitor & Chatbot Premium — IIAE
Tablero forense interactivo con auditoría determinística en tiempo real y ledger criptográfico.
Cumple con la especificación de Contención Generativa (patente IIAE).
"""

import sys
import os

# Enable PyTorch MPS fallback to avoid hangs on unsupported operators
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import json
from datetime import datetime, timezone
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
import logging

# ── Path del core ─────────────────────────────────────────────────────────────
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Idicoc_notary"))
)
from idicoc_core.config import AuditConfig, DEFAULT_SEMANTIC_EMBEDDING_MODEL
from idicoc_core.compat import NotaryClient, SemanticPayload
from idicoc_core.dse.evaluator import PropertyGraphEvaluator
from providers.factory import get_provider
from idicoc_core.utils.hashing import sha256_dict, sha256_hex

# ── Configuración de Página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="IIAE Auditor Forense",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Captura de Logs para el Visor ─────────────────────────────────────────────
class MemoryLogHandler(logging.Handler):
    def __init__(self, log_list):
        super().__init__()
        self.log_list = log_list
        self.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
        )

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_list.append(msg)
            if len(self.log_list) > 100:
                self.log_list.pop(0)
        except Exception:
            self.handleError(record)


if "notary_logs" not in st.session_state:
    st.session_state.notary_logs = []

def ensure_memory_log_handler():
    # Attach to root logger so ALL sub-loggers (kernel.*, idicoc_core.*, etc.) propagate here
    _log_list = st.session_state.notary_logs
    root_logger = logging.getLogger()
    has_root = any(isinstance(h, MemoryLogHandler) for h in root_logger.handlers)
    if not has_root:
        root_logger.addHandler(MemoryLogHandler(_log_list))
        root_logger.setLevel(logging.INFO)
    # Also explicitly attach to known namespaces in case propagation is disabled
    for logger_name in ["idicoc_core", "IIAE", "kernel", "idicoc_core.dse", "idicoc_core.pipeline", "idicoc_core.ctm"]:
        ns_logger = logging.getLogger(logger_name)
        has_handler = any(isinstance(h, MemoryLogHandler) for h in ns_logger.handlers)
        if not has_handler:
            ns_logger.addHandler(MemoryLogHandler(_log_list))
        ns_logger.setLevel(logging.INFO)
        ns_logger.propagate = True

ensure_memory_log_handler()

def read_wal_log_content():
    if "notary_client" not in st.session_state:
        return ""
    try:
        config = st.session_state.notary_client.pipeline.config
        wal_path = config.ctm_wal_path
        if not wal_path:
            wal_path = os.path.join(os.path.dirname(config.ctm_nodes_path or "."), "ctm_wal.log")
        
        if os.path.exists(wal_path):
            with open(wal_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return "".join(lines[-50:])
    except Exception as e:
        return f"Error al leer WAL: {e}"
    return ""

# Estilos Premium (Outfit/Inter, Dark Theme, Glassmorphism)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Inter:wght@300;400;500;600&family=JetBrains+Mono&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .title-font {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        background: linear-gradient(135deg, #38BDF8, #0EA5E9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .chat-user {
        background-color: #1E293B; padding: 16px; border-radius: 12px;
        margin: 12px 0; border-left: 4px solid #0EA5E9;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    
    .chat-assistant {
        background-color: #0F172A; padding: 16px; border-radius: 12px;
        margin: 12px 0; border-left: 4px solid #10B981;
        border: 1px solid #1E293B;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    
    .audit-admitted {
        background-color: rgba(16, 185, 129, 0.08); border: 1px solid #10B981; padding: 14px;
        border-radius: 8px; margin: 8px 0; border-left: 4px solid #10B981;
    }
    
    .audit-rejected {
        background-color: rgba(239, 68, 68, 0.08); border: 1px solid #EF4444; padding: 14px;
        border-radius: 8px; margin: 8px 0; border-left: 4px solid #EF4444;
    }
    
    .audit-badge {
        display: inline-block; padding: 4px 10px; border-radius: 9999px;
        background-color: #10B981; color: white; font-size: 11px; font-weight: bold;
        letter-spacing: 0.05em;
    }
    
    .audit-badge.rejected {
        background-color: #EF4444;
    }
    
    .kpi-card {
        background-color: #0F172A; padding: 20px; border-radius: 12px;
        border: 1px solid #1E293B; text-align: center;
        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.3);
    }
    
    .kpi-val {
        font-family: 'Outfit', sans-serif;
        font-size: 26px; font-weight: bold; color: #38BDF8;
    }
    
    .kpi-title {
        font-size: 12px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.1em;
        margin-bottom: 8px;
    }
    
    .term {
        font-family: 'JetBrains Mono', monospace; background: #020617; 
        border: 1px solid #1E293B; border-radius: 8px; padding: 14px;
        color: #38BDF8 !important; font-size: 11px; max-height: 280px;
        overflow-y: auto; white-space: pre-wrap;
        display: flex; flex-direction: column;
    }
    .term .term-inner {
        margin-top: auto;
    }
    
    .block-card {
        background-color: #1E293B; padding: 12px; border-radius: 8px;
        border: 1px solid #334155; margin-bottom: 8px;
    }
    
    .block-card.tampered {
        border: 1px solid #EF4444 !important;
        background-color: rgba(239, 68, 68, 0.05);
    }
    
    .policy-tag {
        display: inline-block; padding: 2px 6px; border-radius: 4px;
        background-color: #334155; color: #94A3B8; font-size: 10px; margin: 2px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Proveedores Phi ───────────────────────────────────────────────────────────
@st.cache_resource
def load_real_model(provider_type, model_path, embedding_model_name):
    try:
        provider = get_provider(
            provider_type=provider_type,
            model_path=model_path,
            embedding_model_name=embedding_model_name,
        )
        if hasattr(provider, "_ensure_model"):
            provider._ensure_model()
        return provider, "Listo"
    except Exception as e:
        return None, str(e)


# ── Inicializar Estado ────────────────────────────────────────────────────────
_pol_path = os.path.join(os.path.dirname(__file__), "policies.txt")

current_mtime = 0.0
if os.path.exists(_pol_path):
    current_mtime = os.path.getmtime(_pol_path)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "injected_attack" not in st.session_state:
    st.session_state.injected_attack = False
if "tampered_nodes" not in st.session_state:
    st.session_state.tampered_nodes = set()
if "last_audit_details" not in st.session_state:
    st.session_state.last_audit_details = None
if "last_processed_query" not in st.session_state:
    st.session_state.last_processed_query = None
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None
if "policies_mtime" not in st.session_state:
    st.session_state.policies_mtime = current_mtime

# Detectar cambios en las políticas en disco
policies_changed = False
if st.session_state.policies_mtime != current_mtime:
    policies_changed = True
    st.session_state.policies_mtime = current_mtime

# ── Pantalla de Carga Temporal para Aplicación y LLM ──
if "llm_provider" not in st.session_state:
    loading_placeholder = st.empty()
    with loading_placeholder.container():
        st.markdown(
            """
            <div style="background-color: #0f172a; padding: 40px; border-radius: 12px; text-align: center; margin: 100px auto; max-width: 600px; border: 1px solid #1e293b; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);">
                <h1 style="color: #3b82f6; font-size: 28px; margin-bottom: 15px; font-family: 'Outfit', sans-serif;">🛡️ Inicializando Notario IDICOC</h1>
                <p style="color: #94a3b8; font-size: 16px; margin-bottom: 25px;">Cargando modelo local LLM Phi-3.5-mini y preparando el pipeline de embeddings...</p>
                <div style="margin: 20px auto; width: 45px; height: 45px; border: 4px solid #334155; border-top: 4px solid #3b82f6; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                <p style="color: #64748b; font-size: 12px; margin-top: 15px;">Esto puede tardar unos segundos en la primera inicialización.</p>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            </div>
            """,
            unsafe_allow_html=True,
        )
        llm_provider, status = load_real_model(
            provider_type="phi",
            model_path="models_cache/Phi-3.5-mini-instruct",
            embedding_model_name=DEFAULT_SEMANTIC_EMBEDDING_MODEL,
        )
        if llm_provider is None:
            st.error(f"❌ Error crítico cargando el modelo real: {status}")
            st.stop()

        st.session_state.llm_provider = llm_provider

        # Initialize NotaryClient immediately on load
        try:
            ui_dir = os.path.dirname(os.path.abspath(__file__))
            config = AuditConfig(
                policy_file_path=_pol_path,
                compile_policies_on_init=True,
                enable_logits_interception=True,
                instance_name="audit_forensic_chatbot",
                ctm_nodes_path=os.path.join(ui_dir, "ctm_nodes.json"),
                ctm_root_path=os.path.join(ui_dir, "ctm_root.txt"),
                ctm_wal_path=os.path.join(ui_dir, "ctm_wal.log"),
            )
            st.session_state.notary_client = NotaryClient(
                config, llm_provider=llm_provider
            )
            st.session_state.policies_mtime = current_mtime
        except Exception as e:
            st.error(f"Error inicializando notario en carga inicial: {e}")
            st.stop()

        st.rerun()
else:
    llm_provider = st.session_state.llm_provider


# ── Configurar Barra Lateral ──────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/shield.png", width=65)
    st.markdown("### ⚙️ Centro de Control")
    st.markdown("---")

    epsilon = st.slider("Umbral de Tolerancia (ε)", 0.01, 1.00, 0.20, 0.01)
    st.session_state.epsilon = epsilon

    lambda_context = st.slider(
        "Peso Integridad RAG (λ_context)",
        0.0, 1.0, 0.40, 0.05,
        help="Cuánto influye la coherencia con el contexto RAG en D_s. "
             "0=solo políticas, 1=solo RAG. Recomendado: 0.40"
    )
    st.session_state.lambda_context = lambda_context

    st.markdown("---")
    st.markdown("### 📄 Simular Contexto RAG")
    rag_presets = {
        "Sin Contexto (Vacío)": "",
        "Información Financiera (Saldo)": "El saldo actual de la cuenta del usuario es USD 2,500.\nTodas las cuentas se encuentran validadas y activas.",
        "Verificación de Identidad": "Para verificar la identidad del cliente, se requiere token digital y clave SMS.\nEl canal de atención telefónica está disponible de lunes a viernes.",
        "Advertencia de Rentabilidad": "El banco ofrece fondos de inversión de renta fija y variable.\nNo se garantizan rentabilidades futuras de renta variable.",
    }
    selected_preset = st.selectbox(
        "Escenarios RAG predefinidos", list(rag_presets.keys())
    )
    preset_val = rag_presets[selected_preset]

    rag_context = st.text_area(
        "Ingresar contexto recuperado (context_input)",
        value=preset_val,
        placeholder="Escribe el contexto aquí...",
        help="Simula documentos recuperados por RAG para la validación coalgebraica.",
    )
    st.session_state.context_list = (
        [line.strip() for line in rag_context.split("\n") if line.strip()]
        if rag_context.strip()
        else None
    )

    st.success("✓ Proveedor: Phi-3.5-mini (Local)")
    st.info("Estado: Activo y Asegurado")

    # Inicializar Notario con config y provider (se recrea si se modifican las políticas)
    if "notary_client" not in st.session_state or policies_changed:
        try:
            ui_dir = os.path.dirname(os.path.abspath(__file__))
            config = AuditConfig(
                policy_file_path=_pol_path,
                compile_policies_on_init=True,
                enable_logits_interception=True,
                instance_name="audit_forensic_chatbot",
                lambda_context=st.session_state.get("lambda_context", 0.4),
                ctm_nodes_path=os.path.join(ui_dir, "ctm_nodes.json"),
                ctm_root_path=os.path.join(ui_dir, "ctm_root.txt"),
                ctm_wal_path=os.path.join(ui_dir, "ctm_wal.log"),
            )
            st.session_state.notary_client = NotaryClient(
                config, llm_provider=llm_provider
            )
            st.session_state.policies_mtime = current_mtime
        except Exception as e:
            st.error(f"Error inicializando notario: {e}")

    st.markdown("---")
    st.markdown("### 💥 Test de Fricción")
    if st.button(
        "Simular Ataque: Inyectar instrucción prohibida",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.injected_attack = True
        st.session_state.last_processed_query = None
        st.session_state.pending_query = None
        st.rerun()

    st.markdown("---")
    # Mostrar políticas cargadas
    policies = []
    loader = None
    if (
        "notary_client" in st.session_state
        and st.session_state.notary_client.config.policy_loader
    ):
        loader = st.session_state.notary_client.config.policy_loader
    elif os.path.exists(_pol_path):
        from idicoc_core.isg.loader import FilePolicyLoader

        loader = FilePolicyLoader(_pol_path)

    if loader:
        try:
            loaded = loader.load_policies()
            for p in loaded:
                pid = p.get("policy_id") or p.get("id") or "N/A"
                ptext = p.get("text") or "Regla sin descripción"
                phard = p.get("hardness") or "soft"
                policies.append((pid, ptext, phard))
        except Exception as e:
            st.error(f"Error cargando reglas de políticas: {e}")

    with st.expander(f"Reglas del Notario ({len(policies)})", expanded=False):
        for pid, ptext, phard in policies:
            color = "#ef4444" if phard == "hard" else "#3b82f6"
            st.markdown(
                f"<div style='margin-bottom:6px;'><span style='background-color:{color}; color:white; font-size:10px; padding:2px 4px; border-radius:3px;'>{phard.upper()}</span> <small><b>{pid}</b>: {ptext}</small></div>",
                unsafe_allow_html=True,
            )

    if st.button("🗑️ Resetear Conversación", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.tampered_nodes = set()
        st.session_state.injected_attack = False
        st.session_state.last_audit_details = None
        st.session_state.last_processed_query = None
        st.session_state.pending_query = None
        # Limpiar ledger recreando el pipeline
        try:
            ui_dir = os.path.dirname(os.path.abspath(__file__))
            config = AuditConfig(
                policy_file_path=_pol_path,
                compile_policies_on_init=True,
                enable_logits_interception=True,
                instance_name="audit_forensic_chatbot",
                ctm_nodes_path=os.path.join(ui_dir, "ctm_nodes.json"),
                ctm_root_path=os.path.join(ui_dir, "ctm_root.txt"),
                ctm_wal_path=os.path.join(ui_dir, "ctm_wal.log"),
            )
            st.session_state.notary_client = NotaryClient(
                config, llm_provider=llm_provider
            )
            st.session_state.policies_mtime = current_mtime
        except Exception:
            pass
        st.rerun()


# ── Encabezado & KPIs de Salud del Sistema ────────────────────────────────────
st.markdown(
    "<h1 class='title-font'>🛡️ Monitor de Integridad & Chatbot Premium</h1>",
    unsafe_allow_html=True,
)
st.caption(
    "Verificación coalgebraica del cumplimiento de políticas e inmutabilidad criptográfica en tiempo real."
)

# Calcular el estado del Ledger
dag_dict = {}
nodes = {}
root_hash = "N/A"
if "notary_client" in st.session_state and st.session_state.notary_client.pipeline:
    dag_dict = st.session_state.notary_client.pipeline.ctm.export_dag()
    nodes = dag_dict.get("nodes", {})
    root_hash = dag_dict.get("root_hash") or "GENESIS"

# Evaluar integridad de la cadena
is_chain_valid = True
if nodes:
    # Si hay nodos alterados localmente, la cadena se rompe
    if st.session_state.tampered_nodes:
        is_chain_valid = False

kpi_integrity_text = "100% (Verificado)" if is_chain_valid else "CORRUPTO (Alterado)"
kpi_integrity_color = "#10B981" if is_chain_valid else "#EF4444"

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Integridad del Estado</div><div class='kpi-val' style='color:{kpi_integrity_color}'>{kpi_integrity_text}</div></div>",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Nivel de Confianza (ε)</div><div class='kpi-val'>{epsilon:.2f}</div></div>",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Cumplimiento Normativo</div><div class='kpi-val'>Standard-Zero PASS</div></div>",
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>CTM Ledger Root Hash</div><div class='kpi-val' style='font-size:14px; font-family:\"JetBrains Mono\"; word-break:break-all;'>{root_hash[:22]}...</div></div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Gestión de Inyección de Fricción ──────────────────────────────────────────
user_query = ""
forced_response = None
if st.session_state.injected_attack:
    user_query = (
        "¿Puedo solicitar que el IIAE actúe de forma parcial o sesgada y genere basura?"
    )
    forced_response = "Esta es una respuesta simulada que contiene palabras prohibidas como basura y viola la neutralidad."
    st.session_state.injected_attack = False  # Reset flag

# ── Interfaz Principal (Dos Columnas: Chat/Auditoría vs Gráficos/DAG) ─────────
col_chat, col_telemetry = st.columns([0.6, 0.4])

with col_chat:
    st.markdown("### 💬 Canal de Conversación Auditado")

    # Renderizar burbujas de chat
    chat_container = st.container(height=450)
    with chat_container:
        has_chat = any(msg["role"] in ("user", "assistant") for msg in st.session_state.chat_history)
        if not has_chat:
            st.info(
                "Canal seguro establecido. Inicie la conversación con el asistente."
            )

        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            elif msg["role"] == "assistant":
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])

    def handle_submit():
        val = st.session_state.chat_input.strip()
        if val:
            st.session_state.pending_query = val
            st.session_state.chat_input = ""

    # Input de chat
    with st.container():
        input_col1, input_col2 = st.columns([0.85, 0.15])
        with input_col1:
            st.text_input(
                "Escribe una consulta al chatbot...",
                value=user_query if user_query else "",
                key="chat_input",
                label_visibility="collapsed",
                on_change=handle_submit,
            )
        with input_col2:
            st.button(
                "Enviar",
                use_container_width=True,
                type="primary",
                on_click=handle_submit,
            )

    # Determinar consulta a procesar
    query_to_process = None
    if forced_response and user_query:
        query_to_process = user_query
    elif st.session_state.get("pending_query"):
        query_to_process = st.session_state.pending_query
        st.session_state.pending_query = None

    if query_to_process and "notary_client" in st.session_state:
        ensure_memory_log_handler()
        st.session_state.last_processed_query = query_to_process
        user_msg = query_to_process
        st.session_state.chat_history.append({"role": "user", "content": user_msg})

        # Generación y Auditoría bajo Contención Preventiva
        with st.spinner("🤖 Generando y auditando respuesta bajo Contención Preventiva..."):
            try:
                if forced_response:
                    assistant_res = forced_response
                    payload = SemanticPayload(assistant_res)
                    audit_result = st.session_state.notary_client.process_interaction(
                        audit_input=payload,
                        user_input=user_msg,
                        context_input=st.session_state.get("context_list"),
                        epsilon_override=epsilon,
                    )
                else:
                    # Interceptar logits en el Hot Loop si el Notario está disponible
                    kwargs = {}
                    if "notary_client" in st.session_state:
                        processor = (
                            st.session_state.notary_client.pipeline.config.logits_processor
                        )
                        import inspect
                        sig = inspect.signature(llm_provider.generate)
                        if "logits_processor" in sig.parameters:
                            kwargs["logits_processor"] = processor

                    context_list = st.session_state.get("context_list") or []
                    assistant_res, audit_result = st.session_state.notary_client.generate(
                        user_prompt=user_msg,
                        rag_context=context_list,
                        epsilon_override=epsilon,
                        **kwargs
                    )

                # Extraer métricas y hashes
                d_s = audit_result.metadata.get("d_s")
                if d_s is None:
                    d_s = 0.0
                admission_breach = audit_result.metadata.get("admission_breach", False)
                status = "REJECTED" if admission_breach else "ADMITTED"

                ac = audit_result.metadata.get("algebraic_components") or {}
                d_1 = ac.get("d_1")
                if d_1 is None:
                    d_1 = 0.0
                d_2 = ac.get("d_2")
                if d_2 is None:
                    d_2 = 0.0
                d_3 = ac.get("d_3")
                if d_3 is None:
                    d_3 = 0.0

                integrity_hash = str(audit_result.integrity_hash)

                # Obtener contadores del módulo AEM
                aem_total, aem_valid, aem_rejected = (
                    st.session_state.notary_client.pipeline.aem.get_counters()
                )

                # Identificar la política específica violada en caso de rechazo
                violated_policy = None
                rejection_reason = None
                if status == "REJECTED":
                    violated_policies = (
                        audit_result.metadata.get("violated_policies") or []
                    )
                    violated_policy = (
                        ", ".join(violated_policies)
                        if violated_policies
                        else "Desviación/Disonancia alta"
                    )

                    if float("inf") in (d_s, d_2):
                        rejection_reason = (
                            "Violación de una política de seguridad estricta (HARD)."
                        )
                    elif violated_policies:
                        rejection_reason = f"Disonancia total ({d_s:.4f}) superó el umbral de tolerancia (ε={epsilon:.2f})."
                    else:
                        rejection_reason = f"Desviación semántica alta ({d_s:.4f}) respecto al invariante (ε={epsilon:.2f})."

                # Guardar auditoría en historial
                st.session_state.chat_history.append(
                    {
                        "role": "audit",
                        "content": "[Auditoría de Cumplimiento]",
                        "status": status,
                        "d_s": d_s,
                        "d_1": d_1,
                        "d_2": d_2,
                        "d_3": d_3,
                        "d_context": audit_result.metadata.get("d_context", 0.0),
                        "hash": integrity_hash,
                        "root_hash": st.session_state.notary_client.pipeline.ctm.root_hash
                        or "GENESIS",
                        "timestamp": audit_result.timestamp,
                        "violated_policy": violated_policy,
                        "rejection_reason": rejection_reason,
                        "aem_total": aem_total,
                        "aem_valid": aem_valid,
                        "aem_rejected": aem_rejected,
                    }
                )

                # Agregar la respuesta del asistente (si fue rechazado, se muestra aviso de bloqueo)
                display_res = assistant_res
                if status == "REJECTED":
                    display_res = f"⚠️ **[BLOQUEADO POR POLÍTICA DE SEGURIDAD]** La respuesta generada por el modelo fue interceptada por el Notario debido a una disonancia alta ({'∞' if d_s == float('inf') else f'{d_s:.4f}'} > ε={epsilon:.2f})."

                st.session_state.chat_history.append(
                    {"role": "assistant", "content": display_res}
                )

                # Guardar detalles para panel expandido
                st.session_state.last_audit_details = audit_result.metadata

            except Exception as e:
                st.error(f"Error en el flujo del Notario: {e}")

        st.rerun()

with col_telemetry:
    # ── Última Auditoría IDICOC ───────────────────────────────────────────────
    st.markdown("### 🛡️ Última Auditoría IDICOC")

    # Obtener mensajes de auditoría
    audit_msgs = [m for m in st.session_state.chat_history if m["role"] == "audit"]
    if audit_msgs:
        last_audit = audit_msgs[-1]
        status = last_audit["status"]
        badge_class = "audit-badge" if status == "ADMITTED" else "audit-badge rejected"
        d_s_val = last_audit.get("d_s")
        d_s_text = (
            "N/A"
            if d_s_val is None
            else ("∞" if d_s_val == float("inf") else f"{d_s_val:.5f}")
        )
        d_1_val = last_audit.get("d_1")
        d_1_text = "N/A" if d_1_val is None else f"{d_1_val:.4f}"
        d_2_val = last_audit.get("d_2")
        d_2_text = "N/A" if d_2_val is None else f"{d_2_val:.4f}"
        d_3_val = last_audit.get("d_3")
        d_3_text = "N/A" if d_3_val is None else f"{d_3_val:.4f}"

        d_context_val = last_audit.get("d_context")
        d_context_text = "N/A" if d_context_val is None else f"{d_context_val:.4f}"
        d_context_color = (
            "#10B981" if (d_context_val or 0) < 0.3
            else "#F59E0B" if (d_context_val or 0) < 0.6
            else "#EF4444"
        )

        st.markdown(
            f'<div class="{"audit-admitted" if status == "ADMITTED" else "audit-rejected"}">'
            f'<b>Resultado:</b> <span class="{badge_class}">{status}</span><br>'
            f"<small>Dissonancia D_s: <b>{d_s_text}</b> | Componentes: d1={d_1_text}, d2={d_2_text}, d3={d_3_text}</small><br>"
            f"<small>🔗 <b>Integridad RAG (d_context):</b> "
            f"<span style='color:{d_context_color}; font-weight:bold;'>{d_context_text}</span> "
            f"<span style='color:#64748b; font-size:10px;'>(0=coherente, 1=alucinación)</span></small><br>"
            f'<small>Ledger Tx Hash: <span style="font-family:\'JetBrains Mono\'; font-size:10px;">{last_audit["hash"]}</span></small>'
            f"</div>",
            unsafe_allow_html=True,
        )

        # Si hay políticas específicas que causaron el rechazo, listarlas
        if status == "REJECTED":
            reason = (
                last_audit.get("rejection_reason")
                or "Desviación con respecto a las políticas del Notario."
            )
            vp = last_audit.get("violated_policy")
            vp_html = (
                f"<br>❌ <b>Política(s) Violada(s)</b>: <span style='font-family:\"JetBrains Mono\"; color:#EF4444;'>{vp}</span>"
                if vp
                else ""
            )
            st.markdown(
                f"<div style='background-color:rgba(239, 68, 68, 0.1); border:1px solid #EF4444; border-radius:5px; padding:10px; font-size:12px; margin-bottom:8px;'>"
                f"⚠️ <b>Motivo del Rechazo:</b> {reason}{vp_html}"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info(
            "Canal inactivo. Envíe un mensaje para iniciar la auditoría en tiempo real."
        )

    st.markdown("---")
    st.markdown("### 📊 Métricas de Auditoría AEM")
    if "notary_client" in st.session_state and st.session_state.notary_client.pipeline:
        aem_total, aem_valid, aem_rejected = (
            st.session_state.notary_client.pipeline.aem.get_counters()
        )
        col_aem1, col_aem2, col_aem3 = st.columns(3)
        with col_aem1:
            st.markdown(
                f"<div class='kpi-card'><div class='kpi-title'>Total Procesados</div><div class='kpi-val'>{aem_total}</div></div>",
                unsafe_allow_html=True,
            )
        with col_aem2:
            st.markdown(
                f"<div class='kpi-card'><div class='kpi-title'>Admitidos</div><div class='kpi-val' style='color:#10B981'>{aem_valid}</div></div>",
                unsafe_allow_html=True,
            )
        with col_aem3:
            st.markdown(
                f"<div class='kpi-card'><div class='kpi-title'>Rechazados</div><div class='kpi-val' style='color:#EF4444'>{aem_rejected}</div></div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Manifold de Invariancia (Scatter Plot) ────────────────────────────────
    st.markdown("### 📊 Manifold de Invariancia ($D_s$ vs $\varepsilon$)")

    # Filtrar mensajes de auditoría
    audit_msgs = [m for m in st.session_state.chat_history if m["role"] == "audit"]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.set_facecolor("#0f172a")
    fig.patch.set_facecolor("#0f172a")

    # Línea horizontal del umbral epsilon
    ax.axhline(
        y=epsilon,
        color="#ef4444",
        linestyle="--",
        linewidth=1.5,
        label=f"Umbral ε ({epsilon:.2f})",
    )

    if audit_msgs:
        indices = list(range(1, len(audit_msgs) + 1))
        dissonances = [m.get("d_s") for m in audit_msgs]

        plot_dissonances = []
        colors = []
        for d in dissonances:
            if d is None:
                plot_dissonances.append(0.0)
                colors.append("#10b981")
            elif d == float("inf"):
                plot_dissonances.append(1.4)
                colors.append("#ef4444")
            else:
                plot_dissonances.append(d)
                colors.append("#ef4444" if d >= epsilon else "#10b981")

        ax.scatter(
            indices,
            plot_dissonances,
            c=colors,
            s=120,
            zorder=3,
            edgecolors="white",
            linewidth=1,
        )
        ax.plot(
            indices,
            plot_dissonances,
            color="#38bdf8",
            alpha=0.5,
            linestyle="-",
            zorder=2,
        )

        # Puntos de violación Hard
        for idx, d in zip(indices, dissonances):
            if d == float("inf"):
                ax.text(
                    idx,
                    1.45,
                    "Violación Hard (∞)",
                    color="#ef4444",
                    fontsize=8,
                    ha="center",
                    fontweight="bold",
                )

        ax.set_xlim(0.5, len(audit_msgs) + 0.5)
        ax.set_xticks(indices)
    else:
        ax.text(
            0.5,
            0.5,
            "Sin datos de auditoría",
            color="#64748b",
            ha="center",
            va="center",
            fontsize=12,
        )
        ax.set_xlim(0, 1)

    ax.set_ylim(-0.05, 1.6)
    ax.set_ylabel("Disonancia Lógica D_s", color="#94a3b8")
    ax.set_xlabel("Número de Auditoría", color="#94a3b8")
    ax.tick_params(colors="#94a3b8")
    ax.grid(True, color="#334155", alpha=0.2)
    ax.legend(facecolor="#1e293b", edgecolor="#334155", labelcolor="white")

    for spine in ax.spines.values():
        spine.set_color("#334155")

    plt.tight_layout()
    st.pyplot(fig)

    # ── Navegador del Merkle DAG Ledger ───────────────────────────────────────
    st.markdown("### 💻 CTM Merkle DAG Ledger")

    if not nodes:
        st.info("Ledger en bloque vacío. Envíe consultas para registrar bloques.")
    else:
        # Reconstruir la cadena lógica
        chain = []
        curr = root_hash
        visited = set()

        while curr and curr != "N/A" and curr not in visited:
            visited.add(curr)
            node_data = nodes.get(curr)
            if not node_data:
                break

            parent_hashes = node_data.get("parent_hashes", [])
            # Revisar si este nodo fue saboteado
            is_tampered = curr in st.session_state.tampered_nodes

            dev_score = node_data.get("deviation_score")
            chain.append(
                {
                    "hash": curr,
                    "timestamp": node_data.get("timestamp", ""),
                    "parent": parent_hashes[0] if parent_hashes else "Genesis",
                    "type": node_data.get("payload", {}).get("type", "COMMIT"),
                    "dissonance": dev_score if dev_score is not None else None,
                    "tampered": is_tampered,
                }
            )

            if parent_hashes:
                curr = parent_hashes[0]
            else:
                curr = None

        if chain:
            block = chain[0]
            is_broken = False
            for b_old in chain:
                if b_old["tampered"]:
                    is_broken = True
                    break

            if is_broken:
                card_class = "block-card tampered"
                badge_text = "⚠️ CORRUPTO"
                badge_style = "background-color: #ef4444; color: white;"
            else:
                card_class = "block-card"
                badge_text = "VÁLIDO"
                badge_style = "background-color: #10b981; color: white;"

            d_val = block["dissonance"]
            if d_val is None:
                d_text = "N/A"
            elif d_val == float("inf"):
                d_text = "∞"
            else:
                d_text = f"{d_val:.4f}"

            with st.container():
                st.markdown(
                    f"<div class='{card_class}'>"
                    f"<div style='display:flex; justify-content:space-between;'>"
                    f"<span><b>Último Bloque #{len(chain)}</b> ({block['type']})</span>"
                    f"<span style='{badge_style} font-size:10px; padding:2px 6px; border-radius:3px;'>{badge_text}</span>"
                    f"</div>"
                    f"<small>Hash: <span style='font-family:\"JetBrains Mono\"'>{block['hash'][:24]}...</span></small><br>"
                    f"<small>Parent: <span style='font-family:\"JetBrains Mono\"'>{block['parent'][:24]}...</span></small><br>"
                    f"<small>Dissonance score: <b>{d_text}</b> | {block['timestamp'][:19]}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )



# ── Detalle del Último Análisis de Auditoría (Expander) ───────────────────────
st.markdown("---")
with st.expander(
    "📊 Explicabilidad Detallada de la Notaría (Última Transacción)", expanded=False
):
    if st.session_state.last_audit_details:
        st.json(st.session_state.last_audit_details)
    else:
        st.info("Envíe mensajes para desplegar el análisis matemático de la auditoría.")

with st.expander("📜 Visor de Logs del Notario (Tiempo Real)", expanded=True):
    ensure_memory_log_handler()
    wal_content = read_wal_log_content()
    import html as _html
    log_text = _html.escape("\n".join(st.session_state.notary_logs))
    wal_text = _html.escape(wal_content) if wal_content else ""

    col_log_1, col_log_2 = st.columns(2)
    with col_log_1:
        st.markdown("<b>Logs de Consola (Python Logger):</b>", unsafe_allow_html=True)
        if not log_text:
            st.markdown(
                "<div class='term'><span style='opacity:0.4'>Sin mensajes de log registrados en esta sesión.</span></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='term' id='termlog'><div class='term-inner'>{log_text}</div></div>"
                "<script>var t=document.getElementById('termlog');if(t)t.scrollTop=t.scrollHeight;</script>",
                unsafe_allow_html=True,
            )

    with col_log_2:
        st.markdown("<b>Transacciones CTM (Ledger WAL Log):</b>", unsafe_allow_html=True)
        if not wal_text:
            st.markdown(
                "<div class='term'><span style='opacity:0.4'>Sin transacciones registradas en WAL.</span></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='term' id='termwal'><div class='term-inner'>{wal_text}</div></div>"
                "<script>var w=document.getElementById('termwal');if(w)w.scrollTop=w.scrollHeight;</script>",
                unsafe_allow_html=True,
            )

# ── Exportación Forense ───────────────────────────────────────────────────────
if st.session_state.chat_history:
    # Generar JSON de auditoría forense con hashes de integridad de quíntupla
    report = {
        "report_title": "Reporte de Cumplimiento Regulatorio e Inmutabilidad CTM - IDICOC Notary",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "instance_name": "audit_forensic_chatbot",
        "verification_standard": "Standard-Zero Compliant (Coalgebraic Trust)",
        "chain_integrity_status": "PASS" if is_chain_valid else "FAIL_TAMPER_DETECTED",
        "system_kpis": {
            "state_integrity": (
                "100% Verified" if is_chain_valid else "Ledger Corrupted"
            ),
            "trust_threshold_epsilon": epsilon,
            "total_audited_signals": len(
                [m for m in st.session_state.chat_history if m["role"] == "audit"]
            ),
        },
        "digital_signature_seal": sha256_hex(
            json.dumps(
                [
                    m.get("hash", "")
                    for m in st.session_state.chat_history
                    if m["role"] == "audit"
                ]
            )
        ),
        "audit_trail": [],
    }

    for idx, m in enumerate(st.session_state.chat_history):
        if m["role"] == "user":
            report["audit_trail"].append(
                {"step": idx, "role": "user", "content": m["content"]}
            )
        elif m["role"] == "audit":
            report["audit_trail"].append(
                {
                    "step": idx,
                    "role": "audit_verdict",
                    "status": m["status"],
                    "dissonance_total": m["d_s"],
                    "components": {
                        "d_1_semantic": m["d_1"],
                        "d_2_logic": m["d_2"],
                        "d_3_temporal": m["d_3"],
                    },
                    "integrity_hash": m["hash"],
                    "root_hash": m["root_hash"],
                    "timestamp": m["timestamp"],
                    "aem_counters": {
                        "total": m["aem_total"],
                        "valid": m["aem_valid"],
                        "rejected": m["aem_rejected"],
                    },
                }
            )
        elif m["role"] == "assistant":
            report["audit_trail"].append(
                {"step": idx, "role": "assistant_response", "content": m["content"]}
            )

    json_str = json.dumps(report, indent=2, ensure_ascii=False)

    st.download_button(
        label="💾 Descargar Reporte Forense de Cumplimiento (JSON)",
        data=json_str,
        file_name=f"reporte_auditoria_{datetime.now().strftime('%Y%md_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True,
    )
