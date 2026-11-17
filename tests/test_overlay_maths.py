"""Offline tests for the cursor's position maths (no window is shown)."""

import unittest

from PySide6.QtCore import QPointF

from trado.ui.overlay import bend_point, bezier, clean_label, ease, logical_to_physical, physical_to_logical


class PositionTests(unittest.TestCase):
    def test_a_100_percent_screen_changes_nothing(self):
        self.assertEqual(physical_to_logical(500, 300, 0, 0, 1.0), (500, 300))

    def test_a_150_percent_screen_scales_down_from_the_screen_corner(self):
        x, y = physical_to_logical(1500, 900, 0, 0, 1.5)
        self.assertEqual((round(x), round(y)), (1000, 600))

    def test_the_second_screen_keeps_its_own_corner(self):
        # a screen whose top-left is at (1920, 0): its corner must stay where it is, only distances shrink
        x, y = physical_to_logical(1920 + 300, 150, 1920, 0, 1.5)
        self.assertEqual((round(x), round(y)), (1920 + 200, 100))
        self.assertEqual(physical_to_logical(1920, 0, 1920, 0, 1.5), (1920, 0))

    def test_going_there_and_back_gives_the_same_pixel(self):
        for dpr in (1.0, 1.25, 1.5, 2.0):
            lx, ly = physical_to_logical(1234, 567, 0, 0, dpr)
            px, py = logical_to_physical(lx, ly, 0, 0, dpr)
            self.assertAlmostEqual(px, 1234)
            self.assertAlmostEqual(py, 567)


class FlightTests(unittest.TestCase):
    def test_the_flight_starts_and_ends_exactly_on_the_points(self):
        a, b = QPointF(100, 100), QPointF(800, 500)
        bend = bend_point(a, b)
        start, end = bezier(a, bend, b, 0.0), bezier(a, bend, b, 1.0)
        self.assertEqual((start.x(), start.y()), (100, 100))
        self.assertEqual((end.x(), end.y()), (800, 500))

    def test_the_flight_arcs_away_from_the_straight_line(self):
        a, b = QPointF(0, 0), QPointF(1000, 0)
        mid = bezier(a, bend_point(a, b), b, 0.5)
        self.assertGreater(abs(mid.y()), 10)

    def test_easing_runs_from_zero_to_one(self):
        self.assertEqual(ease(0.0), 0.0)
        self.assertEqual(ease(1.0), 1.0)
        self.assertLess(ease(0.25), 0.25)  # slow start

    def test_a_label_is_short_and_one_line(self):
        self.assertEqual(clean_label("Buy\n  button"), "Buy button")
        self.assertLessEqual(len(clean_label("x" * 100)), 28)


if __name__ == "__main__":
    unittest.main()
