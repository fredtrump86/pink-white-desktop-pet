from __future__ import annotations

import unittest

from desktop_pet.resources import (
    POSE_FILENAMES,
    create_tray_icon,
    load_sprite,
    render_sprite_canvas,
)


class ResourceTests(unittest.TestCase):
    def test_all_pose_assets_are_rgba_and_visible(self) -> None:
        for pose in POSE_FILENAMES:
            with self.subTest(pose=pose):
                image = load_sprite(pose)
                self.assertEqual("RGBA", image.mode)
                self.assertIsNotNone(image.getchannel("A").getbbox())

    def test_rendered_canvas_has_requested_size(self) -> None:
        image = render_sprite_canvas(
            pose="idle",
            target_height=320,
            canvas_width=250,
            canvas_height=344,
        )
        self.assertEqual((250, 344), image.size)
        self.assertIsNotNone(image.getchannel("A").getbbox())

    def test_rendered_canvas_has_colorkey_safe_binary_alpha(self) -> None:
        image = render_sprite_canvas(
            pose="wink",
            target_height=240,
            canvas_width=210,
            canvas_height=264,
        )
        histogram = image.getchannel("A").histogram()
        intermediate_pixels = sum(histogram[1:255])
        self.assertEqual(0, intermediate_pixels)

    def test_tray_icon_is_valid(self) -> None:
        icon = create_tray_icon(64)
        self.assertEqual((64, 64), icon.size)
        self.assertEqual("RGBA", icon.mode)
        self.assertIsNotNone(icon.getchannel("A").getbbox())


if __name__ == "__main__":
    unittest.main()
