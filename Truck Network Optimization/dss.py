"""Interactive Streamlit app for the truck network scheduling example.

Change the hub, the trucks and the shipments in the sidebar; the app reruns the
searches from search.py and shows how the quick estimate and the simulation compare.
"""

from __future__ import annotations

import re

import altair as alt
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from model import DEFAULT_READY, Scenario, Schedule, TruckRecord, clock, hhmm, late_shipments, quick_estimate, simulate
from search import SearchResult, all_schedules, best_by, best_by_quick_estimate, local_search, two_level_search
from timeline import figure

DEFAULT_TRAVEL = Scenario().travel_minutes
ORIGINS = list(DEFAULT_TRAVEL)
SERIES_COLORS = {"Local search": "#2a78d6", "Two-level search": "#eb6834"}
MAX_ENUMERATION = 60_000
START_OPTIONS = {
    "Best plan by the quick estimate": "quick",
    "Every truck at the earliest time": "earliest",
    "Every truck at the latest time": "latest",
}
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

st.set_page_config(page_title="Truck Hub Scheduler", page_icon="🚚", layout="wide")

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

st.title("Schedule trucks into the hub")
st.caption(
    "Choose when each truck leaves its origin so the fewest shipments miss the outbound truck. "
    "A local search does the optimizing; a SimPy simulation scores every schedule it tries."
)

# --- Inputs ---
st.sidebar.header("Scenario")
docks = st.sidebar.number_input("Unloading docks at the hub", 1, 4, 2)
unload_minutes = st.sidebar.number_input("Unloading time per truck (min)", 5, 120, 45, step=5)
outbound = st.sidebar.time_input("Outbound truck leaves at", value=pd.Timestamp("13:00").time(), step=900)

with st.sidebar.expander("Travel time to the hub (min)"):
    travel_columns = st.columns(2)
    travel = {
        origin: int(travel_columns[index % 2].number_input(
            f"From {origin}", 10, 480, DEFAULT_TRAVEL[origin], step=10, key=f"travel_{origin}"
        ))
        for index, origin in enumerate(ORIGINS)
    }

st.sidebar.header("Departure options")
earliest = st.sidebar.time_input("Earliest departure", value=pd.Timestamp("06:00").time(), step=900)
latest = st.sidebar.time_input("Latest departure", value=pd.Timestamp("11:00").time(), step=900)
step_minutes = st.sidebar.select_slider("Departure step (min)", options=[15, 30, 60], value=30)

st.sidebar.header("Search")
start_label = st.sidebar.selectbox("Start the search from", list(START_OPTIONS))
top_k = st.sidebar.slider(
    "Two-level search: moves simulated per step", 1, 8, 3,
    help="Every move is ranked with the quick estimate; only this many are simulated.",
)

with st.expander("Shipment ready times (edit to change the scenario)"):
    st.caption("One column per origin, one row per shipment, times as HH:MM. Add rows at the bottom; "
               "clear a cell to remove a shipment.")
    ready_table = st.data_editor(
        pd.DataFrame(DEFAULT_READY),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
    )

# --- Validate inputs ---
errors = []
ready: dict[str, list[str]] = {}
for origin in ORIGINS:
    times = [str(value).strip() for value in ready_table[origin] if pd.notna(value) and str(value).strip()]
    bad = [value for value in times if not TIME_PATTERN.match(value)]
    if bad:
        errors.append(f"Origin {origin} has times that are not HH:MM: {', '.join(bad)}")
    ready[origin] = sorted(times)
earliest_text, latest_text = earliest.strftime("%H:%M"), latest.strftime("%H:%M")
if clock(earliest_text) > clock(latest_text):
    errors.append("The earliest departure is after the latest departure.")
if not any(ready.values()):
    errors.append("There are no shipments.")
if errors:
    for error in errors:
        st.error(error)
    st.stop()


