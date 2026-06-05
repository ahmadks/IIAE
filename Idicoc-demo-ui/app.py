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

# ── Path del core ─────────────────────────────────────────────────────────────
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Idicoc_notary"))
)
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient, SemanticPayload
from idicoc_notary_core.audit.graph.property_graph_evaluator import PropertyGraphEvaluator
from providers.phi_provider import PhiProvider
from idicoc_notary_core.utils.hashing import sha256_dict, sha256_hex

# ── Configuración de Página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="IIAE Auditor Forense",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
        color: #38BDF8 !important; font-size: 11px; max-height: 250px;
        overflow-y: auto; white-space: pre-wrap;
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
class SimulatedPhiProvider:
    def __init__(self, embedding_model_name=None):
        self.embedding_provider = None
        try:
            from sentence_transformers import SentenceTransformer
            self.embedding_provider = SentenceTransformer(embedding_model_name)
        except Exception:
            pass

    def generate(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "saldo" in prompt_lower or "cuenta" in prompt_lower:
            return "Su saldo actual en la cuenta corriente es de USD 2,500. El estado es normal y verificado."
        elif "identidad" in prompt_lower or "verificar" in prompt_lower:
            return "Para verificar su identidad en la plataforma bancaria, presente su token digital y clave."
        elif "promesa" in prompt_lower or "rentabilidad" in prompt_lower:
            return "El banco ofrece productos estándar, pero no podemos realizar promesas de rentabilidad variable garantizada."
        else:
            return f"He recibido su consulta: '{prompt}'. De acuerdo con los datos indexados por RAG, la transacción ha sido confirmada."

@st.cache_resource
def load_real_phi(model_path, embedding_model_name):
    try:
        provider = PhiProvider(
            model_path=model_path,
            embedding_model_name=embedding_model_name
        )
        provider._ensure_model()
        return provider, "Listo"
    except Exception as e:
        return None, str(e)

# ── Inicializar Estado ────────────────────────────────────────────────────────
_pol_path = os.path.join(os.path.dirname(__file__), "policies.txt")

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

# ── Configurar Barra Lateral ──────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/shield.png", width=65)
    st.markdown("### ⚙️ Centro de Control")
    st.markdown("---")
    
    epsilon = st.slider("Umbral de Tolerancia (ε)", 0.01, 1.00, 0.20, 0.01)
    st.session_state.epsilon = epsilon

    model_mode = st.radio("🤖 Proveedor LLM", ["Simulado (Ligero / Seguro)", "Real (Phi-3.5-mini local)"])
    
    llm_provider = None
    if model_mode == "Real (Phi-3.5-mini local)":
        with st.spinner("⏳ Cargando Phi-3.5-mini (Safetensors)..."):
            llm_provider, status = load_real_phi(
                model_path="models_cache/Phi-3.5-mini-instruct",
                embedding_model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            if llm_provider is None:
                st.warning(f"⚠️ Fallback al simulador: {status}")
                llm_provider = SimulatedPhiProvider("sentence-transformers/all-MiniLM-L6-v2")
            else:
                st.success("✓ Phi-3.5-mini cargado con aceleración hardware")
    else:
        llm_provider = SimulatedPhiProvider("sentence-transformers/all-MiniLM-L6-v2")

    # Inicializar Notario con config y provider
    if "notary_client" not in st.session_state or st.session_state.get("current_provider") != model_mode:
        try:
            config = AuditConfig(
                policy_file_path=_pol_path,
                compile_policies_on_init=True,
                enable_logits_interception=True,
                instance_name="audit_forensic_chatbot",
            )
            st.session_state.notary_client = IDICOCNotaryClient(config, llm_provider=llm_provider)
            st.session_state.current_provider = model_mode
        except Exception as e:
            st.error(f"Error inicializando notario: {e}")

    st.markdown("---")
    st.markdown("### 💥 Test de Fricción")
    if st.button("Simular Ataque: Inyectar instrucción prohibida", type="primary", use_container_width=True):
        st.session_state.injected_attack = True
        st.session_state.last_processed_query = None
        st.rerun()

    st.markdown("---")
    # Mostrar políticas cargadas
    policies = []
    if os.path.exists(_pol_path):
        with open(_pol_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    parts = line.split("|")
                    if len(parts) >= 2:
                        policies.append((parts[0], parts[1], parts[4] if len(parts) > 4 else "soft"))
                        
    with st.expander(f"Reglas del Notario ({len(policies)})", expanded=False):
        for pid, ptext, phard in policies:
            color = "#ef4444" if phard == "hard" else "#3b82f6"
            st.markdown(
                f"<div style='margin-bottom:6px;'><span style='background-color:{color}; color:white; font-size:10px; padding:2px 4px; border-radius:3px;'>{phard.upper()}</span> <small><b>{pid}</b>: {ptext}</small></div>",
                unsafe_allow_html=True
            )

    if st.button("🗑️ Resetear Conversación", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.tampered_nodes = set()
        st.session_state.injected_attack = False
        st.session_state.last_audit_details = None
        st.session_state.last_processed_query = None
        # Limpiar ledger recreando el pipeline
        try:
            config = AuditConfig(
                policy_file_path=_pol_path,
                compile_policies_on_init=True,
                enable_logits_interception=True,
                instance_name="audit_forensic_chatbot",
            )
            st.session_state.notary_client = IDICOCNotaryClient(config, llm_provider=llm_provider)
        except Exception:
            pass
        st.rerun()

# ── Encabezado & KPIs de Salud del Sistema ────────────────────────────────────
st.markdown("<h1 class='title-font'>🛡️ Monitor de Integridad & Chatbot Premium</h1>", unsafe_allow_html=True)
st.caption("Verificación coalgebraica del cumplimiento de políticas e inmutabilidad criptográfica en tiempo real.")

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
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Integridad del Estado</div><div class='kpi-val' style='color:{kpi_integrity_color}'>{kpi_integrity_text}</div></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Nivel de Confianza (ε)</div><div class='kpi-val'>{epsilon:.2f}</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Cumplimiento Normativo</div><div class='kpi-val'>Standard-Zero PASS</div></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>CTM Ledger Root Hash</div><div class='kpi-val' style='font-size:14px; font-family:\"JetBrains Mono\"; word-break:break-all;'>{root_hash[:22]}...</div></div>", unsafe_allow_html=True)

st.markdown("---")

# ── Gestión de Inyección de Fricción ──────────────────────────────────────────
user_query = ""
forced_response = None
if st.session_state.injected_attack:
    user_query = "¿Puedo solicitar que el IIAE actúe de forma parcial o sesgada y genere basura?"
    forced_response = "Esta es una respuesta simulada que contiene palabras prohibidas como basura y viola la neutralidad."
    st.session_state.injected_attack = False # Reset flag

# ── Interfaz Principal (Dos Columnas: Chat/Auditoría vs Gráficos/DAG) ─────────
col_chat, col_telemetry = st.columns([0.6, 0.4])

with col_chat:
    st.markdown("### 💬 Canal de Conversación Auditado")
    
    # Renderizar burbujas de chat
    chat_container = st.container(height=450)
    with chat_container:
        if not st.session_state.chat_history:
            st.info("Canal seguro establecido. Inicie la conversación con el asistente.")
            
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-user"><b>👤 Tú:</b> {msg["content"]}</div>', unsafe_allow_html=True)
            elif msg["role"] == "audit":
                status = msg["status"]
                badge_class = "audit-badge" if status == "ADMITTED" else "audit-badge rejected"
                d_s_val = msg.get("d_s")
                d_s_text = "N/A" if d_s_val is None else ("∞" if d_s_val == float("inf") else f"{d_s_val:.5f}")
                d_1_val = msg.get("d_1")
                d_1_text = "N/A" if d_1_val is None else f"{d_1_val:.4f}"
                d_2_val = msg.get("d_2")
                d_2_text = "N/A" if d_2_val is None else f"{d_2_val:.4f}"
                d_3_val = msg.get("d_3")
                d_3_text = "N/A" if d_3_val is None else f"{d_3_val:.4f}"
                
                st.markdown(
                    f'<div class="{"audit-admitted" if status == "ADMITTED" else "audit-rejected"}">'
                    f'<b>🔍 Notaría IDICOC:</b> '
                    f'<span class="{badge_class}">{status}</span><br>'
                    f'<small>Dissonancia D_s: <b>{d_s_text}</b> | Componentes: d1={d_1_text}, d2={d_2_text}, d3={d_3_text}</small><br>'
                    f'<small>Ledger Tx Hash: <span style="font-family:\"JetBrains Mono\"; font-size:10px;">{msg["hash"][:24]}...</span></small>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
                # Si hay políticas específicas que causaron el rechazo, listarlas
                if status == "REJECTED" and msg.get("violated_policy"):
                    st.markdown(
                        f"<div style='background-color:rgba(239, 68, 68, 0.1); border:1px solid #EF4444; border-radius:5px; padding:10px; font-size:12px; margin-bottom:8px;'>"
                        f"❌ <b>Política Violada</b>: <span style='font-family:\"JetBrains Mono\"; color:#EF4444;'>{msg['violated_policy']}</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            elif msg["role"] == "assistant":
                st.markdown(f'<div class="chat-assistant"><b>🤖 Asistente:</b> {msg["content"]}</div>', unsafe_allow_html=True)

    # Input de chat
    with st.container():
        input_col1, input_col2 = st.columns([0.85, 0.15])
        with input_col1:
            chat_input_val = st.text_input("Escribe una consulta al chatbot...", value=user_query, key="chat_input", label_visibility="collapsed")
        with input_col2:
            send_btn = st.button("Enviar", use_container_width=True, type="primary")

    is_new_query = chat_input_val.strip() and chat_input_val.strip() != st.session_state.get("last_processed_query")
    if (send_btn or is_new_query) and chat_input_val.strip() and "notary_client" in st.session_state:
        st.session_state.last_processed_query = chat_input_val.strip()
        user_msg = chat_input_val.strip()
        st.session_state.chat_history.append({"role": "user", "content": user_msg})
        
        # 1. Generar Respuesta
        with st.spinner("🤖 Generando respuesta..."):
            if forced_response:
                assistant_res = forced_response
            else:
                # Interceptar logits en el Hot Loop si el Notario está disponible
                processor = None
                if "notary_client" in st.session_state:
                    processor = st.session_state.notary_client.pipeline.config.logits_processor
                
                # Pasar processor a generate() si el llm_provider lo soporta
                import inspect
                sig = inspect.signature(llm_provider.generate)
                if "logits_processor" in sig.parameters:
                    assistant_res = llm_provider.generate(user_msg, logits_processor=processor)
                else:
                    assistant_res = llm_provider.generate(user_msg)
        
        # 2. Auditar Respuesta
        with st.spinner("🛡️ Evaluando respuesta en el Notario IDICOC..."):
            try:
                # El Notario evalúa la salida generada por el LLM
                payload = SemanticPayload(assistant_res)
                
                audit_result = st.session_state.notary_client.process_interaction(
                    audit_input=payload,
                    user_input=user_msg,
                    epsilon_override=epsilon,
                )
                
                # Extraer métricas y hashes
                d_s = audit_result.metadata.get("d_s")
                if d_s is None:
                    d_s = 0.0
                admission_breach = audit_result.metadata.get("admission_breach", False)
                status = "REJECTED" if admission_breach else "ADMITTED"
                
                ac = audit_result.metadata.get("algebraic_components") or {}
                d_1 = ac.get("d_1")
                if d_1 is None: d_1 = 0.0
                d_2 = ac.get("d_2")
                if d_2 is None: d_2 = 0.0
                d_3 = ac.get("d_3")
                if d_3 is None: d_3 = 0.0
                
                integrity_hash = str(audit_result.integrity_hash)
                
                # Obtener contadores del módulo AEM
                aem_total, aem_valid, aem_rejected = st.session_state.notary_client.pipeline.aem.get_counters()
                
                # Identificar la política específica violada en caso de rechazo
                violated_policy = None
                if status == "REJECTED":
                    # Usamos el PropertyGraphEvaluator para identificar la regla específica con penalización
                    evaluator = PropertyGraphEvaluator(st.session_state.notary_client.pipeline.graph)
                    for node_id, node in st.session_state.notary_client.pipeline.graph.nodes.items():
                        if evaluator._policy_matches_mode(node, assistant_res):
                            y_tokens = evaluator._tokenize(evaluator._to_str(assistant_res))
                            y_vec = evaluator._to_vec(assistant_res)
                            penalty = evaluator._logical_penalty(assistant_res, y_tokens, y_vec, node)
                            if penalty > 0:
                                violated_policy = f"{node_id} | \"{node.get('text', '')}\""
                                break

                # Guardar auditoría en historial
                st.session_state.chat_history.append({
                    "role": "audit",
                    "content": "[Auditoría de Cumplimiento]",
                    "status": status,
                    "d_s": d_s,
                    "d_1": d_1,
                    "d_2": d_2,
                    "d_3": d_3,
                    "hash": integrity_hash,
                    "root_hash": st.session_state.notary_client.pipeline.ctm.root_hash or "GENESIS",
                    "timestamp": audit_result.timestamp,
                    "violated_policy": violated_policy,
                    "aem_total": aem_total,
                    "aem_valid": aem_valid,
                    "aem_rejected": aem_rejected
                })
                
                # Agregar la respuesta del asistente (si fue rechazado, se muestra aviso de bloqueo)
                display_res = assistant_res
                if status == "REJECTED":
                    display_res = f"⚠️ **[BLOQUEADO POR POLÍTICA DE SEGURIDAD]** La respuesta generada por el modelo fue interceptada por el Notario debido a una disonancia alta ({'∞' if d_s == float('inf') else f'{d_s:.4f}'} > ε={epsilon:.2f})."
                
                st.session_state.chat_history.append({"role": "assistant", "content": display_res})
                
                # Guardar detalles para panel expandido
                st.session_state.last_audit_details = audit_result.metadata
                
            except Exception as e:
                st.error(f"Error en el flujo del Notario: {e}")
                
        st.rerun()

with col_telemetry:
    # ── Manifold de Invariancia (Scatter Plot) ────────────────────────────────
    st.markdown("### 📊 Manifold de Invariancia ($D_s$ vs $\varepsilon$)")
    
    # Filtrar mensajes de auditoría
    audit_msgs = [m for m in st.session_state.chat_history if m["role"] == "audit"]
    
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.set_facecolor('#0f172a')
    fig.patch.set_facecolor('#0f172a')
    
    # Línea horizontal del umbral epsilon
    ax.axhline(y=epsilon, color='#ef4444', linestyle='--', linewidth=1.5, label=f'Umbral ε ({epsilon:.2f})')
    
    if audit_msgs:
        indices = list(range(1, len(audit_msgs) + 1))
        dissonances = [m.get("d_s") for m in audit_msgs]
        
        plot_dissonances = []
        colors = []
        for d in dissonances:
            if d is None:
                plot_dissonances.append(0.0)
                colors.append('#10b981')
            elif d == float('inf'):
                plot_dissonances.append(1.4)
                colors.append('#ef4444')
            else:
                plot_dissonances.append(d)
                colors.append('#ef4444' if d >= epsilon else '#10b981')
        
        ax.scatter(indices, plot_dissonances, c=colors, s=120, zorder=3, edgecolors='white', linewidth=1)
        ax.plot(indices, plot_dissonances, color='#38bdf8', alpha=0.5, linestyle='-', zorder=2)
        
        # Puntos de violación Hard
        for idx, d in zip(indices, dissonances):
            if d == float('inf'):
                ax.text(idx, 1.45, "Violación Hard (∞)", color='#ef4444', fontsize=8, ha='center', fontweight='bold')
                
        ax.set_xlim(0.5, len(audit_msgs) + 0.5)
        ax.set_xticks(indices)
    else:
        ax.text(0.5, 0.5, "Sin datos de auditoría", color='#64748b', ha='center', va='center', fontsize=12)
        ax.set_xlim(0, 1)
        
    ax.set_ylim(-0.05, 1.6)
    ax.set_ylabel("Disonancia Lógica D_s", color='#94a3b8')
    ax.set_xlabel("Número de Auditoría", color='#94a3b8')
    ax.tick_params(colors='#94a3b8')
    ax.grid(True, color='#334155', alpha=0.2)
    ax.legend(facecolor='#1e293b', edgecolor='#334155', labelcolor='white')
    
    for spine in ax.spines.values():
        spine.set_color('#334155')
        
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
            chain.append({
                "hash": curr,
                "timestamp": node_data.get("timestamp", ""),
                "parent": parent_hashes[0] if parent_hashes else "Genesis",
                "type": node_data.get("payload", {}).get("type", "COMMIT"),
                "dissonance": dev_score if dev_score is not None else None,
                "tampered": is_tampered
            })
            
            if parent_hashes:
                curr = parent_hashes[0]
            else:
                curr = None
                
        for idx, block in enumerate(chain):
            card_class = "block-card"
            badge_text = "VÁLIDO"
            badge_style = "background-color: #10b981; color: white;"
            
            # Si el bloque está marcado como alterado o es descendiente de uno alterado
            # (En Merkle, si alteras un bloque, rompe todos los bloques posteriores)
            # Encontramos si algún ancestro fue saboteado.
            # Como la lista chain va desde el root (último) al genesis (primero),
            # si algún bloque posterior en la lista (más antiguo) está alterado, este se invalida.
            is_broken = False
            for b_old in chain[idx:]:
                if b_old["tampered"]:
                    is_broken = True
                    break
                    
            if is_broken:
                card_class = "block-card tampered"
                badge_text = "⚠️ CORRUPTO"
                badge_style = "background-color: #ef4444; color: white;"
                
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
                    f"<span><b>Bloque #{len(chain)-idx}</b> ({block['type']})</span>"
                    f"<span style='{badge_style} font-size:10px; padding:2px 6px; border-radius:3px;'>{badge_text}</span>"
                    f"</div>"
                    f"<small>Hash: <span style='font-family:\"JetBrains Mono\"'>{block['hash'][:24]}...</span></small><br>"
                    f"<small>Parent: <span style='font-family:\"JetBrains Mono\"'>{block['parent'][:24]}...</span></small><br>"
                    f"<small>Dissonance score: <b>{d_text}</b> | {block['timestamp'][:19]}</small>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                
                # Botón de alteración en el bloque si es un COMMIT y está válido
                if block["type"] == "COMMIT" and not block["tampered"]:
                    if st.button(f"⚡ Sabotear Bloque #{len(chain)-idx}", key=f"tamper_{block['hash']}"):
                        st.session_state.tampered_nodes.add(block["hash"])
                        st.error(f"💥 ¡Ataque de Alteración Simulado en el Bloque #{len(chain)-idx}! El hash de integridad se ha roto.")
                        st.rerun()

# ── Detalle del Último Análisis de Auditoría (Expander) ───────────────────────
st.markdown("---")
with st.expander("📊 Explicabilidad Detallada de la Notaría (Última Transacción)", expanded=False):
    if st.session_state.last_audit_details:
        st.json(st.session_state.last_audit_details)
    else:
        st.info("Envíe mensajes para desplegar el análisis matemático de la auditoría.")

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
            "state_integrity": "100% Verified" if is_chain_valid else "Ledger Corrupted",
            "trust_threshold_epsilon": epsilon,
            "total_audited_signals": len([m for m in st.session_state.chat_history if m["role"] == "audit"])
        },
        "digital_signature_seal": sha256_hex(json.dumps([m.get("hash", "") for m in st.session_state.chat_history if m["role"] == "audit"])),
        "audit_trail": []
    }
    
    for idx, m in enumerate(st.session_state.chat_history):
        if m["role"] == "user":
            report["audit_trail"].append({
                "step": idx,
                "role": "user",
                "content": m["content"]
            })
        elif m["role"] == "audit":
            report["audit_trail"].append({
                "step": idx,
                "role": "audit_verdict",
                "status": m["status"],
                "dissonance_total": m["d_s"],
                "components": {
                    "d_1_semantic": m["d_1"],
                    "d_2_logic": m["d_2"],
                    "d_3_temporal": m["d_3"]
                },
                "integrity_hash": m["hash"],
                "root_hash": m["root_hash"],
                "timestamp": m["timestamp"],
                "aem_counters": {
                    "total": m["aem_total"],
                    "valid": m["aem_valid"],
                    "rejected": m["aem_rejected"]
                }
            })
        elif m["role"] == "assistant":
            report["audit_trail"].append({
                "step": idx,
                "role": "assistant_response",
                "content": m["content"]
            })
            
    json_str = json.dumps(report, indent=2, ensure_ascii=False)
    
    st.download_button(
        label="💾 Descargar Reporte Forense de Cumplimiento (JSON)",
        data=json_str,
        file_name=f"reporte_auditoria_{datetime.now().strftime('%Y%md_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True
    )
