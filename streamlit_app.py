import streamlit as st
import pandas as pd
import json
import warnings
import logging
import os

# --- SUPPRESS TECHNICAL NOISE ---
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*Accessing __path__ from.*")

try:
    import transformers
    transformers.utils.logging.set_verbosity_error()
except ImportError:
    pass

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

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

# --- SCENARIOS (DEFINITIVE - ENGLISH ONLY) ---
SCENARIOS = {
    "🟩 Scenario 1: Perfect Alignment (Ds ≈ 0)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "The system maintains the same behavior. The system does not depend on hardware or platform.",
        "explanation": "The response perfectly preserves the axioms. No noise or deviation detected."
    },
    "🟦 Scenario 2: Partial Alignment (Ds ≈ 0.33)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "The system maintains the same behavior, although in rare cases it may vary depending on execution conditions.",
        "explanation": "The response partially preserves A1 but introduces noise regarding A2."
    },
    "🟨 Scenario 3: Irrelevant Response (Ds ≈ 0.74)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "The system supports a wide range of applications and can be integrated into different workflows depending on user needs.",
        "explanation": "The response discusses unrelated topics. It does not contradict but fails to preserve the axioms."
    },
    "🟥 Scenario 4: Direct Contradiction (Ds ≈ 0.92)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "The system does not maintain the same behavior and depends heavily on the hardware where it runs.",
        "explanation": "The response directly contradicts both core axioms."
    },
    "🟪 Scenario 5: Creative but Correct (Ds ≈ 0.11)": {
        "context": "A1: The system maintains the same behavior.\nA2: The system does not depend on hardware or platform.",
        "ai_response": "The system behaves consistently in all situations and operates independently of the hardware or platform where it is executed.",
        "explanation": "The response preserves the core meaning while using more natural, creative phrasing."
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
        - **Ds (Dissonance)**: Measures semantic distance from individual axioms.
        - **Hallucination Score**: Measures content that exists in the response but has no support in the knowledge base (Mini-RAG).
        - **The Formula**: $Noise = Output - (Deterministic Core + RAG Support)$.
        - **Key Difference**: While Ds checks if the *canon is preserved*, the Hallucination Score checks if *new, unauthorized info was added*.
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

        # Main Stage View
        if res:
            # Display high-level Epistemic Status
            status = res["status"]
            color = res["analysis"]["status_color"]
            st.markdown(f"""
                <div style="background-color:{color}22; border:2px solid {color}; padding:15px; border-radius:10px; margin-bottom:20px; text-align:center;">
                    <h2 style="color:{color}; margin:0;">SYSTEM STATE: {status}</h2>
                    <p style="color:{color}; margin:0; opacity:0.8;">Epistemic Judgement based on IIAE Professional Standard</p>
                </div>
            """, unsafe_allow_html=True)

        if step == 1:
            st.json(res["stages"]["I1_ingestion"])
        
        elif step == 2:
            st.table(pd.DataFrame([{"Axiom": ax} for ax in res["stages"]["D1_axioms"]]))
            
        elif step == 3:
            st.markdown("#### Epistemic Auditing Dashboard")
            analysis = res["analysis"]
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preservation", f"{analysis['preservation_score']:.2f}")
            c2.metric("Noise", f"{analysis['noise_score']:.2f}")
            c3.metric("Hallucination", f"{analysis['hallucination_score']:.2f}")
            c4.metric("Contradiction", f"{analysis['contradiction_score']:.2f}")
            
            st.markdown("---")
            st.markdown("#### Logical Entailment (Axiom Verification)")
            entail_data = []
            for i, ax in enumerate(res["stages"]["D1_axioms"]):
                e = analysis["entailment"][i]
                # Determine label
                if e["entailment"] > 0.7: label = "✅ ENTAILMENT"
                elif e["contradiction"] > 0.7: label = "❌ CONTRADICTION"
                else: label = "❓ NEUTRAL"
                
                entail_data.append({
                    "Axiom": ax,
                    "Status": label,
                    "Entailment %": f"{e['entailment']*100:.1f}%",
                    "Contradiction %": f"{e['contradiction']*100:.1f}%"
                })
            st.table(pd.DataFrame(entail_data))

            st.markdown("#### RAG Support Trace")
            rag_df = pd.DataFrame(analysis["rag_details"])
            # Format score for display
            rag_df["score"] = rag_df["score"].map(lambda x: f"{x:.2f}")
            st.table(rag_df[["clause", "status", "score", "match"]])
            
        elif step == 4:
            st.write(f"Deterministic Threshold (ε): `{res['epsilon']:.3f}`")
            if res["is_registered"]: st.success("WITHIN ADMISSIBLE MANIFOLD")
            else: st.error("OUTSIDE ADMISSIBLE MANIFOLD")
            
        elif step == 5:
            st.code(json.dumps(res["stages"]["C2_post_receipt"], indent=2), language="json")
            
        elif step == 6:
            status_val = res["status"]
            color = res["analysis"]["status_color"]
            st.markdown(f"<div class='status-box' style='background:{color}22; border:2px solid {color}; color:{color};'><h1>{status_val}</h1><p style='font-size:0.8rem; margin:0;'>This result has been registered in the CTM.</p></div>", unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preservation", f"{res['analysis']['preservation_score']:.2f}")
            c2.metric("Noise", f"{res['analysis']['noise_score']:.2f}")
            c3.metric("Hallucination", f"{res['analysis']['hallucination_score']:.2f}")
            c4.metric("Contradiction", f"{res['analysis']['contradiction_score']:.2f}")
            
            st.markdown("---")
            st.markdown("**Verified Output (After Invariant Projection):**")
            if res["is_registered"]: st.success(res["stages"]["O1_canonical_output"]["verified"])
            else: st.error(res["stages"]["O1_canonical_output"]["verified"])
