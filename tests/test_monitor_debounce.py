"""Regression tests for the drag-monitor button debounce (v1.7.1).

Windows 11 reports the left button as up for isolated samples while Explorer
services the OLE drag loop. The monitor must swallow those bursts: treating
them as a release hid the wheel mid-drag and re-bloomed it with the petals
emptied a tick later, so dropping at that instant was a silent no-op.
"""

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("Explorer drag monitoring is Windows-only", allow_module_level=True)

from PySide6.QtCore import QPoint

from tangerine import monitor as monitor_module
from tangerine.monitor import BUTTON_RELEASE_SAMPLES, VK_LBUTTON, DragMonitor


class _ScriptedKeys:
    """GetAsyncKeyState stand-in: only VK_LBUTTON is exercised."""

    def __init__(self, down: bool = True):
        self.down = down

    def __call__(self, vk: int) -> bool:
        return self.down if vk == VK_LBUTTON else False


@pytest.fixture
def rig(qapp, monkeypatch):
    keys = _ScriptedKeys()
    state = {"pos": QPoint(100, 100), "allowed": True}
    monkeypatch.setattr(monitor_module, "_is_down", keys)
    monkeypatch.setattr(
        monitor_module.context, "wheel_allowed", lambda: state["allowed"]
    )
    monkeypatch.setattr(
        DragMonitor, "_mode_for_current_modifiers", lambda self: "conversion"
    )
    monkeypatch.setattr(DragMonitor, "_drag_files", lambda self: None)
    monkeypatch.setattr(
        DragMonitor, "_cursor", lambda self: QPoint(state["pos"])
    )
    monitor = DragMonitor()
    monitor.stop()
    events: list[tuple] = []
    monitor.wheelShown.connect(
        lambda pos, files, mode: events.append(("shown", files, mode))
    )
    monitor.wheelMoved.connect(lambda pos: events.append(("moved",)))
    monitor.wheelHidden.connect(lambda: events.append(("hidden",)))
    monitor.wheelRefreshed.connect(lambda mode: events.append(("refreshed", mode)))
    return {"monitor": monitor, "keys": keys, "state": state, "events": events}


def _start_drag(rig) -> None:
    """Press, move past the threshold and let the wheel show."""
    rig["monitor"]._tick()
    rig["state"]["pos"] = QPoint(100, 180)
    rig["monitor"]._tick()
    assert [event[0] for event in rig["events"]] == ["shown"]


def test_isolated_up_samples_keep_the_wheel(rig):
    _start_drag(rig)
    monitor, keys, events = rig["monitor"], rig["keys"], rig["events"]

    keys.down = False
    monitor._tick()
    assert ("hidden",) not in events

    keys.down = True
    rig["state"]["pos"] = QPoint(100, 200)
    monitor._tick()
    kinds = [event[0] for event in events]
    assert kinds.count("shown") == 1
    assert kinds[-1] == "moved"


def test_ambiguous_window_does_not_advance_the_gesture(rig):
    monitor, keys, events = rig["monitor"], rig["keys"], rig["events"]
    monitor._tick()  # press at (100, 100)

    keys.down = False
    rig["state"]["pos"] = QPoint(100, 180)
    monitor._tick()  # ambiguous sample: suspended, no wheel yet
    assert events == []

    keys.down = True  # the sample was noise; the drag continues
    monitor._tick()
    assert [event[0] for event in events] == ["shown"]


def test_release_requires_consecutive_up_samples(rig):
    _start_drag(rig)
    monitor, keys, events = rig["monitor"], rig["keys"], rig["events"]

    keys.down = False
    for _ in range(BUTTON_RELEASE_SAMPLES - 1):
        monitor._tick()
        assert ("hidden",) not in events

    monitor._tick()
    assert [event[0] for event in events].count("hidden") == 1

    monitor._tick()
    assert [event[0] for event in events].count("hidden") == 1


def test_context_gate_blocks_the_wheel(rig):
    rig["state"]["allowed"] = False
    rig["monitor"]._tick()
    rig["state"]["pos"] = QPoint(100, 180)
    rig["monitor"]._tick()
    assert rig["events"] == []

    rig["state"]["allowed"] = True
    rig["monitor"]._tick()
    assert [event[0] for event in rig["events"]] == ["shown"]


def test_context_gate_hides_a_visible_wheel(rig):
    _start_drag(rig)
    rig["state"]["allowed"] = False
    rig["state"]["pos"] = QPoint(100, 200)
    rig["monitor"]._tick()
    assert [event[0] for event in rig["events"]][-1] == "hidden"
