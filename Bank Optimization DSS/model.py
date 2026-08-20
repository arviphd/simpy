"""Stochastic SimPy model used by bank staffing optimization example."""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import asdict, dataclass

import simpy


@dataclass(frozen=True)
class Decision:
    tellers: int
    digital_share: float


@dataclass(frozen=True)
class Scenario:
    horizon_minutes: float = 480.0
    mean_interarrival_minutes: float = 3.0
    mean_service_minutes: float = 4.0
    mean_patience_minutes: float = 12.0
    target_p95_wait_minutes: float = 10.0
    max_abandonment_rate: float = 0.05
    required_replication_compliance: float = 0.95
    preferred_utilization_low: float = 0.65
    preferred_utilization_high: float = 0.90
    hourly_teller_cost: float = 28.0
    digital_cost_per_customer: float = 0.65
    waiting_cost_per_customer_minute: float = 0.45
    abandonment_cost: float = 35.0
    utilization_penalty_weight: float = 1200.0
    infeasible_penalty: float = 1_000_000.0


@dataclass
class ReplicationResult:
    seed: int
    arrivals: int
    digital_customers: int
    physical_customers: int
    completed: int
    abandoned: int
    avg_wait: float
    p95_wait: float
    max_queue: int
    avg_queue: float
    utilization: float
    abandonment_rate: float
    total_wait_minutes: float
    elapsed_minutes: float


def percentile(values: list[float], percentile_value: float) -> float:
    """Return the weighted percentile estimate of a numeric sample."""
    if not values:
        return 0.0

    if percentile_value <= 0.0:
        return float(min(values))
    if percentile_value >= 100.0:
        return float(max(values))

    ordered = sorted(values)
    position = (len(ordered) - 1) * (percentile_value / 100.0)
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return float(ordered[int(lower)])

    weight = position - lower
    return float(ordered[int(lower)] * (1.0 - weight) + ordered[int(upper)] * weight)


