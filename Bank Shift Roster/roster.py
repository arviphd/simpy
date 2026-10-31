"""Bank shift roster: an integer program on a rough formula, judged by a simulation.

Day: 9:00-17:00, 8 one-hour periods; the arrival rate changes by hour (lunch rush).
Service: exponential, mean 4 minutes. One shared line, first come first served.
Shifts: full-time 9-17 (cost 8) or part-time 4 hours starting at 9, 10, 11, 12 or 13 (cost 5).
Rule: in every hour, customers arriving in that hour wait at most 1 minute on average.

Step 1  queueing formula (Erlang C): tellers needed in each hour, hour by hour
Step 2  integer program: cheapest shifts that cover those needs
Step 3  simulation: does the roster really meet the rule in every hour?
Step 4  ask the integer program for one teller fewer in one hour; keep the change only if
        the roster is cheaper and the simulation still passes; stop when nothing is kept
"""
from __future__ import annotations

import math
import random
import statistics
import sys

import simpy
from ortools.linear_solver import pywraplp

HOURS = list(range(9, 17))
ARRIVALS_PER_HOUR = [30, 40, 50, 90, 100, 50, 36, 30]     # lunch peak 12-14
MEAN_SERVICE = 4.0                                          # minutes
TARGET_WAIT = 1.0                                           # minutes, per hour
SHIFTS = {"Full 9-17": (9, 17, 8.0)}                        # name -> (start, end, cost)
for s in range(9, 14):
    SHIFTS[f"Part {s}-{s + 4}"] = (s, s + 4, 5.0)           # part-time: dearer per hour, but flexible
REPLICATIONS, BASE_SEED = 20, 2026


# ---------- step 1: queueing formula ----------
def erlang_c_wait(lam_per_min: float, mu_per_min: float, c: int) -> float:
    """Average wait in queue (minutes) for an M/M/c queue in steady state."""
    a = lam_per_min / mu_per_min
    if c <= a:
        return math.inf
    s = sum(a ** k / math.factorial(k) for k in range(c))
    top = a ** c / math.factorial(c) * c / (c - a)
    p_wait = top / (s + top)
    return p_wait / (c * mu_per_min - lam_per_min)


def formula_requirements() -> list[int]:
    req = []
    for lam in ARRIVALS_PER_HOUR:
        c = 1
        while erlang_c_wait(lam / 60, 1 / MEAN_SERVICE, c) > TARGET_WAIT:
            c += 1
        req.append(c)
    return req


# ---------- step 2: integer program ----------
def solve_roster(req: list[int]) -> tuple[dict[str, int], float]:
    solver = pywraplp.Solver.CreateSolver("CBC")
    x = {name: solver.IntVar(0, 20, name) for name in SHIFTS}
    for i, h in enumerate(HOURS):
        solver.Add(sum(x[n] for n, (a, b, _) in SHIFTS.items() if a <= h < b) >= req[i])
    solver.Minimize(sum(SHIFTS[n][2] * x[n] for n in SHIFTS))
    assert solver.Solve() == pywraplp.Solver.OPTIMAL
    roster = {n: int(round(x[n].solution_value())) for n in SHIFTS}
    return roster, solver.Objective().Value()


def coverage(roster: dict[str, int]) -> list[int]:
    return [sum(k for n, k in roster.items() if SHIFTS[n][0] <= h < SHIFTS[n][1]) for h in HOURS]


