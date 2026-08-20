"""Animate a single bank policy using aggregate SimPy event history."""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

from model import Decision, Scenario, simulate


def state_at(
    timeline: list[dict[str, float | int | str]], current_time: float
) -> tuple[int, int, str]:
    current = timeline[0]
    for event in timeline:
        if float(event["time"]) <= current_time:
            current = event
        else:
            break
    return int(current["queue"]), int(current["busy"]), str(current["event"])


def animate(decision: Decision, scenario: Scenario, seed: int = 2026) -> None:
    result, timeline = simulate(decision, scenario, seed=seed)

    animation_end = max(float(event["time"]) for event in timeline)
    frame_count = 300
    frame_times = [
        animation_end * index / (frame_count - 1) for index in range(frame_count)
    ]

    fig, axis = plt.subplots(figsize=(12, 7))
    fig.subplots_adjust(bottom=0.1, top=0.88)
    fig.patch.set_facecolor("#efe7d5")
    axis.set(xlim=(0, 12), ylim=(0, 7), aspect="equal")
    axis.set_facecolor("#f8f4e9")
    axis.axis("off")

    axis.add_patch(Rectangle((0.25, 0.25), 11.5, 6.45, fill=False, ec="#173d35", lw=4))
    axis.text(
        6,
        6.35,
        "BRANCHFLOW BANK",
        ha="center",
        va="center",
        fontsize=21,
        weight="bold",
        color="#173d35",
    )
    axis.add_patch(Rectangle((0.12, 2.5), 0.5, 1.3, color="#73a9b5"))
    axis.add_patch(Rectangle((11.38, 2.5), 0.5, 1.3, color="#c88f77"))
    axis.text(0.85, 3.15, "ARRIVALS", rotation=90, fontsize=9)
    axis.text(11.12, 3.15, "EXIT", rotation=90, fontsize=9)

    teller_lights = []
    x_start = 2.0
    for index in range(max(1, decision.tellers)):
        x = x_start + (0.7 * index)
        desk = FancyBboxPatch(
            (x, 4.8),
            0.6,
            0.62,
            boxstyle="round,pad=0.05,rounding_size=0.08",
            ec="none",
            fc="#cddccf",
            lw=1.3,
            alpha=0.9,
        )
        axis.add_patch(desk)
        axis.text(x + 0.25, 5.1, f"#{index + 1}", fontsize=8, ha="center")
        light = Circle((x + 0.29, 4.95), 0.09, fc="#adc2ae")
        axis.add_patch(light)
        teller_lights.append(light)

    customers = []
    for _ in range(18):
        customer = Circle((3.0, 0.2), 0.22, alpha=0.0)
        axis.add_patch(customer)
        customers.append(customer)

    clock_text = axis.text(
        6,
        0.73,
        "",
        ha="center",
        fontsize=15,
        weight="bold",
        color="#2d463d",
    )
    status_text = axis.text(
        6,
        0.5,
        "",
        ha="center",
        fontsize=10,
        color="#41534d",
    )
    event_text = axis.text(
        6,
        5.85,
        "",
        ha="center",
        fontsize=10,
        color="#765126",
    )
    overflow_text = axis.text(
        10.8,
        2.05,
        "",
        ha="right",
        fontsize=10,
        color="#9b3f2f",
    )

    queue_slots = [3.2 + i * 0.35 for i in range(8)]

    def update(frame_index: int):
        current_time = frame_times[frame_index]
        queue, busy, event = state_at(timeline, current_time)

        visible_customers = min(queue, len(customers))
        hidden_customers = max(0, queue - visible_customers)

        for index, customer in enumerate(customers):
            customer.set_alpha(1.0 if index < visible_customers else 0.0)
            if index < visible_customers:
                customer.center = (queue_slots[min(index, len(queue_slots) - 1)], 0.9)

        for index, light in enumerate(teller_lights):
            light.set_facecolor("#dd6f58" if index < busy else "#adc2ae")

        clock_text.set_text(
            f"Minute {current_time:,.0f} / {scenario.horizon_minutes:,.0f}"
        )
        status_text.set_text(
            f"Queue {queue} | Busy tellers {busy}/{decision.tellers} | Digital share {decision.digital_share:.0%}"
        )
        event_text.set_text(event)
        overflow_text.set_text(
            f"+{hidden_customers} more waiting" if hidden_customers else ""
        )

        return (
            *customers,
            *teller_lights,
            clock_text,
            status_text,
            event_text,
            overflow_text,
        )

    FuncAnimation(fig, update, frames=frame_count, interval=55, blit=True, repeat=True)
    fig.suptitle(
        f"Policy replay: {decision.tellers} tellers + {decision.digital_share:.0%} digital | "
        f"p95 wait {result.p95_wait:.1f} min",
        fontsize=12,
        color="#41534d",
    )
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tellers", type=int, default=3)
    parser.add_argument("--digital-share", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    animate(
        Decision(tellers=args.tellers, digital_share=args.digital_share),
        Scenario(),
        seed=args.seed,
    )
