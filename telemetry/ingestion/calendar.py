from __future__ import annotations

COMMON_GRAND_PRIX_NAMES = [
    "Australian Grand Prix",
    "Bahrain Grand Prix",
    "Saudi Arabian Grand Prix",
    "Chinese Grand Prix",
    "Miami Grand Prix",
    "Emilia Romagna Grand Prix",
    "Monaco Grand Prix",
    "Spanish Grand Prix",
    "Canadian Grand Prix",
    "Austrian Grand Prix",
    "British Grand Prix",
    "Hungarian Grand Prix",
    "Belgian Grand Prix",
    "Dutch Grand Prix",
    "Italian Grand Prix",
    "Azerbaijan Grand Prix",
    "Singapore Grand Prix",
    "Japanese Grand Prix",
    "Qatar Grand Prix",
    "United States Grand Prix",
    "Mexico City Grand Prix",
    "Sao Paulo Grand Prix",
    "Las Vegas Grand Prix",
    "Abu Dhabi Grand Prix",
    "Portuguese Grand Prix",
    "French Grand Prix",
    "German Grand Prix",
    "Turkish Grand Prix",
    "Tuscan Grand Prix",
    "Eifel Grand Prix",
    "Styrian Grand Prix",
    "Sakhir Grand Prix",
    "70th Anniversary Grand Prix",
]


def preferred_grand_prix_index(options: list[str]) -> int:
    for preferred in ("Italian Grand Prix", "Monaco Grand Prix", "British Grand Prix"):
        if preferred in options:
            return options.index(preferred)
    return 0
