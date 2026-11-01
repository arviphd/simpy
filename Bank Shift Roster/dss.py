"""Interactive Streamlit app for the bank shift roster example.

Change the arrivals, service time, waiting rule and shift costs in the sidebar; the app
reruns the loop from roster.py (formula, integer program, simulation) and shows where the
formula and the simulation disagree.
"""

from __future__ import annotations

import importlib.util
import math
from types import ModuleType
from typing import NamedTuple

import altair as alt
import pandas as pd
import streamlit as st

# Read only: the example's defaults. Each scenario runs in its own copy (scenario_module).
import roster as R

HOUR_LABELS = [f"{h}:00" for h in R.HOURS]
SERIES_COLORS = {"Simulation": "#2a78d6", "Formula": "#eb6834"}
MAX_ARRIVALS = 1000                  # customers per hour, keeps the Erlang C formula within float range
CONTEXT_DELTA = {"delta_color": "off", "delta_arrow": "off"}   # a metric note, not a change
OUTCOMES = {"✓ pass": (SERIES_COLORS["Simulation"], "circle"), "✗ fail": ("#d03b3b", "cross")}
DEFAULT_FULL, DEFAULT_PART = R.SHIFTS["Full 9-17"], R.SHIFTS["Part 9-13"]

st.set_page_config(page_title="Bank Shift Roster", page_icon="🏦", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    .headline { padding: 1.1rem 1.4rem; border-radius: 14px; background: #1f3347; color: #f7f9fb; }
    .headline strong { color: #ffd08a; }
    [data-testid="stSidebar"] { min-width: 20rem; max-width: 20rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Roster the tellers")
st.caption(
    "Find the cheapest shifts that keep the average wait in every hour under the target. "
    "An integer program does the optimizing on a queueing formula; a SimPy simulation judges every roster."
)

# --- Inputs ---
st.sidebar.header("Service")
mean_service = st.sidebar.number_input("Average service time (min)", 1.0, 15.0, R.MEAN_SERVICE, step=0.5)
target_wait = st.sidebar.number_input("Target average wait per hour (min)", 0.1, 10.0, R.TARGET_WAIT, step=0.1)

st.sidebar.header("Shifts")
full_cost = st.sidebar.number_input("Full-time 9–17 cost", 1.0, 50.0, DEFAULT_FULL[2], step=0.5)
part_cost = st.sidebar.number_input("Part-time shift cost", 1.0, 50.0, DEFAULT_PART[2], step=0.5)
part_hours = st.sidebar.slider("Part-time shift length (hours)", 2, 6, DEFAULT_PART[1] - DEFAULT_PART[0])

st.sidebar.header("Simulation")
replications = st.sidebar.slider("Days simulated per roster", 5, 100, R.REPLICATIONS, step=5)
base_seed = st.sidebar.number_input("Random seed", 0, 1_000_000, R.BASE_SEED)

with st.expander("Customers arriving per hour (edit to change the scenario)"):
    arrivals_table = st.data_editor(
        pd.DataFrame({"Hour": HOUR_LABELS, "Customers": R.ARRIVALS_PER_HOUR}),
        disabled=["Hour"],
        column_config={"Customers": st.column_config.NumberColumn(min_value=1, max_value=MAX_ARRIVALS, step=1)},
        hide_index=True,
        width="stretch",
    )

# --- Validate inputs ---
arrivals = [int(v) if pd.notna(v) else 0 for v in arrivals_table["Customers"]]
if min(arrivals) < 1:
    st.error("Every hour needs at least 1 customer.")
    st.stop()


class Scenario(NamedTuple):
    arrivals: tuple[int, ...]
    mean_service: float
    target_wait: float
    full_cost: float
    part_cost: float
    part_hours: int
    replications: int
    seed: int


params = Scenario(tuple(arrivals), float(mean_service), float(target_wait),
                  float(full_cost), float(part_cost), int(part_hours), int(replications), int(base_seed))


def scenario_module(p: Scenario) -> ModuleType:
    """A private copy of roster.py with this scenario's constants. roster.py reads its scenario from
    module constants, so editing the shared module would leak between sessions and reruns."""
    spec = importlib.util.spec_from_file_location("roster_scenario", R.__file__)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ARRIVALS_PER_HOUR = list(p.arrivals)
    m.MEAN_SERVICE, m.TARGET_WAIT = p.mean_service, p.target_wait
    m.SHIFTS = m.make_shifts(p.full_cost, p.part_cost, p.part_hours)
    m.REPLICATIONS, m.BASE_SEED = p.replications, p.seed
    return m


M = scenario_module(params)
# Most tellers the integer program can put on each hour: every shift covering it at its limit.
capacity = M.coverage(dict.fromkeys(M.SHIFTS, R.MAX_PER_SHIFT))
overloaded = [i for i, (lam, cap) in enumerate(zip(arrivals, capacity)) if lam / 60 * mean_service >= cap]
needs = None if overloaded else M.formula_requirements()
short = overloaded or [i for i, (need, cap) in enumerate(zip(needs, capacity)) if need > cap]
if short:
    st.error(f"At {HOUR_LABELS[short[0]]} the shifts can put at most {capacity[short[0]]} tellers on duty "
             f"({R.MAX_PER_SHIFT} per shift), which is not enough. Lower the arrivals or the service time.")
    st.stop()


def worst_hour(waits: list[float]) -> str:
    return HOUR_LABELS[waits.index(max(waits))]


@st.cache_data(show_spinner="Optimizing and simulating rosters...", max_entries=64)
def run_loop(p: Scenario) -> dict:
    return scenario_module(p).improve(verbose=False)


@st.cache_data(show_spinner="Simulating the roster with fresh random days...", max_entries=64)
def seed_check(p: Scenario, roster: tuple, sets: int) -> pd.DataFrame:
    """Worst hourly wait of the roster on `sets` independent batches of simulated days."""
    m = scenario_module(p)
    rows = []
    for k in range(sets):
        m.BASE_SEED = p.seed + 100_000 * (k + 1)
        waits = m.evaluate(dict(roster))
        rows.append({"Batch": k + 1, "Worst wait (min)": max(waits), "Worst hour": worst_hour(waits)})
    return pd.DataFrame(rows)


@st.cache_data(show_spinner="Simulating your roster...", max_entries=64)
def try_roster(p: Scenario, roster: tuple) -> list[float] | None:
    """Simulated average waits per hour, or None if customers are still queueing when the model stops at 20:00."""
    m = scenario_module(p)
    try:
        return m.evaluate(dict(roster))
    except m.UnservedCustomers:
        return None


result = run_loop(params)
final = result["roster"]
first = result["log"][0]


# --- Helpers ---
def formula_waits(cover: list[int]) -> list[float | None]:
    out = []
    for lam, c in zip(arrivals, cover):
        w = M.erlang_c_wait(lam / 60, 1 / mean_service, c)
        out.append(None if math.isinf(w) else w)
    return out


def roster_text(roster: dict[str, int]) -> str:
    return ", ".join(f"{k} × {name}" for name, k in roster.items() if k) or "nobody"


def roster_table(roster: dict[str, int]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Shift": name, "Tellers": k, "Cost each": M.SHIFTS[name][2], "Cost": k * M.SHIFTS[name][2]}
        for name, k in roster.items() if k
    )


def roster_cost(roster: dict[str, int]) -> float:
    return sum(k * M.SHIFTS[name][2] for name, k in roster.items())


def cost_delta(difference: float, versus: str) -> dict:
    """Metric delta for a cost difference: red when dearer, green when cheaper, plain text when equal."""
    if abs(difference) < 1e-9:
        return {"delta": f"same as {versus}", **CONTEXT_DELTA}
    return {"delta": f"{difference:+g} vs {versus}", "delta_color": "inverse"}


def hourly_frame(roster: dict[str, int], sim_waits: list[float]) -> pd.DataFrame:
    cover = M.coverage(roster)
    return pd.DataFrame({
        "Hour": HOUR_LABELS, "Customers": arrivals, "Tellers": cover, "Formula needs": needs,
        "Simulation": sim_waits, "Formula": formula_waits(cover),
        "Meets target": ["✓ yes" if w <= target_wait else "✗ no" for w in sim_waits],
    })


def target_rule(title: str) -> alt.Chart:
    return alt.Chart(pd.DataFrame({"y": [target_wait]})).mark_rule(strokeDash=[6, 4], color="#666").encode(
        y=alt.Y("y:Q", title=title))


def wait_chart(frame: pd.DataFrame) -> alt.LayerChart:
    long = frame.melt(id_vars=["Hour"], value_vars=list(SERIES_COLORS), var_name="Source",
                      value_name="Average wait (min)").dropna()
    color = alt.Color("Source:N", scale=alt.Scale(domain=list(SERIES_COLORS), range=list(SERIES_COLORS.values())),
                      legend=alt.Legend(orient="top", title=None))
    base = alt.Chart(long).encode(
        x=alt.X("Hour:N", sort=HOUR_LABELS, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Average wait (min):Q", scale=alt.Scale(zero=True)),
        color=color,
        tooltip=["Hour", "Source", alt.Tooltip("Average wait (min):Q", format=".2f")],
    )
    target_label = alt.Chart(pd.DataFrame({"y": [target_wait], "Hour": [HOUR_LABELS[-1]]})).mark_text(
        align="right", dy=-8, color="#444").encode(
        x=alt.X("Hour:N", sort=HOUR_LABELS), y=alt.Y("y:Q", title="Average wait (min)"),
        text=alt.value(f"target {target_wait:g} min"))
    return (target_rule("Average wait (min)") + base.mark_line(strokeWidth=2)
            + base.mark_point(size=80, filled=True, opacity=1) + target_label).properties(height=320)


def teller_chart(frame: pd.DataFrame) -> alt.LayerChart:
    base = alt.Chart(frame).encode(x=alt.X("Hour:N", sort=HOUR_LABELS, axis=alt.Axis(labelAngle=0)),
                                   tooltip=["Hour", "Customers", "Tellers", "Formula needs"])
    bars = base.mark_bar(color=SERIES_COLORS["Simulation"], cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                         size=28).encode(y=alt.Y("Tellers:Q", title="Tellers on duty", axis=alt.Axis(tickMinStep=1)))
    ticks = base.mark_tick(color=SERIES_COLORS["Formula"], thickness=3, size=40).encode(y="Formula needs:Q")
    return (bars + ticks).properties(height=280)


def show_hourly(roster: dict[str, int], sim_waits: list[float]) -> None:
    frame = hourly_frame(roster, sim_waits)
    left, right = st.columns(2)
    with left:
        st.markdown("**Average wait by arrival hour**")
        st.altair_chart(wait_chart(frame), width="stretch")
        st.caption("Blue: simulated. Orange: the Erlang C formula for the same tellers (missing where the "
                   "formula says the queue grows without limit). Dashed: the target.")
    with right:
        st.markdown("**Tellers on duty**")
        st.altair_chart(teller_chart(frame), width="stretch")
        st.caption("Bars: tellers in the roster. Orange ticks: what the formula says each hour needs.")
    st.dataframe(frame, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="%.2f") for c in SERIES_COLORS})


# --- Headline ---
saving = first["cost"] - result["cost"]
saving_text = (f"That is {saving / first['cost']:.0%} cheaper than the roster built on the formula alone."
               if saving > 1e-9 else "The formula's roster could not be made cheaper.")
st.markdown(
    f"""
    <div class="headline">
      Roster <strong>{roster_text(final)}</strong> for a cost of <strong>{result['cost']:g}</strong>.
      {saving_text}
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

worst = max(result["waits"])
metrics = st.columns(4)
metrics[0].metric("Final cost", f"{result['cost']:g}", **cost_delta(-saving, "formula roster"))
metrics[1].metric("Formula roster cost", f"{first['cost']:g}",
                  "passes in simulation" if first["ok"] else "fails in simulation", **CONTEXT_DELTA)
metrics[2].metric("Worst hourly wait", f"{worst:.2f} min", f"target {target_wait:g} min", **CONTEXT_DELTA)
metrics[3].metric("Work done", f"{result['sims']} simulations", f"{result['ips']} integer programs",
                  **CONTEXT_DELTA)

# --- Tabs ---
plan_tab, rounds_tab, seed_tab, try_tab = st.tabs(
    ["Recommended roster", "Search rounds", "Check with new random days", "Try your own roster"]
)

with plan_tab:
    if worst > target_wait:
        st.warning("Even the formula's roster fails in the simulation and no cheaper roster passed, so the "
                   "roster below does not meet the target. Raise staffing by hand in the last tab.")
    show_hourly(final, result["waits"])
    st.subheader("Shifts")
    st.dataframe(roster_table(final), hide_index=True, width="stretch")

with rounds_tab:
    rounds = pd.DataFrame(
        {"Round": k, "Ask the IP for": step["step"], "Cost": step["cost"],
         "Worst wait (min)": max(step["waits"]),
         "Worst hour": worst_hour(step["waits"]),
         "Simulation": "✓ pass" if step["ok"] else "✗ fail", "Roster": roster_text(step["roster"])}
        for k, step in enumerate(result["log"], 1)
    )
    domain = list(OUTCOMES)
    outcome = alt.Color("Simulation:N", scale=alt.Scale(domain=domain, range=[c for c, _ in OUTCOMES.values()]),
                        legend=alt.Legend(orient="top", title=None))
    base = alt.Chart(rounds).encode(
        x=alt.X("Round:O", axis=alt.Axis(labelAngle=0)),
        tooltip=["Round", "Ask the IP for", "Cost", alt.Tooltip("Worst wait (min):Q", format=".2f"),
                 "Worst hour", "Simulation"],
    )
    cost_chart = (base.mark_line(color="#999", strokeWidth=2).encode(y=alt.Y("Cost:Q", scale=alt.Scale(zero=False)))
                  + base.mark_point(size=110, filled=True, opacity=1).encode(
                      y="Cost:Q", color=outcome,
                      shape=alt.Shape("Simulation:N", scale=alt.Scale(domain=domain,
                                                                      range=[s for _, s in OUTCOMES.values()]),
                                      legend=None))
                  ).properties(height=300)
    st.altair_chart(cost_chart, width="stretch")
    st.caption("Each point is a roster the integer program proposed and the simulation judged. "
               "A failing roster is undone; the loop stops when no cheaper roster passes.")
    st.dataframe(rounds, hide_index=True, width="stretch",
                 column_config={"Worst wait (min)": st.column_config.NumberColumn(format="%.2f")})

with seed_tab:
    st.caption(
        f"The loop judges every roster on the same {replications} simulated days, so a roster that just "
        "scrapes under the target may only pass on those days. Here the final roster is replayed on new, "
        "independent batches of days."
    )
    sets = st.slider("Batches of new days", 5, 50, 20, step=5)
    # Tabs all run on every rerun, so this costs as much as the loop itself; run it only on request.
    if st.toggle("Run the check", key=f"seed_check_{params}"):
        check = seed_check(params, tuple(final.items()), sets)
        passed = int((check["Worst wait (min)"] <= target_wait).sum())
        left, right = st.columns(2)
        left.metric("Batches that meet the target", f"{passed} of {sets}", f"{passed / sets:.0%}", **CONTEXT_DELTA)
        right.metric("Worst wait across batches", f"{check['Worst wait (min)'].max():.2f} min",
                     f"in the {check.loc[check['Worst wait (min)'].idxmax(), 'Worst hour']} hour", **CONTEXT_DELTA)
        dots = alt.Chart(check).mark_circle(size=90, opacity=1, color=SERIES_COLORS["Simulation"],
                                            stroke="#fcfcfb", strokeWidth=2).encode(
            x=alt.X("Batch:O", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Worst wait (min):Q", scale=alt.Scale(zero=True)),
            tooltip=["Batch", alt.Tooltip("Worst wait (min):Q", format=".2f"), "Worst hour"],
        )
        st.altair_chart((target_rule("Worst wait (min)") + dots).properties(height=300), width="stretch")
        st.caption(f"Each dot is the worst hourly average wait over {replications} new days. Dashed: the target.")
        if passed < sets:
            st.info("If many batches miss the target, simulate more days per roster in the sidebar so the loop's "
                    "judgement is less tied to one set of days.")

with try_tab:
    st.caption("Set the number of tellers on each shift. The roster is simulated immediately with the same days "
               "the loop used. The inputs start at the recommended roster and reset when it changes.")
    reset_key = str(params)   # the recommended roster follows from the scenario
    columns = st.columns(len(M.SHIFTS))
    chosen = {
        name: int(column.number_input(name, 0, R.MAX_PER_SHIFT, final.get(name, 0), key=f"try_{name}_{reset_key}"))
        for column, name in zip(columns, M.SHIFTS)
    }
    if min(M.coverage(chosen)) == 0:
        st.error("Some hours have no teller, so the customers who arrive then are never served. "
                 "Add a shift that covers every hour.")
    elif (chosen_waits := (result["waits"] if chosen == final        # the loop already simulated it
                           else try_roster(params, tuple(chosen.items())))) is None:
        st.error("Customers are still queueing at 20:00, three hours after closing. This roster is far too "
                 "small for the arrivals; add tellers.")
    else:
        chosen_cost = roster_cost(chosen)
        left, middle, right = st.columns(3)
        left.metric("Cost", f"{chosen_cost:g}", **cost_delta(chosen_cost - result["cost"], "recommended"))
        middle.metric("Worst hourly wait", f"{max(chosen_waits):.2f} min", f"target {target_wait:g} min",
                      **CONTEXT_DELTA)
        right.metric("Meets the target", "✓ every hour" if max(chosen_waits) <= target_wait else
                     f"✗ {sum(w > target_wait for w in chosen_waits)} hours miss")
        show_hourly(chosen, chosen_waits)
