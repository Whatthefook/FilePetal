"""Internationalization: lookups, fallbacks, formatting and en/es parity.

The persistent default language stays ``"en"`` so the rest of the suite (and
any temporary verification script) keeps seeing English strings; every test
here restores the previous language at teardown.
"""

import pytest

from tangerine import i18n, settings


@pytest.fixture(autouse=True)
def restore_language():
    original = settings.get("language", i18n.DEFAULT_LANGUAGE) or i18n.DEFAULT_LANGUAGE
    yield
    i18n.set_language(original)


def test_english_is_the_default():
    i18n.set_language(i18n.DEFAULT_LANGUAGE)
    assert i18n.current_language() == "en"
    assert i18n.tr("wheel.convert") == "Convert"
    assert i18n.tr("tray.quit") == "Quit FilePetal"


def test_spanish_translations():
    i18n.set_language("es")
    assert i18n.current_language() == "es"
    assert i18n.tr("wheel.convert") == "Convertir"
    assert i18n.tr("tray.quit") == "Salir de FilePetal"
    assert i18n.tr("tool.img.compress") == "Comprimir"
    assert i18n.tr("progress.cancel") == "Cancelar"


def test_unknown_key_falls_back_to_the_key():
    assert i18n.tr("does.not.exist") == "does.not.exist"


def test_format_kwargs_are_applied():
    assert i18n.tr("action.converting_to", target="PDF") == "Converting to PDF"
    assert i18n.tr("wheel.files_count", n=3) == "3 files"
    i18n.set_language("es")
    assert i18n.tr("action.converting_to", target="PDF") == "Convirtiendo a PDF"


def test_language_tables_have_parity_and_coverage():
    english = i18n.TRANSLATIONS["en"]
    spanish = i18n.TRANSLATIONS["es"]
    assert len(english) > 150, "expected a comprehensive key table"
    assert set(english) <= set(spanish), sorted(set(english) - set(spanish))
    for key, value in english.items():
        assert isinstance(value, str) and value
    for key, value in spanish.items():
        assert isinstance(value, str) and value


def test_system_unsupported_locale_falls_back_to_english(monkeypatch):
    monkeypatch.setattr(i18n, "_system_locale_name", lambda: "de_DE")
    settings.set("language", "system")
    assert i18n.resolve_language() == "en"
    assert i18n.current_language() == "en"
    assert i18n.tr("wheel.convert") == "Convert"


def test_system_supported_locale_resolves(monkeypatch):
    monkeypatch.setattr(i18n, "_system_locale_name", lambda: "es_MX")
    settings.set("language", "system")
    assert i18n.resolve_language() == "es"
    assert i18n.tr("wheel.convert") == "Convertir"


def test_set_language_persists_and_notifies():
    seen = []

    def listener(code):
        seen.append(code)

    i18n.add_listener(listener)
    try:
        i18n.set_language("es")
        i18n.set_language("en")
    finally:
        i18n.remove_listener(listener)
    assert seen == ["es", "en"]
    assert settings.get("language") == "en"
