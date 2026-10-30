"""Deterministic SimPy model of a small truck network feeding one hub.

Four trucks, one at each origin (A, B, C, D), drive to a hub. A truck carries every
shipment at its origin that is ready when it leaves; anything not ready waits for
tomorrow. The hub has a limited number of unloading docks, and one outbound truck
leaves the hub at a fixed time. A shipment is on time only if its truck has been
unloaded before the outbound truck leaves.

There is no randomness anywhere in this model. Simulation is used because the
objective (how many shipments are late) depends on how the trucks interact at the
docks, which a simple formula ignores.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import simpy


def hhmm(minutes: float) -> str:
    """Format minutes after midnight as HH:MM."""
    m = int(round(minutes))
    return f"{m // 60:02d}:{m % 60:02d}"


def clock(text: str) -> int:
    """Parse HH:MM into minutes after midnight."""
    hours, mins = text.split(":")
    return int(hours) * 60 + int(mins)


# Shipments waiting at each origin, by the time they are ready to be picked up.
DEFAULT_READY = {
    "A": ["07:00", "07:30", "08:30", "10:00", "10:30", "10:30"],
    "B": ["06:00", "06:30", "09:30", "10:30", "10:30", "11:00"],
    "C": ["07:30", "07:30", "08:00", "09:30", "09:30", "10:00"],
    "D": ["07:00", "09:00", "09:30", "10:00", "10:00", "11:00"],
}


@dataclass(frozen=True)
class Scenario:
    travel_minutes: dict[str, int] = field(default_factory=lambda: {"A": 60, "B": 90, "C": 120, "D": 150})
    ready: dict[str, list[str]] = field(default_factory=lambda: dict(DEFAULT_READY))
    docks: int = 2
    unload_minutes: int = 45
    outbound_departure: str = "13:00"
    earliest_departure: str = "06:00"
    latest_departure: str = "11:00"
    step_minutes: int = 30

    @property
    def origins(self) -> list[str]:
        return list(self.travel_minutes)

    @property
    def slots(self) -> list[int]:
        """Allowed departure times, in minutes after midnight."""
        return list(range(clock(self.earliest_departure), clock(self.latest_departure) + 1, self.step_minutes))

    @property
    def total_shipments(self) -> int:
        return sum(len(times) for times in self.ready.values())


# A schedule maps each origin to its truck's departure time (minutes after midnight).
Schedule = dict[str, int]


@dataclass
class TruckRecord:
    origin: str
    departs: int
    carries: int
    arrives: int
    unload_start: int
    unload_end: int
    on_time: bool


def carried(scenario: Scenario, origin: str, departure: int) -> int:
    """Number of shipments ready at the origin by the truck's departure."""
    return sum(clock(t) <= departure for t in scenario.ready[origin])


def quick_estimate(schedule: Schedule, scenario: Scenario | None = None) -> int:
    """Rough objective: late shipments if every truck unloads the moment it arrives.

    This is the 'formula' version of the objective. It is fast, but it ignores the
    dock limit, so it cannot see trucks queueing at the hub.
    """
    sc = scenario or Scenario()
    outbound = clock(sc.outbound_departure)
    on_time = 0
    for origin in sc.origins:
        finish = schedule[origin] + sc.travel_minutes[origin] + sc.unload_minutes
        if finish <= outbound:
            on_time += carried(sc, origin, schedule[origin])
    return sc.total_shipments - on_time


def simulate(schedule: Schedule, scenario: Scenario | None = None) -> tuple[int, list[TruckRecord]]:
    """Exact objective: play the day in SimPy, with trucks queueing for the docks.

    Returns the number of late shipments and one record per truck (for timelines).
    """
    sc = scenario or Scenario()
    outbound = clock(sc.outbound_departure)
    start = min(min(schedule.values()), sc.slots[0])
    env = simpy.Environment(initial_time=start)
    docks = simpy.Resource(env, capacity=sc.docks)
    records: list[TruckRecord] = []

    def truck(origin: str):
        departs = schedule[origin]
        yield env.timeout(departs - env.now)                 # wait until departure
        yield env.timeout(sc.travel_minutes[origin])         # drive to the hub
        arrives = int(env.now)
        with docks.request() as request:                     # queue for a dock
            yield request
            unload_start = int(env.now)
            yield env.timeout(sc.unload_minutes)             # unload
        unload_end = int(env.now)
        records.append(TruckRecord(origin, departs, carried(sc, origin, departs), arrives,
                                   unload_start, unload_end, unload_end <= outbound))

    for origin in sc.origins:
        env.process(truck(origin))
    env.run()

    records.sort(key=lambda r: (r.arrives, r.origin))
    on_time = sum(r.carries for r in records if r.on_time)
    return sc.total_shipments - on_time, records


def late_shipments(schedule: Schedule, scenario: Scenario | None = None) -> int:
    """Convenience wrapper: the simulated objective only."""
    return simulate(schedule, scenario)[0]
