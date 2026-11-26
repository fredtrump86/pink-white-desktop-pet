from __future__ import annotations

import argparse
import sys
from pathlib import Path

from desktop_pet.application import run_desktop_pet
from desktop_pet.diagnostics import run_headless_check
from desktop_pet.resources import save_app_icon


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="粉白桌宠")
    parser.add_argument(
        "--check",
        action="store_true",
        help="执行无需显示窗口的资源与配置检查",
    )
    parser.add_argument(
        "--make-icon",
        type=Path,
        metavar="PATH",
        help="根据角色素材生成应用图标",
    )
    parser.add_argument(
        "--smoke-window",
        action="store_true",
        help="启动窗口并在 1.5 秒后自动退出，用于构建验证",
    )
    parser.add_argument(
        "--smoke-interactions",
        action="store_true",
        help="依次切换动作与气泡后自动退出，用于交互验证",
    )
    parser.add_argument(
        "--smoke-auto",
        action="store_true",
        help="验证自动动作定时器会切换到可见动作",
    )
    parser.add_argument(
        "--smoke-hover",
        action="store_true",
        help="验证鼠标悬停会触发随机互动动作",
    )
    parser.add_argument(
        "--smoke-result",
        type=Path,
        metavar="PATH",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def write_smoke_result(path: Path | None, label: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"SMOKE_OK:{label}\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    if args.check:
        run_headless_check()
        return 0

    if args.make_icon:
        save_app_icon(args.make_icon)
        if sys.stdout is not None:
            print(f"图标已生成：{args.make_icon}")
        return 0

    if args.smoke_window:
        run_desktop_pet(smoke_after_ms=1500)
        write_smoke_result(args.smoke_result, "window")
        return 0

    if args.smoke_interactions:
        run_desktop_pet(
            smoke_after_ms=6800,
            interaction_smoke=True,
        )
        write_smoke_result(args.smoke_result, "interactions")
        return 0

    if args.smoke_auto:
        run_desktop_pet(
            smoke_after_ms=5200,
            verify_auto_action=True,
        )
        write_smoke_result(args.smoke_result, "auto")
        return 0

    if args.smoke_hover:
        run_desktop_pet(
            smoke_after_ms=1400,
            verify_hover_action=True,
        )
        write_smoke_result(args.smoke_result, "hover")
        return 0

    run_desktop_pet()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
