import streamlit as st
import pandas as pd
import json
from iiae_core.pipeline import IIAE_Pipeline

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="IIAE Integrity Console",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f8fafc; color: #1e293b; }
    .top-bar {
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px 20px; background-color: white; border-bottom: 1px solid #e2e8f0;
        margin-bottom: 10px;
    }
    .audit-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e2e8f0; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        margin-bottom: 15px;
    }
    .section-label { 
        font-size: 0.7rem; font-weight: 700; color: #94a3b8; 
        text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 5px;
    }
    .status-box {
        padding: 20px; border-radius: 12px; text-align: center; font-weight: bold;
    }
    .deep-dive-box {
        background-color: #f1f5f9; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6;
    }
    </style>
""", unsafe_allow_html=True)

# --- INITIALIZATION ---
if "pipeline" not in st.session_state:
    st.session_state.pipeline = IIAE_Pipeline()
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "current_step" not in st.session_state:
    st.session_state.current_step = 1

# --- SCENARIOS (ENGLISH - REFINED AXIOMS) ---
SCENARIOS = {
    "🟩 Scenario 1: Perfect Alignment (Ds≈0)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "The system maintains its behavior and does not depend on the hardware.",
        "explanation": "Response perfectly mirrors the refined axioms. Near-zero drift expected."
    },
    "🟨 Scenario 2: Partial Alignment (Ds≈0.5)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "The system maintains its behavior, but might depend on the hardware in some cases.",
        "explanation": "A1 is preserved, but A2 is explicitly weakened. Drift detected."
    },
    "🟧 Scenario 3: Irrelevant Response (Ds=1)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "IIAE is a universal framework for verifying information integrity.",
        "explanation": "Response discusses a different topic. Total structural violation."
    },
    "🟥 Scenario 4: Contradictory Output (Ds=1)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "The system does not maintain its behavior and depends entirely on the hardware.",
        "explanation": "Response explicitly negates the axioms. Direct conflict."
    },
    "🟦 Scenario 5: Creative Preservation (Ds≈0.2)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "The system behaves consistently and functions identically regardless of where it is executed.",
        "explanation": "Uses different words but the same meaning. Registered via semantic overlap."
    }
}

# --- TOOLTIP CONTENT (FOUNDER VISION) ---
def show_deep_dive(step):
    if step == 1:
        st.markdown(r"""
        **I₁ Ingestion (Signal Capture)**
        - **Simulation**: We parse the text for signal.
        - **Reality**: Real-world RAG systems measure **SNR (Signal-to-Noise Ratio)**.
        - **Difference**: Production environments use entropy analysis to reject low-quality retrieved chunks.
        """)
    elif step == 2:
        st.markdown(r"""
        **DSE (Axiom Extraction)**
        - **Simulation**: We extract text strings that look like axioms.
        - **Reality**: A production DSE extracts **Structural Invariants**.
        - **Key Difference**: In production, DSE normalizes axioms and detects logical contradictions between the canon and the output.
        """)
    elif step == 3:
        st.markdown(r"""
        **DQE (Drift Quantification)**
        - **Simulation**: We calculate Ds based on semantic similarity.
        - **Reality**: Production DQE measures **Residual Stochastic Noise**.
        - **The Formula**: $Noise = Output - Deterministic Core$.
        - **Key Difference**: We measure $Noise Energy$ vs $Signal Energy$. If noise exceeds the manifold, it's a 'Hallucination'.
        """)
    elif step == 4:
        st.markdown(r"""
        **Epsilon (ε) Guard**
        - **Simulation**: ε is a stable threshold derived from axiom density ($N$).
        - **Reality**: ε is a **Dynamic Security Parameter**.
        - **Key Difference**: Medical systems use $\epsilon \approx 0.01$, while creative agents use $\epsilon \approx 0.4$.
        """)
    elif step == 5:
        st.markdown(r"""
        **CTM (Ledger Block)**
        - **Simulation**: We hash the final result.
        - **Reality**: CTM registers **The Entire Process Trace**.
        - **Key Difference**: Every transformation (AEM -> DSE -> DQE) is hashed into a Merkle Tree for a full cryptographic audit.
        """)
    elif step == 6:
        st.markdown(r"""
        **Final Verdict**
        - **Core Mantra**: "Simulation compares text; Reality separates Signal from Noise."
        - **REGISTERED**: Means the stochastic response has been successfully snapped to the deterministic manifold.
        """)

# --- TOP BAR ---
st.markdown("""
    <div class="top-bar">
        <div style="font-weight: 800; font-size: 1.1rem; color: #1e293b;">⚖️ IIAE Deterministic Standard</div>
        <div style="font-size: 0.8rem; color: #64748b; font-weight: 500;">Integrity Console · Founder Vision v1.6</div>
    </div>
