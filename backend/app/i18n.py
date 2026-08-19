"""Notification text translations.

The language is a static deployment setting (``Settings.language``, defaulting
to "en"): the household's phone(s) always receive push notifications through
Home Assistant, so there is no per-request signal to detect a phone's locale
server-side, and the plan explicitly doesn't need dynamic switching.
"""

from typing import Final

from app.languages import DEFAULT_LANGUAGE

_TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "plant_title": "{nickname} needs water",
        "plant_message": "{nickname} is overdue for watering.",
        "room_title": "{room_name}: {count} plants need water",
        "room_message": "{room_name} has {count} plants overdue for watering.",
        "action_watered": "Watered",
        "action_snooze_1d": "Snooze 1 day",
        "action_away_3d": "Away 3 days",
        "action_water_all": "Water all",
    },
    "hu": {
        "plant_title": "{nickname}: locsolásra van szükség",
        "plant_message": "{nickname}: elkésett a locsolás.",
        "room_title": "{room_name}: {count} növényt meg kell locsolni",
        "room_message": "{room_name}: {count} növény locsolása késésben van.",
        "action_watered": "Megöntözve",
        "action_snooze_1d": "Elhalasztás 1 napra",
        "action_away_3d": "Távol 3 napig",
        "action_water_all": "Mindet megöntözöm",
    },
}

def translate(key: str, language: str = DEFAULT_LANGUAGE, **kwargs: object) -> str:
    """Looks up ``key`` in ``language``'s catalog, falling back to English for
    an unknown language or a missing key (so a typo/partial catalog never
    crashes the notification tick)."""
    catalog = _TRANSLATIONS.get(language, _TRANSLATIONS[DEFAULT_LANGUAGE])
    template = catalog.get(key, _TRANSLATIONS[DEFAULT_LANGUAGE][key])
    return template.format(**kwargs)
