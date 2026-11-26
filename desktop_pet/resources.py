from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw


COLORKEY_ALPHA_THRESHOLD = 112


POSE_FILENAMES: dict[str, str] = {
    "idle": "idle.png",
    "wave": "wave.png",
    "wink": "wink.png",
    "sleep": "sleep.png",
    "stretch": "stretch.png",
    "yawn": "yawn.png",
    "think": "think.png",
    "cheer": "cheer.png",
    "shy": "shy.png",
    "read": "read.png",
    "drink": "drink.png",
}


def resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parent.parent


def character_dir() -> Path:
    return resource_root() / "assets" / "characters"


def sprite_path(pose: str) -> Path:
    try:
        filename = POSE_FILENAMES[pose]
    except KeyError as exc:
        raise ValueError(f"未知角色姿势：{pose}") from exc
    return character_dir() / filename


def load_sprite(pose: str) -> Image.Image:
    path = sprite_path(pose)
    with Image.open(path) as image:
        converted = image.convert("RGBA")
        converted.load()
    alpha = converted.getchannel("A")
    if alpha.getbbox() is None:
        raise ValueError(f"角色素材完全透明：{path}")
    return converted


def crop_to_subject(image: Image.Image, padding: int = 8) -> Image.Image:
    alpha_bbox = image.getchannel("A").getbbox()
    if alpha_bbox is None:
        raise ValueError("无法裁剪完全透明的图片")
    left, top, right, bottom = alpha_bbox
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def render_sprite_canvas(
    pose: str,
    target_height: int,
    canvas_width: int,
    canvas_height: int,
) -> Image.Image:
    subject = crop_to_subject(load_sprite(pose))
    max_width = max(1, canvas_width - 12)
    max_height = max(1, target_height)
    scale = min(max_width / subject.width, max_height / subject.height)
    size = (
        max(1, round(subject.width * scale)),
        max(1, round(subject.height * scale)),
    )
    resized = subject.resize(size, Image.Resampling.LANCZOS)
    binary_alpha = resized.getchannel("A").point(
        lambda alpha: 255 if alpha >= COLORKEY_ALPHA_THRESHOLD else 0
    )
    resized.putalpha(binary_alpha)
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    x = (canvas_width - resized.width) // 2
    y = canvas_height - resized.height - 4
    canvas.alpha_composite(resized, (x, y))
    return canvas


def create_tray_icon(size: int = 64) -> Image.Image:
    idle = crop_to_subject(load_sprite("idle"))
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    inset = max(2, size // 16)
    draw.ellipse(
        (inset, inset, size - inset, size - inset),
        fill=(245, 190, 202, 255),
    )

    face_crop = idle.crop(
        (
            0,
            0,
            idle.width,
            max(1, min(idle.height, round(idle.height * 0.47))),
        )
    )
    face_crop.thumbnail((round(size * 0.82), round(size * 0.82)), Image.Resampling.LANCZOS)
    x = (size - face_crop.width) // 2
    y = max(1, size - face_crop.height - 2)
    icon.alpha_composite(face_crop, (x, y))
    return icon


def save_app_icon(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    icon = create_tray_icon(256)
    icon.save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
