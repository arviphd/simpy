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
- `replicate.py`: runs many days (one seed per day) and reports the average wait with a
  95% interval, the best and worst day, and teller utilization.

## Setup

From this directory:

```bash
python3 -m pip install -r requirements.txt
```

## Run

```bash
python3 bank_sim.py        # one day with seed 7: event log, summary, plot
python3 animate_bank.py    # animated replay of the same day
python3 replicate.py       # 20 days (seeds 1-20) with 2 and with 3 tellers
```

`replicate.py` accepts `--tellers` (one or more values), `--days` and `--first-seed`, for
example `python3 replicate.py --tellers 2 3 4 --days 30`. With the defaults it reports an
average wait of 2.82 minutes (95% interval 2.15 to 3.49) with 2 tellers and 0.35 minutes
(0.27 to 0.42) with 3. One day can mislead: across those 20 days the 2-teller average
ranges from about 1 to 6 minutes.

## Notes

- The seed fixes the day: the same seed replays the same customers.
- Arrival gaps and service times are drawn from one random stream. Changing the number
  of tellers changes the order of the draws, so later arrivals differ between runs with
  different staffing. For a fair comparison of policies, use separate streams for
  arrivals and service, as in `Bank Optimization DSS`.

## Extending the example

- Extreme test: run `replicate.py --tellers 50`. The wait should vanish.
- Add customers who walk out after waiting too long.
- Let the arrival rate change by hour (a lunch rush).
