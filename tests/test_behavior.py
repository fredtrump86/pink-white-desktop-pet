from __future__ import annotations

import random
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import desktop_pet.application as application_module
from desktop_pet.application import (
    ACTION_LINES,
    DRAG_STALE_TIMEOUT_SECONDS,
    HOVER_ACTIONS,
    HOVER_TRIGGER_DELAY_MS,
    DesktopPet,
)
from desktop_pet.behavior import POSE_DURATIONS_MS, PetBehavior


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class RecordingRandom:
    def __init__(self) -> None:
        self.populations: list[tuple[str, ...]] = []

    def choice(self, population: tuple[str, ...]) -> str:
        self.populations.append(tuple(population))
        return population[0]


class MinimumIntervalRandom:
    def __init__(self) -> None:
        self.bounds: list[tuple[int, int]] = []

    def randint(self, lower: int, upper: int) -> int:
        self.bounds.append((lower, upper))
        return lower


class PetBehaviorTests(unittest.TestCase):
    def test_disabled_auto_action_returns_idle(self) -> None:
        behavior = PetBehavior(auto_enabled=False)
        self.assertEqual("idle", behavior.next_auto_pose())

    def test_over_ten_minutes_uses_only_read_and_sleep_uniform_pool(self) -> None:
        clock = FakeClock()
        randomizer = RecordingRandom()
        behavior = PetBehavior(
            auto_enabled=True,
            clock=clock,
            randomizer=randomizer,  # type: ignore[arg-type]
        )
        clock.value += 601.0

        behavior.next_auto_pose()

        self.assertEqual([("sleep", "read")], randomizer.populations)

    def test_touch_resets_rest_timer(self) -> None:
        clock = FakeClock()
        randomizer = RecordingRandom()
        behavior = PetBehavior(
            auto_enabled=True,
            clock=clock,
            randomizer=randomizer,  # type: ignore[arg-type]
        )
        clock.value += 700.0
        behavior.touch()
        behavior.next_auto_pose()

        self.assertNotIn("sleep", randomizer.populations[0])
        self.assertNotIn("read", randomizer.populations[0])

    def test_before_ten_minutes_uses_all_non_rest_actions_uniform_pool(self) -> None:
        expected = {
            "wave",
            "wink",
            "stretch",
            "yawn",
            "think",
            "cheer",
            "shy",
            "drink",
        }
        for idle_seconds in (30.0, 120.0, 400.0, 599.0):
            with self.subTest(idle_seconds=idle_seconds):
                clock = FakeClock()
                randomizer = RecordingRandom()
                behavior = PetBehavior(
                    auto_enabled=True,
                    clock=clock,
                    randomizer=randomizer,  # type: ignore[arg-type]
                )
                clock.value += idle_seconds

                behavior.next_auto_pose()

                self.assertEqual(1, len(randomizer.populations))
                self.assertEqual(expected, set(randomizer.populations[0]))
                self.assertEqual(8, len(randomizer.populations[0]))

    def test_short_idle_always_produces_visible_action(self) -> None:
        for seed in range(30):
            behavior = PetBehavior(
                auto_enabled=True,
                randomizer=random.Random(seed),
            )
            with self.subTest(seed=seed):
                poses = [behavior.next_auto_pose() for _ in range(10)]
                self.assertNotIn("idle", poses)

    def test_uniform_selection_allows_the_same_action_to_repeat(self) -> None:
        clock = FakeClock()
        randomizer = RecordingRandom()
        behavior = PetBehavior(
            auto_enabled=True,
            clock=clock,
            randomizer=randomizer,  # type: ignore[arg-type]
        )
        first = behavior.next_auto_pose()
        second = behavior.next_auto_pose()
        self.assertEqual(first, second)
        self.assertEqual(randomizer.populations[0], randomizer.populations[1])

    def test_all_action_durations_are_positive(self) -> None:
        for pose in (
            "wave",
            "wink",
            "sleep",
            "stretch",
            "yawn",
            "think",
            "cheer",
            "shy",
            "read",
            "drink",
        ):
            with self.subTest(pose=pose):
                self.assertGreater(PetBehavior.duration_ms(pose), 0)

    def test_read_and_sleep_actions_last_thirty_minutes(self) -> None:
        thirty_minutes_ms = 30 * 60 * 1000
        self.assertEqual(thirty_minutes_ms, PetBehavior.duration_ms("read"))
        self.assertEqual(thirty_minutes_ms, PetBehavior.duration_ms("sleep"))

    def test_every_auto_pose_has_a_dispatchable_action(self) -> None:
        auto_poses = set(POSE_DURATIONS_MS) - {"idle"}
        dispatchable_poses = set(ACTION_LINES) | {"sleep"}
        self.assertEqual(set(), auto_poses - dispatchable_poses)


