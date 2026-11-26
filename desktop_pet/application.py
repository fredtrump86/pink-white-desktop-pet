from __future__ import annotations

import ctypes
import os
import queue
import random
import tempfile
import threading
import time
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from tkinter import font as tkfont
from typing import Callable

from PIL import ImageTk

from desktop_pet.behavior import PetBehavior
from desktop_pet.config import APP_NAME, PetSettings, SettingsStore
from desktop_pet.resources import POSE_FILENAMES, create_tray_icon, render_sprite_canvas
from desktop_pet.single_instance import AlreadyRunningError, SingleInstance
from desktop_pet.startup import is_start_with_windows, set_start_with_windows


TRANSPARENT_KEY = "#00ff01"
BUBBLE_TRANSPARENT_KEY = "#00feff"
AUTO_ACTION_INITIAL_MIN_DELAY_MS = 15_000
AUTO_ACTION_INITIAL_MAX_DELAY_MS = 25_000
AUTO_ACTION_IDLE_MIN_INTERVAL_MS = 20_000
AUTO_ACTION_IDLE_MAX_INTERVAL_MS = 40_000
AUTO_HEARTBEAT_INTERVAL_MS = 500
AUTO_WATCHDOG_INTERVAL_MS = 2_000
AUTO_HEARTBEAT_STALE_SECONDS = 3.0
DRAG_STALE_TIMEOUT_SECONDS = 5.0
CLICK_MOVE_THRESHOLD = 5
HOVER_TRIGGER_DELAY_MS = 350
HOVER_COOLDOWN_SECONDS = 4.0
HOVER_ACTIONS = ("wave", "wink", "shy")
HOVER_INTERRUPTIBLE_POSES = frozenset({"idle", "read", "sleep"})

CLICK_LINES = [
    "嘿嘿，被你发现啦～",
    "今天也要开心呀！",
    "摸摸头会有好运喔～",
    "我在这里陪你。",
]
WAVE_LINES = [
    "嗨～很高兴见到你！",
    "来打个招呼吧～",
    "今天也请多关照！",
]
SLEEP_LINES = [
    "有一点点困啦……",
    "陪我休息一小会儿吧～",
    "记得不要熬夜喔。",
]
ACTION_LINES: dict[str, list[str]] = {
    "wave": WAVE_LINES,
    "wink": CLICK_LINES,
    "stretch": [
        "伸个懒腰，精神满满～",
        "坐久了要记得活动一下呀。",
        "一、二、三，舒展开啦！",
    ],
    "yawn": [
        "唔……好像有一点困了。",
        "偷偷打个小哈欠～",
        "忙完这一会儿就休息吧。",
    ],
    "think": [
        "让我认真想一想……",
        "今天还有什么有趣的事呢？",
        "嗯，我好像有个小点子。",
    ],
    "cheer": [
        "加油加油，你一定可以！",
        "今天也要元气满满～",
        "完成一点点也值得开心！",
    ],
    "shy": [
        "我会安静陪着你的～",
        "突然看我，会有点害羞啦。",
        "能待在这里真好。",
    ],
    "read": [
        "你忙你的，我看会儿书～",
        "安静陪伴模式开启。",
        "偶尔慢下来也很好呀。",
    ],
    "drink": [
        "喝口水再继续吧～",
        "别忘了补充水分呀。",
        "给自己留一点休息时间。",
    ],
}
AMBIENT_LINES = [
    "我一直都在这里喔～",
    "专心的时候也要放松肩膀呀。",
    "今天过得还顺利吗？",
    "累了就看看我，休息几秒吧。",
    "悄悄陪你一会儿。",
]


