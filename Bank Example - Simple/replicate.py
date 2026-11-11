"""Replicate the bank day over many seeds and report the average wait with a 95% interval."""

from __future__ import annotations

import argparse
import contextlib
import io
import statistics

from bank_sim import BankSimulation

# Two-sided 95% Student t values by degrees of freedom; larger samples use 1.96.
T_975 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
    23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
    30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980,
}


def t_value(df: int) -> float:
    for limit in sorted(T_975):
        if df <= limit:
            return T_975[limit]
    return 1.96


def replicate(tellers: int, days: int, first_seed: int) -> list[dict]:
    results = []
    for seed in range(first_seed, first_seed + days):
        simulation = BankSimulation(tellers=tellers, seed=seed)
        with contextlib.redirect_stdout(io.StringIO()):  # hide the per-day summary
            results.append(simulation.run(make_plots=False, show_plot=False))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tellers", type=int, nargs="+", default=[2, 3])
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--first-seed", type=int, default=1)
    args = parser.parse_args()
    if args.days < 2:
        parser.error("--days must be at least 2 to compute an interval")

    print(f"{args.days} days, seeds {args.first_seed} to {args.first_seed + args.days - 1}")
    for tellers in args.tellers:
        results = replicate(tellers, args.days, args.first_seed)
        waits = [r["avg_wait"] for r in results]
        mean = statistics.fmean(waits)
        half = t_value(args.days - 1) * statistics.stdev(waits) / args.days**0.5
        utilization = statistics.fmean(r["utilization"] for r in results)
        print(
            f"{tellers} tellers: average wait {mean:.2f} min "
            f"(95% interval {mean - half:.2f} to {mean + half:.2f}), "
            f"best day {min(waits):.2f}, worst day {max(waits):.2f}, "
            f"tellers busy {utilization:.0%}"
        )


if __name__ == "__main__":
    main()