class ContextMenuTests(unittest.TestCase):
    def test_menu_is_unposted_before_callback_runs(self) -> None:
        events: list[str] = []

        class FakeMenu:
            def unpost(self) -> None:
                events.append("unpost")

            def grab_release(self) -> None:
                events.append("release")

        class FakeRoot:
            def after(self, delay_ms: int, callback: object) -> None:
                events.append(f"after:{delay_ms}")
                callback()  # type: ignore[operator]

        pet = object.__new__(DesktopPet)
        pet.context_menu = FakeMenu()  # type: ignore[assignment]
        pet.root = FakeRoot()  # type: ignore[assignment]

        pet._run_context_menu_command(lambda: events.append("callback"))

        self.assertEqual(
            ["unpost", "release", "after:30", "callback"],
            events,
        )


class FakeRoot:
    def __init__(self) -> None:
        self.scheduled: list[tuple[str, int, object]] = []
        self.cancelled: list[str] = []
        self.grab_releases = 0

    def after(self, delay_ms: int, callback: object) -> str:
        timer_id = f"timer-{len(self.scheduled)}"
        self.scheduled.append((timer_id, delay_ms, callback))
        return timer_id

    def after_cancel(self, timer_id: str) -> None:
        self.cancelled.append(timer_id)

    def grab_release(self) -> None:
        self.grab_releases += 1