def _enable_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class DesktopPet:
    def __init__(
        self,
        root: tk.Tk,
        store: SettingsStore | None = None,
        *,
        enable_tray: bool = True,
    ) -> None:
        self.root = root
        self.store = store or SettingsStore()
        self.runtime_log_path = self.store.path.parent / "runtime.log"
        self.settings = self.store.load()
        self.settings.start_with_windows = is_start_with_windows()
        self.behavior = PetBehavior(auto_enabled=self.settings.auto_action)
        self.randomizer = random.Random()

        self.current_pose = "idle"
        self.pose_timer: str | None = None
        self.pose_deadline_at: float | None = None
        self.auto_heartbeat_timer: str | None = None
        self.auto_watchdog_timer: str | None = None
        self.action_queue_timer: str | None = None
        self.auto_action_count = 0
        self.auto_recovery_count = 0
        self.last_auto_heartbeat_at = time.monotonic()
        self.next_auto_action_at = time.monotonic()
        self._schedule_next_auto_action(initial=True)
        self.bubble_timer: str | None = None
        self.bubble: tk.Toplevel | None = None
        self.bubble_canvas: tk.Canvas | None = None
        self.bubble_font: tkfont.Font | None = None
        self.bubble_width = 268
        self.bubble_height = 88
        self.tray_icon = None
        self.tray_thread: threading.Thread | None = None
        self.is_hidden = False
        self.is_closing = False
        self.drag_origin: tuple[int, int, int, int] | None = None
        self.drag_last_event_at: float | None = None
        self.dragged = False
        self.click_timer: str | None = None
        self.hover_timer: str | None = None
        self.last_hover_action_at = float("-inf")
        self.suppress_release_click = False
        self.photo_images: dict[str, ImageTk.PhotoImage] = {}
        self.action_queue: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()

        self.topmost_var = tk.BooleanVar(value=self.settings.topmost)
        self.auto_var = tk.BooleanVar(value=self.settings.auto_action)
        self.startup_var = tk.BooleanVar(value=self.settings.start_with_windows)
        self.root.report_callback_exception = self._report_callback_exception

        self._configure_window()
        self._build_canvas()
        self._build_context_menu()
        self._build_bubble_window()
        self._reload_sprites()
        self._restore_position()
        self._bind_events()
        if enable_tray:
            self._start_tray()

        self.root.deiconify()
        self.root.lift()
        self.action_queue_timer = self.root.after(80, self._drain_action_queue)
        self._schedule_auto_heartbeat()
        self._schedule_auto_watchdog()
        if self.settings.auto_action:
            self.root.after(650, self._announce_auto_action)

    @property
    def window_width(self) -> int:
        return max(210, round(self.settings.sprite_height * 0.78))

    @property
    def window_height(self) -> int:
        return self.settings.sprite_height + 24

    def _configure_window(self) -> None:
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_KEY)
        self.root.attributes("-topmost", self.settings.topmost)
        if os.name == "nt":
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
            self.root.wm_attributes("-toolwindow", True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_canvas(self) -> None:
        self.canvas = tk.Canvas(
            self.root,
            width=self.window_width,
            height=self.window_height,
            bg=TRANSPARENT_KEY,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack()
        self.image_item = self.canvas.create_image(
            self.window_width // 2,
            self.window_height,
            anchor="s",
        )

    def _build_context_menu(self) -> None:
        menu = tk.Menu(self.root, tearoff=False)

        def invoke(callback: Callable[[], None]) -> Callable[[], None]:
            return lambda: self._run_context_menu_command(callback)

        menu.add_command(label="👋 挥挥手", command=invoke(self.wave))
        menu.add_command(label="😉 眨眨眼", command=invoke(self.wink))
        menu.add_command(label="😴 休息一下", command=invoke(self.sleep))

        action_menu = tk.Menu(menu, tearoff=False)
        action_menu.add_command(
            label="🙆 伸个懒腰",
            command=invoke(lambda: self.perform_action("stretch")),
        )
        action_menu.add_command(
            label="🥱 打个哈欠",
            command=invoke(lambda: self.perform_action("yawn")),
        )
        action_menu.add_command(
            label="🤔 认真想想",
            command=invoke(lambda: self.perform_action("think")),
        )
        action_menu.add_command(
            label="✨ 开心加油",
            command=invoke(lambda: self.perform_action("cheer")),
        )
        action_menu.add_command(
            label="☺ 害羞一下",
            command=invoke(lambda: self.perform_action("shy")),
        )
        action_menu.add_command(
            label="📖 安静看书",
            command=invoke(lambda: self.perform_action("read")),
        )
        action_menu.add_command(
            label="☕ 喝口水",
            command=invoke(lambda: self.perform_action("drink")),
        )
        menu.add_cascade(label="更多动作", menu=action_menu)
        menu.add_separator()

        size_menu = tk.Menu(menu, tearoff=False)
        size_menu.add_command(label="小", command=invoke(lambda: self.set_size(220)))
        size_menu.add_command(label="中", command=invoke(lambda: self.set_size(280)))
        size_menu.add_command(label="大", command=invoke(lambda: self.set_size(360)))
        menu.add_cascade(label="角色大小", menu=size_menu)

        menu.add_checkbutton(
            label="始终置顶",
            variable=self.topmost_var,
            command=invoke(self.toggle_topmost),
        )

        auto_menu = tk.Menu(menu, tearoff=False)
        auto_menu.add_checkbutton(
            label="启用自动动作",
            variable=self.auto_var,
            command=invoke(self.toggle_auto_action),
        )
        auto_menu.add_command(
            label="立即测试自动动作",
            command=invoke(self.test_auto_action_now),
        )
        auto_menu.add_command(
            label="查看自动动作状态",
            command=invoke(self.show_auto_action_status),
        )
        menu.add_cascade(label="自动动作（已开启）", menu=auto_menu)
        self.auto_menu_index = menu.index("end")

        menu.add_checkbutton(
            label="开机启动",
            variable=self.startup_var,
            command=invoke(self.toggle_startup),
        )
        menu.add_command(label="回到右下角", command=invoke(self.move_to_corner))
        menu.add_separator()
        menu.add_command(label="关于", command=invoke(self.show_about))
        menu.add_command(label="退出", command=invoke(self.close))
        menu.configure(postcommand=self._refresh_context_menu)
        self.context_menu = menu

    def _build_bubble_window(self) -> None:
        bubble = tk.Toplevel(self.root)
        bubble.withdraw()
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        if os.name == "nt":
            bubble.wm_attributes("-toolwindow", True)
            bubble.wm_attributes("-transparentcolor", BUBBLE_TRANSPARENT_KEY)
        bubble.configure(bg=BUBBLE_TRANSPARENT_KEY)

        canvas = tk.Canvas(
            bubble,
            width=self.bubble_width,
            height=self.bubble_height,
            bg=BUBBLE_TRANSPARENT_KEY,
            bd=0,
            highlightthickness=0,
        )
        canvas.pack()
        self.bubble = bubble
        self.bubble_canvas = canvas
        self.bubble_font = tkfont.Font(
            root=bubble,
            family="Microsoft YaHei UI",
            size=10,
            weight="bold",
        )
        self._draw_bubble("我在这里陪你～")

    @staticmethod
    def _rounded_rectangle(
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        **kwargs: object,
    ) -> int:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            **kwargs,
        )

    def _draw_bubble(self, text: str) -> None:
        if self.bubble_canvas is None or self.bubble_font is None:
            return
        canvas = self.bubble_canvas
        canvas.delete("all")

        probe = canvas.create_text(
            0,
            0,
            text=text,
            width=218,
            anchor="nw",
            font=self.bubble_font,
        )
        bbox = canvas.bbox(probe) or (0, 0, 218, 24)
        text_height = max(20, bbox[3] - bbox[1])
        canvas.delete(probe)

        self.bubble_width = 268
        self.bubble_height = max(82, text_height + 48)
        canvas.configure(
            width=self.bubble_width,
            height=self.bubble_height,
        )
        card_bottom = self.bubble_height - 18

        self._rounded_rectangle(
            canvas,
            8,
            8,
            self.bubble_width - 5,
            card_bottom + 4,
            18,
            fill="#dba2b1",
            outline="",
        )
        canvas.create_polygon(
            160,
            card_bottom - 2,
            184,
            card_bottom - 2,
            143,
            card_bottom + 13,
            fill="#fff9fb",
            outline="#e5a8b8",
            width=2,
        )
        self._rounded_rectangle(
            canvas,
            4,
            4,
            self.bubble_width - 9,
            card_bottom,
            18,
            fill="#fff9fb",
            outline="#e5a8b8",
            width=2,
        )
        canvas.create_oval(
            18,
            16,
            24,
            22,
            fill="#f3b8c7",
            outline="",
        )
        canvas.create_oval(
            26,
            11,
            30,
            15,
            fill="#f8d7df",
            outline="",
        )
        canvas.create_text(
            self.bubble_width // 2,
            card_bottom // 2 + 2,
            text=text,
            width=214,
            justify="center",
            fill="#65424c",
            font=self.bubble_font,
        )

    def _bind_events(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._show_context_menu)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Enter>", self._on_hover_enter)
        self.canvas.bind("<Leave>", self._on_hover_leave)

    def _reload_sprites(self) -> None:
        self.photo_images.clear()
        for pose in POSE_FILENAMES:
            rendered = render_sprite_canvas(
                pose=pose,
                target_height=self.settings.sprite_height,
                canvas_width=self.window_width,
                canvas_height=self.window_height,
            )
            self.photo_images[pose] = ImageTk.PhotoImage(rendered)
        self.canvas.configure(width=self.window_width, height=self.window_height)
        self.canvas.coords(
            self.image_item,
            self.window_width // 2,
            self.window_height,
        )
        self.canvas.itemconfigure(
            self.image_item,
            image=self.photo_images[self.current_pose],
        )

    def _restore_position(self) -> None:
        if self.settings.x is None or self.settings.y is None:
            self.move_to_corner(save=False)
            return
        x, y = self._clamp_position(self.settings.x, self.settings.y)
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")

    def _clamp_position(self, x: int, y: int) -> tuple[int, int]:
        max_x = max(0, self.root.winfo_screenwidth() - self.window_width)
        max_y = max(0, self.root.winfo_screenheight() - self.window_height - 36)
        return max(0, min(max_x, x)), max(0, min(max_y, y))

    def move_to_corner(self, save: bool = True) -> None:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, screen_width - self.window_width - 28)
        y = max(0, screen_height - self.window_height - 72)
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
        if save:
            self._save_position()

    def _on_press(self, event: tk.Event) -> None:
        self._cancel_timer("hover_timer")
        self.behavior.touch()
        self.drag_last_event_at = time.monotonic()
        self.drag_origin = (
            event.x_root,
            event.y_root,
            self.root.winfo_x(),
            self.root.winfo_y(),
        )
        self.dragged = False
        try:
            self.root.grab_set()
        except tk.TclError:
            pass

    def _on_drag(self, event: tk.Event) -> None:
        if self.drag_origin is None:
            return
        self.drag_last_event_at = time.monotonic()
        start_x, start_y, window_x, window_y = self.drag_origin
        delta_x = event.x_root - start_x
        delta_y = event.y_root - start_y
        if abs(delta_x) >= CLICK_MOVE_THRESHOLD or abs(delta_y) >= CLICK_MOVE_THRESHOLD:
            self.dragged = True
        x, y = self._clamp_position(window_x + delta_x, window_y + delta_y)
        self.root.geometry(f"+{x}+{y}")
        self._reposition_bubble()

    def _on_release(self, _: tk.Event) -> None:
        was_dragged = self.dragged
        if was_dragged:
            self._save_position()
        elif self.suppress_release_click:
            self.suppress_release_click = False
        else:
            if self.click_timer is not None:
                self._cancel_timer("click_timer")
            self.click_timer = self.root.after(220, self._run_single_click)
        self._clear_drag_state()
        if was_dragged and self.settings.auto_action:
            self._schedule_next_auto_action()

    def _on_double_click(self, _: tk.Event) -> str:
        if self.click_timer is not None:
            self._cancel_timer("click_timer")
        self.suppress_release_click = True
        self.wave()
        return "break"

    def _run_single_click(self) -> None:
        self.click_timer = None
        self.wink()

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        delta = 20 if event.delta > 0 else -20
        self.set_size(self.settings.sprite_height + delta)

    def _on_hover_enter(self, _: tk.Event | None) -> None:
        now = time.monotonic()
        if (
            self.is_closing
            or self.is_hidden
            or self.drag_origin is not None
            or self.current_pose not in HOVER_INTERRUPTIBLE_POSES
            or self.hover_timer is not None
            or self._hover_is_on_cooldown(now)
        ):
            return
        self.hover_timer = self.root.after(
            HOVER_TRIGGER_DELAY_MS,
            self._run_hover_action,
        )

    def _on_hover_leave(self, _: tk.Event | None) -> None:
        self._cancel_timer("hover_timer")

    def _hover_is_on_cooldown(self, now: float) -> bool:
        return (
            self.current_pose == "idle"
            and now - self.last_hover_action_at < HOVER_COOLDOWN_SECONDS
        )

    def _run_hover_action(self) -> None:
        self.hover_timer = None
        now = time.monotonic()
        if (
            self.is_closing
            or self.is_hidden
            or self.drag_origin is not None
            or self.current_pose not in HOVER_INTERRUPTIBLE_POSES
            or self._hover_is_on_cooldown(now)
        ):
            return
        self.last_hover_action_at = now
        self.perform_action(self.randomizer.choice(HOVER_ACTIONS))

    def _show_context_menu(self, event: tk.Event) -> None:
        self._hide_bubble()
        self._refresh_context_menu()
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _refresh_context_menu(self) -> None:
        state = "已开启" if self.settings.auto_action else "已关闭"
        self.context_menu.entryconfigure(
            self.auto_menu_index,
            label=f"自动动作（{state}）",
        )

    def _run_context_menu_command(self, callback: Callable[[], None]) -> None:
        try:
            self.context_menu.unpost()
            self.context_menu.grab_release()
        except tk.TclError:
            pass
        self.root.after(30, callback)

    def set_pose(
        self,
        pose: str,
        *,
        bubble_text: str | None = None,
        duration_ms: int | None = None,
        user_action: bool = True,
    ) -> None:
        if pose not in self.photo_images:
            raise ValueError(f"未知姿势：{pose}")
        self._cancel_timer("pose_timer")

        if user_action:
            self.behavior.touch()
        self.current_pose = pose
        self.canvas.itemconfigure(self.image_item, image=self.photo_images[pose])
        if bubble_text:
            self.show_bubble(bubble_text)

        actual_duration = (
            self.behavior.duration_ms(pose)
            if duration_ms is None
            else duration_ms
        )
        if pose != "idle" and actual_duration > 0:
            self.pose_deadline_at = time.monotonic() + actual_duration / 1000
            self.pose_timer = self.root.after(
                actual_duration,
                self._return_to_idle,
            )
        else:
            self.pose_deadline_at = None
        if user_action and self.settings.auto_action:
            self._schedule_next_auto_action(base_at=self.pose_deadline_at)

    def wave(self) -> None:
        self.set_pose("wave", bubble_text=self.randomizer.choice(WAVE_LINES))

    def wink(self) -> None:
        self.set_pose("wink", bubble_text=self.randomizer.choice(CLICK_LINES))

    def sleep(self) -> None:
        self.set_pose("sleep", bubble_text=self.randomizer.choice(SLEEP_LINES))

    def perform_action(self, pose: str, *, user_action: bool = True) -> None:
        try:
            lines = ACTION_LINES[pose]
        except KeyError as exc:
            raise ValueError(f"没有为动作配置台词：{pose}") from exc
        self.set_pose(
            pose,
            bubble_text=self.randomizer.choice(lines),
            user_action=user_action,
        )

    def _announce_auto_action(self) -> None:
        if (
            not self.is_closing
            and not self.is_hidden
            and self.settings.auto_action
            and self.current_pose == "idle"
        ):
            self.show_bubble("自动动作已开启，等我自己动一动吧～", 2800)

    def _schedule_auto_heartbeat(
        self,
        delay_ms: int = AUTO_HEARTBEAT_INTERVAL_MS,
    ) -> None:
        if self.is_closing or self.auto_heartbeat_timer is not None:
            return
        self.auto_heartbeat_timer = self.root.after(
            delay_ms,
            self._auto_heartbeat,
        )

    def _schedule_next_auto_action(
        self,
        *,
        base_at: float | None = None,
        initial: bool = False,
    ) -> None:
        if not self.settings.auto_action:
            return
        if initial:
            lower = AUTO_ACTION_INITIAL_MIN_DELAY_MS
            upper = AUTO_ACTION_INITIAL_MAX_DELAY_MS
        else:
            lower = AUTO_ACTION_IDLE_MIN_INTERVAL_MS
            upper = AUTO_ACTION_IDLE_MAX_INTERVAL_MS
        delay_ms = self.randomizer.randint(lower, upper)
        self.next_auto_action_at = (
            time.monotonic() if base_at is None else base_at
        ) + delay_ms / 1000

    def _schedule_auto_watchdog(self) -> None:
        if self.is_closing or self.auto_watchdog_timer is not None:
            return
        self.auto_watchdog_timer = self.root.after(
            AUTO_WATCHDOG_INTERVAL_MS,
            self._auto_watchdog,
        )

    def _auto_heartbeat(self) -> None:
        self.auto_heartbeat_timer = None
        if self.is_closing:
            return

        now = time.monotonic()
        self.last_auto_heartbeat_at = now
        try:
            self._recover_stale_drag(now)
            self._recover_stale_pose(now)
            if self.is_hidden:
                return
            if (
                self.settings.auto_action
                and self.drag_origin is None
                and now >= self.next_auto_action_at
            ):
                if self.current_pose == "idle":
                    self._run_auto_action()
                    self.auto_action_count += 1
                    self._schedule_next_auto_action(
                        base_at=self.pose_deadline_at,
                    )
                else:
                    self._schedule_next_auto_action(
                        base_at=self.pose_deadline_at,
                    )
        except Exception as exc:
            self._schedule_next_auto_action()
            self._record_runtime_error("自动动作心跳", exc, exc.__traceback__)
        finally:
            if not self.is_closing:
                self._schedule_auto_heartbeat()

    def _auto_watchdog(self) -> None:
        self.auto_watchdog_timer = None
        if self.is_closing:
            return
        try:
            now = time.monotonic()
            heartbeat_is_stale = (
                now - self.last_auto_heartbeat_at
                >= AUTO_HEARTBEAT_STALE_SECONDS
            )
            if self.auto_heartbeat_timer is None or heartbeat_is_stale:
                self._cancel_timer("auto_heartbeat_timer")
                self.auto_recovery_count += 1
                self._schedule_next_auto_action()
                self._schedule_auto_heartbeat(delay_ms=50)
        except Exception as exc:
            self._record_runtime_error("自动动作看门狗", exc, exc.__traceback__)
        finally:
            if not self.is_closing:
                self._schedule_auto_watchdog()

    def _recover_stale_drag(self, now: float) -> bool:
        if self.drag_origin is None or self.drag_last_event_at is None:
            return False
        if now - self.drag_last_event_at < DRAG_STALE_TIMEOUT_SECONDS:
            return False
        self._clear_drag_state()
        if self.settings.auto_action:
            self._schedule_next_auto_action(base_at=now)
        return True

    def _recover_stale_pose(self, now: float) -> bool:
        if (
            self.current_pose == "idle"
            or self.pose_deadline_at is None
            or now < self.pose_deadline_at + 1.0
        ):
            return False
        self._return_to_idle()
        return True

    def _clear_drag_state(self) -> None:
        self.drag_origin = None
        self.drag_last_event_at = None
        self.dragged = False
        try:
            self.root.grab_release()
        except tk.TclError:
            pass

    def _return_to_idle(self) -> None:
        self.pose_timer = None
        self.pose_deadline_at = None
        if not self.is_closing:
            self.set_pose("idle", user_action=False)

    def _run_auto_action(self) -> None:
        if (
            self.is_closing
            or self.is_hidden
            or not self.settings.auto_action
            or self.current_pose != "idle"
        ):
            return

        pose = self.behavior.next_auto_pose()
        if pose == "sleep":
            self.set_pose(
                "sleep",
                bubble_text=self.randomizer.choice(SLEEP_LINES),
                user_action=False,
            )
        elif pose != "idle":
            self.perform_action(pose, user_action=False)
        else:
            self.show_bubble(self.randomizer.choice(AMBIENT_LINES), 4600)

    def show_bubble(self, text: str, duration_ms: int = 3600) -> None:
        if (
            self.is_closing
            or self.is_hidden
            or self.bubble is None
            or self.bubble_canvas is None
        ):
            return
        self._cancel_timer("bubble_timer")

        was_visible = self.bubble.state() == "normal"
        if not was_visible:
            self.bubble.withdraw()
        self._draw_bubble(text)
        self.bubble.update_idletasks()
        self._reposition_bubble()
        if not was_visible:
            self.bubble.deiconify()
        self.bubble.lift()
        self.bubble_timer = self.root.after(duration_ms, self._hide_bubble)

    def _reposition_bubble(self) -> None:
        if self.bubble is None or not self.bubble.winfo_exists():
            return
        width = self.bubble_width
        height = self.bubble_height
        x = self.root.winfo_x() + (self.window_width - width) // 2 - 24
        y = self.root.winfo_y() - height + 18
        if y < 0:
            y = self.root.winfo_y() + 16
            x = self.root.winfo_x() - width + 18
        x = max(0, min(self.root.winfo_screenwidth() - width, x))
        self.bubble.geometry(f"{width}x{height}+{x}+{max(0, y)}")

    def _hide_bubble(self) -> None:
        if self.bubble_timer is not None:
            try:
                self.root.after_cancel(self.bubble_timer)
            except tk.TclError:
                pass
            self.bubble_timer = None
        if self.bubble is not None and self.bubble.winfo_exists():
            try:
                self.bubble.withdraw()
            except tk.TclError:
                pass

    def set_size(self, sprite_height: int) -> None:
        sprite_height = max(220, min(440, int(sprite_height)))
        if sprite_height == self.settings.sprite_height:
            return
        anchor_x = self.root.winfo_x() + self.window_width
        anchor_y = self.root.winfo_y() + self.window_height
        self.settings.sprite_height = sprite_height
        self._reload_sprites()
        x, y = self._clamp_position(
            anchor_x - self.window_width,
            anchor_y - self.window_height,
        )
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
        self._save_position()

    def toggle_topmost(self) -> None:
        self.settings.topmost = bool(self.topmost_var.get())
        self.root.attributes("-topmost", self.settings.topmost)
        self._save_settings()

    def toggle_auto_action(self) -> None:
        self.settings.auto_action = bool(self.auto_var.get())
        self.behavior.auto_enabled = self.settings.auto_action
        self.behavior.touch()
        if self.settings.auto_action:
            self._schedule_next_auto_action(initial=True)
            self._schedule_auto_heartbeat(delay_ms=50)
            self._schedule_auto_watchdog()
        self._save_settings()
        self.show_bubble(
            "自动动作已开启，我会自己活动啦～"
            if self.settings.auto_action
            else "自动动作已关闭，我会乖乖站好。",
            4200,
        )

    def test_auto_action_now(self) -> None:
        if not self.settings.auto_action:
            self.auto_var.set(True)
            self.settings.auto_action = True
            self.behavior.auto_enabled = True
            self._save_settings()
        self.set_pose(
            "stretch",
            bubble_text="自动动作测试成功～之后我会自己活动啦！",
            user_action=False,
        )
        self.auto_action_count += 1
        self._schedule_next_auto_action(base_at=self.pose_deadline_at)

    def show_auto_action_status(self) -> None:
        if not self.settings.auto_action:
            self.show_bubble("自动动作当前是关闭状态。", 3600)
            return
        remaining = max(0.0, self.next_auto_action_at - time.monotonic())
        seconds = max(1, int(remaining + 0.999))
        self.show_bubble(
            f"自动动作已开启\n约 {seconds} 秒后活动 · 已主动 {self.auto_action_count} 次",
            4600,
        )

    def toggle_startup(self) -> None:
        enabled = bool(self.startup_var.get())
        try:
            set_start_with_windows(enabled)
        except (OSError, RuntimeError) as exc:
            self.startup_var.set(not enabled)
            self.show_bubble(f"开机启动设置失败：{exc}", 4000)
            return
        self.settings.start_with_windows = enabled
        self._save_settings()
        self.show_bubble("已开启开机启动～" if enabled else "已关闭开机启动。")

    def show_about(self) -> None:
        self.show_bubble(
            "粉白桌宠 v0.2\n单击互动 · 双击挥手 · 右键发现更多动作",
            4800,
        )

    def toggle_visibility(self) -> None:
        if self.is_hidden:
            self.is_hidden = False
            self.root.deiconify()
            self.root.lift()
            if self.settings.auto_action:
                self._schedule_next_auto_action()
        else:
            self.is_hidden = True
            self._hide_bubble()
            self.root.withdraw()

    def _start_tray(self) -> None:
        try:
            import pystray
        except ImportError:
            return

        def dispatch(callback: Callable[[], None]) -> Callable[..., None]:
            def wrapped(*_: object) -> None:
                self.action_queue.put(callback)

            return wrapped

        menu = pystray.Menu(
            pystray.MenuItem("显示 / 隐藏", dispatch(self.toggle_visibility), default=True),
            pystray.MenuItem("挥挥手", dispatch(self.wave)),
            pystray.MenuItem("眨眨眼", dispatch(self.wink)),
            pystray.MenuItem("休息一下", dispatch(self.sleep)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "始终置顶",
                dispatch(self._tray_toggle_topmost),
                checked=lambda _: self.settings.topmost,
            ),
            pystray.MenuItem(
                "自动动作",
                dispatch(self._tray_toggle_auto),
                checked=lambda _: self.settings.auto_action,
            ),
            pystray.MenuItem(
                "开机启动",
                dispatch(self._tray_toggle_startup),
                checked=lambda _: self.settings.start_with_windows,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", dispatch(self.close)),
        )
        self.tray_icon = pystray.Icon(
            "pink_white_desktop_pet",
            create_tray_icon(),
            APP_NAME,
            menu,
        )
        self.tray_thread = threading.Thread(
            target=self.tray_icon.run,
            name="desktop-pet-tray",
            daemon=True,
        )
        self.tray_thread.start()

    def _drain_action_queue(self) -> None:
        self.action_queue_timer = None
        if self.is_closing:
            return
        try:
            while True:
                try:
                    callback = self.action_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    callback()
                except Exception as exc:
                    self._record_runtime_error(
                        "托盘动作队列",
                        exc,
                        exc.__traceback__,
                    )
        finally:
            if not self.is_closing:
                self.action_queue_timer = self.root.after(
                    80,
                    self._drain_action_queue,
                )

    def _tray_toggle_topmost(self) -> None:
        self.topmost_var.set(not self.settings.topmost)
        self.toggle_topmost()

    def _tray_toggle_auto(self) -> None:
        self.auto_var.set(not self.settings.auto_action)
        self.toggle_auto_action()

    def _tray_toggle_startup(self) -> None:
        self.startup_var.set(not self.settings.start_with_windows)
        self.toggle_startup()

    def _save_position(self) -> None:
        self.settings.x = self.root.winfo_x()
        self.settings.y = self.root.winfo_y()
        self._save_settings()

    def _save_settings(self) -> None:
        try:
            self.store.save(self.settings)
        except OSError:
            pass

    def _cancel_timer(self, timer_name: str) -> None:
        timer_id = getattr(self, timer_name, None)
        setattr(self, timer_name, None)
        if timer_id is None:
            return
        try:
            self.root.after_cancel(timer_id)
        except (tk.TclError, ValueError):
            pass

    def _report_callback_exception(
        self,
        exception_type: type[BaseException],
        exception: BaseException,
        traceback_object: object,
    ) -> None:
        self._record_runtime_error(
            "Tk 回调",
            exception,
            traceback_object,
        )

    def _record_runtime_error(
        self,
        context: str,
        error: BaseException,
        traceback_object: object | None = None,
    ) -> None:
        try:
            self.runtime_log_path.parent.mkdir(parents=True, exist_ok=True)
            if traceback_object is None:
                details = "".join(
                    traceback.format_exception_only(type(error), error)
                )
            else:
                details = "".join(
                    traceback.format_exception(
                        type(error),
                        error,
                        traceback_object,  # type: ignore[arg-type]
                    )
                )
            with self.runtime_log_path.open("a", encoding="utf-8") as log_file:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                log_file.write(f"[{timestamp}] {context}\n{details}\n")
        except OSError:
            pass

    def close(self) -> None:
        if self.is_closing:
            return
        self.is_closing = True
        self._save_position()
        for timer_name in (
            "pose_timer",
            "auto_heartbeat_timer",
            "auto_watchdog_timer",
            "action_queue_timer",
            "click_timer",
            "hover_timer",
        ):
            self._cancel_timer(timer_name)
        self._hide_bubble()
        if self.bubble is not None:
            try:
                self.bubble.destroy()
            except tk.TclError:
                pass
            self.bubble = None
            self.bubble_canvas = None
            self.bubble_font = None
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except (OSError, RuntimeError):
                pass
        self.root.destroy()


def run_desktop_pet(
    smoke_after_ms: int | None = None,
    *,
    interaction_smoke: bool = False,
    verify_auto_action: bool = False,
    verify_hover_action: bool = False,
) -> None:
    _enable_dpi_awareness()
    single_instance = SingleInstance()
    temporary_settings: tempfile.TemporaryDirectory[str] | None = None
    try:
        single_instance.acquire()
    except AlreadyRunningError:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(
                None,
                "粉白桌宠已经在运行啦，请看看桌面或系统托盘～",
                APP_NAME,
                0x40,
            )
        return

    root = tk.Tk()
    auto_verification_error: str | None = None
    try:
        store = None
        if smoke_after_ms is not None:
            temporary_settings = tempfile.TemporaryDirectory(
                prefix="pink-pet-gui-check-"
            )
            store = SettingsStore(
                Path(temporary_settings.name) / "settings.json"
            )
        pet = DesktopPet(
            root,
            store=store,
            enable_tray=smoke_after_ms is None,
        )
        if interaction_smoke:
            poses = [
                "wave",
                "wink",
                "stretch",
                "yawn",
                "think",
                "cheer",
                "shy",
                "read",
                "drink",
                "sleep",
            ]
            for index, pose in enumerate(poses):
                callback = (
                    pet.wave
                    if pose == "wave"
                    else pet.wink
                    if pose == "wink"
                    else pet.sleep
                    if pose == "sleep"
                    else lambda selected=pose: pet.perform_action(selected)
                )
                root.after(250 + index * 600, callback)
        if verify_auto_action:
            pet.dragged = True
            pet.drag_origin = (
                0,
                0,
                pet.root.winfo_x(),
                pet.root.winfo_y(),
            )
            def release_and_accelerate_auto_check() -> None:
                pet._on_release(None)  # type: ignore[arg-type]
                pet.next_auto_action_at = time.monotonic() + 1.0

            root.after(700, release_and_accelerate_auto_check)

            def verify_visible_auto_pose() -> None:
                nonlocal auto_verification_error
                if pet.auto_action_count < 1:
                    auto_verification_error = (
                        "拖动释放后自动动作仍未恢复，触发次数为 0"
                    )

            root.after(2600, verify_visible_auto_pose)
        if verify_hover_action:
            pet.randomizer = random.Random(8)
            pet.set_pose("read", user_action=False)
            root.after(100, pet._run_hover_action)

            def verify_visible_hover_pose() -> None:
                nonlocal auto_verification_error
                if pet.current_pose not in HOVER_ACTIONS:
                    auto_verification_error = (
                        "鼠标悬停未切换到挥手、眨眼或害羞动作"
                    )

            root.after(
                350,
                verify_visible_hover_pose,
            )
        if smoke_after_ms is not None:
            root.after(smoke_after_ms, pet.close)
        root.mainloop()
        if auto_verification_error is not None:
            raise RuntimeError(auto_verification_error)
    except Exception as exc:
        messagebox.showerror(APP_NAME, f"桌宠启动失败：\n{exc}")
        raise
    finally:
        single_instance.release()
        if temporary_settings is not None:
            temporary_settings.cleanup()
