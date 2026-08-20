"""Enumerative simulation optimization for bank staffing example."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from model import Decision, Scenario, simulate


@dataclass
class CandidateResult:
    tellers: int
    digital_share: float
    replications: int
    is_feasible: bool
    objective: float
    operating_cost: float
    digital_cost: float
    waiting_cost: float
    abandonment_cost: float
    soft_penalty: float
    feasibility_penalty: float
    avg_arrivals: float
    avg_wait: float
    p95_wait: float
    avg_queue: float
    max_queue: float
    utilization: float
    abandonment_rate: float
    p95_compliance_rate: float
    abandonment_compliance_rate: float
    wait_std_dev: float


def _mean(results, attribute: str) -> float:
    return statistics.fmean(getattr(result, attribute) for result in results)


def evaluate(
    decision: Decision,
    scenario: Scenario,
    replications: int = 20,
    base_seed: int = 2026,
) -> CandidateResult:
    if replications < 1:
        raise ValueError("replications must be at least 1")

    results = [
        simulate(decision, scenario, seed=base_seed + replication)[0]
        for replication in range(replications)
    ]

    avg_arrivals = _mean(results, "arrivals")
    avg_digital = _mean(results, "digital_customers")
    avg_abandoned = _mean(results, "abandoned")
    avg_total_wait = _mean(results, "total_wait_minutes")
    avg_wait = _mean(results, "avg_wait")
    p95_wait = _mean(results, "p95_wait")
    utilization = _mean(results, "utilization")
    abandonment_rate = _mean(results, "abandonment_rate")

    operating_cost = (
        decision.tellers
        * scenario.hourly_teller_cost
        * (scenario.horizon_minutes / 60.0)
    )
    waiting_cost = avg_total_wait * scenario.waiting_cost_per_customer_minute
    abandonment_cost = avg_abandoned * scenario.abandonment_cost
    digital_cost = avg_digital * scenario.digital_cost_per_customer

    below_pref = max(0.0, scenario.preferred_utilization_low - utilization)
    above_pref = max(0.0, utilization - scenario.preferred_utilization_high)
    soft_penalty = scenario.utilization_penalty_weight * (below_pref**2 + above_pref**2)

    p95_compliance_rate = statistics.fmean(
        1.0 if result.p95_wait <= scenario.target_p95_wait_minutes else 0.0
        for result in results
    )
    abandonment_compliance_rate = statistics.fmean(
        1.0 if result.abandonment_rate <= scenario.max_abandonment_rate else 0.0
        for result in results
    )

    is_feasible = (
        p95_compliance_rate >= scenario.required_replication_compliance
        and abandonment_compliance_rate >= scenario.required_replication_compliance
    )

    feasibility_penalty = 0.0 if is_feasible else scenario.infeasible_penalty
    objective = (
        operating_cost
        + digital_cost
        + waiting_cost
        + abandonment_cost
        + soft_penalty
        + feasibility_penalty
    )

    waits = [result.avg_wait for result in results]
    wait_std_dev = statistics.pstdev(waits) if len(waits) > 1 else 0.0

    return CandidateResult(
        tellers=decision.tellers,
        digital_share=decision.digital_share,
        replications=replications,
        is_feasible=is_feasible,
        objective=objective,
        operating_cost=operating_cost,
        digital_cost=digital_cost,
        waiting_cost=waiting_cost,
        abandonment_cost=abandonment_cost,
        soft_penalty=soft_penalty,
        feasibility_penalty=feasibility_penalty,
        avg_arrivals=avg_arrivals,
        avg_wait=avg_wait,
        p95_wait=p95_wait,
        avg_queue=_mean(results, "avg_queue"),
        max_queue=_mean(results, "max_queue"),
        utilization=utilization,
        abandonment_rate=abandonment_rate,
        p95_compliance_rate=p95_compliance_rate,
        abandonment_compliance_rate=abandonment_compliance_rate,
        wait_std_dev=wait_std_dev,
    )


def optimize(
    scenario: Scenario,
    teller_options: range = range(1, 7),
    digital_options: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.4),
    replications: int = 20,
    base_seed: int = 2026,
) -> list[CandidateResult]:
    candidates = [
        evaluate(
            Decision(tellers=tellers, digital_share=digital_share),
            scenario,
            replications=replications,
            base_seed=base_seed,
        )
        for tellers in teller_options
        for digital_share in digital_options
    ]
    if not candidates:
        raise ValueError(
            "No candidate policies were generated. Check teller/digital option ranges."
        )
    return sorted(candidates, key=lambda candidate: candidate.objective)


def export_results(
    candidates: list[CandidateResult],
    output_directory: Path = Path("outputs"),
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)

    csv_path = output_directory / "optimization_results.csv"
    json_path = output_directory / "recommended_policy.json"

    rows = [asdict(candidate) for candidate in candidates]
    if not rows:
        raise ValueError("No optimization candidates to export.")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    feasible = [candidate for candidate in candidates if candidate.is_feasible]
    recommendation = min(
        feasible if feasible else candidates,
        key=lambda candidate: candidate.objective,
    )
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(recommendation), handle, indent=2)

    return csv_path, json_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replications", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path, default=Path("outputs"))
    args = parser.parse_args()

    scenario = Scenario()
    candidates = optimize(
        scenario,
        teller_options=range(1, 7),
        digital_options=(0.0, 0.1, 0.2, 0.3, 0.4),
        replications=args.replications,
        base_seed=args.seed,
    )

    csv_path, json_path = export_results(candidates, output_directory=args.output)
    best = candidates[0]
    feasible = [candidate for candidate in candidates if candidate.is_feasible]

    print(f"Best policy: {best.tellers} tellers + {best.digital_share:.0%}")
    print(f"Objective: ${best.objective:,.2f}")
    print(
        f"Compliance: p95 {best.p95_compliance_rate:.0%}; "
        f"abandonment {best.abandonment_compliance_rate:.0%}"
    )
    print(f"Feasible options: {len(feasible)} / {len(candidates)}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
