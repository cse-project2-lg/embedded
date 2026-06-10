from datetime import datetime, timezone

import dateutil.parser


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_datetime(value: str | None) -> datetime:
    if not value:
        raise ValueError("Timestamp is missing or empty. Cannot substitute current time for sensor data.")

    dt = dateutil.parser.isoparse(value)

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt