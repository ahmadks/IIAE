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
    st.session_state.pipeline = IIAE_Pipeline()
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# SCENARIOS DEFINITION
SCENARIOS = {
    "🟩 Scenario 1: Perfectly Aligned": {
        "context": "A1: The system must enforce invariance.\nA2: The system must remain substrate-agnostic.",
        "ai_response": "The system enforces invariance and remains substrate-agnostic.",
        "description": "100% semantic preservation. No noise introduced."
    },
    "🟨 Scenario 2: Partially Aligned": {
        "context": "A1: The model must preserve invariance.\nA2: The model must avoid substrate dependence.",
        "ai_response": "The model preserves invariance but may depend on the substrate in some cases.",
        "description": "A1 preserved, A2 violated."
    },
    "🟧 Scenario 3: Irrelevant Response": {
        "context": "A1: The system must enforce invariance.\nA2: The system must remain substrate-agnostic.",
        "ai_response": "IIAE is a universal framework for information integrity.",
        "description": "Does not preserve A1 or A2. Structural drift detected."
    },
    "🟥 Scenario 4: Contradictory Response": {
        "context": "A1: The system must enforce invariance.\nA2: The system must remain substrate-agnostic.",
        "ai_response": "The system does not enforce invariance and depends entirely on the substrate.",
        "description": "Explicit structural contradiction."
    },
    "🟦 Scenario 5: Creative Preservation": {
        "context": "A1: The system must enforce invariance.\nA2: The system must remain substrate-agnostic.",
        "ai_response": "The system maintains its invariant behavior and does not rely on any specific substrate, regardless of implementation.",
        "description": "Axioms preserved with added descriptive content."
    }
}

# Scenario Selection
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/guarantee.png", width=80)
    st.title("IIAE Control")
    st.markdown("---")
    
    st.markdown("### 🎭 Select Scenario")
    selected_scenario_name = st.selectbox("Load Scenarios", list(SCENARIOS.keys()), key="selected_scenario")
    scenario_data = SCENARIOS[selected_scenario_name]
    
    st.markdown("---")
    st.markdown("### 📏 Deterministic Epsilon (ϵ)")
    # We calculate epsilon based on the scenario axioms count
    n_axioms = len([l for l in scenario_data["context"].split('\n') if l.strip()])
    calc_epsilon = st.session_state.pipeline.cmc.calculate_deterministic_epsilon(n_axioms)
    st.metric("Auto-calculated ϵ", f"{calc_epsilon:.3f}")
    st.caption("Formula: 1 - (1 / (1 + log(1+N)))")
    
    st.markdown("---")
    st.info("Architecture: IDICOC-DSE v1.0 (OFFLINE MODE)")

# Header
st.markdown("<h1 style='text-align: center;'>⚖️ IIAE Deterministic Standard</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; opacity: 0.7;'>{scenario_data['description']}</p>", unsafe_allow_html=True)

# --- 1. INPUT LAYER ---
st.markdown("<div class='section-header'><h3>📥 Layer 1: Exogenous Input & Signal Capture</h3></div>", unsafe_allow_html=True)
c1, c2 = st.columns(2)

with c1:
    # Use dynamic key based on scenario to force widget reset
    context_input = st.text_area("Immutable Truth Context (Canon):", 
        value=scenario_data["context"], 
        height=150, 
        key=f"ctx_{selected_scenario_name}")

with c2:
    # Use dynamic key based on scenario to force widget reset
    ai_response_input = st.text_area("AI Response to Verify (Stochastic):", 
        value=scenario_data["ai_response"], 
        height=150, 
        key=f"resp_{selected_scenario_name}")

if st.button("🚀 EXECUTE DETERMINISTIC PIPELINE", type="primary", use_container_width=True):
    # Set the calculated epsilon before execution
    st.session_state.pipeline.epsilon = calc_epsilon
    st.session_state.pipeline.dqe.epsilon = calc_epsilon
    st.session_state.pipeline.cmc.epsilon = calc_epsilon
    
    st.session_state.last_result = st.session_state.pipeline.execute(
        "IIAE Verification Task", 
        context_input, 
        ai_response_input
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
        st.markdown(f"<div class='metric-box'><h4>Threshold (ϵ)</h4><h2>{res['epsilon']:.3f}</h2></div>", unsafe_allow_html=True)
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
        st.write(f"**I₂: Deviation Quantification** (Ds calculado: {stages['I2_ds']:.3f})")
        for exp in res["explanations"]:
            st.write(exp)
        st.write("**C₁: Pre-Seal Receipt** (State commitment before correction)")
        st.json(stages["C1_pre_receipt"])

    with st.expander("🛠️ O₁ Canonicalization & C₂ Final Seal (Re-alignment)", expanded=False):
        st.write("**O₁: Output Canonicalization** (Manifold Snapping)")
        st.write(f"Raw Input: `{stages['O1_canonical_output']['raw']}`")
        st.write(f"Verified Result: `{stages['O1_canonical_output']['verified']}`")
        st.write("**C₂: Final Seal Receipt** (Verification state locked)")
        st.json(stages["C2_post_receipt"])

    with st.expander("🔗 S₁ State-Transition Proof (Chain of Trust)", expanded=False):
        st.write("**S₁: Forensic Proof** (Cryptographic link between Pre and Post states)")
        st.code(f"Transition Proof Hash: {stages['S1_proof']}")
        st.success("Reasoning lineage verified. Integrity loop closed.")

    st.divider()
    st.subheader("Final Manifold Snapping")
    st.write("**Verified Output (After Invariant Projection):**")
    if res["is_valid"]:
        st.success(stages["O1_canonical_output"]["verified"])
    else:
        st.error(stages["O1_canonical_output"]["verified"])

else:
    st.info("Awaiting execution... Select a scenario or enter manual text and press the button.")

st.markdown("<div style='text-align: center; padding: 40px; opacity: 0.3;'>Powered by IIAE Core Engine — v1.0.0-Deterministic-Zero-Offline</div>", unsafe_allow_html=True)
