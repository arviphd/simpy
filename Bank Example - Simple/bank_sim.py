"""Simple standalone bank simulation summary metrics and plots."""

from __future__ import annotations

import statistics

import matplotlib.pyplot as plt
import random
import simpy


class BankSimulation:
    def __init__(
        self,
        simulation_time: float = 480.0,
        mean_interarrival: float = 3.0,
        mean_service: float = 4.0,
        tellers: int = 2,
        seed: int = 42,
        verbose: bool = False,
    ):
        self.sim_time = simulation_time
        self.mean_interarrival = mean_interarrival
        self.mean_service = mean_service
        self.tellers = tellers
        self.verbose = verbose

        self.rng = random.Random(seed)

        self.env = simpy.Environment()
        self.counter = simpy.Resource(self.env, capacity=tellers)

        self.wait_times: list[float] = []
        self.system_times: list[float] = []
        self.service_times: list[float] = []

        self._queue_times = [0.0]
        self._queue_vals = [0]
        self._service_times = [0.0]
        self._service_vals = [0]

        self.total_service_busy = 0.0
        self.customers_completed = 0
        self.arrivals_count = 0
        self.timeline: list[tuple[float, int, int]] = []

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)

    def _record(self, timeline_time: float, queue_len: int, tellers_in_use: int) -> None:
        self._queue_times.append(timeline_time)
        self._queue_vals.append(queue_len)
        self._service_times.append(timeline_time)
        self._service_vals.append(tellers_in_use)
        self.timeline.append((round(timeline_time, 2), queue_len, tellers_in_use))

    def _record_time_avg(
        self,
        times: list[float],
        vals: list[int | float],
        end_time: float,
    ) -> float:
        if not times:
            return 0.0
        area = 0.0
        for index in range(len(times) - 1):
            area += (times[index + 1] - times[index]) * vals[index]
        area += (end_time - times[-1]) * vals[-1]
        return area / end_time if end_time > 0 else 0.0

    @staticmethod
    def _pct(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = int((len(ordered) - 1) * (p / 100.0))
        return ordered[index]

    def _customer(self, cid: int):
        arrival = self.env.now
        self._log(f"{self.env.now:6.2f}: customer {cid} arrived")
        self._record(self.env.now, len(self.counter.queue), len(self.counter.users))

        with self.counter.request() as request:
            yield request
            wait = self.env.now - arrival
            self.wait_times.append(wait)

            self._record(self.env.now, len(self.counter.queue), len(self.counter.users))
            self._log(
                f"{self.env.now:6.2f}: customer {cid} starts service after {wait:5.2f} min"
            )

            service_time = self.rng.expovariate(1.0 / self.mean_service)
            self.service_times.append(service_time)
            self.total_service_busy += service_time
            yield self.env.timeout(service_time)

            self._log(f"{self.env.now:6.2f}: customer {cid} completed")
            self.system_times.append(self.env.now - arrival)
            self.customers_completed += 1

            self._record(self.env.now, len(self.counter.queue), len(self.counter.users))

    def _arrivals(self):
        cid = 1
        while self.env.now < self.sim_time:
            self.arrivals_count += 1
            self.env.process(self._customer(cid))
            cid += 1
            yield self.env.timeout(self.rng.expovariate(1.0 / self.mean_interarrival))

    def run(
        self,
        make_plots: bool = True,
        output_plot: str = "bank_sim_plot.png",
        show_plot: bool = True,
    ):
        self._record(0.0, 0, 0)
        self.env.process(self._arrivals())
        self.env.run(until=self.sim_time)

        avg_wait = statistics.mean(self.wait_times) if self.wait_times else 0.0
        avg_system = statistics.mean(self.system_times) if self.system_times else 0.0
        avg_queue = self._record_time_avg(self._queue_times, self._queue_vals, self.sim_time)
        avg_tellers_in_use = self._record_time_avg(
            self._service_times,
            self._service_vals,
            self.sim_time,
        )

        utilization = (
            self.total_service_busy / (self.tellers * self.sim_time)
            if self.tellers and self.sim_time > 0
            else 0.0
        )

        results = {
            "simulation_time": self.sim_time,
            "tellers": self.tellers,
            "customers_completed": self.customers_completed,
            "arrivals": self.arrivals_count,
            "avg_wait": avg_wait,
            "avg_system": avg_system,
            "p95_wait": self._pct(self.wait_times, 95),
            "max_queue": max(self._queue_vals),
            "avg_queue": avg_queue,
            "avg_tellers_in_use": avg_tellers_in_use,
            "utilization": utilization,
        }

        print("\n===== Results =====")
        print(f"Simulation time:          {results['simulation_time']:.2f} min")
        print(f"Tellers:                  {results['tellers']}")
        print(f"Customers completed:      {results['customers_completed']}")
        print(f"Arrivals:                 {results['arrivals']}")
        print(f"Avg waiting time:         {results['avg_wait']:.2f} min")
        print(f"Avg total system time:    {results['avg_system']:.2f} min")
        print(f"95th pct waiting time:    {results['p95_wait']:.2f} min")
        print(f"Max queue length:         {results['max_queue']}")
        print(f"Average queue length:     {results['avg_queue']:.2f}")
        print(f"Avg tellers in use:       {results['avg_tellers_in_use']:.2f}")
        print(f"Teller utilization:       {results['utilization']:.2%}")

        if make_plots:
            self._plot_results(results, output_plot=output_plot, show_plot=show_plot)

        return results

    def _plot_results(self, results, output_plot: str = "bank_sim_plot.png", show_plot: bool = True):
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))

        axes[0, 0].plot(self._queue_times, self._queue_vals, drawstyle="steps-post")
        axes[0, 0].set_title("Queue length")
        axes[0, 0].set_xlabel("Time")
        axes[0, 0].set_ylabel("Customers")
        axes[0, 0].grid(True, alpha=0.2)

        axes[0, 1].plot(self._service_times, self._service_vals, drawstyle="steps-post")
        axes[0, 1].set_title("Tellers in use")
        axes[0, 1].set_xlabel("Time")
        axes[0, 1].set_ylabel("Busy tellers")
        axes[0, 1].set_ylim(0, max(1, self.tellers))
        axes[0, 1].grid(True, alpha=0.2)

        if self.wait_times:
            axes[1, 0].hist(self.wait_times, bins=20, alpha=0.7)
            axes[1, 0].axvline(
                results["avg_wait"],
                color="tab:blue",
                linestyle="--",
                label="avg",
            )
            axes[1, 0].set_title("Waiting time distribution")
            axes[1, 0].set_xlabel("Minutes")
            axes[1, 0].set_ylabel("Count")
            axes[1, 0].legend()
        else:
            axes[1, 0].set_title("Waiting time distribution")
            axes[1, 0].text(0.5, 0.5, "No wait times\n(records empty)", ha="center", va="center")

        if self.system_times:
            axes[1, 1].hist(self.system_times, bins=20, color="tab:green", alpha=0.7)
            axes[1, 1].axvline(
                results["avg_system"],
                color="red",
                linestyle="--",
                label="avg",
            )
            axes[1, 1].set_title("System time distribution")
            axes[1, 1].set_xlabel("Minutes")
            axes[1, 1].set_ylabel("Count")
            axes[1, 1].legend()
        else:
            axes[1, 1].set_title("System time distribution")
            axes[1, 1].text(
                0.5,
                0.5,
                "No system times\n(records empty)",
                ha="center",
                va="center",
            )

        fig.tight_layout()
        if output_plot:
            fig.savefig(output_plot, dpi=140, bbox_inches="tight")
            print(f"Saved plot: {output_plot}")

        if show_plot:
            plt.show()
        plt.close(fig)


if __name__ == "__main__":
    simulation = BankSimulation(
        simulation_time=480.0,
        mean_interarrival=3.0,
        mean_service=4.0,
        tellers=2,
        seed=7,
        verbose=True,
    )
    simulation.run(make_plots=True, show_plot=True, output_plot="bank_sim_plot.png")
