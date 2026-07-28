import re

_WHITESPACE_RE = re.compile(r"\s+")

ROUTE_ALIASES = {
    "po": "oral",
}

FREQUENCY_ALIASES = {
    "qd": "daily",
}


def _basic_normalize(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = _WHITESPACE_RE.sub(" ", value.strip().lower())

    return normalized or None


def normalize_medication_name(name: str | None) -> str | None:
    normalized = _basic_normalize(name)

    if normalized is None:
        return None

    return normalized.rstrip(".")


def normalize_dose(value: str | None) -> str | None:
    return _basic_normalize(value)


def normalize_route(value: str | None) -> str | None:
    normalized = _basic_normalize(value)

    if normalized is None:
        return None

    return ROUTE_ALIASES.get(normalized, normalized)


def normalize_frequency(value: str | None) -> str | None:
    normalized = _basic_normalize(value)

    if normalized is None:
        return None

    return FREQUENCY_ALIASES.get(normalized, normalized)


def normalize_status(value: str | None) -> str | None:
    return _basic_normalize(value)
