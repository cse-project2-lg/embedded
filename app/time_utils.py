from datetime import datetime, timezone

import dateutil.parser


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_datetime(value: str | None) -> datetime:
    if not value:
        return now_utc()

    dt = dateutil.parser.isoparse(value)

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt