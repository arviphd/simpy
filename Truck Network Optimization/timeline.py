"""Draw the hub timeline (waiting and unloading) for the quick-estimate plan and the
search result, side by side, and save it as a PNG."""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt

from model import Scenario, Schedule, clock, hhmm, quick_estimate, simulate
from search import all_schedules, best_by, local_search


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
    ticks = range(11 * 60, 14 * 60 + 1, 30)
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([hhmm(t) for t in ticks])
    ax.set_xlim(11 * 60, 14 * 60)
    ax.set_title(f"{title}\nquick estimate {quick_estimate(schedule, scenario)} late, simulation {late} late")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docks", type=int, default=2)
    parser.add_argument("--out", default="hub_timeline.png")
    args = parser.parse_args()
    scenario = Scenario(docks=args.docks)

    plan = best_by(lambda s: quick_estimate(s, scenario), all_schedules(scenario))
    improved = local_search(plan, scenario).schedule

    fig, axes = plt.subplots(1, 2, figsize=(13, 4), sharey=False)
    draw(axes[0], plan, scenario, "Plan from the quick estimate")
    draw(axes[1], improved, scenario, "After search with the simulation")
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
