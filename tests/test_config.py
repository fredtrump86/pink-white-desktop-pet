from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from desktop_pet.config import (
    DEFAULT_SPRITE_HEIGHT,
    MAX_SPRITE_HEIGHT,
    MIN_SPRITE_HEIGHT,
    PetSettings,
    SettingsStore,
)


class SettingsStoreTests(unittest.TestCase):
    def test_default_sprite_height_is_compact(self) -> None:
        self.assertEqual(280, DEFAULT_SPRITE_HEIGHT)
        self.assertEqual(280, PetSettings().sprite_height)

    def test_utf8_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "中文目录" / "设置.json"
            store = SettingsStore(path)
            expected = PetSettings(
                sprite_height=360,
                topmost=False,
                auto_action=False,
                start_with_windows=True,
                x=123,
                y=456,
            )
            store.save(expected)
            self.assertEqual(expected, store.load())
            self.assertNotIn("\ufffd", path.read_text(encoding="utf-8"))

    def test_malformed_json_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text("{bad json", encoding="utf-8")
            self.assertEqual(PetSettings(), SettingsStore(path).load())

    def test_size_is_bounded(self) -> None:
        too_small = PetSettings.from_mapping({"sprite_height": -10})
        too_large = PetSettings.from_mapping({"sprite_height": 9999})
        self.assertEqual(MIN_SPRITE_HEIGHT, too_small.sprite_height)
        self.assertEqual(MAX_SPRITE_HEIGHT, too_large.sprite_height)

    def test_saved_json_contains_chinese_safe_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            SettingsStore(path).save(PetSettings())
            decoded = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("sprite_height", decoded)


if __name__ == "__main__":
    unittest.main()
