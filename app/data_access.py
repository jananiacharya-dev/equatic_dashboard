import re
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import bindparam, create_engine, text

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)

_RANGE_UNITS = {
    "h": timedelta(hours=1),
    "d": timedelta(days=1),
    "w": timedelta(weeks=1),
    "m": timedelta(days=30),  # calendar months aren't fixed-length; 30d is close enough for a chart range picker
}
_RANGE_RE = re.compile(r"(\d+)([hdwm])")


def parse_range(range_str):
    match = _RANGE_RE.fullmatch(range_str)
    if not match:
        raise ValueError(f"unrecognized range: {range_str!r}")
    qty, unit = match.groups()
    end = datetime(2026, 8, 6, tzinfo=timezone.utc)  # TODO: frozen "now" for demo; revert to datetime.now(timezone.utc)
    start = end - int(qty) * _RANGE_UNITS[unit]
    return start, end


def _to_df(result):
    return pd.DataFrame(result.fetchall(), columns=list(result.keys()))


def count_tags():
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM sensor_inventory")).scalar_one()


def get_page_tags(page):
    sql = text("""
        SELECT tag_id, source_tag_id, instrument_type, measurement, units,
               range_min, range_max, subsystem, stack_group, stack_id,
               cell_number, signal_class, data_source, display_page, display_group
        FROM sensor_inventory
        WHERE display_page = :page
        ORDER BY display_group
    """)
    with engine.connect() as conn:
        return _to_df(conn.execute(sql, {"page": page}))


def get_readings(tag_ids, start, end):
    sql = text("""
        SELECT r.tag_id, i.measurement, i.units, i.display_group,
               r.ts_utc, r.value_avg, r.value_min, r.value_max, r.quality
        FROM sensor_readings r
        JOIN sensor_inventory i ON i.tag_id = r.tag_id
        WHERE r.tag_id IN :tag_ids
          AND r.ts_utc BETWEEN :start AND :end
        ORDER BY r.tag_id, r.ts_utc
    """).bindparams(bindparam("tag_ids", expanding=True))
    with engine.connect() as conn:
        return _to_df(conn.execute(sql, {"tag_ids": list(tag_ids), "start": start, "end": end}))


def get_metric_series(metric_id, start, end, resolution="daily"):
    sql = text("""
        SELECT ts_utc, value
        FROM metric_values
        WHERE metric_id = :metric_id
          AND resolution = :resolution
          AND ts_utc BETWEEN :start AND :end
        ORDER BY ts_utc
    """)
    with engine.connect() as conn:
        return _to_df(conn.execute(
            sql, {"metric_id": metric_id, "resolution": resolution, "start": start, "end": end}
        ))


def get_latest_metrics():
    sql = text("""
        SELECT DISTINCT ON (mv.metric_id)
               mv.metric_id, mr.name, mr.units, mv.ts_utc, mv.value
        FROM metric_values mv
        JOIN metric_registry mr ON mr.metric_id = mv.metric_id
        WHERE mr.level IN ('1', 'both')
        ORDER BY mv.metric_id, mv.ts_utc DESC
    """)
    with engine.connect() as conn:
        return _to_df(conn.execute(sql))


def get_annotations(start, end):
    sql = text("""
        SELECT annotation_id, ts_utc, event_type, description, test_run_id, created_by
        FROM annotations
        WHERE ts_utc BETWEEN :start AND :end
        ORDER BY ts_utc
    """)
    with engine.connect() as conn:
        return _to_df(conn.execute(sql, {"start": start, "end": end}))
