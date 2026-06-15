from datetime import datetime, timezone, timedelta
import pytz

MSK = pytz.timezone("Europe/Moscow")

_MONTHS_GEN = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
_MONTHS_SHORT = [
    "", "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]


def utc_to_msk(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MSK)


def fmt_msk(dt: datetime) -> str:
    """Returns '11 июня, 22:00 МСК'"""
    msk = utc_to_msk(dt)
    return f"{msk.day} {_MONTHS_GEN[msk.month]}, {msk.strftime('%H:%M')} МСК"


def fmt_date_msk(dt: datetime) -> str:
    """Returns '11 июня'"""
    msk = utc_to_msk(dt)
    return f"{msk.day} {_MONTHS_GEN[msk.month]}"


def fmt_time(dt: datetime, reference_msk_date=None) -> str:
    """Returns '22:00' if same MSK day as reference, else '22:00 (12 июн)'"""
    msk = utc_to_msk(dt)
    time_str = msk.strftime("%H:%M")
    if reference_msk_date and msk.date() == reference_msk_date:
        return time_str
    return f"{time_str} ({msk.day} {_MONTHS_SHORT[msk.month]})"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_match_window() -> tuple[str, str]:
    """(start_iso, end_iso) covering from now until end of tomorrow in MSK."""
    now = now_utc()
    now_msk = utc_to_msk(now)
    tomorrow = now_msk.date() + timedelta(days=1)
    end_msk = MSK.localize(datetime(tomorrow.year, tomorrow.month, tomorrow.day, 23, 59, 59))
    return now.isoformat(), end_msk.astimezone(timezone.utc).isoformat()
