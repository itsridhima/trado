"""Offline tests for reading the hidden pointing tag, hiding it, and mapping it to real screen pixels."""

import unittest

from trado.pointing import (
    Geometry, PointTagFilter, describe_target, parse_point_tag, resolve_height_fix, strip_point_tags,
)

# A 2560x1600 laptop screen shrunk to a 1568x980 picture.
LAPTOP = Geometry(image_width=1568, image_height=980, left=0, top=0, width=2560, height=1600)


class ParseTests(unittest.TestCase):
    def test_a_normal_tag_is_mapped_to_real_pixels(self):
        target = parse_point_tag("[POINT:784,490:Quantity box]", LAPTOP)
        self.assertEqual((target.x, target.y), (1280, 800))  # the middle of the picture is the middle of the screen
        self.assertEqual(target.label, "Quantity box")
        self.assertAlmostEqual(target.across, 784 / 1567, places=3)

    def test_none_and_junk_give_no_target(self):
        for tag in ["[POINT:none]", "[point:NONE]", None, "", "[POINT:]", "[POINT:abc,def]", "[POINT:10;20]",
                    "[POINT:-5,10]", "[POINT:1e3,5]", "[POINT:10,20:a]b]", "POINT:10,20", "[POINT:10,20:x:screen2:extra]",
                    "[POINT:1,2]; rm -rf /"]:
            self.assertIsNone(parse_point_tag(tag, LAPTOP), tag)

    def test_numbers_are_clamped_to_the_picture_and_the_screen(self):
        target = parse_point_tag("[POINT:99999,99999:Far away]", LAPTOP)
        self.assertEqual((target.image_x, target.image_y), (1567, 979))
        self.assertEqual((target.x, target.y), (2559, 1599))  # the last real pixel, never off the screen

    def test_no_screenshot_means_nothing_to_point_at(self):
        self.assertIsNone(parse_point_tag("[POINT:10,20:Thing]", None))

    def test_a_second_monitor_with_negative_position(self):
        left_monitor = Geometry(image_width=1280, image_height=720, left=-1920, top=-100, width=1920, height=1080)
        target = parse_point_tag("[POINT:0,0:Top left]", left_monitor)
        self.assertEqual((target.x, target.y), (-1920, -100))  # real coordinates on the virtual desktop
        target = parse_point_tag("[POINT:1279,719:Bottom right]", left_monitor)
        self.assertEqual((target.x, target.y), (-1, 979))

    def test_label_is_cleaned_and_limited(self):
        target = parse_point_tag("[POINT:5,5:  Buy \x1b[2J  button ]", LAPTOP)  # a hidden terminal code inside the label
        self.assertEqual(target.label, "Buy button")  # is removed, and the spacing tidied
        target = parse_point_tag("[POINT:5,5:" + "x" * 60 + "]", LAPTOP)
        self.assertEqual(len(target.label), 40)  # long labels are cut
        target = parse_point_tag("[POINT:5,5:Buy\tbutton\x07]", LAPTOP)
        self.assertEqual(target.label, "Buy button")
        self.assertNotIn("\x07", target.label)

    def test_a_screen_number_is_accepted_and_ignored(self):
        self.assertIsNotNone(parse_point_tag("[POINT:100,100:Chart:screen1]", LAPTOP))

    def test_description_is_plain_words(self):
        text = describe_target(parse_point_tag("[POINT:784,490:Quantity box]", LAPTOP))
        self.assertIn("(1280, 800)", text)
        self.assertIn('"Quantity box"', text)
        self.assertIn("50% across", text)


