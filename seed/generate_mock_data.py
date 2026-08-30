"""Generate mock time-series data for every tag in sensor_inventory.

Reads metadata from the DB and routes by signal_class:
  analog           -> sensor_readings (1-min avg/min/max)
  discrete         -> state_events (occasional HIGH/LOW flips)
  control_feedback -> nothing (EPC trending unconfirmed)

Also writes daily metric_values (CDR, uptime, CE) and a few annotations.

Usage:
    python generate_mock_data.py --hours 48        # default
    python generate_mock_data.py --hours 168       # a full week (slower)
"""

import argparse
import math
import os
import random
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

STEP_MIN = 1  # matches the plant's 1-minute sync aggregation
ACTIVE_AREA_CM2 = 1500.0  # PROVISIONAL — placeholder, confirm real value (electrode active area per stack group, cm^2)
UPTIME_CURRENT_THRESHOLD_A = 50.0  # PROVISIONAL — confirm real cutoff


def is_group_up(amps):
    """Only place the up/down definition lives — storage and the panel just consume it."""
    return amps > UPTIME_CURRENT_THRESHOLD_A


def _is_down(group, t_minutes, downtime):
    """Whether the group is in one of its randomly-scheduled outage windows at this minute."""
    if not downtime:
        return False
    return any(start <= t_minutes < end for start, end in downtime.get(group, []))


def build_downtime_windows(rng, n_steps, groups):
    """1-2 random outage windows per group (30-180 min each) over the generation period."""
    windows = {}
    for group in groups:
        group_windows = []
        for _ in range(int(rng.integers(1, 3))):
            dur = int(rng.integers(30, 181))
            start = int(rng.integers(0, max(n_steps - dur, 1)))
            group_windows.append((start, start + dur))
        windows[group] = group_windows
    return windows


def profile(row, t_minutes, rng, downtime=None):
    """A plausible value for this tag at this time: baseline + daily wave + noise."""
    lo, hi = row.range_min, row.range_max
    mid = (lo + hi) / 2
    span = (hi - lo)
    daily = math.sin(2 * math.pi * (t_minutes % 1440) / 1440)

    if row.instrument_type == "V":        # cell voltage: tight band, slow drift
        base = 2.05 if row.cell_number else 140.0
        drift = 0.00005 * t_minutes if row.cell_number else 0.002 * t_minutes
        noise = rng.normal(0, 0.01 if row.cell_number else 0.5)
        return base + drift + noise
    if row.instrument_type == "I":        # stack group current: steady while operating, ~0 during downtime
        if _is_down(row.stack_group, t_minutes, downtime):
            return max(0.0, rng.normal(0, 5))
        return 3200.0 + rng.normal(0, 80)
    if row.instrument_type == "PT":
        return mid + 0.05 * span * daily + rng.normal(0, 0.02 * span)
    if row.instrument_type == "TT":
        return mid + 0.15 * span * daily + rng.normal(0, 0.02 * span)
    if row.instrument_type == "FM":
        return mid + 0.10 * span * daily + rng.normal(0, 0.03 * span)
    if row.instrument_type == "pHT":
        return mid + 0.2 * daily + rng.normal(0, 0.05)
    return mid + rng.normal(0, 0.05 * span)


def current_density_and_uptime_rows(readings):
    """readings: iterable of (stack_group, ts, amps). Returns metric_values rows for
    current_density and uptime (raw + daily) — used both by a live generation run and
    by the fast recompute path, so the two never drift out of sync."""
    mv = [
        dict(metric_id="current_density", ts_utc=ts,
             value=round(amps / ACTIVE_AREA_CM2, 4), resolution="raw", stack_group=group)
        for group, ts, amps in readings
    ]
    mv += [
        dict(metric_id="uptime", ts_utc=ts,
             value=100.0 if is_group_up(amps) else 0.0, resolution="raw", stack_group=group)
        for group, ts, amps in readings
    ]
    daily_uptime = {}
    for group, ts, amps in readings:
        daily_uptime.setdefault((group, ts.replace(hour=0, minute=0)), []).append(
            100.0 if is_group_up(amps) else 0.0)
    mv += [
        dict(metric_id="uptime", ts_utc=ts, value=round(float(np.mean(vs)), 1),
             resolution="daily", stack_group=group)
        for (group, ts), vs in daily_uptime.items()
    ]
    return mv