# ---------- step 3: simulation ----------
def simulate_day(roster: dict[str, int], seed: int) -> list[list[float]]:
    """Waits of customers grouped by the hour they arrived. Tellers finish the customer
    they are serving when their shift ends, but take no new customer after it."""
    rng_arr, rng_srv = random.Random(seed), random.Random(seed + 10_000)   # separate streams
    env = simpy.Environment(initial_time=9 * 60)
    line = simpy.Store(env)
    waits = [[] for _ in HOURS]

    def arrivals():
        while True:
            h = int(env.now // 60)
            if h >= 17:
                return
            rate = ARRIVALS_PER_HOUR[h - 9] / 60
            gap = rng_arr.expovariate(rate)
            # thinning-free piecewise approach: if the gap crosses the hour, restart at the boundary
            if env.now + gap >= (h + 1) * 60:
                yield env.timeout((h + 1) * 60 - env.now)
                continue
            yield env.timeout(gap)
            line.put((env.now, rng_srv.expovariate(1 / MEAN_SERVICE)))

    def teller(start: int, end: int):
        yield env.timeout(start * 60 - env.now)
        closing = end == 17          # tellers on duty at closing serve everyone already inside
        while env.now < end * 60 or (closing and line.items):
            if env.now >= end * 60:
                arrived, service = (yield line.get())
            else:
                get = line.get()
                res = yield get | env.timeout(end * 60 - env.now)
                if get not in res:
                    get.cancel()
                    continue
                arrived, service = res[get]
            waits[int(arrived // 60) - 9].append(env.now - arrived)
            yield env.timeout(service)

    env.process(arrivals())
    for name, k in roster.items():
        a, b, _ = SHIFTS[name]
        for _ in range(k):
            env.process(teller(a, b))
    env.run(until=20 * 60)
    assert not line.items, "customers left unserved"
    return waits


def evaluate(roster: dict[str, int]) -> list[float]:
    """Average wait per arrival hour, averaged over the replications (same seeds for every roster)."""
    per_hour = [[] for _ in HOURS]
    for r in range(REPLICATIONS):
        for i, w in enumerate(simulate_day(roster, BASE_SEED + r)):
            if w:
                per_hour[i].append(statistics.fmean(w))
    return [statistics.fmean(v) if v else 0.0 for v in per_hour]


# ---------- step 4: improve ----------
def improve(verbose: bool = True) -> dict:
    """Start from the formula's requirements. The integer program builds the cheapest roster;
    the simulation checks it. Then, hour by hour, try asking the integer program for one teller
    fewer; keep the change only if the new roster is cheaper AND the simulation still passes."""
    req = formula_requirements()
    roster, cost = solve_roster(req)
    waits = evaluate(roster)
    sims, ips = 1, 1
    log = [dict(step="formula plan", req=list(req), cover=coverage(roster), cost=cost, waits=waits, ok=max(waits) <= TARGET_WAIT, roster=roster)]
    while True:
        accepted = False
        trials = []
        for i in range(len(HOURS)):
            if req[i] <= 1:
                continue
            trial = list(req); trial[i] -= 1
            r2, c2 = solve_roster(trial); ips += 1
            if c2 < cost - 1e-9:
                trials.append((c2, i, trial, r2))
        for c2, i, trial, r2 in sorted(trials, key=lambda t: t[0]):
            w2 = evaluate(r2); sims += 1
            ok = max(w2) <= TARGET_WAIT
            log.append(dict(step=f"one fewer at {HOURS[i]}:00", req=trial, cover=coverage(r2), cost=c2, waits=w2, ok=ok, roster=r2))
            if verbose:
                print(f"  try {HOURS[i]}:00 -> cost {c2:.2f} worst wait {max(w2):.2f} {'KEEP' if ok else 'reject'}")
            if ok:
                req, roster, cost, waits, accepted = trial, r2, c2, w2, True
                break
        if not accepted:
            break
    return dict(req=req, roster=roster, cost=cost, waits=waits, sims=sims, ips=ips, log=log)


def main() -> None:
    req = formula_requirements()
    print("Tellers needed by the formula:", dict(zip(HOURS, req)))
    result = improve(verbose=False)
    for k, step in enumerate(result["log"], 1):
        status = "pass" if step["ok"] else "FAIL"
        print(f"\nRound {k}: {step['step']}  cost {step['cost']:.0f}  {status}")
        print("  roster ", {n: v for n, v in step["roster"].items() if v})
        print("  tellers", step["cover"])
        print("  waits  ", [round(w, 2) for w in step["waits"]])
    first = result["log"][0]["cost"]
    print(f"\nFinal cost {result['cost']:.0f} (formula roster {first:.0f}), "
          f"{result['ips']} integer programs, {result['sims']} simulations")


if __name__ == "__main__":
    main()
