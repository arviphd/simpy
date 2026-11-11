# BranchFlow: SimPy Optimization, DSS, and Animation

This example is a small, inspectable simulation-optimization project in Python. It
chooses a daily branch policy by trying every candidate policy on repeated stochastic
simulations, and then presents the result in a decision-support app and an animated
replay.

## Decision problem

The optimizer chooses:

- `tellers`: staffed physical-service capacity, from 1 to 6 by default.
- `digital_share`: the share of arrivals handled digitally, from 0% to 40%.

The daily objective includes teller labor, digital transactions, customer waiting,
abandonment, and a soft penalty when utilization is outside the preferred 65%-90%
band. Each replication (one simulated day) is checked against two service rules, and
a policy is feasible only if at least 95% of its replications pass each rule.
Infeasible policies get a large penalty:

- The day's 95th-percentile wait is no more than 10 minutes.
- The day's abandonment rate is no more than 5%.

Every policy is evaluated with the same sequence of random seeds. Independent
decision-stable streams are used for arrivals, routing, and each customer's patience
and service time. This common-random-numbers design makes comparisons less noisy
while retaining stochastic operations.

## Project map

- `model.py`: SimPy model, inputs, KPIs, feasibility data, and event timeline.
- `optimize.py`: replicated grid search, objective calculation, ranking, CSV export,
  and recommended-policy JSON export.
- `dss.py`: interactive Streamlit DSS for assumptions, constraints, alternatives,
  trade-offs, and deterministic replay charts.
- `animate.py`: Matplotlib floor-view animation for a selected policy.

## Setup

From this directory:

```bash
python3 -m pip install -r requirements.txt
```

This installs into the active global Python environment. Use an isolated environment
instead if the machine hosts projects with incompatible dependency requirements.

## Run the optimization experiment

```bash
python3 optimize.py --replications 20 --seed 2026
```

The command tries 6 teller levels × 5 digital shares (0%, 10%, ..., 40%) = 30
policies, and creates `outputs/optimization_results.csv` and
`outputs/recommended_policy.json`. With these settings, 20 of the 30 policies are
feasible and the best is 3 tellers with 10% digital, at $859.29 a day. Two tellers
fail the abandonment rule at every digital share. Start with 3-5 replications while changing the
model, then use 20 or more for comparison and 30 or more for final sign-off.

## Open the DSS

```bash
streamlit run dss.py
```

Change demand, service, patience, service-level constraints, search bounds, and
replication count in the sidebar. The app reruns the complete candidate experiment
and reports the best feasible policy. If no policy is feasible, it says so explicitly
and displays the least-cost penalized alternative rather than presenting it as valid.
Changing an input invalidates the displayed results until the optimization button is
selected again.

The app's defaults differ from `optimize.py`: it uses 15 test runs and steps the
digital share by 5%, so it tries 54 policies. With those defaults it recommends 3
tellers with 25% digital ($878.71 a day), not the 10% that `optimize.py` finds. To
match the command-line result, set the test runs to 20. The difference is itself a
lesson: with few replications, policies whose costs are close can swap places.

## Run an animation

```bash
python3 animate.py --tellers 3 --digital-share 0.2 --seed 2026
```

Use the teller count and digital share recommended by the DSS or optimizer. The
animation uses an exact seeded replay, so its operating story can be reproduced.

## Extending the example

Good next decision variables are shift-specific staffing, appointment allocation,
express-service capacity, and cross-trained staff. Before expanding the search,
publish each new cost and service KPI separately, state which rules are truly hard,
and keep the seed and replication configuration with every exported result.
