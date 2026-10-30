# Truck Network Optimization: Simulation as the Objective Function

This example chooses truck departure times for a small hub network with a
neighborhood search. The search does the optimizing; a deterministic SimPy model
only scores each candidate schedule, because the true objective depends on how
trucks interact at the hub and is hard to write as a formula.

## Decision problem

- Four origins, **A, B, C, D**, each with one truck driving to a single **hub**.
  Travel time to the hub: A 60 min, B 90, C 120, D 150.
- Each origin has 6 shipments with different ready times (24 in total). A truck takes
  every shipment that is ready when it leaves. Shipments not ready yet wait for the
  next day and count as **late**.
- The hub has **2 unloading docks**. Unloading a truck takes **45 minutes**. A truck
  that arrives when both docks are busy waits.
- One **outbound truck leaves the hub at 13:00**. Any shipment unloaded after that is
  **late**.

The optimizer chooses each truck's departure time, every 30 minutes from 06:00 to
11:00 (11 options per truck, 14,641 schedules). The objective is the number of late
shipments.

The model has no randomness. Leaving later picks up more shipments, but if every
truck leaves as late as it can, all four reach the hub together and two of them
queue for a dock.

## Two objective functions

| | Quick estimate (`quick_estimate`) | Simulation (`simulate`) |
|---|---|---|
| Rule | A truck is on time if departure + travel + unloading ends before 13:00 | SimPy plays the day; the docks are a `simpy.Resource` |
| Dock queues | Ignored | Modeled |
| Cost | Almost free | One full simulation |

With unlimited docks the two always agree. With 2 docks they can disagree badly.

## Results for the default scenario

| Schedule | Quick estimate | Simulation |
|---|---|---|
| Best by the quick estimate (all trucks reach the hub at 12:00) | 4 late | 15 late |
| After local search scored by simulation | 5 late | 5 late |

- Local search starts from the quick-estimate schedule and moves one truck 30 minutes
  at a time: 15 → 9 → 5 late in two moves, using 24 simulations. Both moves send a
  truck earlier with the same load, freeing a dock before the others arrive.
- 5 late is the optimum over all 14,641 schedules (checked by enumeration). The
  remaining shipments are late because they are not ready in time.
- Two-level search (rank every move with the quick estimate, simulate only the best
  3) reaches the same schedule with 10 simulations.

With 3 docks (`--docks 3`) the quick-estimate schedule has 10 late shipments; one
search move brings it to the optimum of 4.

## Project map

- `model.py`: scenario data, the quick estimate, and the deterministic SimPy model.
- `search.py`: enumeration, local search with the simulation as the objective, and the
  two-level screen-then-simulate search.
- `timeline.py`: saves `hub_timeline.png`, a side-by-side hub timeline (waiting and
  unloading per truck) for the quick-estimate schedule and the search result.
- `dss.py`: Streamlit app to change the scenario and analyze the searches.
- `tests/test_core.py`: regression tests for the model and the search results.

## Setup

From this directory:

```bash
python3 -m pip install -r requirements.txt
```

## Run

```bash
python3 search.py                 # results for the default scenario
python3 search.py --docks 3       # a third dock
python3 search.py --top-k 5       # simulate more moves per step in the two-level search
python3 timeline.py               # saves hub_timeline.png
python3 -m unittest discover -s tests
```

## Open the app

```bash
python3 -m streamlit run dss.py
```

The sidebar sets the docks, unloading time, outbound departure, travel times, departure
window and search settings; the shipment ready times are editable on the page. Results
update as you change inputs. The tabs show the recommended schedule and its hub
timeline, each search's progress and cost, how often the quick estimate disagrees with
the simulation across all schedules, and a sandbox for simulating any schedule by hand.
Comparing against every schedule is skipped above 60,000 schedules (for example, a
15-minute departure step).

## Extending the example

- Make unloading time depend on the number of shipments, or add more docks.
- Replace steepest descent with first-improvement, or add tabu search or random
  restarts. Starting from every truck at 06:00 shows where plain local search stalls.
- Add a second outbound truck with its own departure time and destinations.
- Add random travel times. Each schedule then needs several replications, and the
  comparison should use common random numbers.
