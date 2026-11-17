"""Offline tests for where the top line and the panel are placed (pure maths, no window is shown)."""

import unittest

from PySide6.QtCore import QRect

from trado.ui.panel import HANDLE_H, HANDLE_W, PANEL_WIDTH, handle_rect, panel_rect


class PanelGeometryTests(unittest.TestCase):
    def test_the_line_is_centred_on_the_top_edge(self):
        screen = QRect(0, 0, 1920, 1080)
        r = handle_rect(screen)
        self.assertEqual((r.width(), r.height()), (HANDLE_W, HANDLE_H))
        self.assertEqual(r.y(), 0)
        self.assertEqual(r.x() + r.width() // 2, 960)

    def test_the_line_grows_a_little_when_the_mouse_is_over_it(self):
        screen = QRect(0, 0, 1920, 1080)
        self.assertGreater(handle_rect(screen, hover=True).width(), handle_rect(screen).width())

    def test_the_panel_is_small_and_attached_to_the_top_centre(self):
        screen = QRect(0, 0, 1920, 1080)
        r = panel_rect(screen, 190)
        self.assertEqual(r.width(), PANEL_WIDTH)
        self.assertEqual(r.y(), 0)
        self.assertEqual(r.x() + r.width() // 2, 960)
        self.assertLess(r.width(), screen.width() // 4)

    def test_it_follows_a_screen_that_does_not_start_at_zero(self):
        # A second monitor placed to the left has a negative x; the panel must stay on that screen.
        screen = QRect(-1280, 0, 1280, 720)
        r = panel_rect(screen, 190)
        self.assertGreaterEqual(r.x(), -1280)
        self.assertLessEqual(r.x() + r.width(), 0)


if __name__ == "__main__":
    unittest.main()