class BankSimulation:
    """SimPy-based queue model with common-random-number streams."""

    def __init__(self, decision: Decision, scenario: Scenario, seed: int = 42):
        if decision.tellers < 1:
            raise ValueError("At least one teller is required.")
        if not (0.0 <= decision.digital_share <= 1.0):
            raise ValueError("digital_share must be in [0, 1].")

        self.decision = decision
        self.scenario = scenario
        self.seed = seed

        self.arrival_rng = random.Random(seed)
        self.routing_rng = random.Random(seed + 10_000)

        self.env = simpy.Environment()
        self.counter = simpy.Resource(self.env, capacity=decision.tellers)

        self.arrivals = 0
        self.digital_customers = 0
        self.physical_customers = 0
        self.completed = 0
        self.abandoned = 0
        self.wait_times: list[float] = []
        self.total_wait_minutes = 0.0
        self.busy_minutes_in_horizon = 0.0
        self.max_queue = 0

        self.timeline: list[dict[str, float | int | str]] = []
        self._queue_points: list[tuple[float, int]] = [(0.0, 0)]

    def _snapshot(self, event: str) -> None:
        queue = len(self.counter.queue)
        busy = len(self.counter.users)
        now = float(self.env.now)

        self.max_queue = max(self.max_queue, queue)
        self._queue_points.append((now, queue))
        self.timeline.append(
            {
                "time": round(now, 4),
                "queue": queue,
                "busy": busy,
                "event": event,
            }
        )

    def _customer_rng(self, customer_id: int, salt: int) -> random.Random:
        return random.Random(self.seed * 1_000_003 + customer_id * 97_409 + salt)

    def _record_busy(self, service_start: float, service_end: float) -> None:
        if service_end <= service_start:
            return
        clipped_start = max(0.0, min(service_start, self.scenario.horizon_minutes))
        clipped_end = max(0.0, min(service_end, self.scenario.horizon_minutes))
        if clipped_end > clipped_start:
            self.busy_minutes_in_horizon += clipped_end - clipped_start

    def _customer(self, customer_id: int):
        arrival_time = self.env.now
        self.physical_customers += 1

        patience = self._customer_rng(customer_id, 37).expovariate(
            1.0 / self.scenario.mean_patience_minutes
        )

        with self.counter.request() as request:
            self._snapshot(f"Customer {customer_id} joined")
            outcome = yield request | self.env.timeout(patience)
            if request in outcome:
                wait = float(self.env.now - arrival_time)
                self.wait_times.append(wait)
                self.total_wait_minutes += wait
                self._snapshot(f"Customer {customer_id} started service")

                service_time = self._customer_rng(customer_id, 53).expovariate(
                    1.0 / self.scenario.mean_service_minutes
                )
                service_start = float(self.env.now)
                yield self.env.timeout(service_time)
                self._record_busy(service_start, float(self.env.now))
                self.completed += 1
                self._snapshot(f"Customer {customer_id} completed")
                return

        self.abandoned += 1
        wait = float(self.env.now - arrival_time)
        self.total_wait_minutes += wait
        self._snapshot(f"Customer {customer_id} abandoned")

    def _arrivals(self):
        customer_id = 1
        while self.env.now < self.scenario.horizon_minutes:
            interarrival = self.arrival_rng.expovariate(
                1.0 / self.scenario.mean_interarrival_minutes
            )
            yield self.env.timeout(interarrival)
            if self.env.now > self.scenario.horizon_minutes:
                break

            self.arrivals += 1
            if self.routing_rng.random() < self.decision.digital_share:
                self.digital_customers += 1
                self._snapshot(f"Customer {customer_id} routed digitally")
            else:
                self.env.process(self._customer(customer_id))
            customer_id += 1

    def _average_queue(self) -> float:
        if not self._queue_points or self.scenario.horizon_minutes <= 0:
            return 0.0

        points = sorted(self._queue_points, key=lambda point: point[0])
        area = 0.0

        for index, (start, value) in enumerate(points):
            end = (
                points[index + 1][0]
                if index + 1 < len(points)
                else self.scenario.horizon_minutes
            )
            clipped_start = min(start, self.scenario.horizon_minutes)
            clipped_end = min(end, self.scenario.horizon_minutes)
            area += max(0.0, clipped_end - clipped_start) * value

        return area / self.scenario.horizon_minutes

    def run(self) -> ReplicationResult:
        self._snapshot("Branch opened")
        self.env.process(self._arrivals())
        self.env.run()
        self._snapshot("Branch cleared")

        utilization_denom = self.decision.tellers * self.scenario.horizon_minutes
        utilization = (
            self.busy_minutes_in_horizon / utilization_denom
            if utilization_denom > 0
            else 0.0
        )

        return ReplicationResult(
            seed=self.seed,
            arrivals=self.arrivals,
            digital_customers=self.digital_customers,
            physical_customers=self.physical_customers,
            completed=self.completed,
            abandoned=self.abandoned,
            avg_wait=statistics.fmean(self.wait_times) if self.wait_times else 0.0,
            p95_wait=percentile(self.wait_times, 95.0),
            max_queue=self.max_queue,
            avg_queue=self._average_queue(),
            utilization=utilization,
            abandonment_rate=self.abandoned / self.physical_customers
            if self.physical_customers > 0
            else 0.0,
            total_wait_minutes=self.total_wait_minutes,
            elapsed_minutes=float(self.env.now),
        )


def simulate(
    decision: Decision,
    scenario: Scenario,
    seed: int = 42,
) -> tuple[ReplicationResult, list[dict[str, float | int | str]]]:
    simulation = BankSimulation(decision=decision, scenario=scenario, seed=seed)
    result = simulation.run()
    return result, simulation.timeline


def result_as_dict(result: ReplicationResult) -> dict[str, int | float]:
    return asdict(result)
