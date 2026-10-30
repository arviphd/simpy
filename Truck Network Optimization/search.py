"""Neighborhood search with the simulation as the objective function.

Three ways to search the truck schedules:

1. Enumerate every schedule (possible here, because the toy is small).
2. Local search: move one truck 30 minutes earlier or later, keep the best improving
   move, stop when no move helps. Every candidate is scored by a full simulation.
3. Two-level search: score every move with the quick estimate, then simulate only
   the most promising few.
"""

from __future__ import annotations

import argparse
import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

from model import Scenario, Schedule, hhmm, late_shipments, quick_estimate, simulate


@dataclass
class SearchResult:
    schedule: Schedule
    late: int
    simulations: int = 0
    quick_estimates: int = 0
    path: list[tuple[Schedule, int]] = field(default_factory=list)


def all_schedules(scenario: Scenario) -> list[Schedule]:
    origins = scenario.origins
    return [dict(zip(origins, combo)) for combo in itertools.product(scenario.slots, repeat=len(origins))]


def neighbors(schedule: Schedule, scenario: Scenario) -> list[Schedule]:
    """All schedules that move exactly one truck by one step."""
    result = []
    for origin in scenario.origins:
        for step in (-scenario.step_minutes, scenario.step_minutes):
            candidate = dict(schedule)
            candidate[origin] += step
            if candidate[origin] in scenario.slots:
                result.append(candidate)
    return result


def best_by(score: Callable[[Schedule], int], schedules: list[Schedule]) -> Schedule:
    """Lowest score; ties go to later departures (they pick up more shipments)."""
    return min(schedules, key=lambda s: (score(s), -sum(s.values())))


def local_search(start: Schedule, scenario: Scenario) -> SearchResult:
    """Steepest-descent local search; every neighbor is simulated."""
    current, best = dict(start), late_shipments(start, scenario)
    result = SearchResult(current, best, simulations=1, path=[(dict(current), best)])
    while True:
        scored = []
        for candidate in neighbors(current, scenario):
            scored.append((late_shipments(candidate, scenario), candidate))
            result.simulations += 1
        value, candidate = min(scored, key=lambda item: item[0])
        if value >= best:
            break
        current, best = candidate, value
        result.path.append((dict(current), best))
    result.schedule, result.late = current, best
    return result


def two_level_search(start: Schedule, scenario: Scenario, top_k: int = 3) -> SearchResult:
    """Screen every move with the quick estimate; simulate only the best top_k."""
    current, best = dict(start), late_shipments(start, scenario)
    result = SearchResult(current, best, simulations=1, path=[(dict(current), best)])
    while True:
        screened = []
        for candidate in neighbors(current, scenario):
            screened.append((quick_estimate(candidate, scenario), candidate))
            result.quick_estimates += 1
        screened.sort(key=lambda item: item[0])
        scored = []
        for _, candidate in screened[:top_k]:
            scored.append((late_shipments(candidate, scenario), candidate))
            result.simulations += 1
        value, candidate = min(scored, key=lambda item: item[0])
        if value >= best:
            break
        current, best = candidate, value
        result.path.append((dict(current), best))
    result.schedule, result.late = current, best
    return result


def describe(name: str, schedule: Schedule, scenario: Scenario) -> None:
    late, records = simulate(schedule, scenario)
    print(f"\n{name}: quick estimate {quick_estimate(schedule, scenario)} late, simulation {late} late")
    for r in records:
        flag = "" if r.on_time else "  <- after the outbound truck"
        print(f"  {r.origin}: leaves {hhmm(r.departs)}, carries {r.carries}, arrives {hhmm(r.arrives)}, "
              f"unloads {hhmm(r.unload_start)}-{hhmm(r.unload_end)}{flag}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docks", type=int, default=2, help="number of unloading docks at the hub")
    parser.add_argument("--top-k", type=int, default=3, help="moves simulated per step in the two-level search")
    args = parser.parse_args()
    scenario = Scenario(docks=args.docks)

    everything = all_schedules(scenario)
    print(f"{scenario.total_shipments} shipments, {len(everything):,} possible schedules, {scenario.docks} docks")

    plan = best_by(lambda s: quick_estimate(s, scenario), everything)
    describe("Best plan by the quick estimate", plan, scenario)

    ls = local_search(plan, scenario)
    print("\nLocal search from that plan, simulation as the objective:")
    print("  " + "  ->  ".join(str(late) for _, late in ls.path) + f" late   ({ls.simulations} simulations)")
    describe("Local search result", ls.schedule, scenario)

    two = two_level_search(plan, scenario, args.top_k)
    print(f"\nTwo-level search: {two.late} late with {two.simulations} simulations "
          f"and {two.quick_estimates} quick estimates")

    optimum = min(late_shipments(s, scenario) for s in everything)
    print(f"\nBest possible over all {len(everything):,} schedules: {optimum} late")


if __name__ == "__main__":
    main()