@st.cache_data(show_spinner="Searching schedules...")
def run_searches(params: tuple, start_mode: str, top_k: int) -> dict:
    scenario = _scenario(*params)
    quick_plan = best_by_quick_estimate(scenario)
    start = {
        "quick": quick_plan,
        "earliest": {origin: scenario.slots[0] for origin in scenario.origins},
        "latest": {origin: scenario.slots[-1] for origin in scenario.origins},
    }[start_mode]
    return {
        "quick_plan": quick_plan,
        "local": local_search(start, scenario),
        "two_level": two_level_search(start, scenario, top_k),
    }


@st.cache_data(show_spinner="Simulating every schedule...")
def check_every_schedule(params: tuple) -> dict | None:
    """Compare the quick estimate with the simulation for every schedule.

    Returns the best simulated schedule and a count of schedules per (quick estimate,
    simulation) pair, or None if there are too many schedules to simulate.
    """
    scenario = _scenario(*params)
    if scenario.schedule_count > MAX_ENUMERATION:
        return None
    everything = all_schedules(scenario)
    lates = [late_shipments(s, scenario) for s in everything]
    pairs = pd.DataFrame({"Quick estimate": [quick_estimate(s, scenario) for s in everything],
                          "Simulation": lates})
    late_of = {tuple(s.values()): late for s, late in zip(everything, lates)}
    best = best_by(lambda s: late_of[tuple(s.values())], everything)
    return {
        "counts": pairs.value_counts().rename("Schedules").reset_index(),
        "optimistic": int((pairs["Quick estimate"] < pairs["Simulation"]).sum()),
        "optimum": late_of[tuple(best.values())],
        "optimum_schedule": best,
    }


def _scenario(docks, unload_minutes, outbound, travel, ready, earliest, latest, step_minutes) -> Scenario:
    return Scenario(
        travel_minutes=dict(travel),
        ready={origin: list(times) for origin, times in ready},
        docks=docks,
        unload_minutes=unload_minutes,
        outbound_departure=outbound,
        earliest_departure=earliest,
        latest_departure=latest,
        step_minutes=step_minutes,
    )


params = (
    int(docks), int(unload_minutes), outbound.strftime("%H:%M"),
    tuple(travel.items()), tuple((origin, tuple(times)) for origin, times in ready.items()),
    earliest_text, latest_text, int(step_minutes),
)
scenario = _scenario(*params)
result = run_searches(params, START_OPTIONS[start_label], int(top_k))
full = check_every_schedule(params)
local: SearchResult = result["local"]
two_level: SearchResult = result["two_level"]


# --- Helpers ---
def truck_table(records: list[TruckRecord]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Truck": r.origin,
            "Leaves": hhmm(r.departs),
            "Carries": r.carries,
            "Arrives": hhmm(r.arrives),
            "Waits (min)": r.unload_start - r.arrives,
            "Unloads": f"{hhmm(r.unload_start)}–{hhmm(r.unload_end)}",
            "Status": "On time" if r.on_time else "⚠ Late: after the outbound truck",
        }
        for r in records
    )


def show_timeline(panels: list[tuple[Schedule, str]]) -> None:
    fig = figure(panels, scenario)
    st.pyplot(fig)
    plt.close(fig)
    st.caption("Grey: waiting for a dock. Dark blue: unloaded in time. Red: unloading ends after the outbound truck.")


def moves(path: list[tuple[Schedule, int]]) -> list[str]:
    labels = ["Start"]
    for (before, _), (after, _) in zip(path, path[1:]):
        changed = [o for o in after if after[o] != before[o]]
        labels.append(", ".join(f"{o} {hhmm(before[o])} → {hhmm(after[o])}" for o in changed))
    return labels


def share(count: int, total: int) -> str:
    """Percent of total, without rounding a nonzero count to 0% or a shortfall to 100%."""
    if 0 < count / total < 0.001:
        return "<0.1% of all"
    if 0.999 < count / total < 1:
        return ">99.9% of all"
    return f"{count / total:.1%} of all"


def plural(count: int, word: str) -> str:
    return f"{count:,} {word}" + ("" if count == 1 else "s")


def schedule_text(schedule: Schedule) -> str:
    return ", ".join(f"{origin} {hhmm(t)}" for origin, t in schedule.items())