class SchedulerRecoveryTests(unittest.TestCase):
    def test_scheduler_uses_recommended_quieter_intervals(self) -> None:
        self.assertEqual(
            15_000,
            getattr(application_module, "AUTO_ACTION_INITIAL_MIN_DELAY_MS", None),
        )
        self.assertEqual(
            25_000,
            getattr(application_module, "AUTO_ACTION_INITIAL_MAX_DELAY_MS", None),
        )
        self.assertEqual(
            20_000,
            getattr(application_module, "AUTO_ACTION_IDLE_MIN_INTERVAL_MS", None),
        )
        self.assertEqual(
            40_000,
            getattr(application_module, "AUTO_ACTION_IDLE_MAX_INTERVAL_MS", None),
        )

    def test_next_auto_action_is_scheduled_after_pose_finishes(self) -> None:
        root = FakeRoot()
        randomizer = MinimumIntervalRandom()
        pet = object.__new__(DesktopPet)
        pet.root = root  # type: ignore[assignment]
        pet.is_closing = False
        pet.is_hidden = False
        pet.settings = SimpleNamespace(auto_action=True)
        pet.drag_origin = None
        pet.drag_last_event_at = None
        pet.dragged = False
        pet.current_pose = "idle"
        pet.pose_deadline_at = None
        pet.next_auto_action_at = 0.0
        pet.auto_action_count = 0
        pet.auto_heartbeat_timer = "running"
        pet.last_auto_heartbeat_at = 0.0
        pet.randomizer = randomizer  # type: ignore[assignment]
        pet._record_runtime_error = lambda *args: None  # type: ignore[method-assign]

        def run_action() -> None:
            pet.current_pose = "think"
            pet.pose_deadline_at = 105.2

        pet._run_auto_action = run_action  # type: ignore[method-assign]

        with patch("desktop_pet.application.time.monotonic", return_value=100.0):
            pet._auto_heartbeat()

        self.assertEqual([(20_000, 40_000)], randomizer.bounds)
        self.assertEqual(125.2, pet.next_auto_action_at)

    def test_first_auto_action_uses_behavior_pool(self) -> None:
        performed: list[tuple[str, bool]] = []
        pet = object.__new__(DesktopPet)
        pet.is_closing = False
        pet.is_hidden = False
        pet.settings = SimpleNamespace(auto_action=True)
        pet.current_pose = "idle"
        pet.auto_action_count = 0
        pet.behavior = SimpleNamespace(next_auto_pose=lambda: "wave")
        pet.perform_action = (  # type: ignore[method-assign]
            lambda pose, user_action=True: performed.append((pose, user_action))
        )

        pet._run_auto_action()

        self.assertEqual([("wave", False)], performed)

    def test_auto_heartbeat_reschedules_after_action_exception(self) -> None:
        root = FakeRoot()
        errors: list[tuple[str, str]] = []
        pet = object.__new__(DesktopPet)
        pet.root = root  # type: ignore[assignment]
        pet.is_closing = False
        pet.is_hidden = False
        pet.settings = SimpleNamespace(auto_action=True)
        pet.drag_origin = None
        pet.drag_last_event_at = None
        pet.dragged = False
        pet.current_pose = "idle"
        pet.next_auto_action_at = 0.0
        pet.auto_action_count = 0
        pet.auto_heartbeat_timer = "running"
        pet.last_auto_heartbeat_at = 0.0
        pet.randomizer = random.Random(1)
        pet._record_runtime_error = (  # type: ignore[method-assign]
            lambda context, error, traceback_object=None: errors.append(
                (context, str(error))
            )
        )

        def fail_action() -> None:
            raise RuntimeError("动作切换失败")

        pet._run_auto_action = fail_action  # type: ignore[method-assign]

        pet._auto_heartbeat()

        self.assertEqual(0, pet.auto_action_count)
        self.assertIsNotNone(pet.auto_heartbeat_timer)
        self.assertEqual(1, len(root.scheduled))
        self.assertEqual([("自动动作心跳", "动作切换失败")], errors)

    def test_stale_drag_state_is_released_and_auto_action_rearmed(self) -> None:
        root = FakeRoot()
        pet = object.__new__(DesktopPet)
        pet.root = root  # type: ignore[assignment]
        pet.drag_origin = (1, 2, 3, 4)
        pet.drag_last_event_at = 100.0
        pet.dragged = True
        pet.settings = SimpleNamespace(auto_action=True)
        pet.next_auto_action_at = 999.0
        pet.randomizer = MinimumIntervalRandom()  # type: ignore[assignment]

        now = 100.0 + DRAG_STALE_TIMEOUT_SECONDS + 0.1
        recovered = pet._recover_stale_drag(now)

        self.assertTrue(recovered)
        self.assertIsNone(pet.drag_origin)
        self.assertIsNone(pet.drag_last_event_at)
        self.assertFalse(pet.dragged)
        self.assertEqual(1, root.grab_releases)
        self.assertEqual(now + 20.0, pet.next_auto_action_at)

    def test_watchdog_recreates_a_missing_heartbeat(self) -> None:
        root = FakeRoot()
        pet = object.__new__(DesktopPet)
        pet.root = root  # type: ignore[assignment]
        pet.is_closing = False
        pet.auto_watchdog_timer = "running"
        pet.auto_heartbeat_timer = None
        pet.last_auto_heartbeat_at = 0.0
        pet.auto_recovery_count = 0
        pet.next_auto_action_at = 999999999.0
        pet.settings = SimpleNamespace(auto_action=True)
        pet.randomizer = MinimumIntervalRandom()  # type: ignore[assignment]
        pet._record_runtime_error = lambda *args: None  # type: ignore[method-assign]

        pet._auto_watchdog()

        self.assertEqual(1, pet.auto_recovery_count)
        self.assertIsNotNone(pet.auto_heartbeat_timer)
        self.assertIsNotNone(pet.auto_watchdog_timer)
        self.assertEqual([50, 2_000], [item[1] for item in root.scheduled])

    def test_hidden_pet_never_deiconifies_bubble(self) -> None:
        class BubbleThatMustStayHidden:
            def state(self) -> str:
                raise AssertionError("隐藏状态不应访问或显示气泡")

        pet = object.__new__(DesktopPet)
        pet.is_closing = False
        pet.is_hidden = True
        pet.bubble = BubbleThatMustStayHidden()  # type: ignore[assignment]
        pet.bubble_canvas = object()  # type: ignore[assignment]

        pet.show_bubble("不应显示")

    def test_pointer_events_are_bound_only_once(self) -> None:
        class FakeWidget:
            def __init__(self) -> None:
                self.events: list[str] = []

            def bind(self, event: str, callback: object) -> None:
                self.events.append(event)

        pet = object.__new__(DesktopPet)
        pet.root = FakeWidget()  # type: ignore[assignment]
        pet.canvas = FakeWidget()  # type: ignore[assignment]

        pet._bind_events()

        self.assertEqual([], pet.root.events)  # type: ignore[attr-defined]
        self.assertEqual(8, len(pet.canvas.events))  # type: ignore[attr-defined]
        self.assertIn("<Enter>", pet.canvas.events)  # type: ignore[attr-defined]
        self.assertIn("<Leave>", pet.canvas.events)  # type: ignore[attr-defined]

    def test_hover_is_delayed_then_runs_one_of_the_expected_actions(self) -> None:
        root = FakeRoot()
        performed: list[str] = []
        pet = object.__new__(DesktopPet)
        pet.root = root  # type: ignore[assignment]
        pet.is_closing = False
        pet.is_hidden = False
        pet.drag_origin = None
        pet.current_pose = "idle"
        pet.hover_timer = None
        pet.last_hover_action_at = float("-inf")
        pet.randomizer = random.Random(8)
        pet.perform_action = performed.append  # type: ignore[method-assign]

        pet._on_hover_enter(None)  # type: ignore[arg-type]

        self.assertEqual(1, len(root.scheduled))
        _, delay_ms, callback = root.scheduled[0]
        self.assertEqual(HOVER_TRIGGER_DELAY_MS, delay_ms)
        callback()  # type: ignore[operator]
        self.assertEqual(1, len(performed))
        self.assertIn(performed[0], HOVER_ACTIONS)
        self.assertIsNone(pet.hover_timer)

    def test_hover_leave_cancels_a_pending_action(self) -> None:
        root = FakeRoot()
        pet = object.__new__(DesktopPet)
        pet.root = root  # type: ignore[assignment]
        pet.is_closing = False
        pet.is_hidden = False
        pet.drag_origin = None
        pet.current_pose = "idle"
        pet.hover_timer = None
        pet.last_hover_action_at = float("-inf")
        pet.randomizer = random.Random(1)

        pet._on_hover_enter(None)  # type: ignore[arg-type]
        pending_timer = pet.hover_timer
        pet._on_hover_leave(None)  # type: ignore[arg-type]

        self.assertIsNone(pet.hover_timer)
        self.assertEqual([pending_timer], root.cancelled)

    def test_hover_does_not_interrupt_an_active_pose(self) -> None:
        root = FakeRoot()
        pet = object.__new__(DesktopPet)
        pet.root = root  # type: ignore[assignment]
        pet.is_closing = False
        pet.is_hidden = False
        pet.drag_origin = None
        pet.current_pose = "wave"
        pet.hover_timer = None
        pet.last_hover_action_at = float("-inf")

        pet._on_hover_enter(None)  # type: ignore[arg-type]

        self.assertEqual([], root.scheduled)
        self.assertIsNone(pet.hover_timer)

    def test_hover_can_interrupt_reading_and_sleeping(self) -> None:
        for resting_pose in ("read", "sleep"):
            with self.subTest(resting_pose=resting_pose):
                root = FakeRoot()
                performed: list[str] = []
                pet = object.__new__(DesktopPet)
                pet.root = root  # type: ignore[assignment]
                pet.is_closing = False
                pet.is_hidden = False
                pet.drag_origin = None
                pet.current_pose = resting_pose
                pet.hover_timer = None
                pet.last_hover_action_at = time.monotonic()
                pet.randomizer = random.Random(8)
                pet.perform_action = performed.append  # type: ignore[method-assign]

                pet._on_hover_enter(None)  # type: ignore[arg-type]

                self.assertEqual(1, len(root.scheduled))
                _, delay_ms, callback = root.scheduled[0]
                self.assertEqual(HOVER_TRIGGER_DELAY_MS, delay_ms)
                callback()  # type: ignore[operator]
                self.assertEqual(1, len(performed))
                self.assertIn(performed[0], HOVER_ACTIONS)

    def test_hover_cooldown_prevents_retriggering(self) -> None:
        root = FakeRoot()
        pet = object.__new__(DesktopPet)
        pet.root = root  # type: ignore[assignment]
        pet.is_closing = False
        pet.is_hidden = False
        pet.drag_origin = None
        pet.current_pose = "idle"
        pet.hover_timer = None
        pet.last_hover_action_at = time.monotonic()

        pet._on_hover_enter(None)  # type: ignore[arg-type]

        self.assertEqual([], root.scheduled)
        self.assertIsNone(pet.hover_timer)


if __name__ == "__main__":
    unittest.main()
