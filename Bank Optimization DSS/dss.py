"""Interactive Streamlit decision-support system for bank staffing."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from model import Decision, Scenario, simulate
from optimize import optimize

st.set_page_config(page_title="BranchFlow DSS", page_icon="🏦", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=Fraunces:opsz,wght@9..144,700&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Fraunces', serif; }
    .stApp { background: linear-gradient(145deg, #f6f1e7 0%, #eef5ef 52%, #e5eef2 100%); }
    .recommendation { padding: 1.2rem 1.4rem; border-radius: 18px; background: #173d35; color: #fffaf0; box-shadow: 0 16px 38px rgba(23,61,53,.18); }
    .recommendation strong { color: #ffce78; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("BranchFlow Decision Studio")
st.caption("Simulation-based optimization for teller staffing and digital adoption")

# --- Inputs ---
st.sidebar.header("Operating assumptions")
mean_interarrival = st.sidebar.slider(
    "Mean interarrival (minutes)", 1.0, 8.0, 3.0, 0.25
)
mean_service = st.sidebar.slider("Mean service time (minutes)", 1.0, 10.0, 4.0, 0.25)
mean_patience = st.sidebar.slider(
    "Mean customer patience (minutes)", 3.0, 30.0, 12.0, 1.0
)
horizon = st.sidebar.slider("Open time (minutes)", 120.0, 720.0, 480.0, 15.0)
replications = st.sidebar.slider("Replications", 3, 50, 15)

st.sidebar.header("Hard constraints")
target_p95_wait = st.sidebar.slider("Max mean p95 wait (minutes)", 2.0, 30.0, 10.0, 0.5)
max_abandonment_rate = st.sidebar.slider("Max abandonment rate", 0.0, 0.25, 0.05, 0.01)
required_compliance = st.sidebar.slider(
    "Required replication compliance", 0.5, 1.0, 0.95, 0.05
)

st.sidebar.header("Search space")
min_tellers = st.sidebar.slider("Minimum tellers", 1, 10, 1)
max_tellers = st.sidebar.slider("Maximum tellers", min_tellers, 12, 6)
min_digital = st.sidebar.slider("Minimum digital share", 0.0, 1.0, 0.0, 0.05)
max_digital = st.sidebar.slider("Maximum digital share", min_digital, 1.0, 0.4, 0.05)
step_digital = 0.05


def _current_config() -> dict[str, float | int]:
    return {
        "mean_interarrival_minutes": mean_interarrival,
        "mean_service_minutes": mean_service,
        "mean_patience_minutes": mean_patience,
        "horizon_minutes": horizon,
        "target_p95_wait_minutes": target_p95_wait,
        "max_abandonment_rate": max_abandonment_rate,
        "required_replication_compliance": required_compliance,
        "min_tellers": min_tellers,
        "max_tellers": max_tellers,
        "min_digital": min_digital,
        "max_digital": max_digital,
        "replications": replications,
    }


current_config = _current_config()

if st.sidebar.button("Optimize policy"):
    with st.spinner("Running optimization..."):
        scenario = Scenario(
            horizon_minutes=horizon,
            mean_interarrival_minutes=mean_interarrival,
            mean_service_minutes=mean_service,
            mean_patience_minutes=mean_patience,
            target_p95_wait_minutes=target_p95_wait,
            max_abandonment_rate=max_abandonment_rate,
            required_replication_compliance=required_compliance,
        )

        digital_options = tuple(
            round(min_digital + index * step_digital, 2)
            for index in range(int((max_digital - min_digital) / step_digital) + 1)
        )
        if digital_options and digital_options[-1] != round(max_digital, 2):
            digital_options += (max_digital,)

        teller_options = range(min_tellers, max_tellers + 1)
        candidates = optimize(
            scenario,
            teller_options=teller_options,
            digital_options=digital_options,
            replications=replications,
            base_seed=2026,
        )

        st.session_state.candidates = candidates
        st.session_state.scenario = scenario
        st.session_state.optimization_config = current_config

if "candidates" not in st.session_state:
    st.info("Set parameters and click **Optimize policy** to run the study.")
    st.stop()

if st.session_state.optimization_config != current_config:
    st.warning("Inputs changed. Re-run **Optimize policy** to refresh recommendations.")
    st.stop()

candidates = st.session_state.candidates
active_scenario = st.session_state.scenario

feasible = [candidate for candidate in candidates if candidate.is_feasible]
best = feasible[0] if feasible else candidates[0]

feasibility_message = (
    "All hard service constraints satisfied."
    if best.is_feasible
    else "No tested policy met all hard constraints; showing least-penalty option."
)

st.markdown(
    f"""
    <div class="recommendation">
      <div style="opacity:.75;text-transform:uppercase;letter-spacing:.12em;font-size:.8rem">Recommended policy</div>
      <div style="font-size:1.7rem;margin:.3rem 0"><strong>{best.tellers} tellers</strong> + <strong>{best.digital_share:.0%}</strong> digital</div>
      <div>{feasibility_message}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