""", unsafe_allow_html=True)

# --- PERSISTENT INPUT LAYER ---
st.markdown("<div class='audit-card'>", unsafe_allow_html=True)
sc_col, ctx_col, resp_col, act_col = st.columns([1, 1.5, 1.5, 0.8])

with sc_col:
    st.markdown("<div class='section-label'>Scenario Selection</div>", unsafe_allow_html=True)
    selected_scenario_name = st.selectbox("Load Scenario", list(SCENARIOS.keys()), label_visibility="collapsed")
    scenario_data = SCENARIOS[selected_scenario_name]
    st.caption(f"ℹ️ {scenario_data['explanation']}")

with ctx_col:
    st.markdown("<div class='section-label'>Axioms (The Canon)</div>", unsafe_allow_html=True)
    context_input = st.text_area("Canon:", scenario_data["context"], height=80, key=f"ctx_{selected_scenario_name}", label_visibility="collapsed")

with resp_col:
    st.markdown("<div class='section-label'>AI Response (To Verify)</div>", unsafe_allow_html=True)
    ai_response_input = st.text_area("Response:", scenario_data["ai_response"], height=80, key=f"resp_{selected_scenario_name}", label_visibility="collapsed")

with act_col:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 VERIFY", type="primary", use_container_width=True):
        n_axioms = len([l for l in context_input.split('\n') if l.strip()])
        calc_epsilon = st.session_state.pipeline.cmc.calculate_deterministic_epsilon(n_axioms)
        st.session_state.pipeline.epsilon = calc_epsilon
        st.session_state.pipeline.dqe.epsilon = calc_epsilon
        st.session_state.pipeline.cmc.epsilon = calc_epsilon
        st.session_state.last_result = st.session_state.pipeline.execute("Task", context_input, ai_response_input)
        st.session_state.current_step = 2
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# --- NAVIGATION & CONTENT ---
col_nav, col_content = st.columns([1, 3])

with col_nav:
    steps = ["1. Ingestion", "2. Axioms (DSE)", "3. Dissonance (DQE)", "4. Guard (ε)", "5. Merkle Seal", "6. Final Summary"]
    for i, title in enumerate(steps, 1):
        if st.button(title, key=f"s_{i}", use_container_width=True, type="primary" if st.session_state.current_step == i else "secondary"):
            st.session_state.current_step = i
            st.rerun()

with col_content:
    if not st.session_state.last_result:
        st.info("Awaiting verification... Press the VERIFY button above.")
    else:
        res = st.session_state.last_result
        step = st.session_state.current_step
        
        # --- TITLE WITH INFO POPOVER ---
        t_col1, t_col2 = st.columns([5, 1])
        t_col1.markdown(f"### Stage {step}: {steps[step-1][3:]}")
        with t_col2:
            with st.popover("💡 Deep Dive"):
                show_deep_dive(step)

        if step == 1:
            st.json(res["stages"]["I1_ingestion"])
        
        elif step == 2:
            st.table(pd.DataFrame([{"Axiom": ax} for ax in res["stages"]["D1_axioms"]]))
            
        elif step == 3:
            st.metric("Dissonance Score (Ds)", f"{res['ds']:.3f}")
            for exp in res["explanations"]: st.warning(exp)
            
        elif step == 4:
            st.write(f"Deterministic Threshold (ε): `{res['epsilon']:.3f}`")
            if res["is_registered"]: st.success("WITHIN ADMISSIBLE MANIFOLD")
            else: st.error("OUTSIDE ADMISSIBLE MANIFOLD")
            
        elif step == 5:
            st.code(json.dumps(res["stages"]["C2_post_receipt"], indent=2), language="json")
            
        elif step == 6:
            status_val = res.get("status", "REGISTERED" if res["is_registered"] else "QUARANTINED")
            color = "#10b981" if res["is_registered"] else "#ef4444"
            st.markdown(f"<div class='status-box' style='background:{color}22; border:2px solid {color}; color:{color};'><h1>{status_val}</h1><p style='font-size:0.8rem; margin:0;'>This result has been registered in the CTM.</p></div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            c1.metric("Final Ds", f"{res['ds']:.3f}")
            c2.metric("Epsilon Limit", f"{res['epsilon']:.3f}")
            
            st.markdown("---")
            st.markdown("**Verified Output (After Invariant Projection):**")
            if res["is_registered"]: st.success(res["stages"]["O1_canonical_output"]["verified"])
            else: st.error(res["stages"]["O1_canonical_output"]["verified"])
