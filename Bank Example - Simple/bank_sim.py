import random
import statistics
import simpy


class BankSimulation:
    def __init__(
        self,
        simulation_time=480.0,
        mean_interarrival=3.0,
        mean_service=4.0,
        tellers=2,
        seed=42,
        verbose=True,
    ):
        self.sim_time = simulation_time
        self.mean_interarrival = mean_interarrival
        self.mean_service = mean_service
        self.tellers = tellers
        self.verbose = verbose

        self.rng = random.Random(seed)
        random.seed(seed)

        self.env = simpy.Environment()
        self.counter = simpy.Resource(self.env, capacity=tellers)

        self.wait_times = []
        self.system_times = []
        self.service_times = []

        self._queue_times = [0.0]
        self._queue_vals = [0]

        self._service_times = [0.0]
        self._service_vals = [0]

        self.total_service_busy = 0.0
        self.timeline = []
        self.customers_completed = 0

    def _record(self, timeline_time, queue_len, tellers_in_use):
        self._queue_times.append(timeline_time)
        self._queue_vals.append(queue_len)
        self._service_times.append(timeline_time)
        self._service_vals.append(tellers_in_use)

    def _record_time_avg(self, times, vals, end_time):
        if not times:
            return 0.0
        area = 0.0
        for i in range(len(times) - 1):
            area += (times[i + 1] - times[i]) * vals[i]
        area += (end_time - times[-1]) * vals[-1]
        return area / end_time if end_time > 0 else 0.0

    def _pct(self, data, p):
        if not data:
            return 0.0
        s = sorted(data)
        idx = int((p / 100.0) * (len(s) - 1))
        return s[idx]

    def _log(self, msg):
        if self.verbose:
            print(msg)
        self.timeline.append((round(self.env.now, 2), msg))

    def customer(self, cid):
        arrival = self.env.now
        self._log(f"{self.env.now:6.2f}  Customer {cid:03d} arrives")

        with self.counter.request() as req:
            # Before waiting, this customer is in queue if no teller available.
            self._record(self.env.now, len(self.counter.queue), len(self.counter.users))

            yield req

            wait = self.env.now - arrival
            self.wait_times.append(wait)

            # Teller assigned: record state after entering service.
            self._record(self.env.now, len(self.counter.queue), len(self.counter.users))
            self._log(
                f"{self.env.now:6.2f}  Customer {cid:03d} starts service "
                f"(wait={wait:5.2f} min, queue={len(self.counter.queue)})"
            )

            service_time = self.rng.expovariate(1.0 / self.mean_service)
            self.service_times.append(service_time)
            self.total_service_busy += service_time

            yield self.env.timeout(service_time)
            self._log(
                f"{self.env.now:6.2f}  Customer {cid:03d} ends service "
                f"(service={service_time:5.2f} min)"
            )

            self.system_times.append(self.env.now - arrival)
            self.customers_completed += 1

        # Teller released automatically.
        self._record(self.env.now, len(self.counter.queue), len(self.counter.users))

    def arrivals(self):
        cid = 1
        while self.env.now < self.sim_time:
            self.env.process(self.customer(cid))
            cid += 1
            yield self.env.timeout(self.rng.expovariate(1.0 / self.mean_interarrival))

    def run(self, make_plots=True, output_plot="bank_sim_plot.png", show_plot=True):
        self._record(0.0, 0, 0)
        self.env.process(self.arrivals())
        self.env.run(until=self.sim_time)

        avg_wait = statistics.mean(self.wait_times) if self.wait_times else 0.0
        avg_system = statistics.mean(self.system_times) if self.system_times else 0.0
        avg_queue = self._record_time_avg(self._queue_times, self._queue_vals, self.sim_time)
        avg_tellers_in_use = self._record_time_avg(
            self._service_times, self._service_vals, self.sim_time
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
        print(f"Avg waiting time:         {results['avg_wait']:.2f} min")
        print(f"Avg total system time:    {results['avg_system']:.2f} min")
        print(f"95th pct waiting time:    {results['p95_wait']:.2f} min")
        print(f"Max queue length:         {results['max_queue']}")
        print(f"Average queue length:     {results['avg_queue']:.2f}")
        print(f"Avg tellers in use:       {results['avg_tellers_in_use']:.2f}")
        print(f"Teller utilization:       {results['utilization']:.2%}")

        if make_plots:
            self.plot_results(results, output_plot=output_plot, show_plot=show_plot)

        return results

    def plot_results(self, results, output_plot="bank_sim_plot.png", show_plot=True):
        try:
            import matplotlib.pyplot as plt
        except Exception:
            print("matplotlib is not installed. Run: python3 -m pip install matplotlib")
            return

        fig, axs = plt.subplots(2, 2, figsize=(12, 8))

        axs[0, 0].plot(self._queue_times, self._queue_vals, drawstyle="steps-post")
        axs[0, 0].set_title("Queue Length Over Time")
        axs[0, 0].set_xlabel("Time (min)")
        axs[0, 0].set_ylabel("Customers waiting")
        axs[0, 0].grid(True, alpha=0.2)

        axs[0, 1].plot(
            self._service_times,
            self._service_vals,
            drawstyle="steps-post",
            color="tab:orange",
        )
        axs[0, 1].set_title("Tellers in Use Over Time")
        axs[0, 1].set_xlabel("Time (min)")
        axs[0, 1].set_ylabel("Busy tellers")
        axs[0, 1].set_ylim(0, max(1, self.tellers))
        axs[0, 1].grid(True, alpha=0.2)

        if self.wait_times:
            axs[1, 0].hist(self.wait_times, bins=20, color="tab:blue", alpha=0.7)
            axs[1, 0].axvline(results['avg_wait'], color='red', linestyle='--', label='Avg wait')
            axs[1, 0].set_title("Waiting Time Distribution")
            axs[1, 0].set_xlabel("Minutes")
            axs[1, 0].set_ylabel("Count")
            axs[1, 0].legend()
        else:
            axs[1, 0].set_title("Waiting Time Distribution")
            axs[1, 0].text(0.5, 0.5, "No wait times\n(records are empty)", ha='center', va='center')

        if self.system_times:
            axs[1, 1].hist(self.system_times, bins=20, color="tab:green", alpha=0.7)
            axs[1, 1].axvline(results['avg_system'], color='red', linestyle='--', label='Avg system time')
            axs[1, 1].set_title("Total Time in System Distribution")
            axs[1, 1].set_xlabel("Minutes")
            axs[1, 1].set_ylabel("Count")
            axs[1, 1].legend()
        else:
            axs[1, 1].set_title("Total Time in System Distribution")
            axs[1, 1].text(0.5, 0.5, "No system times\n(records are empty)", ha='center', va='center')

        fig.tight_layout()

        if output_plot:
            fig.savefig(output_plot, dpi=140, bbox_inches="tight")
            print(f"Saved plot: {output_plot}")

        if show_plot:
            plt.show()

        plt.close(fig)


if __name__ == "__main__":
    sim = BankSimulation(
        simulation_time=480.0,
        mean_interarrival=3.0,
        mean_service=4.0,
        tellers=2,
        seed=7,
        verbose=True,
    )
    sim.run(make_plots=True, show_plot=True, output_plot="bank_sim_plot.png")