cols = st.columns(5)
cols[0].metric("Daily objective", f"${best.objective:,.0f}")
cols[1].metric("Average wait", f"{best.avg_wait:.1f} min")
cols[2].metric("p95 wait", f"{best.p95_wait:.1f} min")
cols[3].metric("Abandonment", f"{best.abandonment_rate:.1%}")
cols[4].metric("Utilization", f"{best.utilization:.1%}")

st.caption(
    f"Replication compliance: p95 wait {best.p95_compliance_rate:.0%}; "
    f"abandonment {best.abandonment_compliance_rate:.0%}; "
    f"target {active_scenario.required_replication_compliance:.0%}."
)

frame = pd.DataFrame([asdict(candidate) for candidate in candidates]).copy()
frame["feasible"] = frame["is_feasible"]
left, right = st.columns([1.25, 1])

with left:
    st.subheader("Cost-service tradeoff")
    st.scatter_chart(
        frame,
        x="avg_wait",
        y="objective",
        color="feasible",
    )

with right:
    st.subheader("Objective decomposition")
    st.bar_chart(
        {
            "Operating": [best.operating_cost],
            "Digital": [best.digital_cost],
            "Waiting": [best.waiting_cost],
            "Abandonment": [best.abandonment_cost],
            "Utilization penalty": [best.soft_penalty],
            "Feasibility penalty": [best.feasibility_penalty],
        }
    )

st.subheader("Ranked candidates")
frame_display = frame[
    [
        "tellers",
        "digital_share",
        "objective",
        "avg_wait",
        "p95_wait",
        "abandonment_rate",
        "utilization",
        "is_feasible",
    ]
].rename(
    columns={
        "tellers": "Tellers",
        "digital_share": "Digital share",
        "objective": "Objective",
        "avg_wait": "Avg wait",
        "p95_wait": "p95 wait",
        "abandonment_rate": "Abandonment",
        "utilization": "Utilization",
        "is_feasible": "Feasible",
    }
)
frame_display["Digital share"] = frame_display["Digital share"].map(
    lambda value: f"{value:.0%}"
)
frame_display["Objective"] = frame_display["Objective"].map(
    lambda value: f"${value:,.0f}"
)
frame_display["Avg wait"] = frame_display["Avg wait"].map(lambda value: f"{value:.1f}")
frame_display["p95 wait"] = frame_display["p95 wait"].map(lambda value: f"{value:.1f}")
frame_display["Abandonment"] = frame_display["Abandonment"].map(
    lambda value: f"{value:.1%}"
)
frame_display["Utilization"] = frame_display["Utilization"].map(
    lambda value: f"{value:.1%}"
)

st.dataframe(frame_display)

st.subheader("Deterministic benchmark snapshot")
st.caption("Using fixed seed 2026 for a comparable scenario replay.")
benchmark, _ = simulate(
    Decision(tellers=best.tellers, digital_share=best.digital_share),
    active_scenario,
    seed=2026,
)
st.json(
    {
        "tellers": best.tellers,
        "digital_share": best.digital_share,
        "avg_wait": benchmark.avg_wait,
        "p95_wait": benchmark.p95_wait,
        "abandonment_rate": benchmark.abandonment_rate,
    }
)
