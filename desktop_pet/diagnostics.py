from __future__ import annotations

import tempfile
import sys
from pathlib import Path

from desktop_pet.behavior import POSE_DURATIONS_MS, PetBehavior
from desktop_pet.config import PetSettings, SettingsStore
from desktop_pet.resources import POSE_FILENAMES, load_sprite


def run_headless_check() -> None:
    for pose in POSE_FILENAMES:
        image = load_sprite(pose)
        if image.mode != "RGBA":
            raise RuntimeError(f"{pose} 不是 RGBA 素材")
        if image.getchannel("A").getbbox() is None:
            raise RuntimeError(f"{pose} 没有可见角色内容")

    with tempfile.TemporaryDirectory(prefix="pink-pet-check-") as temporary:
        path = Path(temporary) / "中文设置" / "settings.json"
        store = SettingsStore(path)
        expected = PetSettings(
            sprite_height=360,
            topmost=False,
            auto_action=False,
            start_with_windows=False,
            x=120,
            y=240,
        )
        store.save(expected)
        actual = store.load()
        if actual != expected:
            raise RuntimeError("设置文件 UTF-8 往返检查失败")

    behavior = PetBehavior(auto_enabled=False)
    if behavior.next_auto_pose() != "idle":
        raise RuntimeError("关闭自动动作后仍返回了非待机状态")
    if set(POSE_DURATIONS_MS) != set(POSE_FILENAMES):
        raise RuntimeError("动作时长与角色素材不匹配")

    if sys.stdout is not None:
        print("CHECK_OK：角色素材、透明通道、中文设置与行为状态均有效")
