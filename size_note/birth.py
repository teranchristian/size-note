from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BirthParts:
    year: int
    month: int | None = None
    day: int | None = None

    @property
    def approximate(self) -> bool:
        return self.month is None or self.day is None

    def display(self) -> str:
        if self.month is None:
            return f"{self.year:04d}"
        if self.day is None:
            return f"{self.year:04d}-{self.month:02d}"
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"


def parse_birth(value: str, *, today: date | None = None) -> BirthParts:
    raw = value.strip()
    pieces = raw.split("-")
    if len(pieces) not in {1, 2, 3} or not all(piece.isdigit() for piece in pieces):
        raise ValueError("Birth must use YYYY, YYYY-MM, or YYYY-MM-DD.")

    if len(pieces[0]) != 4:
        raise ValueError("Birth year must use four digits, for example 2024.")
    if len(pieces) >= 2 and len(pieces[1]) != 2:
        raise ValueError("Birth month must use two digits, for example 2024-05.")
    if len(pieces) == 3 and len(pieces[2]) != 2:
        raise ValueError("Birth day must use two digits, for example 2024-05-12.")

    parts = BirthParts(
        year=int(pieces[0]),
        month=int(pieces[1]) if len(pieces) >= 2 else None,
        day=int(pieces[2]) if len(pieces) == 3 else None,
    )
    validate_birth_parts(parts.year, parts.month, parts.day, today=today)
    return parts


def validate_birth_parts(
    year: int | None,
    month: int | None,
    day: int | None,
    *,
    today: date | None = None,
) -> None:
    if year is None:
        if month is not None or day is not None:
            raise ValueError("Birth month or day cannot be stored without a birth year.")
        return
    if day is not None and month is None:
        raise ValueError("Birth day cannot be stored without a birth month.")

    current = today or date.today()
    if year < 1 or year > current.year:
        raise ValueError("Birth year cannot be in the future.")
    if month is not None and not 1 <= month <= 12:
        raise ValueError("Birth month must be between 1 and 12.")
    if month is not None and year == current.year and month > current.month:
        raise ValueError("Birth month cannot be in the future.")

    if day is not None:
        try:
            exact = date(year, month, day)
        except ValueError as exc:
            raise ValueError("Birth date is not a valid calendar date.") from exc
        if exact > current:
            raise ValueError("Birth date cannot be in the future.")


def birth_parts(
    year: int | None, month: int | None, day: int | None
) -> BirthParts | None:
    if year is None:
        return None
    return BirthParts(year=year, month=month, day=day)


def youngest_possible_age(
    year: int,
    month: int | None = None,
    day: int | None = None,
    *,
    today: date | None = None,
) -> int:
    current = today or date.today()
    validate_birth_parts(year, month, day, today=current)

    if month is None:
        # Keep the younger possible age through the entire unknown birth year.
        # The age advances on 1 January of the following year.
        return max(0, current.year - year - 1)

    if day is None:
        # Keep the younger possible age through the entire unknown birth month.
        # The age advances on the first day of the following month.
        age = current.year - year
        if current.month <= month:
            age -= 1
        return max(0, age)

    return _age_on(current, date(year, month, day))


def effective_growth_stage(
    fallback: str,
    year: int | None,
    month: int | None = None,
    day: int | None = None,
    *,
    today: date | None = None,
) -> str:
    if year is None:
        return fallback
    age = youngest_possible_age(year, month, day, today=today)
    return "adult" if age >= 18 else "child"


def review_interval_days(
    fallback_growth_stage: str,
    year: int | None,
    month: int | None,
    day: int | None,
    *,
    item_key: str,
    shoe_keys: set[str],
    today: date | None = None,
) -> int | None:
    stage = effective_growth_stage(
        fallback_growth_stage, year, month, day, today=today
    )
    if stage == "adult":
        return None

    if year is None:
        return 90 if item_key in shoe_keys else 180

    age = youngest_possible_age(year, month, day, today=today)
    if age < 3:
        return 90
    if age < 7:
        return 120
    if age < 13:
        return 180
    return 270


def _age_on(today: date, born: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
