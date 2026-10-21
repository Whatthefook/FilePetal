"""Foreground context gate (v1.9.1): keep the wheel out of games.

Measured on Windows 11: borderless full-screen windows report QUNS=5
(ACCEPTS_NOTIFICATIONS), so the geometry check is what catches them; a
maximised window overshoots its monitor edges by ~8 px, stops at the work
area, and reports SW_SHOWMAXIMIZED, so it stays allowed (that keeps
"automatically hide the taskbar" setups working). Shell surfaces are never
gated: file work must always work.
"""

import os
import sys

import pytest

if sys.platform != "win32":
    pytest.skip("Foreground window probes are Windows-only", allow_module_level=True)

from tangerine import context

SMALL_FRAME = (100, 100, 900, 700)
MONITOR = (0, 0, 1920, 1080)


def _install(monkeypatch, **overrides):
    """Patch every Win32 probe with scripted values and reset the cache."""
    values = {
        "hwnd": 1234,
        "pid": 4242,
        "cls": "Chrome_WidgetWin_1",
        "quns": 5,
        "maximized": False,
        "frame": SMALL_FRAME,
        "monitor": MONITOR,
        "suppress": True,
    }
    values.update(overrides)
    calls = {"probe": 0}

    monkeypatch.setattr(context, "_foreground_window", lambda: values["hwnd"])
    monkeypatch.setattr(context, "_window_pid", lambda hwnd: values["pid"])
    monkeypatch.setattr(context, "_window_class", lambda hwnd: values["cls"])
    monkeypatch.setattr(context, "_quns_state", lambda: values["quns"])
    monkeypatch.setattr(context, "_is_maximized", lambda hwnd: values["maximized"])
    monkeypatch.setattr(context, "_window_frame", lambda hwnd: values["frame"])
    monkeypatch.setattr(context, "_monitor_rect", lambda hwnd: values["monitor"])
    monkeypatch.setattr(
        context.settings,
        "get",
        lambda key, default=None: (
            values["suppress"] if key == "suppressInFullscreen" else default
        ),
    )
    original_probe = context._probe

    def counting_probe():
        calls["probe"] += 1
        return original_probe()

    monkeypatch.setattr(context, "_probe", counting_probe)
    monkeypatch.setattr(context, "_cache", None)
    return values, calls


def test_shell_surfaces_are_always_allowed(monkeypatch):
    for window_class in (
        "CabinetWClass",
        "ExploreWClass",
        "Progman",
        "WorkerW",
        "Shell_TrayWnd",
        "XamlExplorerHostIslandWindow",
    ):
        _install(monkeypatch, cls=window_class, quns=2, frame=MONITOR)
        assert context.wheel_allowed() is True


def test_own_windows_are_allowed(monkeypatch):
    _install(monkeypatch, pid=os.getpid())
    assert context.wheel_allowed() is True


def test_no_foreground_window_is_allowed(monkeypatch):
    _install(monkeypatch, hwnd=0)
    assert context.wheel_allowed() is True


def test_game_classes_are_blocked_regardless_of_geometry(monkeypatch):
    for window_class in ("UnityWndClass", "SDL_app", "unrealwindow", "Valve001"):
        _install(monkeypatch, cls=window_class)
        assert context.wheel_allowed() is False


def test_quns_blocked_states_are_refused(monkeypatch):
    for state in (1, 2, 3, 4):
        _install(monkeypatch, quns=state)
        assert context.wheel_allowed() is False


def test_quns_unknown_allows_a_windowed_app(monkeypatch):
    _install(monkeypatch, quns=None)
    assert context.wheel_allowed() is True


def test_borderless_fullscreen_is_blocked(monkeypatch):
    _install(monkeypatch, frame=MONITOR)
    assert context.wheel_allowed() is False


def test_slightly_inset_fullscreen_is_blocked(monkeypatch):
    _install(monkeypatch, frame=(5, 5, 1915, 1075))
    assert context.wheel_allowed() is False


def test_geometry_tolerance_boundary(monkeypatch):
    _install(monkeypatch, frame=(11, 11, 1909, 1069))
    assert context.wheel_allowed() is False

    _install(monkeypatch, frame=(12, 12, 1908, 1068))
    assert context.wheel_allowed() is True


def test_maximized_window_is_allowed_even_when_it_fills_the_work_area(monkeypatch):
    _install(monkeypatch, maximized=True, frame=(-8, -8, 1928, 1040))
    assert context.wheel_allowed() is True


def test_windowed_app_is_allowed(monkeypatch):
    _install(monkeypatch)
    assert context.wheel_allowed() is True


def test_kill_switch_allows_everything(monkeypatch):
    _install(
        monkeypatch, suppress=False, cls="UnityWndClass", quns=1, frame=MONITOR
    )
    assert context.wheel_allowed() is True


def test_results_are_cached_for_the_ttl(monkeypatch):
    _, calls = _install(monkeypatch, frame=MONITOR)
    assert context.wheel_allowed() is False
    assert context.wheel_allowed() is False
    assert calls["probe"] == 1

    context._cache = None
    assert context.wheel_allowed() is False
    assert calls["probe"] == 2


def test_probe_failures_fail_open(monkeypatch):
    monkeypatch.setattr(
        context.settings,
        "get",
        lambda key, default=None: True if key == "suppressInFullscreen" else default,
    )

    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr(context, "_probe", broken)
    monkeypatch.setattr(context, "_cache", None)
    assert context.wheel_allowed() is True
