"""Replay animation for the simple bank simulation."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
from matplotlib.widgets import Button, Slider

from bank_sim import BankSimulation


def _value_at(times: list[float], values: list[float], current_time: float) -> float:
    current_value = values[0]
    for index, event_time in enumerate(times):
        if event_time > current_time:
            break
        current_value = values[index]
    return current_value


def _move(start: tuple[float, float], end: tuple[float, float], progress: float) -> tuple[float, float]:
    eased = progress * progress * (3.0 - 2.0 * progress)
    return (
        start[0] + (end[0] - start[0]) * eased,
        start[1] + (end[1] - start[1]) * eased,
    )


def animate(simulation: BankSimulation, duration_seconds: float = 16) -> None:
    if not simulation._queue_times:
        raise ValueError("No timeline data. Call simulation.run() first.")

    frame_count = min(320, max(80, len(simulation._queue_times)))
    frame_times = [
        simulation.sim_time * frame / (frame_count - 1)
        for frame in range(frame_count)
    ]

    fig, bank_axis = plt.subplots(figsize=(12, 7))
    fig.subplots_adjust(bottom=0.14, top=0.9)
    fig.patch.set_facecolor("#efe8d8")
    bank_axis.set(xlim=(0, 12), ylim=(0, 7), aspect="equal")
    bank_axis.set_facecolor("#f8f1df")
    bank_axis.axis("off")

    bank_axis.add_patch(Rectangle((0.25, 0.25), 11.5, 6.5, fill=False,
                                  edgecolor="#3d4a3f", linewidth=4))
    bank_axis.text(6, 6.42, "COMMUNITY BANK", ha="center", va="center",
                   fontsize=19, weight="bold", color="#26382c")

    bank_axis.add_patch(Rectangle((0.15, 2.5), 0.45, 1.35, color="#86b8c9"))
    bank_axis.text(0.88, 3.18, "ENTRANCE", rotation=90, ha="center", va="center",
                   fontsize=9, color="#355865")
    bank_axis.add_patch(Rectangle((11.4, 2.5), 0.45, 1.35, color="#d69a75"))
    bank_axis.text(11.12, 3.18, "EXIT", rotation=90, ha="center", va="center",
                   fontsize=9, color="#70472f")

    teller_positions: list[tuple[float, float]] = []
    teller_spacing = 8.0 / max(1, simulation.tellers)
    for teller in range(simulation.tellers):
        teller_x = 2.0 + teller_spacing * (teller + 0.5)
        teller_positions.append((teller_x, 5.15))
        desk = FancyBboxPatch(
            (teller_x - 0.7, 4.65), 1.4, 0.65,
            boxstyle="round,pad=0.05,rounding_size=0.08",
            facecolor="#496b52", edgecolor="#26382c", linewidth=1.5,
        )
        bank_axis.add_patch(desk)
        bank_axis.text(teller_x, 4.98, f"TELLER {teller + 1}", ha="center",
                       va="center", fontsize=9, color="white", weight="bold")

    max_queue = max(simulation._queue_vals)
    queue_positions = []
    for index in range(max_queue):
        row, column = divmod(index, 7)
        x = 8.8 - column * 1.05
        y = 3.65 - row * 0.85
        queue_positions.append((x, y))
        bank_axis.add_patch(Circle((x, y), 0.08, color="#b8aa8c", alpha=0.65))

    bank_axis.text(5.6, 4.12, "CUSTOMER QUEUE", ha="center", fontsize=9,
                   color="#75684f")
    bank_axis.plot([2.1, 9.35], [4.0, 4.0], color="#b18b45", linewidth=2)

    queue_customer_color = "#2878a5"
    teller_customer_color = "#e59a2f"
    queue_customers = [
        Circle((-1, -1), 0.23, color=queue_customer_color, ec="white", lw=1.2, zorder=5)
        for _ in range(max_queue)
    ]
    teller_customers = [
        Circle((-1, -1), 0.23, color=teller_customer_color, ec="white", lw=1.2, zorder=5)
        for _ in range(simulation.tellers)
    ]
    for customer in queue_customers + teller_customers:
        bank_axis.add_patch(customer)

    clock = bank_axis.text(6, 0.72, "", ha="center", fontsize=12, weight="bold", color="#26382c")
    status = bank_axis.text(6, 0.42, "", ha="center", fontsize=10,
                            color="#59655b")

    playback = {"position": 0.0, "speed": 1.0}
    paused = False

    def update(_frame):
        nonlocal paused
        frame_index = min(int(playback["position"]), frame_count - 1)
        current_time = frame_times[frame_index]
        next_index = min(frame_index + 1, frame_count - 1)
        next_time = frame_times[next_index]
        progress = playback["position"] - int(playback["position"])

        queue_count = int(_value_at(simulation._queue_times, simulation._queue_vals, current_time))
        busy_tellers = int(_value_at(simulation._service_times, simulation._service_vals, current_time))
        next_queue_count = int(_value_at(simulation._queue_times, simulation._queue_vals, next_time))
        next_busy_tellers = int(_value_at(simulation._service_times, simulation._service_vals, next_time))

        entrance = (0.8, 3.18)
        exit_position = (11.2, 3.18)
        service_positions = [(x, y - 0.72) for x, y in teller_positions]

        leaving_queue = max(0, queue_count - next_queue_count)
        newly_busy = list(range(busy_tellers, next_busy_tellers))
        handoff_count = max(0, leaving_queue - len(newly_busy))
        handoff_tellers = list(range(min(handoff_count, busy_tellers)))
        destination_tellers = newly_busy + handoff_tellers

        for customer in queue_customers + teller_customers:
            customer.center = (-1, -1)

        if next_queue_count >= queue_count:
            for index in range(min(queue_count, len(queue_customers))):
                queue_customers[index].center = queue_positions[index]
            for index in range(queue_count, min(next_queue_count, len(queue_customers))):
                if index < len(queue_positions):
                    queue_customers[index].center = _move(
                        entrance, queue_positions[index], progress
                    )
        else:
            leaving_count = queue_count - next_queue_count
            for index in range(min(leaving_count, len(queue_customers))):
                if index < len(destination_tellers):
                    target = service_positions[destination_tellers[index]]
                    queue_customers[index].center = _move(
                        queue_positions[index], target, progress
                    )
            for index in range(min(next_queue_count, len(queue_customers) - leaving_count)):
                customer_index = leaving_count + index
                if customer_index < len(queue_customers) and index < len(queue_positions):
                    queue_customers[customer_index].center = _move(
                        queue_positions[customer_index], queue_positions[index], progress
                    )

        shared_busy = min(busy_tellers, next_busy_tellers)
        for index in range(shared_busy):
            if index < len(destination_tellers) and index in handoff_tellers:
                teller_customers[index].center = _move(
                    service_positions[index], exit_position, progress
                )
            else:
                teller_customers[index].center = service_positions[index]

        if next_busy_tellers > busy_tellers:
            for index in range(busy_tellers, min(next_busy_tellers, len(teller_customers))):
                if next_queue_count >= queue_count and index < len(queue_positions):
                    teller_customers[index].center = _move(
                        entrance, service_positions[index], progress
                    )
        elif next_busy_tellers < busy_tellers:
            for index in range(next_busy_tellers, min(busy_tellers, len(teller_customers))):
                if index < len(service_positions):
                    teller_customers[index].center = _move(
                        service_positions[index], exit_position, progress
                    )

        clock.set_text(f"Minute {current_time:5.1f} of {simulation.sim_time:.0f}")
        status.set_text(
            f"Waiting: {queue_count}     |     Tellers busy: "
            f"{busy_tellers}/{simulation.tellers}     |     "
            f"Speed: {playback['speed']:.2f}x"
        )

        if playback["position"] >= frame_count - 1:
            if not paused:
                animation.event_source.stop()
            return (*queue_customers, *teller_customers, clock, status)

        playback["position"] += playback["speed"]
        return (*queue_customers, *teller_customers, clock, status)

    interval_ms = max(20, int(duration_seconds * 1000 / frame_count))
    animation = FuncAnimation(
        fig,
        update,
        frames=None,
        interval=interval_ms,
        repeat=False,
        blit=False,
        cache_frame_data=False,
    )

    speed_slider = Slider(
        fig.add_axes([0.25, 0.085, 0.5, 0.03]),
        "Speed",
        0.05,
        4.0,
        valinit=1.0,
        valstep=0.05,
        valfmt="%1.2fx",
    )
    playback["speed"] = speed_slider.val

    pause_button = Button(fig.add_axes([0.39, 0.025, 0.1, 0.05]), "Pause")
    restart_button = Button(fig.add_axes([0.52, 0.025, 0.1, 0.05]), "Restart")

    def change_speed(speed):
        playback["speed"] = speed

    def toggle_pause(_event):
        nonlocal paused
        paused = not paused
        if paused:
            animation.event_source.stop()
            pause_button.label.set_text("Play")
        else:
            animation.event_source.start()
            pause_button.label.set_text("Pause")

    def restart(_event):
        nonlocal paused
        playback["position"] = 0.0
        animation.event_source.start()
        paused = False
        pause_button.label.set_text("Pause")

    pause_button.on_clicked(toggle_pause)
    restart_button.on_clicked(restart)
    speed_slider.on_changed(change_speed)

    plt.show()


if __name__ == "__main__":
    simulation = BankSimulation(
        simulation_time=480.0,
        mean_interarrival=3.0,
        mean_service=4.0,
        tellers=2,
        seed=7,
        verbose=False,
    )
    simulation.run(make_plots=False, show_plot=False)
    animate(simulation)
