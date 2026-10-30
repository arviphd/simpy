"""Draw the hub timeline (waiting and unloading) for the quick-estimate plan and the
search result, side by side, and save it as a PNG."""

from __future__ import annotations

import argparse
import math

import matplotlib.pyplot as plt

from model import Scenario, Schedule, clock, hhmm, quick_estimate, simulate
from search import best_by_quick_estimate, local_search


def draw(ax, schedule: Schedule, scenario: Scenario, title: str) -> None:
    late, records = simulate(schedule, scenario)
    outbound = clock(scenario.outbound_departure)
    for row, r in enumerate(reversed(records)):
        if r.unload_start > r.arrives:
            ax.barh(row, r.unload_start - r.arrives, left=r.arrives, color="#E7E6E6")
            ax.text((r.arrives + r.unload_start) / 2, row, "waits", ha="center", va="center", fontsize=9, color="#595959")
        ax.barh(row, r.unload_end - r.unload_start, left=r.unload_start, color="#44546A" if r.on_time else "#C62828")
        ax.text((r.unload_start + r.unload_end) / 2, row, "unload", ha="center", va="center", fontsize=9, color="white")
    ax.set_yticks(range(len(records)))
    ax.set_yticklabels([f"{r.origin} ({r.carries})" for r in reversed(records)])
    ax.axvline(outbound, color="#ED7D31", linestyle="--")
    ax.text(outbound + 2, -0.45, "outbound leaves", color="#C55A11", fontsize=9)
    # Fit the window to the hub activity: from the hour before the first arrival (or the
    # outbound truck) to the half hour after the last unload.
    low = min(outbound, *(r.arrives for r in records)) // 60 * 60
    high = math.ceil((max(outbound, *(r.unload_end for r in records)) + 15) / 30) * 30
    ticks = range(low, high + 1, 30 if high - low <= 240 else 60)
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([hhmm(t) for t in ticks])
    ax.set_xlim(low, high)
    ax.set_title(f"{title}\nquick estimate {quick_estimate(schedule, scenario)} late, simulation {late} late")


def figure(panels: list[tuple[Schedule, str]], scenario: Scenario):
    """One hub timeline per (schedule, title), side by side."""
    fig, axes = plt.subplots(1, len(panels), figsize=(6.5 * len(panels), 4), squeeze=False)
    for ax, (schedule, title) in zip(axes[0], panels):
        draw(ax, schedule, scenario, title)
    fig.tight_layout()
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docks", type=int, default=2)
    parser.add_argument("--out", default="hub_timeline.png")
    args = parser.parse_args()
    scenario = Scenario(docks=args.docks)

    plan = best_by_quick_estimate(scenario)
    improved = local_search(plan, scenario).schedule

    fig = figure([(plan, "Plan from the quick estimate"),
                  (improved, "After search with the simulation")], scenario)
    fig.savefig(args.out, dpi=150)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
