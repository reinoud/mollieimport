import datetime
from main import next_same_day_in_year


def test_next_same_day_in_year_future_same_year():
    # orig date June 15; from_date is earlier in same year
    orig = datetime.date(2020, 6, 15)
    from_date = datetime.date(2026, 1, 10)
    res = next_same_day_in_year(orig, from_date)
    assert res == datetime.date(2026, 6, 15)


def test_next_same_day_in_year_passed_this_year():
    # orig date Jan 6; from_date after Jan 6 -> next year
    orig = datetime.date(2021, 1, 6)
    from_date = datetime.date(2026, 1, 19)
    res = next_same_day_in_year(orig, from_date)
    assert res == datetime.date(2027, 1, 6)


def test_next_same_day_feb29_fallback():
    orig = datetime.date(2020, 2, 29)
    from_date = datetime.date(2021, 1, 1)
    res = next_same_day_in_year(orig, from_date)
    # 2021 isn't leap year; fallback to Mar 1
    assert res == datetime.date(2021, 3, 1)

