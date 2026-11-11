# Simulation for Optimization with SimPy

Teaching material for learning discrete event simulation in Python with
[SimPy](https://simpy.readthedocs.io/), and for using simulation to make better decisions.
The material starts with a simulated queue and ends with simulation working alongside an
integer program.

Every example uses the same setting: a bank branch where customers arrive at random and
wait for tellers. Each folder is a self-contained project with its own README,
requirements and run commands.

## Why simulate? Averages hide queues

A customer arrives every 3 minutes on average, service takes 4 minutes on average, and
there are 2 tellers.

- **Plan with averages:** each teller gets a customer every 6 minutes and is free after 4.
  Nobody waits.
- **Simulate the randomness** (exponential gaps and service times, 20 simulated days using
  seeds 1 to 20 in `Bank Example - Simple/replicate.py`; other seeds give slightly different figures): the
  average wait is about **2.8 minutes**, 1 customer in 20 waits more than 11 minutes, and
  the line peaks near 8, even though the tellers are busy only 67% of the time.

Busy and quiet spells do not cancel out. You only see the queue by playing out the
randomness.

## Three uses of simulation in optimization

| Use | When | Project |
|---|---|---|
| **1. Stress-test a plan** | An optimizer or an averages-based plan gives a decision. Simulation plays it against real randomness to check whether it holds up. | [Bank Example - Simple](Bank%20Example%20-%20Simple/) |
| **2. Optimize under uncertainty** | Randomness drives the answer and the math model would be complex. Search over the options and score each one on many simulated days. | [Bank Optimization DSS](Bank%20Optimization%20DSS/) |
| **3. Simulation as the objective** | An integer program finds the solution but has only a rough formula for one part of the problem. Simulation judges each solution, and the model is adjusted and solved again. | [Bank Shift Roster](Bank%20Shift%20Roster/) |

In all three, optimization (or a search) proposes and simulation tests.

## The projects

| Folder | What it shows | Main tools |
|---|---|---|
| [`Bank Example - Simple`](Bank%20Example%20-%20Simple/) | One day at a branch with 2 tellers and one shared line. Reports average and 95th-percentile wait, line length and teller utilization, with an animated replay and a script that replicates the day over many seeds. | SimPy, Matplotlib |
| [`Bank Optimization DSS`](Bank%20Optimization%20DSS/) | Chooses the number of tellers and the share of customers served digitally. Scores every policy on 20 replicated days under service-level rules, then presents the result in a decision-support app and an animation. | SimPy, Streamlit, pandas |
| [`Bank Shift Roster`](Bank%20Shift%20Roster/) | Builds the cheapest daily shift roster. An Erlang C formula and a covering integer program propose rosters, and SimPy checks each one hour by hour until no cheaper roster passes. | SimPy, OR-Tools, Streamlit |

## Suggested path

1. **Build a simulation.** Run `Bank Example - Simple`. Before you run it, guess the
   average wait with 2 tellers, then compare your guess with the result. Read the event
   log for the first 10 customers and check two by hand.
2. **Replicate and compare.** Run `replicate.py` to play 20 days (seeds 1 to 20) and report
   the average wait with a 95% interval (mean ± t × s ÷ √n). This gives 2.8 minutes (2.1 to
   3.5) with 2 tellers and 0.35 minutes (0.27 to 0.42) with 3, so the two intervals do not
   overlap. Try 50 tellers as an extreme test: the wait should vanish.
3. **Search over options.** Run `optimize.py` in `Bank Optimization DSS`, then open its app.
   Tighten the walk-out limit from 5% to 2%, or shorten the arrival gap from 3 to 2.5
   minutes, and see whether the best policy changes. Compare 5 and 20 test runs: with few
   runs, close policies can swap places.
4. **Combine optimization and simulation.** Run `Bank Shift Roster`. See where the queueing
   formula is too cautious (the bank opens empty, the lunch rush is short) and where it is
   too optimistic (the lunch queue carries into the next hour).

Each project README ends with ideas for extending it.

## SimPy in 17 lines

```python
import simpy, random

env = simpy.Environment()                       # the clock and the event list
tellers = simpy.Resource(env, capacity=2)       # the tellers, with their own line
waits = []

def customer(env):                              # one customer's story
    arrive = env.now
    with tellers.request() as req:              # join the line
        yield req                               # resume when a teller is free
        waits.append(env.now - arrive)
        yield env.timeout(random.expovariate(1/4))   # service time passes

def arrivals(env):
    while True:
        yield env.timeout(random.expovariate(1/3))
        env.process(customer(env))

env.process(arrivals(env))
env.run(until=480)                              # one 8-hour day
print(sum(waits) / len(waits))
```

This sketch sets no seed, so each run plays a different random day and prints a different
average. Add `random.seed(1)` at the top to replay the same day. `bank_sim.py` in
`Bank Example - Simple` is the full version, with a seed, KPIs, an event log and plots.

## Key ideas

- **Discrete event simulation.** Entities (customers) flow through resources (tellers) and
  wait in queues. Events (arrival, service start, departure) change the state. The clock
  jumps from one event to the next, and nothing is tracked in between.
- **Replicate.** One run is one day, and one day can mislead. Use about 5 runs while
  building, 20 or more to compare options, and 30 or more before signing off. Report a
  range, not just one number.
- **Common random numbers.** A seed fixes the day. Test every policy on the same days, with
  separate random streams for arrivals and service, so that differences come from the
  policy and not from luck.
- **Verify, then validate.** Verify that the model was built right: hand traces, extreme
  tests (50 tellers means no wait) and checks on the animation. Validate that it is the right
  model: compare with historical data and show the animation to the people who run the
  process.
- **Terminating versus steady state.** A bank opens empty and closes each day, so keep the
  empty start. A plant that runs around the clock never empties, so discard the warm-up
  before measuring.
- **Simulation does not search.** It scores only the options you give it. Wrap a search
  around it: try every option when there are few, and use the structure of the problem when
  there are many. Binary search works when more capacity is always safer, and a quick
  approximate model can shortlist candidates.

## An exercise without code: the newsvendor

Ask an AI coding agent to build this from the description alone:

> A dark store stocks fresh 1-litre milk packs each morning. Daily demand is
> Normal(100, 20) packs. A pack costs ₹30 and sells for ₹50; unsold packs are thrown away
> at night. For stock levels 70 to 130, simulate the same 2,000 days and plot average
> profit. Compare the best level with the critical-ratio formula, and report the share of
> days with a stock-out at each level.

The best stock is about 95 packs, below average demand, because the critical ratio is
20 ÷ (20 + 30) = 0.4. Then add something the formula cannot handle, such as a 4 pm
top-up delivery or a rule that stock-outs happen on at most 10% of days.

## When not to simulate

Uncertainty is a reason to model it, not necessarily a reason to simulate. If the problem
can be written as equations and a few scenarios capture the risk, a two-stage stochastic
program solves it directly and gives a provably best answer over those scenarios (see the
farmer problem in Birge and Louveaux). Simulation is still useful afterwards to
stress-test that plan on many random outcomes.

## Setup

Python 3.10 or later. Each project has its own `requirements.txt`. From inside a project
folder:

```bash
python3 -m pip install -r requirements.txt
```

A separate virtual environment per project keeps their dependencies apart.

## Further reading

- A. M. Law, *Simulation Modeling and Analysis*: the standard text on simulation studies,
  input modeling, replication and validation.
- [SimPy documentation](https://simpy.readthedocs.io/)
- J. Atlason, M. Epelman and S. Henderson (2004), "Call center staffing with simulation and
  cutting plane methods", *Annals of Operations Research*: the optimize, simulate and add a
  cut loop behind `Bank Shift Roster`.
- C. Miranda, P. Rey, A. Sauré and R. Weber (2018), metro ticket-booth staffing with an
  integer program and discrete event simulation, *Interfaces*.
- J. Birge and F. Louveaux, *Introduction to Stochastic Programming*: the farmer problem.