class HeightFixTests(unittest.TestCase):
    def test_the_fix_multiplies_the_up_and_down_number_by_width_over_height(self):
        geometry = Geometry(1008, 567, 0, 0, 1920, 1080)  # a 16:9 screen shrunk to a 1008x567 picture
        plain = parse_point_tag("[POINT:500,150:Box]", geometry)
        fixed = parse_point_tag("[POINT:500,150:Box]", geometry, correct_height=True)
        self.assertEqual(plain.image_y, 150)
        self.assertEqual(fixed.image_y, round(150 * 1008 / 567))  # 267
        self.assertEqual(fixed.image_x, 500)  # sideways is never touched

    def test_a_corrected_number_is_still_clamped(self):
        geometry = Geometry(1008, 567, 0, 0, 1920, 1080)
        target = parse_point_tag("[POINT:10,9999:Far]", geometry, correct_height=True)
        self.assertEqual(target.image_y, 566)
        self.assertEqual(target.y, 1079)

    def test_which_models_get_the_fix(self):
        self.assertTrue(resolve_height_fix("qwen/qwen3.8-27b", "auto"))
        self.assertTrue(resolve_height_fix("  QWEN/Qwen3.8-27B ", "auto"))
        self.assertFalse(resolve_height_fix("some/other-model", "auto"))
        self.assertTrue(resolve_height_fix("some/other-model", "aspect"))
        self.assertFalse(resolve_height_fix("qwen/qwen3.8-27b", "none"))

    def test_the_real_16_9_measurements_land_in_the_right_places_through_trados_own_code(self):
        # From the real 16:9 run: picture 1008x567, (what the AI said, where the target's centre really is).
        geometry = Geometry(1008, 567, 0, 0, 1008, 567)
        runs = [((195, 90), (206, 164)), ((190, 145), (206, 254)), ((180, 204), (142, 360)),
                ((293, 197), (296, 360)), ((590, 136), (598, 251)), ((525, 275), (578, 488))]
        for said, true in runs:
            target = parse_point_tag(f"[POINT:{said[0]},{said[1]}:x]", geometry, correct_height=True)
            self.assertLess(abs(target.y - true[1]), 20, (said, true))  # up-and-down: within 20 pixels
        # sideways is accurate at this picture size, except the two far-left answers the AI was also a little off on
        for said, true in runs[:5]:
            self.assertLess(abs(said[0] - true[0]), 40)


class StripTests(unittest.TestCase):
    def test_tags_are_removed_from_finished_text(self):
        self.assertEqual(strip_point_tags("Click here is the box. [POINT:10,20:Box]"), "Click here is the box.")
        self.assertEqual(strip_point_tags("Nothing to point at. [POINT:none]"), "Nothing to point at.")
        self.assertEqual(strip_point_tags("Plain answer."), "Plain answer.")


class StreamFilterTests(unittest.TestCase):
    def run_stream(self, chunks):
        f = PointTagFilter()
        shown = "".join(f.feed(c) for c in chunks) + f.flush()
        return shown, f.tag

    def test_tag_at_the_end_is_hidden_and_remembered(self):
        shown, tag = self.run_stream(["This is the quantity box. ", "[POINT:784,490:Quantity box]"])
        self.assertEqual(shown, "This is the quantity box. ")
        self.assertEqual(tag, "[POINT:784,490:Quantity box]")

    def test_tag_split_across_tiny_pieces_is_still_hidden(self):
        text = "Here it is. [POINT:12,34:Buy button]"
        for size in (1, 2, 3, 5, 7):
            shown, tag = self.run_stream([text[i:i + size] for i in range(0, len(text), size)])
            self.assertEqual(shown, "Here it is. ", size)
            self.assertEqual(tag, "[POINT:12,34:Buy button]", size)

    def test_ordinary_brackets_and_markdown_links_pass_through(self):
        shown, tag = self.run_stream(["Use the [Buy] option, or [see this]. ", "Also [PO", "and more."])
        self.assertEqual(shown, "Use the [Buy] option, or [see this]. Also [POand more.")
        self.assertIsNone(tag)

    def test_a_tag_that_never_finishes_is_dropped_not_spoken(self):
        shown, tag = self.run_stream(["The box is here. [POINT:10,2"])
        self.assertEqual(shown, "The box is here. ")
        self.assertIsNone(tag)

    def test_text_after_a_mid_answer_tag_is_still_shown(self):
        shown, tag = self.run_stream(["Look here [POINT:1,2:Spot] and then read the number."])
        self.assertEqual(shown, "Look here  and then read the number.")
        self.assertEqual(tag, "[POINT:1,2:Spot]")

    def test_lowercase_tag_is_recognised_and_none_tag_is_hidden(self):
        shown, tag = self.run_stream(["Nothing to show. [point:none]"])
        self.assertEqual(shown, "Nothing to show. ")
        self.assertEqual(tag, "[point:none]")


if __name__ == "__main__":
    unittest.main()
