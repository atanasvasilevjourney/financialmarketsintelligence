"""Monthly index OpEx calendar (SPX/SPY-style third Friday heuristic).

Uses NYSE weekday math only (no holiday calendar). Documented limitation: if the
third Friday is a full NYSE holiday, real expiry may shift — badge may be off by
one session until a live exchange calendar adapter lands (Phase 3).
"""

from __future__ import annotations

from datetime import date, timedelta

from brief.models import OpexBadge


def third_friday(year: int, month: int) -> date:
    """Return the third Friday of ``month`` in ``year``."""
    d = date(year, month, 1)
    # weekday(): Mon=0 … Fri=4
    days_until_friday = (4 - d.weekday()) % 7
    first_friday = d + timedelta(days=days_until_friday)
    return first_friday + timedelta(days=14)


def _prev_nyse_session(d: date, n: int = 1) -> date:
    cur = d
    for _ in range(n):
        cur -= timedelta(days=1)
        while cur.weekday() >= 5:
            cur -= timedelta(days=1)
    return cur


def _next_nyse_session(d: date, n: int = 1) -> date:
    cur = d
    for _ in range(n):
        cur += timedelta(days=1)
        while cur.weekday() >= 5:
            cur += timedelta(days=1)
    return cur


def opex_badge_for(trading_date: date) -> OpexBadge:
    """Badge for monthly index OpEx relative to ``trading_date`` (America/New_York date)."""
    opex = third_friday(trading_date.year, trading_date.month)
    if trading_date > opex:
        # Next month OpEx for forward context when past this month's expiry
        if trading_date.month == 12:
            opex = third_friday(trading_date.year + 1, 1)
        else:
            opex = third_friday(trading_date.year, trading_date.month + 1)

    t_minus_1 = _prev_nyse_session(opex, 1)
    t_plus_1 = _next_nyse_session(opex, 1)

    badge = ""
    session_offset: int | None = None
    show_block = False

    if trading_date == opex:
        badge = "INDEX OpEx TODAY"
        session_offset = 0
        show_block = True
    elif trading_date == t_minus_1:
        badge = "INDEX OpEx T-1"
        session_offset = -1
        show_block = True
    elif trading_date == t_plus_1:
        badge = "INDEX OpEx T+1"
        session_offset = 1
        show_block = True
    else:
        delta = (opex - trading_date).days
        if 0 < delta <= 7:
            badge = f"INDEX OpEx in {delta}d ({opex.isoformat()})"
        elif -7 <= delta < 0:
            badge = f"INDEX OpEx {abs(delta)}d ago"

    return OpexBadge(
        monthly_opex_date=opex.isoformat(),
        badge=badge,
        session_offset=session_offset,
        show_opex_block=show_block,
        rule="spx_monthly_third_friday_nyse_weekdays",
    )
