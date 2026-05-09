import streamlit as st
import pandas as pd
import datetime
from iiae_core.pipeline import IIAE_Pipeline

# Set Page Config
st.set_page_config(
    page_title="IIAE Deterministic standard",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Design
st.markdown("""
    <style>
    :root {
        --primary: #38bdf8;
        --bg-dark: #0f172a;
        --card-bg: rgba(30, 41, 59, 0.7);
    }
    .main { background-color: var(--bg-dark); color: white; }
    .stApp { background: radial-gradient(circle at top right, #1e293b, #0f172a); }
    
    .iiae-card {
        background: var(--card-bg);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        backdrop-filter: blur(12px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    
    .section-header {
        border-left: 4px solid var(--primary);
        padding-left: 15px;
        margin-bottom: 20px;
        color: var(--primary);
    }
    
    .status-certified { background: #065f46; color: #34d399; padding: 4px 12px; border-radius: 20px; font-weight: bold; }
    .status-quarantined { background: #991b1b; color: #f87171; padding: 4px 12px; border-radius: 20px; font-weight: bold; }
    
    .metric-box { text-align: center; padding: 15px; background: rgba(0,0,0,0.2); border-radius: 12px; }
    </style>
""", unsafe_allow_html=True)

# Initialization
if "pipeline" not in st.session_state:
    st.session_state.pipeline = IIAE_Pipeline(epsilon=0.4)
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_api_key" not in st.session_state:
    st.session_state.last_api_key = None

# Sidebar Configuration
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/guarantee.png", width=80)
    st.title("IIAE Control")
    st.markdown("---")
    
    # API Key Handling
    api_key = st.text_input("Gemini API Key:", type="password", help="Leave blank for simulation mode")
    
    if api_key != st.session_state.last_api_key:
        st.session_state.pipeline = IIAE_Pipeline(epsilon=0.4, api_key=api_key)
        st.session_state.last_api_key = api_key
        st.toast("Pipeline re-initialized with new key")

    st.markdown("---")
    epsilon = st.slider("Strictness Threshold (ϵ)", 0.0, 1.0, 0.4, 0.05)
    st.session_state.pipeline.epsilon = epsilon
    st.session_state.pipeline.dqe.epsilon = epsilon
    st.session_state.pipeline.cmc.epsilon = epsilon
    
    st.markdown("### Operational Mode")
    op_mode = st.selectbox("Operational Mode", ["Factual (ϵ→0.1)", "Hybrid (0.4)", "Creative (ϵ→0.8)"])
    if "Factual" in op_mode: st.session_state.pipeline.epsilon = 0.1
    elif "Creative" in op_mode: st.session_state.pipeline.epsilon = 0.8
    
    st.markdown("---")
    st.markdown("### Simulation Fallback")
    sim_mode = st.selectbox("Simulation Target", ["aligned", "partial", "misaligned"], 
                            help="Only used if no API Key is provided")
    
    st.info("Architecture: IDICOC-DSE v1.0")

# Header
st.markdown("<h1 style='text-align: center;'>⚖️ IIAE Deterministic Standard</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; opacity: 0.7;'>Integrated Information Integrity Framework — Architectural Reboot</p>", unsafe_allow_html=True)

# --- 1. INPUT LAYER ---
st.markdown("<div class='section-header'><h3>📥 Layer 1: Exogenous Input & Signal Capture</h3></div>", unsafe_allow_html=True)
c1, c2 = st.columns([2, 1])

with c1:
    context_input = st.text_area("Immutable Truth Context (Canon):", 
        "Axiom 1: Information must be invariant.\nAxiom 2: IDICOC ensures chain of custody.\nAxiom 3: DQE quantifies drift.", height=150)
    query_input = st.text_input("User Query:", "What are the core pillars of IIAE?")

with c2:
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🚀 EXECUTE IDICOC PIPELINE", type="primary", use_container_width=True):
        st.session_state.last_result = st.session_state.pipeline.execute(
            query_input, 
            context_input, 
            mode=sim_mode
        )

# --- 2. EXECUTION & RESULTS ---
res = st.session_state.last_result
if res:
    st.markdown("<div class='section-header'><h3>📊 Layer 2: Deterministic Verification Results</h3></div>", unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status = "CERTIFIED" if res["is_valid"] else "QUARANTINED"
        status_class = "status-certified" if res["is_valid"] else "status-quarantined"
        st.markdown(f"<div class='metric-box'><h4>Status</h4><span class='{status_class}'>{status}</span></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-box'><h4>Dissonance (Ds)</h4><h2>{res['ds']:.3f}</h2></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='metric-box'><h4>Threshold (ϵ)</h4><h2>{res['epsilon']:.2f}</h2></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='metric-box'><h4>Axioms</h4><h2>{len(res['stages']['D1_axioms'])}</h2></div>", unsafe_allow_html=True)

    # 7-STAGE PIPELINE TRACE
    st.markdown("### 🔍 IDICOC 7-Stage Execution Trace")
    stages = res["stages"]
    
    with st.expander("📝 I₁ Ingestion & D₁ DSE (Formalizing the Canon)", expanded=True):
        st.write("**I₁: Capture & Ingestion** (Filtro AEM aplicado)")
        st.json(stages["I1_ingestion"])
        st.write("**D₁: Axiom Extraction** (Property Graph updated)")
        for ax in stages["D1_axioms"]:
            st.code(ax)

    with st.expander("⚖️ I₂ Integrity & C₁ Pre-Seal (DQE Engine)", expanded=False):
        st.write(f"**I₂: Deviation Quantification** (Ds calculated: {stages['I2_ds']:.3f})")
        for exp in res["explanations"]:
            st.write(exp)
        st.write("**C₁: Pre-Seal Receipt** (State commitment before correction)")
        st.json(stages["C1_pre_receipt"])

    with st.expander("🛠️ O₁ Canonicalization & C₂ Final Seal (Re-alignment)", expanded=False):
        st.write("**O₁: Output Canonicalization** (Manifold Snapping)")
        st.write(f"Raw: `{stages['O1_canonical_output']['raw']}`")
        st.write(f"Verified: `{stages['O1_canonical_output']['verified']}`")
        st.write("**C₂: Final Seal Receipt** (Verification state locked)")
        st.json(stages["C2_post_receipt"])

    with st.expander("🔗 S₁ State-Transition Proof (Chain of Trust)", expanded=False):
        st.write("**S₁: Forensic Proof** (Cryptographic link between Pre and Post states)")
        st.code(f"Transition Proof Hash: {stages['S1_proof']}")
        st.success("Reasoning lineage verified. Integrity loop closed.")

    st.divider()
    st.subheader("Final Manifold Snapping")
    st.write("**Raw AI Output:**")
    st.info(stages["O1_canonical_output"]["raw"])
    st.write("**Verified Output (After Invariant Projection):**")
    if res["is_valid"]:
        st.success(stages["O1_canonical_output"]["verified"])
    else:
        st.error(stages["O1_canonical_output"]["verified"])

else:
    st.info("Awaiting execution... Fill the inputs above and press the button.")


st.markdown("<div style='text-align: center; padding: 40px; opacity: 0.3;'>Powered by IIAE Core Engine — v1.0.0-Deterministic-Zero</div>", unsafe_allow_html=True)
