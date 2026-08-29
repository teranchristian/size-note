import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def clean_text(value: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())


def normalize(value: str | None) -> str:
    if not value:
        return ""
    return clean_text(value).casefold()


def optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_text(value)
    return cleaned or None
