"""Regression tests for the bank shift roster model and loop."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from roster import coverage, evaluate, formula_requirements, improve, simulate_day, solve_roster  # noqa: E402


class RosterTests(unittest.TestCase):
    def test_formula_requirements(self):
        self.assertEqual(formula_requirements(), [4, 5, 5, 8, 9, 5, 4, 4])

    def test_integer_program_covers_every_hour(self):
        req = formula_requirements()
        roster, cost = solve_roster(req)
        self.assertEqual(cost, 57)
        self.assertTrue(all(c >= r for c, r in zip(coverage(roster), req)))

    def test_simulation_is_reproducible(self):
        roster, _ = solve_roster(formula_requirements())
        self.assertEqual(simulate_day(roster, 7), simulate_day(roster, 7))

    def test_loop_result(self):
        result = improve(verbose=False)
        self.assertEqual(result["cost"], 54)
        self.assertEqual(result["sims"], 4)
        self.assertLessEqual(max(evaluate(result["roster"])), 1.0)


if __name__ == "__main__":
    unittest.main()
