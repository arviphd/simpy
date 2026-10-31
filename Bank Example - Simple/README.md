# Bank Example - Simple

A single-day SimPy model of a bank branch: customers arrive at random, join one
shared line, and are served first come, first served by a fixed number of tellers.

## Model

- Arrivals: exponential gaps, mean 3 minutes.
- Service: exponential, mean 4 minutes.
- Tellers: 2, a `simpy.Resource` with that capacity.
- One day: 480 minutes. Customers still waiting at closing are counted with their wait so far,
  so the wait figures are a lower bound.

The parameters are arguments of `BankSimulation` (`simulation_time`, `mean_interarrival`,
`mean_service`, `tellers`, `seed`).

Reported measures: average and 95th-percentile wait, average time in the bank, maximum
and average line length, average tellers in use, and teller utilization.

## Project map

- `bank_sim.py`: the model, the summary measures, and a four-panel plot saved as
  `bank_sim_plot.png`.
- `animate_bank.py`: replays one simulated day as an animation with play, pause and speed
  controls.

## Setup

From this directory:

```bash
python3 -m pip install -r requirements.txt
```

## Run

```bash
python3 bank_sim.py        # one day with seed 7: event log, summary, plot
python3 animate_bank.py    # animated replay of the same day
```

## Notes

- The seed fixes the day: the same seed replays the same customers.
- Arrival gaps and service times are drawn from one random stream. Changing the number
  of tellers changes the order of the draws, so later arrivals differ between runs with
  different staffing. For a fair comparison of policies, use separate streams for
  arrivals and service, as in `Bank Optimization DSS`.

## Extending the example

- Run 20 or more seeds and report the average wait with a 95% interval.
- Add customers who walk out after waiting too long.
- Let the arrival rate change by hour (a lunch rush).