# --- Headline ---
quick_plan_late = simulate(result["quick_plan"], scenario)[0]
quick_plan_estimate = quick_estimate(result["quick_plan"], scenario)
quick_plan_wrong = quick_plan_estimate < quick_plan_late
docks_text = plural(scenario.docks, "dock")
quick_note = (
    f"The plan that looks best on the quick estimate promises {quick_plan_estimate} late "
    f"but the simulation shows {quick_plan_late}, because trucks queue for the {docks_text}."
    if quick_plan_wrong else
    f"With {docks_text}, the quick estimate's best plan is also right in the simulation."
)
st.markdown(
    f"""
    <div class="headline">
      Leave at <strong>{schedule_text(local.schedule)}</strong>:
      <strong>{local.late}</strong> of {scenario.total_shipments} shipments late.
      {quick_note}
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

metric_columns = st.columns(4)
metric_columns[0].metric("Quick-estimate plan (simulated)", f"{quick_plan_late} late",
                         help=f"The quick estimate said {quick_plan_estimate} late.")
metric_columns[1].metric("Local search", f"{local.late} late", plural(local.simulations, "simulation"),
                         delta_color="off")
metric_columns[2].metric("Two-level search", f"{two_level.late} late",
                         plural(two_level.simulations, "simulation"), delta_color="off")
if full:
    gap = local.late - full["optimum"]
    metric_columns[3].metric(
        "Best possible", f"{full['optimum']} late",
        "search found it" if gap == 0 else f"search is {gap} above it",
        delta_color="off" if gap == 0 else "inverse",
        help=f"Checked by simulating all {scenario.schedule_count:,} schedules.",
    )
else:
    metric_columns[3].metric("Best possible", "not checked",
                             help=f"{scenario.schedule_count:,} schedules is too many to simulate them all here.")

# --- Tabs ---
plan_tab, progress_tab, compare_tab, try_tab = st.tabs(
    ["Recommended schedule", "Search progress", "Quick estimate vs simulation", "Try your own schedule"]
)

with plan_tab:
    st.subheader("Hub timeline: where the search started vs where it ended")
    show_timeline([(local.path[0][0], f"Search start ({start_label.lower()})"),
                   (local.schedule, "Local search result")])
    st.subheader("Recommended schedule")
    st.dataframe(truck_table(simulate(local.schedule, scenario)[1]), hide_index=True, width="stretch")
    if two_level.schedule != local.schedule:
        st.info(f"The two-level search ended at a different schedule ({schedule_text(two_level.schedule)}) "
                f"with {two_level.late} late.")
    if full and full["optimum"] < local.late:
        st.warning(f"The local search stopped at {local.late} late, but {full['optimum']} late is possible, "
                   f"for example {schedule_text(full['optimum_schedule'])}. "
                   "Try a different starting point.")

with progress_tab:
    rows = [
        {"Search": name, "Step": step, "Late shipments": late, "Move": move}
        for name, search in (("Local search", local), ("Two-level search", two_level))
        for step, ((_, late), move) in enumerate(zip(search.path, moves(search.path)))
    ]
    progress = pd.DataFrame(rows)
    color = alt.Color("Search:N", scale=alt.Scale(domain=list(SERIES_COLORS), range=list(SERIES_COLORS.values())),
                      legend=alt.Legend(orient="top", title=None))
    base = alt.Chart(progress).encode(
        x=alt.X("Step:O", title="Improving move", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Late shipments:Q", scale=alt.Scale(zero=True), axis=alt.Axis(tickMinStep=1, grid=True)),
        color=color,
        tooltip=["Search", "Step", "Late shipments", "Move"],
    )
    ends = progress.groupby("Search").tail(1)
    chart = (
        base.mark_line(strokeWidth=2)
        + base.mark_point(size=80, filled=True, opacity=1)
        + alt.Chart(ends).mark_text(align="left", dx=8, color="#444").encode(
            x="Step:O", y="Late shipments:Q", text=alt.Text("Search:N")
        )
    ).properties(height=320)
    st.altair_chart(chart, width="stretch")
    st.caption("Each point is a schedule the search moved to. Both searches stop when no single move helps.")

    st.subheader("What each search cost")
    costs = [
        {"Method": method, "Late shipments": search.late, "Simulations": search.simulations,
         "Quick estimates": search.quick_estimates}
        for method, search in (("Local search (simulate every move)", local),
                               (f"Two-level search (simulate best {top_k})", two_level))
    ]
    if full:
        costs.append({"Method": "Simulate every schedule", "Late shipments": full["optimum"],
                      "Simulations": scenario.schedule_count, "Quick estimates": scenario.schedule_count})
    st.dataframe(pd.DataFrame(costs), hide_index=True, width="stretch")
    st.subheader("Moves")
    st.dataframe(progress[["Search", "Step", "Move", "Late shipments"]], hide_index=True, width="stretch")

with compare_tab:
    if not full:
        st.info(f"{scenario.schedule_count:,} schedules is too many to compare here. Use a larger departure step.")
    else:
        total, optimistic = scenario.schedule_count, full["optimistic"]
        left, middle, right = st.columns(3)
        left.metric("Schedules where the two agree", f"{total - optimistic:,}",
                    share(total - optimistic, total), delta_color="off")
        middle.metric("Schedules where the quick estimate is too optimistic", f"{optimistic:,}",
                      share(optimistic, total), delta_color="off")
        right.metric("Quick estimate's favourite plan", "one of them" if quick_plan_wrong else "estimated correctly",
                     f"{quick_plan_estimate} late estimated, {quick_plan_late} simulated", delta_color="off")
        if quick_plan_wrong and optimistic / total < 0.05:
            st.caption("The quick estimate is right for almost every schedule, but searching with it steers "
                       "straight to the few where it is wrong: plans that bring every truck in at once.")
        elif quick_plan_wrong:
            st.caption("The quick estimate is wrong for many schedules here, including the one it rates best.")
        counts = full["counts"].assign(Share=lambda frame: frame["Schedules"] / total)
        heatmap = alt.Chart(counts).mark_rect(stroke="#fcfcfb", strokeWidth=2).encode(
            x=alt.X("Quick estimate:O", title="Late shipments, quick estimate", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Simulation:O", title="Late shipments, simulation", sort="descending"),
            color=alt.Color("Schedules:Q", scale=alt.Scale(scheme="blues", type="log"),
                            legend=alt.Legend(title="Schedules (log scale)")),
            tooltip=["Quick estimate", "Simulation", "Schedules", alt.Tooltip("Share:Q", format=".1%")],
        ).properties(height=420)
        st.altair_chart(heatmap, width="stretch")
        st.caption(
            f"Each cell counts schedules out of {total:,}. Cells on the diagonal are schedules the quick "
            "estimate gets right; cells above it are schedules where dock queues make the real result worse. "
            "The quick estimate can never be too pessimistic: queueing only delays trucks."
        )

with try_tab:
    st.caption("Pick a departure time for each truck. The schedule is simulated immediately. "
               "The sliders start at the recommended schedule and reset when it changes.")
    slot_labels = [hhmm(t) for t in scenario.slots]
    # Keyed on the slots and the recommendation, so a new scenario starts from its own result.
    reset_key = "_".join(slot_labels) + "|" + schedule_text(local.schedule)
    pick_columns = st.columns(len(scenario.origins))
    chosen: Schedule = {}
    for column, origin in zip(pick_columns, scenario.origins):
        default = hhmm(local.schedule[origin])
        label = column.select_slider(f"Truck {origin} leaves", options=slot_labels,
                                     value=default if default in slot_labels else slot_labels[0],
                                     key=f"try_{origin}_{reset_key}")
        chosen[origin] = clock(label)
    chosen_late, chosen_records = simulate(chosen, scenario)
    left, right, third = st.columns(3)
    left.metric("Simulation", f"{chosen_late} late")
    right.metric("Quick estimate", f"{quick_estimate(chosen, scenario)} late")
    third.metric("Compared with the recommended schedule", f"{chosen_late - local.late:+d} late",
                 delta_color="off")
    show_timeline([(chosen, "Your schedule")])
    st.dataframe(truck_table(chosen_records), hide_index=True, width="stretch")
