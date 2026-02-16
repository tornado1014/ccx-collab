"""Internationalization support for the web dashboard."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "ko")

# In-memory translation cache
_translations: Dict[str, Dict[str, str]] = {}


def _load_translations(locale: str) -> Dict[str, str]:
    """Load translations for a locale from JSON file."""
    if locale in _translations:
        return _translations[locale]

    locale_file = LOCALES_DIR / locale / "messages.json"
    if locale_file.is_file():
        try:
            data = json.loads(locale_file.read_text(encoding="utf-8"))
            _translations[locale] = data
            logger.debug("Loaded %d translations for locale '%s'", len(data), locale)
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load translations for '%s': %s", locale, exc)

    _translations[locale] = {}
    return {}


def get_text(key: str, locale: str = DEFAULT_LOCALE) -> str:
    """Get translated text for a key. Falls back to English, then the key itself."""
    translations = _load_translations(locale)
    if key in translations:
        return translations[key]

    # Fallback to English
    if locale != DEFAULT_LOCALE:
        en_translations = _load_translations(DEFAULT_LOCALE)
        if key in en_translations:
            return en_translations[key]

    return key


def get_locale_from_request(request) -> str:
    """Determine locale from request query param or cookie."""
    # Check query parameter first
    lang = request.query_params.get("lang", "")
    if lang in SUPPORTED_LOCALES:
        return lang

    # Check cookie
    lang = request.cookies.get("lang", "")
    if lang in SUPPORTED_LOCALES:
        return lang

    return DEFAULT_LOCALE


def setup_jinja2_i18n(templates) -> None:
    """Add translation function to Jinja2 environment globals."""
    if templates is None:
        return

    templates.env.globals["_"] = get_text
    templates.env.globals["supported_locales"] = SUPPORTED_LOCALES
    logger.debug("i18n Jinja2 globals registered")
