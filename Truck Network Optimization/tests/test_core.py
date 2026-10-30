"""Regression tests for the truck network model and search results."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model import Scenario, clock, quick_estimate, simulate  # noqa: E402
from search import all_schedules, best_by, best_by_quick_estimate, local_search, two_level_search  # noqa: E402


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.scenario = Scenario()
        self.plan = best_by(lambda s: quick_estimate(s, self.scenario), all_schedules(self.scenario))

    def test_model_is_deterministic(self):
        self.assertEqual(simulate(self.plan, self.scenario), simulate(self.plan, self.scenario))

    def test_quick_estimate_matches_simulation_when_docks_are_unlimited(self):
        unlimited = Scenario(docks=4)
        for schedule in all_schedules(unlimited)[::97]:
            self.assertEqual(quick_estimate(schedule, unlimited), simulate(schedule, unlimited)[0])

    def test_quick_estimate_plan_bunches_at_the_hub(self):
        _, records = simulate(self.plan, self.scenario)
        self.assertEqual({r.arrives for r in records}, {clock("12:00")})
        self.assertEqual(quick_estimate(self.plan, self.scenario), 4)
        self.assertEqual(simulate(self.plan, self.scenario)[0], 15)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.scenario = Scenario()
        self.plan = best_by(lambda s: quick_estimate(s, self.scenario), all_schedules(self.scenario))

    def test_local_search_reaches_the_optimum(self):
        result = local_search(self.plan, self.scenario)
        self.assertEqual([late for _, late in result.path], [15, 9, 5])
        self.assertEqual(result.simulations, 24)
        optimum = min(simulate(s, self.scenario)[0] for s in all_schedules(self.scenario))
        self.assertEqual(result.late, optimum)

    def test_two_level_search_needs_fewer_simulations(self):
        result = two_level_search(self.plan, self.scenario, top_k=3)
        self.assertEqual(result.late, 5)
        self.assertEqual(result.simulations, 10)

    def test_quick_estimate_plan_without_enumeration_matches_best_by(self):
        for scenario in (Scenario(), Scenario(docks=1, unload_minutes=60), Scenario(step_minutes=60)):
            expected = best_by(lambda s: quick_estimate(s, scenario), all_schedules(scenario))
            self.assertEqual(best_by_quick_estimate(scenario), expected)

    def test_searches_stop_when_there_is_only_one_departure_slot(self):
        scenario = Scenario(earliest_departure="10:00", latest_departure="10:00")
        start = {origin: clock("10:00") for origin in scenario.origins}
        self.assertEqual(local_search(start, scenario).schedule, start)
        self.assertEqual(two_level_search(start, scenario).schedule, start)


class AppTests(unittest.TestCase):
    def setUp(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("streamlit is not installed")
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dss.py"), default_timeout=120).run()

    def test_app_runs_and_reports_default_results(self):
        app = self.app
        self.assertEqual(list(app.exception), [])
        metrics = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(metrics["Local search"], "5 late")
        self.assertEqual(metrics["Best possible"], "5 late")

    def test_app_skips_the_full_check_when_there_are_too_many_schedules(self):
        app = self.app
        app.sidebar.select_slider[0].set_value(15).run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual({m.label: m.value for m in app.metric}["Best possible"], "not checked")


if __name__ == "__main__":
    unittest.main()
