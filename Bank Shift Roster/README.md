# Bank Shift Roster: Optimization with Simulation as the Judge

This example builds a daily shift roster for a bank branch. An integer program finds the
cheapest roster, but it can only use a rough formula for how long customers wait. A SimPy
model then plays the roster on many days and judges whether it really meets the service
rule. The two take turns until no cheaper roster passes.

## Decision problem

- The branch is open **9:00 to 17:00**. Arrivals per hour, from 9:00:
  30, 40, 50, **90, 100** (lunch rush), 50, 36, 30.
- Service takes 4 minutes on average (exponential). One shared line, first come first served.
- Shifts: **full-time 9–17, cost 8**, or **part-time 4 hours** starting at 9, 10, 11, 12 or
  13, **cost 5** each.
- Rule: customers arriving in any hour wait **at most 1 minute on average**.

The decision is how many people to put on each of the 6 shifts (0 to 10 each gives about
1.8 million rosters). The goal is the cheapest roster that meets the rule.

## The loop

1. **Formula.** The Erlang C (M/M/c) formula gives the tellers each hour needs, treating
   every hour as if it ran forever on its own.
2. **Integer program.** A covering IP (OR-Tools, CBC) finds the cheapest shifts that give at
   least that many tellers in every hour.
3. **Simulation.** SimPy plays the roster for 20 days (same seeds for every roster, separate
   random streams for arrivals and service) and reports the average wait per hour.
4. **Adjust.** Ask the IP for one teller fewer in one hour. Keep the change only if the new
   roster is cheaper and the simulation still passes. Stop when no change is kept.

## Results for the default scenario

| Round | Ask the IP for | Cost | Simulation | Decision |
|---|---|---|---|---|
| 1 | Formula's needs | 57 | Every hour passes | Start |
| 2 | 1 fewer at 13:00 | 52 | 14:00 waits 1.52 min | Undo |
| 3 | 1 fewer at 9:00 | 54 | Worst hour 0.99 min | Keep |
| 4 | 1 fewer at 13:00 | 52 | 14:00 waits 1.52 min | Undo, stop |

Final roster: 3 full-time, 4 part-time 10–14, 1 part-time 11–15, 1 part-time 13–17.
Cost 54, 5% below the formula's roster, using 17 IP solves and 4 simulations.

The formula is wrong in both directions:

| Hour | Tellers | Formula wait | Simulated wait | Why |
|---|---|---|---|---|
| 9:00 | 3 | 1.78 | 0.94 | The bank opens empty |
| 13:00 | 8 | 1.60 | 0.87 | The rush is short; the queue never fully builds |
| 14:00 | 5 | 0.78 | 1.52 | The lunch queue carries over |

## Project map

- `roster.py`: the formula, the integer program, the SimPy model and the improvement loop.
- `tests/test_core.py`: regression tests for the formula, the IP and the loop result.

## Setup

From this directory:

```bash
python3 -m pip install -r requirements.txt
```

## Run

```bash
python3 roster.py
python3 -m unittest discover -s tests
```

## Extending the example

- Raise the lunch rush to 120 customers and see which hours the formula gets wrong.
- Tighten the rule to 0.5 minutes, or use "90% of customers wait under 3 minutes".
- Add a 2-hour shift or a split shift.
- Instead of asking for one teller fewer, add a cut to the IP wherever the simulation fails
  (the approach of Atlason, Epelman and Henderson).
