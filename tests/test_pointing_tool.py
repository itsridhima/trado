"""Offline tests for the pointing calibration tool's fake page and scoring (the AI is not called)."""

import unittest

from tools.run_pointing_test import HEIGHT, TARGETS, WIDTH, centre, evaluate, make_page


class FakePageTests(unittest.TestCase):
    def test_page_has_the_right_size_and_every_target_is_on_it(self):
        self.assertEqual(make_page().size, (WIDTH, HEIGHT))
        for name, (left, top, right, bottom) in TARGETS.items():
            self.assertTrue(0 <= left < right <= WIDTH and 0 <= top < bottom <= HEIGHT, name)

    def test_the_marked_spots_really_are_drawn_where_the_targets_say(self):
        page = make_page().convert("RGB")
        buy_x, buy_y = map(int, centre(TARGETS["Buy button"]))
        self.assertEqual(page.getpixel((TARGETS["Buy button"][0] + 5, buy_y)), (30, 150, 70))  # the green button
        sell = TARGETS["Sell button"]
        self.assertEqual(page.getpixel((sell[0] + 5, buy_y)), (200, 50, 50))  # the red button


class ScoringTests(unittest.TestCase):
    def rows_from(self, convert):
        return [(name, convert(*centre(rect))) for name, rect in TARGETS.items()]

    def test_perfect_pixel_answers_are_recognised_as_pixels(self):
        result = evaluate(self.rows_from(lambda x, y: (round(x), round(y))))
        self.assertEqual((result["pixels"], result["missing"]), (len(TARGETS), 0))
        self.assertTrue(result["verdict"].startswith("PIXELS"))
        self.assertLess(result["median_error_px"], 2)

    def test_a_zero_to_thousand_scale_is_recognised(self):
        result = evaluate(self.rows_from(lambda x, y: (round(x / WIDTH * 1000), round(y / HEIGHT * 1000))))
        self.assertGreaterEqual(result["thousand"], len(TARGETS) - 1)
        self.assertTrue(result["verdict"].startswith("THOUSAND"))

    def test_wild_guesses_and_missing_answers_are_unreliable(self):
        rows = [(name, (5, 5)) for name in list(TARGETS)[:4]] + [(name, None) for name in list(TARGETS)[4:]]
        result = evaluate(rows)
        self.assertEqual(result["missing"], 2)
        self.assertTrue(result["verdict"].startswith("UNRELIABLE"))

    def test_a_smaller_picture_scales_the_targets_and_still_scores_perfect_answers_perfectly(self):
        from tools.run_pointing_test import scaled_targets

        scale = 1008 / WIDTH
        small = scaled_targets(scale)
        self.assertEqual(set(small), set(TARGETS))
        left, top, right, bottom = small["Buy button"]
        self.assertEqual((left, top), (round(120 * scale), round(520 * scale)))
        rows = [(name, (round(centre(rect)[0]), round(centre(rect)[1]))) for name, rect in small.items()]
        result = evaluate(rows, 1008, round(HEIGHT * scale), small)
        self.assertEqual(result["pixels"], len(TARGETS))
        self.assertAlmostEqual(result["median_ratio_x"], 1.0, delta=0.02)

    def test_answers_that_belong_to_a_smaller_copy_show_up_as_a_ratio_below_one(self):
        # What the AI did on the first real run: its up-and-down numbers were about 62% of the truth.
        rows = [(name, (round(centre(rect)[0] * 0.64), round(centre(rect)[1] * 0.64))) for name, rect in TARGETS.items()]
        result = evaluate(rows)
        self.assertAlmostEqual(result["median_ratio_y"], 0.64, delta=0.02)
        self.assertAlmostEqual(result["median_ratio_x"], 0.64, delta=0.02)
        self.assertTrue(result["verdict"].startswith("UNRELIABLE"))

    def test_the_first_real_run_scores_as_unreliable_with_a_low_vertical_ratio(self):
        real = [("Quantity box", (160, 155)), ("Price box", (245, 250)), ("Buy button", (148, 341)),
                ("Sell button", (475, 345)), ("Green candle", (920, 235)), ("Profit and loss number", (810, 480))]
        result = evaluate(real)
        self.assertEqual(result["pixels"], 0)
        self.assertAlmostEqual(result["median_ratio_y"], 0.62, delta=0.02)

    def test_both_real_runs_are_explained_by_the_height_fix(self):
        # The first real run (picture 1568x980) and the second (1008x630), exactly as printed by the tool.
        from tools.run_pointing_test import scaled_targets

        run1 = [("Quantity box", (160, 155)), ("Price box", (245, 250)), ("Buy button", (148, 341)),
                ("Sell button", (475, 345)), ("Green candle", (920, 235)), ("Profit and loss number", (810, 480))]
        run2 = [("Quantity box", (192, 98)), ("Price box", (195, 155)), ("Buy button", (130, 218)),
                ("Sell button", (290, 220)), ("Green candle", (595, 150)), ("Profit and loss number", (575, 308))]
        first = evaluate(run1)
        self.assertEqual((first["pixels"], first["aspect"]), (0, 6))
        self.assertTrue(first["verdict"].startswith("ASPECT FIX"))
        second = evaluate(run2, 1008, 630, scaled_targets(1008 / WIDTH))
        self.assertEqual((second["pixels"], second["aspect"]), (0, 6))
        self.assertLess(second["median_error_aspect"], 20)  # after the fix every answer is within about 15 pixels
        self.assertTrue(second["verdict"].startswith("ASPECT FIX"))

    def test_other_screen_shapes(self):
        from tools.run_pointing_test import page_height_for

        self.assertEqual(page_height_for("16:10"), 980)
        self.assertEqual(page_height_for("16:9"), 882)
        self.assertEqual(page_height_for("4:3"), 1176)
        for bad in ["32:9", "21:9"]:  # too wide for the page to hold all the targets
            with self.assertRaises(ValueError):
                page_height_for(bad)
        page = make_page(882)
        self.assertEqual(page.size, (WIDTH, 882))
        for name, (left, top, right, bottom) in TARGETS.items():
            self.assertLessEqual(bottom, 882, name)  # every target still fits on the shorter page

    def test_an_ai_that_scales_height_by_height_over_width_is_fixed_on_any_shape(self):
        # Pretend the AI's up-and-down number is true_y * (height/width) on a 16:9 page: the fix must recover every target.
        height = 882
        rows = [(name, (round(centre(rect)[0]), round(centre(rect)[1] * height / WIDTH))) for name, rect in TARGETS.items()]
        result = evaluate(rows, WIDTH, height)
        self.assertEqual(result["aspect"], len(TARGETS))
        self.assertEqual(result["pixels"], 0)

    def test_trados_own_code_gets_all_of_the_real_runs_right_with_the_fix_and_none_without_it(self):
        from tools.run_pointing_test import hits_through_trado, scaled_targets

        run2 = [("Quantity box", (192, 98)), ("Price box", (195, 155)), ("Buy button", (130, 218)),
                ("Sell button", (290, 220)), ("Green candle", (595, 150)), ("Profit and loss number", (575, 308))]
        targets = scaled_targets(1008 / WIDTH)
        self.assertEqual(hits_through_trado(run2, (1008, 630), targets, correct_height=True), 6)
        self.assertEqual(hits_through_trado(run2, (1008, 630), targets, correct_height=False), 0)
        self.assertEqual(hits_through_trado([("Buy button", None)], (1008, 630), targets, correct_height=True), 0)

    def test_a_run_where_questions_failed_is_called_incomplete_not_unreliable(self):
        from tools.run_pointing_test import final_verdict

        # Your real run: only the first two were answered before the free daily allowance ran out.
        answered = [("Quantity box", (195, 100)), ("Price box", (194, 160))]
        from tools.run_pointing_test import scaled_targets

        result = evaluate(answered, 1008, 630, scaled_targets(1008 / WIDTH))
        self.assertEqual((result["aspect"], result["total"]), (2, 2))  # the two real answers were fine after the fix
        verdict = final_verdict(result, failed=4, planned=6)
        self.assertTrue(verdict.startswith("INCOMPLETE"))
        self.assertIn("4 of 6", verdict)
        self.assertEqual(final_verdict(result, failed=0, planned=2), result["verdict"])

    def test_slightly_off_still_counts_but_far_off_does_not(self):
        near = [(name, (round(centre(rect)[0]) + 8, round(centre(rect)[1]) - 8)) for name, rect in TARGETS.items()]
        self.assertGreaterEqual(evaluate(near)["pixels"], len(TARGETS) - 1)
        far = [(name, (round(centre(rect)[0]) + 400, round(centre(rect)[1]) + 300)) for name, rect in TARGETS.items()]
        self.assertEqual(evaluate(far)["pixels"], 0)


if __name__ == "__main__":
    unittest.main()
