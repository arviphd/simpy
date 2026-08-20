"""Regression tests for simulation, optimization, and export behavior."""

from __future__ import annotations

import ast
import csv
import json
import tempfile
import unittest
from pathlib import Path

from model import Decision, Scenario, simulate
from optimize import evaluate, export_results, optimize


class SimulationTests(unittest.TestCase):
    def test_seeded_replay_is_reproducible(self):
        decision = Decision(tellers=2, digital_share=0.2)
        scenario = Scenario(horizon_minutes=120.0)
        first, first_timeline = simulate(decision, scenario, seed=17)
        second, second_timeline = simulate(decision, scenario, seed=17)

        self.assertEqual(first, second)
        self.assertEqual(first_timeline, second_timeline)

    def test_arrival_stream_is_shared_across_decisions(self):
        scenario = Scenario(horizon_minutes=120.0)
        low_digital, _ = simulate(Decision(1, 0.0), scenario, seed=23)
        high_digital, _ = simulate(Decision(4, 0.7), scenario, seed=23)
        self.assertEqual(low_digital.arrivals, high_digital.arrivals)

    def test_wait_accounting_includes_abandoned_customers(self):
        scenario = Scenario(
            horizon_minutes=180.0,
            mean_interarrival_minutes=0.8,
            mean_service_minutes=8.0,
            mean_patience_minutes=2.0,
        )
        result, _ = simulate(Decision(1, 0.0), scenario, seed=31)
        self.assertGreater(result.abandoned, 0)
        served_wait_minutes = result.avg_wait * result.completed
        self.assertGreater(result.total_wait_minutes, served_wait_minutes)

    def test_join_snapshot_includes_newly_queued_customer(self):
        scenario = Scenario(
            horizon_minutes=60.0,
            mean_interarrival_minutes=0.5,
            mean_service_minutes=10.0,
            mean_patience_minutes=30.0,
        )
        _, timeline = simulate(Decision(1, 0.0), scenario, seed=7)
        second_join = next(
            event for event in timeline if event["event"] == "Customer 2 joined"
        )
        self.assertEqual(second_join["busy"], 1)
        self.assertEqual(second_join["queue"], 1)

    def test_abandonment_snapshot_excludes_departed_customer(self):
        scenario = Scenario(
            horizon_minutes=10.0,
            mean_interarrival_minutes=2.0,
            mean_service_minutes=30.0,
            mean_patience_minutes=0.2,
        )
        _, timeline = simulate(Decision(1, 0.0), scenario, seed=1)
        first_abandonment = next(
            event for event in timeline if event["event"] == "Customer 3 abandoned"
        )
        self.assertEqual(first_abandonment["queue"], 0)


class OptimizerTests(unittest.TestCase):
    def test_dss_source_parses(self):
        dss_path = Path(__file__).resolve().parents[1] / "dss.py"
        ast.parse(dss_path.read_text(encoding="utf-8"), filename=str(dss_path))

    def test_dss_exposes_objective_weights(self):
        dss_path = Path(__file__).resolve().parents[1] / "dss.py"
        source = dss_path.read_text(encoding="utf-8")
        for weight in (
            "hourly_teller_cost",
            "digital_cost_per_customer",
            "waiting_cost_per_customer_minute",
            "abandonment_cost",
            "utilization_penalty_weight",
        ):
            self.assertIn(weight, source)

    def test_compliance_calculation_is_in_range(self):
        scenario = Scenario(horizon_minutes=120.0, required_replication_compliance=1.0)
        candidate = evaluate(Decision(3, 0.2), scenario, replications=4, base_seed=51)
        self.assertTrue(0.0 <= candidate.p95_compliance_rate <= 1.0)
        self.assertTrue(0.0 <= candidate.abandonment_compliance_rate <= 1.0)

    def test_objective_components_include_digital_cost(self):
        scenario = Scenario(
            horizon_minutes=120.0,
            mean_interarrival_minutes=0.5,
            mean_service_minutes=8.0,
            mean_patience_minutes=2.0,
            required_replication_compliance=1.0,
        )
        candidate = evaluate(Decision(1, 0.2), scenario, replications=4, base_seed=51)
        self.assertFalse(candidate.is_feasible)
        expected = (
            candidate.operating_cost
            + candidate.digital_cost
            + candidate.waiting_cost
            + candidate.abandonment_cost
            + candidate.soft_penalty
            + candidate.feasibility_penalty
        )
        self.assertAlmostEqual(candidate.objective, expected)

    def test_optimize_with_empty_search_space_raises(self):
        scenario = Scenario()
        with self.assertRaises(ValueError):
            optimize(scenario, teller_options=range(0), digital_options=())

    def test_export_results_rejects_empty_candidates(self):
        with self.assertRaises(ValueError):
            export_results([])

    def test_export_includes_recommendation(self):
        scenario = Scenario(horizon_minutes=60.0)
        candidates = list(
            reversed(
                optimize(
                    scenario,
                    teller_options=range(2, 4),
                    digital_options=(0.2,),
                )
            )
        )
        with tempfile.TemporaryDirectory() as working:
            csv_path, json_path = export_results(
                candidates, output_directory=Path(working)
            )
            with csv_path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            with json_path.open(encoding="utf-8") as handle:
                recommendation = json.load(handle)
            expected = min(
                (candidate for candidate in candidates if candidate.is_feasible),
                key=lambda candidate: candidate.objective,
            )
            self.assertEqual(len(rows), 2)
            self.assertEqual(int(recommendation["tellers"]), expected.tellers)
            self.assertAlmostEqual(
                float(recommendation["objective"]), expected.objective
            )
            self.assertIn("digital_cost", recommendation)
            self.assertIn("p95_compliance_rate", recommendation)


if __name__ == "__main__":
    unittest.main()
