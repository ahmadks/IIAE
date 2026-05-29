"""
IIAE Production Monitor — Demo UI (Clean Rewrite)
Notario IDICOC integrado con simulador de audit_input (numérico y semántico).
"""
import sys
import os
import json
import numpy as np
import streamlit as st

# ── Path del core ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Idicoc_notary")))
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient
from IdicocConfg import build_notary_config

# ── Página ────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="IIAE Production Monitor", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono&display=swap');
.term {font-family:'JetBrains Mono',monospace;background:#090D16;border:1px solid #334155; border-radius:6px;padding:12px;color:#38BDF8!important;font-size:11px; height:250px;overflow-y:scroll;white-space:pre-wrap;}
.policy-card {background-color:#1e293b; padding:10px; border-radius:5px; margin-bottom:10px;}
</style>
""", unsafe_allow_html=True)

# ── WAL helper ────────────────────────────────────────────────────────────────
WAL_FILE = os.path.join(os.path.dirname(__file__), "ctm_wal.log")
def tail_wal(path: str, n: int = 15) -> str:
    if not os.path.exists(path):
        return "El archivo WAL todavía no existe. Envía datos al Notario."
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()[-n:]
    return "\n".join(reversed(lines))

# ── Políticas ─────────────────────────────────────────────────────────────────
_pol_path = os.path.join(os.path.dirname(__file__), "policies.txt")
try:
    with open(_pol_path) as _f:
        policies_text = _f.read()
except Exception as _ex:
    policies_text = f"# Error cargando policies.txt: {_ex}"

policies_list = [p.strip() for p in policies_text.splitlines() if p.strip() and not p.startswith("#")]
policies_dicts = []
for i, p in enumerate(policies_list):
    parts = p.split("|")
    if len(parts) >= 3:
        pol = {
            "id": parts[0].strip(),
            "text": parts[1].strip(),
            "policy_type": parts[2].strip(),
            "polarity": parts[3].strip() if len(parts) > 3 else "affirmative",
            "hardness": parts[4].strip() if len(parts) > 4 else "hard",
        }
        for extra in parts[6:]:
            if "=" in extra:
                k, v = extra.split("=", 1)
                pol[k.strip()] = v.strip()
        policies_dicts.append(pol)
    else:
        policies_dicts.append({"id": f"p{i}", "text": p, "policy_type": "semantic", "polarity": "affirmative", "hardness": "soft"})

# ── Sesión y Notario ──────────────────────────────────────────────────────────
if "base_bins" not in st.session_state:
    st.session_state.base_bins = [0.25, 0.25, 0.25, 0.25]
if "context_list" not in st.session_state:
    st.session_state.context_list = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "stream_active" not in st.session_state:
    st.session_state.stream_active = False

@st.cache_resource
def get_notary(eps: float):
    # La configuración se recompila solo si eps cambia o hay reset
    cfg = build_notary_config(eps, policies_dicts)
    cfg.ctm_mode = "full"
    return IDICOCNotaryClient(cfg)

def _send_to_notary(payload: str, eps: float):
    try:
        notary = get_notary(eps)
        res = notary.process_interaction(
            audit_input=payload,
            context_input=st.session_state.context_list,
            context_policies=policies_list,
        )
        st.session_state.last_result = res
    except Exception as e:
        st.error(f"Error procesando la señal: {e}")

def _numeric_payload(noise_level: float) -> str:
    base = np.array(st.session_state.base_bins, dtype=float)
    noise = np.random.normal(0, float(noise_level), 4)
    raw = np.clip(base + noise, 0, None)
    s = raw.sum()
    bins = (raw / s if s > 1e-10 else base).tolist()
    dominant_idx = int(np.argmax(bins))
    bin_desc = ", ".join(f"Bin{i}={v:.4f}" for i, v in enumerate(bins))
    entropy = float(-sum(v * np.log(v + 1e-12) for v in bins))
    balance = "equilibrada" if max(bins) < 0.4 else "sesgada"
    
    return (
        f"Señal de distribución numérica de auditoría: [{bin_desc}]. "
        f"Distribución {balance}. Bin dominante: Bin{dominant_idx} ({bins[dominant_idx]:.4f}). "
        f"Entropía estimada: {entropy:.4f}. "
        f"Ruido gaussiano aplicado: σ={noise_level:.3f}."
    )

# ── Callbacks ─────────────────────────────────────────────────────────────────
def on_send_numeric(eps, noise):
    _send_to_notary(_numeric_payload(noise), eps)

def on_send_semantic(text, eps):
    if text.strip():
        _send_to_notary(text.strip(), eps)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/shield.png", width=70)
    st.title("IIAE Telemetry")
    st.markdown("---")
    epsilon_ref = st.slider("Umbral Tolerancia ε", 0.01, 1.00, 0.20, 0.01)
    noise_level = st.slider("Ruido Gaussiano σ", 0.0, 1.0, 0.1, 0.01)
    st.markdown("---")
    with st.expander("Reglas Activas (policies.txt)", expanded=False):
        for pol in policies_dicts:
            st.markdown(f"<div class='policy-card'><b>{pol['policy_type'].upper()}</b>: {pol['text']}</div>", unsafe_allow_html=True)
    
    # Stream Control
    st.markdown("---")
    st.session_state.stream_active = st.toggle("Activar Stream Automático", value=st.session_state.stream_active)
    
    # Fragment que se auto-recarga cada segundo
    @st.fragment(run_every="1s")
    def heartbeat():
        if st.session_state.stream_active:
            # Enviar señal automática usando el ruido y eps actuales
            _send_to_notary(_numeric_payload(noise_level), epsilon_ref)
        else:
            pass
    heartbeat()

# ── Cabecera ──────────────────────────────────────────────────────────────────
st.title("🛡️ Production Monitor — IIAE")
st.caption("Interfaz de inyección de señales para el Notario IDICOC.")

# ── Área Principal (Tabs) ─────────────────────────────────────────────────────
tab_num, tab_sem = st.tabs(["📊 Simulación Numérica", "💬 Entrada Semántica"])

with tab_num:
    st.markdown("### Simular Señal Vectorial (4 Bins)")
    st.write("Ajusta los valores base. El ruido gaussiano se aplicará dinámicamente antes de enviar al Notario.")
    c1, c2, c3, c4 = st.columns(4)
    st.session_state.base_bins[0] = c1.slider("Bin 0", 0.0, 1.0, st.session_state.base_bins[0], 0.05, key="n_b0")
    st.session_state.base_bins[1] = c2.slider("Bin 1", 0.0, 1.0, st.session_state.base_bins[1], 0.05, key="n_b1")
    st.session_state.base_bins[2] = c3.slider("Bin 2", 0.0, 1.0, st.session_state.base_bins[2], 0.05, key="n_b2")
    st.session_state.base_bins[3] = c4.slider("Bin 3", 0.0, 1.0, st.session_state.base_bins[3], 0.05, key="n_b3")
    
    st.button("🚀 Enviar Señal Única", on_click=on_send_numeric, args=(epsilon_ref, noise_level), use_container_width=True, type="primary")

    with st.expander("👁 Vista previa del texto semántico generado por el Wrapper", expanded=False):
        st.code(_numeric_payload(noise_level), language="text")

with tab_sem:
    st.markdown("### Inyección de Texto Libre")
    st.write("Cualquier texto introducido será analizado semánticamente y mapeado al mismo espacio latente.")
    sem_input = st.text_area("Texto de auditoría", height=100, placeholder="Escribe aquí un mensaje para el notario...")
    st.button("📤 Enviar Texto Semántico", on_click=on_send_semantic, args=(sem_input, epsilon_ref), type="primary")

# ── AEM Output y Métricas ─────────────────────────────────────────────────────
st.markdown("---")
st.subheader("🔍 Salida del Modelo de Ejecución de Auditoría (AEM)")
if st.session_state.last_result:
    res = st.session_state.last_result
    # Extraer métricas DSE si existen
    metrics = res.get("dissonance_metrics", {})
    status = res.get("status", "UNKNOWN")
    corr_flag = res.get("correction_flag", False)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Status", status)
    col2.metric("D_s (Total)", f"{metrics.get('d_s', 0.0):.4f}")
    col3.metric("d_1 (Ancla K)", f"{metrics.get('d_1', 0.0):.4f}")
    col4.metric("d_2 (Grafo/Políticas)", f"{metrics.get('d_2', 0.0):.4f}")
    
    flag_color = "red" if corr_flag else "green"
    col5.markdown(f"**Correction Flag:**<br><span style='color:{flag_color}; font-size:20px'><b>{corr_flag}</b></span>", unsafe_allow_html=True)

    with st.expander("Ver estado canónico completo (CanonicalStateDTO)", expanded=False):
        canonical = res.get("canonical_state", "")
        if hasattr(canonical, "model_dump_json"):
            st.json(canonical.model_dump_json())
        else:
            st.text(str(canonical))
else:
    st.info("Aún no se ha enviado ninguna señal. Envía una señal o activa el Stream Automático para ver las métricas DSE calculadas.")

# ── Monitorización WAL ────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("💻 Raw WAL Tail (últimos registros)")
st.caption(f"Leyendo desde: `{WAL_FILE}`")

raw_log = tail_wal(WAL_FILE, 15)
st.markdown(f'<div class="term">{raw_log}</div>', unsafe_allow_html=True)
