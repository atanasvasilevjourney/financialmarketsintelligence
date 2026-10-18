from __future__ import annotations

from datetime import date

from brief.opex_calendar import opex_badge_for, third_friday


def test_third_friday_october_2026() -> None:
    assert third_friday(2026, 10) == date(2026, 10, 16)


def test_opex_badge_on_expiry_day() -> None:
    badge = opex_badge_for(date(2026, 10, 16))
    assert badge.show_opex_block
    assert badge.session_offset == 0
    assert "TODAY" in badge.badge


def test_opex_badge_t_minus_one() -> None:
    badge = opex_badge_for(date(2026, 10, 15))
    assert badge.show_opex_block
    assert badge.session_offset == -1
    assert "T-1" in badge.badge


def test_opex_badge_inactive_mid_month() -> None:
    badge = opex_badge_for(date(2026, 10, 1))
    assert not badge.show_opex_block
    assert badge.session_offset is None
