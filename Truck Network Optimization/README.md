# Truck Network Optimization: Simulation as the Objective Function

A small, fully deterministic example of using simulation **only to evaluate the
objective function** inside an optimization search. The optimizer (a neighborhood
search) still decides; the simulation just scores each candidate, because the true
objective is too tangled to write as a formula.

It is a toy version of a real truck-network planner (HaulPLAN), small enough to
build in class and to check by hand.

## The problem

- Four origins, **A, B, C, D**, each with one truck driving to a single **hub**.
  Travel time to the hub: A 60 min, B 90, C 120, D 150.
- Each origin has 6 shipments with different ready times (24 in total). A truck takes
  every shipment that is ready when it leaves. Shipments not ready yet wait for
  tomorrow and count as **late**.
- The hub has only **2 unloading docks**. Unloading a truck takes **45 minutes**.
  A truck that arrives when both docks are busy waits.
- One **outbound truck leaves the hub at 13:00**. Any shipment unloaded after that is
  **late**.

**Decision:** the departure time of each truck, every 30 minutes from 06:00 to 11:00
(11 options per truck, so 11^4 = 14,641 schedules).

**Objective:** minimize the number of late shipments.

There is no randomness anywhere. Leaving later picks up more shipments, but if every
truck leaves as late as it can, all four reach the hub together and two of them
queue for a dock. That interaction is what a simple formula misses.

## Two ways to score a schedule

| | Quick estimate (`quick_estimate`) | Simulation (`simulate`) |
|---|---|---|
| Idea | A truck is on time if departure + travel + 45 min is before 13:00 | SimPy plays the day; the docks are a `simpy.Resource` with capacity 2 |
| Sees dock queues? | No | Yes |
| Cost | Almost free | One full simulation |

With unlimited docks the two always agree (there is a test for this). With 2 docks
they can disagree badly.

## Results (default scenario)

```text
python3 search.py
```

| | Quick estimate says | Simulation says |
|---|---|---|
| Best plan by the quick estimate (every truck leaves as late as it can; all arrive 12:00) | 4 late | **15 late** |
| After local search with the simulation as the objective | 5 late | **5 late** |

- The local search starts from the quick-estimate plan and moves one truck ±30 min at
  a time: **15 → 9 → 5 late** in two moves, using **24 simulations**. Both moves send a
  truck 30 minutes earlier with the same load, so it frees a dock before the others
  arrive. The quick estimate sees no benefit in that, so it can never find it.
- **5 late is the best of all 14,641 schedules** (checked by enumeration). The
  remaining 5 shipments are late only because they are not ready in time.
- **Two-level search** (screen every move with the quick estimate, simulate only the
  best 3): same 5-late plan with **10 simulations** instead of 24.

Try a third dock with `python3 search.py --docks 3`: the quick-estimate plan improves
to 10 late but still bunches at the hub, and one search move fixes it (4 late).

## Project map

- `model.py`: scenario data, the quick estimate, and the deterministic SimPy model.
- `search.py`: enumeration, local search with the simulation as the objective, and
  the two-level (screen-then-simulate) search. Prints the results above.
- `timeline.py`: saves `hub_timeline.png`, a side-by-side hub timeline (waiting and
  unloading per truck) for the quick-estimate plan and the search result.
- `tests/test_core.py`: regression tests that pin the numbers used in class.

## Setup and run

From this directory:

```bash
python3 -m pip install -r requirements.txt
python3 search.py                 # results above
python3 search.py --docks 3       # extension: a third dock
python3 timeline.py               # saves hub_timeline.png
python3 -m unittest discover -s tests
```

## Ideas for students

- Add a third dock, or make unloading depend on the number of shipments.
- Replace steepest descent with first-improvement, or add tabu or random restarts
  (start from every truck at 06:00 and see where plain local search gets stuck).
- Add a second outbound truck with its own departure time and destinations.
- Add randomness to travel times: now the problem becomes use 2 (optimize under
  uncertainty), and each schedule needs several replications.

## How it connects to the course

- **Simulation sessions:** the third use of simulation. Use 1 stress-tests a plan
  (here, the quick-estimate plan), use 2 optimizes under uncertainty (the bank DSS),
  use 3 uses simulation only as the objective (this project).
- **Heuristics sessions (7-10):** the same neighborhood search; only the score changes.
