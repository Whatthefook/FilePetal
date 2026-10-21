"""Smoke tests: every package module imports and key entry points exist."""

import importlib
import sys

import pytest

MODULES = [
    "tangerine",
    "tangerine.paths",
    "tangerine.theme",
    "tangerine.settings",
    "tangerine.naming",
    "tangerine.catalog",
    "tangerine.media",
    "tangerine.engines",
    "tangerine.documents",
    "tangerine.tools",
    "tangerine.jobs",
    "tangerine.progress",
    "tangerine.dragfiles",
    "tangerine.wheel",
    "tangerine.monitor",
    "tangerine.editors",
    "tangerine.actions",
    "tangerine.settings_window",
    "tangerine.main",
]

if sys.platform != "win32":
    MODULES.remove("tangerine.dragfiles")
    MODULES.remove("tangerine.monitor")


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    assert importlib.import_module(name) is not None


def test_optional_icons_module():
    """``tangerine.icons`` may exist in newer layouts; if so it must expose icon_for."""
    try:
        icons = importlib.import_module("tangerine.icons")
    except ImportError:
        return
    assert callable(getattr(icons, "icon_for", None))


def test_key_symbols_exist():
    from tangerine import actions, catalog, engines, tools, wheel

    assert callable(engines.convert_single)
    assert callable(engines.convert_image)
    assert callable(tools.compress_image)
    assert callable(tools.compress_video)
    assert callable(tools.compress_audio)
    assert callable(tools.make_collage)
    assert callable(tools.read_qr_codes)
    assert callable(catalog.conversions_for)
    assert callable(catalog.tools_for)
    assert callable(catalog.family_of)
    assert callable(actions.run_tool)
    assert callable(actions.run_conversions)

    icon_for = getattr(wheel, "icon_for", None)
    if icon_for is None:
        icon_for = getattr(importlib.import_module("tangerine.icons"), "icon_for", None)
    assert callable(icon_for)
    assert icon_for("jpg")


def test_catalog_ids_are_unique():
    from tangerine import catalog

    ids = []
    for group in (catalog.IMAGE_TOOLS, catalog.AUDIO_TOOLS, catalog.VIDEO_TOOLS,
                  catalog.GIF_TOOLS, catalog.PDF_TOOLS, catalog.ARCHIVE_TOOLS,
                  catalog.NO_OP):
        ids.extend(tool.id for tool in group)
    assert len(ids) == len(set(ids))


def test_version_is_declared():
    from tangerine import paths

    assert paths.APP_VERSION
    assert isinstance(paths.APP_BUILD, int)