def recompute_current_metrics(engine):
    """Re-derive current_density/uptime for every I-type reading already in
    sensor_readings, without regenerating sensor_readings itself. Much faster than a
    full reseed, and also backfills uptime for older readings written before that
    metric existed, keeping the two consistent with each other."""
    df = pd.read_sql(text("""
        SELECT i.stack_group, r.ts_utc, r.value_avg
        FROM sensor_readings r
        JOIN sensor_inventory i ON i.tag_id = r.tag_id
        WHERE i.instrument_type = 'I'
        ORDER BY r.ts_utc
    """), engine)
    print(f"{len(df)} existing I-type readings found")

    mv = current_density_and_uptime_rows(list(zip(df.stack_group, df.ts_utc, df.value_avg)))
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO metric_values (metric_id, ts_utc, value, resolution, stack_group) "
            "VALUES (:metric_id, :ts_utc, :value, :resolution, :stack_group) "
            "ON CONFLICT (metric_id, ts_utc, resolution, stack_group) "
            "DO UPDATE SET value = EXCLUDED.value"), mv)
    print(f"{len(mv)} metric_values recomputed (current_density + uptime, raw + daily)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--batch", type=int, default=50_000)
    ap.add_argument("--recompute-current-metrics", action="store_true",
                     help="Skip regenerating sensor_readings; just recompute "
                          "current_density/uptime from existing I-type readings (fast).")
    args = ap.parse_args()

    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://equatic:equatic_dev@localhost:5432/plant_dashboard")
    engine = create_engine(url)

    if args.recompute_current_metrics:
        recompute_current_metrics(engine)
        return

    rng = np.random.default_rng(42)

    inv = pd.read_sql("SELECT * FROM sensor_inventory", engine)
    analog = inv[inv.signal_class == "analog"]
    discrete = inv[inv.signal_class == "discrete"]
    print(f"{len(analog)} analog tags, {len(discrete)} discrete tags, "
          f"{args.hours}h at {STEP_MIN}-min steps")

    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = end - timedelta(hours=args.hours)
    n_steps = args.hours * 60 // STEP_MIN

    current_groups = analog.loc[analog.instrument_type == "I", "stack_group"].unique()
    downtime = build_downtime_windows(rng, n_steps, current_groups)
    for group, windows in downtime.items():
        print(f"  {group} current downtime: {windows} (minutes from start)")

    # --- analog -> sensor_readings, batched inserts ---
    buf = []
    total = 0
    current_readings = []  # (stack_group, ts, amps) for I-type tags, used below to derive current_density
    with engine.begin() as conn:
        for _, row in analog.iterrows():
            for s in range(n_steps):
                ts = start + timedelta(minutes=s * STEP_MIN)
                v = profile(row, s * STEP_MIN, rng, downtime)
                if row.instrument_type == "I":
                    current_readings.append((row.stack_group, ts, v))
                jitter = abs(rng.normal(0, 0.3))
                buf.append(dict(tag_id=row.tag_id, ts_utc=ts,
                                value_avg=round(v, 4),
                                value_min=round(v - jitter, 4),
                                value_max=round(v + jitter, 4),
                                quality="good"))
                if len(buf) >= args.batch:
                    conn.execute(text(
                        "INSERT INTO sensor_readings VALUES "
                        "(:tag_id, :ts_utc, :value_avg, :value_min, :value_max, :quality) "
                        "ON CONFLICT DO NOTHING"), buf)
                    total += len(buf)
                    buf = []
                    print(f"  {total:,} readings...", end="\r")
        if buf:
            conn.execute(text(
                "INSERT INTO sensor_readings VALUES "
                "(:tag_id, :ts_utc, :value_avg, :value_min, :value_max, :quality) "
                "ON CONFLICT DO NOTHING"), buf)
            total += len(buf)
    print(f"\n{total:,} sensor_readings written")

    # --- discrete -> state_events: mostly OK, occasional HIGH excursions ---
    events = []
    for _, row in discrete.iterrows():
        t = start
        state = "OK"
        while t < end:
            t += timedelta(minutes=int(rng.integers(120, 600)))
            state = "HIGH" if state == "OK" else "OK"
            if t < end:
                events.append(dict(tag_id=row.tag_id, ts_utc=t, state=state))
    with engine.begin() as conn:
        if events:
            conn.execute(text(
                "INSERT INTO state_events VALUES (:tag_id, :ts_utc, :state) "
                "ON CONFLICT DO NOTHING"), events)
    print(f"{len(events)} state_events written")

    # --- daily metric_values (gcdr_day, uptime) ---
    mv = []
    days = max(args.hours // 24, 1)
    for d in range(days):
        ts = (start + timedelta(days=d)).replace(hour=0, minute=0)
        mv.append(
            dict(metric_id="gcdr_day", ts_utc=ts,
                 value=round(rng.normal(950, 60), 1), resolution="daily", stack_group=""))
        # PROVISIONAL — plant-wide uptime is still random mock, unrelated to the
        # real per-group current-threshold computation below; no defined formula yet
        # for how per-group uptime should roll up to a system-wide figure.
        mv.append(
            dict(metric_id="uptime", ts_utc=ts,
                 value=round(float(np.clip(rng.normal(88, 6), 60, 100)), 1),
                 resolution="daily", stack_group=""))

    # --- current_density + uptime, derived from the I-type readings captured above ---
    mv += current_density_and_uptime_rows(current_readings)

    # --- ce at raw (1-min) resolution, mean-reverting drift + rare excursions,
    # rolled up into hourly/daily so short and long range pickers both have data ---
    raw_ce = []
    level = 72.0
    for s in range(n_steps):
        ts = start + timedelta(minutes=s * STEP_MIN)
        level = float(np.clip(level + rng.normal(0, 0.15), 65, 78))
        v = level + rng.normal(0, 1.2)
        if rng.random() < 0.01:
            v += rng.choice([-1, 1]) * rng.uniform(8, 16)
        raw_ce.append((ts, round(float(np.clip(v, 40, 95)), 2)))

    mv += [dict(metric_id="ce", ts_utc=ts, value=v, resolution="raw", stack_group="") for ts, v in raw_ce]

    hourly_ce, daily_ce = {}, {}
    for ts, v in raw_ce:
        hourly_ce.setdefault(ts.replace(minute=0), []).append(v)
        daily_ce.setdefault(ts.replace(hour=0, minute=0), []).append(v)
    mv += [dict(metric_id="ce", ts_utc=ts, value=round(float(np.mean(vs)), 2), resolution="hourly", stack_group="")
           for ts, vs in hourly_ce.items()]
    mv += [dict(metric_id="ce", ts_utc=ts, value=round(float(np.mean(vs)), 2), resolution="daily", stack_group="")
           for ts, vs in daily_ce.items()]

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO metric_values (metric_id, ts_utc, value, resolution, stack_group) "
            "VALUES (:metric_id, :ts_utc, :value, :resolution, :stack_group) "
            "ON CONFLICT DO NOTHING"), mv)
    print(f"{len(mv)} metric_values written")

    # --- seed users + a few annotations ---
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (name, email, role, password_hash) VALUES "
            "('Admin User', 'admin@example.com', 'admin', 'dev-only-not-a-hash'), "
            "('Operator User', 'operator@example.com', 'operator', 'dev-only-not-a-hash') "
            "ON CONFLICT (email) DO NOTHING"))
        # annotations has no natural unique key to ON CONFLICT on, so guard
        # in Python: only seed the demo rows once, otherwise reruns pile up
        # duplicates anchored to whatever "now" happened to be each time.
        if conn.execute(text("SELECT COUNT(*) FROM annotations")).scalar_one() == 0:
            conn.execute(text(
                "INSERT INTO annotations (ts_utc, event_type, description, created_by) VALUES "
                "(:t1, 'flush', 'Acid flush SG-2', 1), "
                "(:t2, 'outage', 'Grid power dip, 4 min', 1), "
                "(:t3, 'config_change', 'Catholyte flow setpoint +5%', 1)"),
                dict(t1=start + timedelta(hours=6),
                     t2=start + timedelta(hours=20),
                     t3=start + timedelta(hours=30)))
    print("Users and annotations seeded. Done.")


if __name__ == "__main__":
    main()
