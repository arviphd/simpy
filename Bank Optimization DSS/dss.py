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
    .block-container { padding-top: 2rem; }
    .recommendation { padding: 1.35rem 1.55rem; border-radius: 18px; background: #173d35; color: #fffaf0; box-shadow: 0 16px 38px rgba(23,61,53,.18); }
    .recommendation strong { color: #ffce78; }
    .human-card { min-height: 10rem; padding: 1rem 1.1rem; border-radius: 14px; border: 1px solid rgba(23,61,53,.13); background: rgba(255,255,255,.56); }
    .human-card h4 { margin: 0 0 .5rem; color: #173d35; font-size: 1rem; }
    .human-card p { margin: .3rem 0; color: #39564f; font-size: .92rem; line-height: 1.45; }
    .status-pill { display: inline-block; margin-top: .55rem; padding: .24rem .55rem; border-radius: 999px; background: rgba(255,206,120,.18); color: #ffdc9e; font-size: .78rem; }
    [data-testid="stSidebar"] { min-width: 20rem; max-width: 20rem; }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 1rem; }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .28rem; }
    [data-testid="stSidebar"] h2 { margin: .25rem 0 0; font-size: 1.08rem; }
    [data-testid="stSidebar"] h3 { margin: .25rem 0 0; font-size: 1rem; }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] { margin-bottom: -.15rem; }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { font-size: .75rem; }
    [data-testid="stSidebar"] [data-testid="stNumberInput"] { margin-bottom: -.1rem; }
    [data-testid="stSidebar"] [data-testid="stExpander"] details { border-radius: 10px; }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary { padding: .43rem .65rem; }
    [data-testid="stSidebar"] [data-testid="stExpanderDetails"] { padding: .05rem .6rem .5rem; }
    [data-testid="stSidebar"] .stButton button { margin-top: .25rem; min-height: 2.5rem; background: #173d35; color: #fffaf0; border: 0; }
    .objective-note { margin: .25rem 0 .35rem; padding: .58rem .68rem; border: 1px solid rgba(23,61,53,.16); border-radius: 10px; background: rgba(255,255,255,.48); font-size: .71rem; line-height: 1.4; color: #294a42; }
    .objective-note strong { color: #173d35; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Plan today’s branch service")
st.caption(
    "Find a staffing and digital-service mix that protects customers without overspending."
)

# --- Inputs ---
st.sidebar.header("Set up the decision")
st.sidebar.caption("Open a section only when you need to change it.")

with st.sidebar.expander("Demand & branch operations", expanded=False):
    input_left, input_right = st.columns(2)
    with input_left:
        mean_interarrival = st.number_input(
            "Arrival gap (min)",
            1.0,
            8.0,
            3.0,
            0.25,
            help="Average minutes between arriving customers.",
        )
        mean_patience = st.number_input(
            "Patience (min)",
            3.0,
            30.0,
            12.0,
            1.0,
            help="How long a customer typically waits before leaving.",
        )
        replications = st.number_input(
            "Test runs",
            3,
            50,
            15,
            1,
            help="More runs increase confidence but take longer.",
        )
    with input_right:
        mean_service = st.number_input("Service time (min)", 1.0, 10.0, 4.0, 0.25)
        horizon = st.number_input("Open time (min)", 120.0, 720.0, 480.0, 15.0)

with st.sidebar.expander("Decision priorities", expanded=False):
    weight_left, weight_right = st.columns(2)
    with weight_left:
        hourly_teller_cost = st.number_input(
            "Teller / hr ($)", min_value=0.0, value=28.0, step=1.0
        )
        waiting_cost = st.number_input(
            "Wait / cust-min ($)", min_value=0.0, value=0.45, step=0.05
        )
        utilization_penalty_weight = st.number_input(
            "Workload penalty", min_value=0.0, value=1200.0, step=100.0
        )
    with weight_right:
        digital_cost = st.number_input(
            "Digital visit ($)", min_value=0.0, value=0.65, step=0.05
        )
        abandonment_cost = st.number_input(
            "Lost customer ($)", min_value=0.0, value=35.0, step=1.0
        )

with st.sidebar.expander("Customer-service guardrails", expanded=False):
    guardrail_left, guardrail_right = st.columns(2)
    with guardrail_left:
        target_p95_wait = st.number_input(
            "Long-wait limit (min)",
            2.0,
            30.0,
            10.0,
            0.5,
            help="The 95th-percentile wait should remain below this limit.",
        )
        required_compliance_pct = st.number_input("Confidence (%)", 50, 100, 95, 5)
    with guardrail_right:
        max_abandonment_pct = st.number_input("Max lost (%)", 0, 25, 5, 1)
    required_compliance = required_compliance_pct / 100.0
    max_abandonment_rate = max_abandonment_pct / 100.0

with st.sidebar.expander("Options to test", expanded=False):
    option_left, option_right = st.columns(2)
    with option_left:
        min_tellers = st.number_input("Min tellers", 1, 10, 1, 1)
        min_digital_pct = st.number_input("Min digital (%)", 0, 100, 0, 5)
    with option_right:
        max_tellers = st.number_input("Max tellers", min_tellers, 12, 6, 1)
        max_digital_pct = st.number_input(
            "Max digital (%)", min_digital_pct, 100, 40, 5
        )
    min_digital = min_digital_pct / 100.0
    max_digital = max_digital_pct / 100.0
step_digital = 0.05

st.sidebar.markdown(
    f"""
    <div class="objective-note">
      <strong>Goal: lowest daily impact</strong><br>
      ${hourly_teller_cost:.0f}/teller-hour · ${digital_cost:.2f}/digital visit ·
      ${waiting_cost:.2f}/wait minute · ${abandonment_cost:.0f}/lost customer.<br>
      Also avoids staff workload outside 65%–90% and rejects choices that miss the service guardrails.
    </div>
    """,
    unsafe_allow_html=True,
)


def _current_config() -> dict[str, float | int]:
    return {
        "mean_interarrival_minutes": mean_interarrival,
        "mean_service_minutes": mean_service,
        "mean_patience_minutes": mean_patience,
        "horizon_minutes": horizon,
        "target_p95_wait_minutes": target_p95_wait,
        "max_abandonment_rate": max_abandonment_rate,
        "required_replication_compliance": required_compliance,
        "hourly_teller_cost": hourly_teller_cost,
        "digital_cost_per_customer": digital_cost,
        "waiting_cost_per_customer_minute": waiting_cost,
        "abandonment_cost": abandonment_cost,
        "utilization_penalty_weight": utilization_penalty_weight,
        "min_tellers": min_tellers,
        "max_tellers": max_tellers,
        "min_digital": min_digital,
        "max_digital": max_digital,
        "replications": replications,
    }


current_config = _current_config()

if st.sidebar.button("Find the best plan", width="stretch"):
    with st.spinner("Running optimization..."):
        scenario = Scenario(
            horizon_minutes=horizon,
            mean_interarrival_minutes=mean_interarrival,
            mean_service_minutes=mean_service,
            mean_patience_minutes=mean_patience,
            target_p95_wait_minutes=target_p95_wait,
            max_abandonment_rate=max_abandonment_rate,
            required_replication_compliance=required_compliance,
            hourly_teller_cost=hourly_teller_cost,
            digital_cost_per_customer=digital_cost,
            waiting_cost_per_customer_minute=waiting_cost,
            abandonment_cost=abandonment_cost,
            utilization_penalty_weight=utilization_penalty_weight,
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
    st.markdown(
        """
        <div class="recommendation">
          <div style="opacity:.72;text-transform:uppercase;letter-spacing:.12em;font-size:.76rem">The decision</div>
          <div style="font-size:1.7rem;margin:.35rem 0">How many tellers should be scheduled, and how much demand should move to digital service?</div>
          <div style="opacity:.84">Review the assumptions at left, then select <strong>Find the best plan</strong>.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

if st.session_state.optimization_config != current_config:
    st.warning(
        "The assumptions changed. Select **Find the best plan** to update the recommendation."
    )
    st.stop()

candidates = st.session_state.candidates
active_scenario = st.session_state.scenario

feasible = [candidate for candidate in candidates if candidate.is_feasible]
best = feasible[0] if feasible else candidates[0]

feasibility_message = (
    "Meets the customer-service guardrails"
    if best.is_feasible
    else "No tested plan meets every customer-service guardrail"
)
recommendation_reason = (
    "This is the lowest-impact plan among the choices that protect the service targets."
    if best.is_feasible
    else "This is the closest tested plan, but the service targets need attention before approval."
)

st.markdown(
    f"""
    <div class="recommendation">
      <div style="opacity:.72;text-transform:uppercase;letter-spacing:.12em;font-size:.76rem">Recommended branch plan</div>
      <div style="font-size:1.85rem;margin:.35rem 0">Schedule <strong>{best.tellers} tellers</strong> and guide <strong>{best.digital_share:.0%} of visits</strong> to digital service</div>
      <div style="opacity:.86">{recommendation_reason}</div>
      <div class="status-pill">{feasibility_message}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")
cols = st.columns(4)
cols[0].metric("Typical customer wait", f"{best.avg_wait:.1f} min")
cols[1].metric("Long-wait benchmark", f"{best.p95_wait:.1f} min")
cols[2].metric("Customers likely to leave", f"{best.abandonment_rate:.1%}")
cols[3].metric("Teller workload", f"{best.utilization:.0%}")

frame = pd.DataFrame([asdict(candidate) for candidate in candidates]).copy()
frame["feasible"] = frame["is_feasible"]
expected_digital = round(best.avg_arrivals * best.digital_share)
expected_branch = round(best.avg_arrivals - expected_digital)
summary_left, summary_right = st.columns(2)

with summary_left:
    st.markdown(
        f"""
        <div class="human-card">
          <h4>What the day should look like</h4>
          <p>About <strong>{best.avg_arrivals:.0f} customer visits</strong> are expected.</p>
          <p>Roughly <strong>{expected_digital}</strong> can use digital service, leaving <strong>{expected_branch}</strong> for the teller line.</p>
          <p>The typical teller should be actively serving customers about <strong>{best.utilization:.0%}</strong> of open time.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with summary_right:
    guardrail_text = (
        f"The plan stayed within both service limits in at least {active_scenario.required_replication_compliance:.0%} of test runs."
        if best.is_feasible
        else f"One or more service limits missed the {active_scenario.required_replication_compliance:.0%} confidence target. Consider testing more tellers or a higher digital share."
    )
    st.markdown(
        f"""
        <div class="human-card">
          <h4>Why this plan was selected</h4>
          <p>It balances staffing cost against the business impact of waiting and customers leaving.</p>
          <p>{guardrail_text}</p>
          <p>Estimated combined daily cost and impact: <strong>${best.objective:,.0f}</strong>.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.subheader("Other plans worth considering")
st.caption("Compare the closest alternatives before committing the schedule.")
comparison_pool = feasible if feasible else candidates
comparison = pd.DataFrame([asdict(candidate) for candidate in comparison_pool[:6]])
comparison["Plan"] = comparison.apply(
    lambda row: f"{int(row['tellers'])} tellers · {row['digital_share']:.0%} digital",
    axis=1,
)
comparison["Daily cost & impact"] = comparison["objective"].map(
    lambda value: f"${value:,.0f}"
)
comparison["Typical wait"] = comparison["avg_wait"].map(
    lambda value: f"{value:.1f} min"
)
comparison["Long wait"] = comparison["p95_wait"].map(lambda value: f"{value:.1f} min")
comparison["Customers lost"] = comparison["abandonment_rate"].map(
    lambda value: f"{value:.1%}"
)
comparison["Teller workload"] = comparison["utilization"].map(
    lambda value: f"{value:.0%}"
)
st.dataframe(
    comparison[
        [
            "Plan",
            "Daily cost & impact",
            "Typical wait",
            "Long wait",
            "Customers lost",
            "Teller workload",
        ]
    ],
    hide_index=True,
    width="stretch",
)

with st.expander("See how the recommendation was calculated"):
    st.caption(
        "The model tests every allowed staffing and digital-service combination across repeated simulated days. "
        "Plans that miss either customer-service guardrail are not eligible for the recommendation."
    )
    chart_left, chart_right = st.columns([1.2, 1])
    with chart_left:
        st.markdown("#### Cost versus customer wait")
        st.scatter_chart(frame, x="avg_wait", y="objective", color="feasible")
    with chart_right:
        st.markdown("#### What makes up the selected plan")
        cost_frame = pd.DataFrame(
            {
                "Impact": [
                    "Teller labor",
                    "Digital handling",
                    "Customer waiting",
                    "Customers leaving",
                    "Workload outside preferred range",
                ],
                "Dollar equivalent": [
                    best.operating_cost,
                    best.digital_cost,
                    best.waiting_cost,
                    best.abandonment_cost,
                    best.soft_penalty,
                ],
            }
        ).set_index("Impact")
        st.bar_chart(cost_frame)

    st.markdown("#### All tested plans")
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
            "objective": "Daily cost & impact",
            "avg_wait": "Typical wait",
            "p95_wait": "Long wait",
            "abandonment_rate": "Customers lost",
            "utilization": "Teller workload",
            "is_feasible": "Meets guardrails",
        }
    )
    frame_display["Digital share"] = frame_display["Digital share"].map(
        lambda value: f"{value:.0%}"
    )
    frame_display["Daily cost & impact"] = frame_display["Daily cost & impact"].map(
        lambda value: f"${value:,.0f}"
    )
    frame_display["Typical wait"] = frame_display["Typical wait"].map(
        lambda value: f"{value:.1f} min"
    )
    frame_display["Long wait"] = frame_display["Long wait"].map(
        lambda value: f"{value:.1f} min"
    )
    frame_display["Customers lost"] = frame_display["Customers lost"].map(
        lambda value: f"{value:.1%}"
    )
    frame_display["Teller workload"] = frame_display["Teller workload"].map(
        lambda value: f"{value:.0%}"
    )
    st.dataframe(frame_display, hide_index=True, width="stretch")

    benchmark, _ = simulate(
        Decision(tellers=best.tellers, digital_share=best.digital_share),
        active_scenario,
        seed=2026,
    )
    st.caption(
        f"Comparable single-day replay (seed 2026): {benchmark.avg_wait:.1f}-minute typical wait, "
        f"{benchmark.p95_wait:.1f}-minute long-wait benchmark, and {benchmark.abandonment_rate:.1%} customers lost."
    )
