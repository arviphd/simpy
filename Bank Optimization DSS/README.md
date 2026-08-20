# BranchFlow: SimPy Optimization, DSS, and Animation

This example translates the optimization workflow from the AnyLogic guide into a
small, inspectable Python project. It chooses a daily branch policy using repeated
stochastic simulations and then exposes the result through a decision-support app
and an animated replay.

## Decision problem

The optimizer chooses:

- `tellers`: staffed physical-service capacity, from 1 to 6 by default.
- `digital_share`: the share of arrivals handled digitally, from 0% to 40%.

The daily objective includes teller labor, digital transactions, customer waiting,
abandonment, and a soft penalty when utilization is outside the preferred 65%-90%
band. A large penalty is added unless at least 95% of replications satisfy each
hard constraint:

- Mean replicated p95 wait must be no more than 10 minutes.
- Mean replicated abandonment must be no more than 5%.

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

The command creates `outputs/optimization_results.csv` and
`outputs/recommended_policy.json`. Start with 3-5 replications while changing the
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
