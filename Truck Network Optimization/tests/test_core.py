"""Regression tests: the numbers used in the class slides must not drift."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model import Scenario, clock, quick_estimate, simulate  # noqa: E402
from search import all_schedules, best_by, local_search, two_level_search  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
