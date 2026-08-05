"""Seed sensor_inventory and metric_registry for the Singapore plant.

Every tag is generated from the plant's structure (4 groups x 6 stacks x 52 cells),
never typed by hand. Change the constants, rerun, and the inventory follows.

Usage:
    python seed_metadata.py            # seeds the database
    python seed_metadata.py --dry-run  # prints counts only, no DB needed
"""

import argparse
import os

STACK_GROUPS = ["SG-1", "SG-2", "SG-3", "SG-4"]
STACKS_PER_GROUP = 6
CELLS_PER_STACK = 52

# 18 total, 001 & 020 are intake.
PHT_INTAKE = ["pHT-001", "pHT-020"]
PHT_EFFLUENT = [f"pHT-{n:03d}" for n in
                [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]]

LS_TAGS = [f"LS-{n:03d}" for n in [1, 2, 3, 4, 5, 6, 7, 8]]

EPC_PER_STACK = 3  # 72 total = 3 x 24 stacks (EPC/PRLV/BPRV family)


def stack_ids():
    """ES-01..ES-24 with their group: SG-1 owns ES-01..06, SG-2 owns ES-07..12, ..."""
    out = []
    n = 0
    for group in STACK_GROUPS:
        for _ in range(STACKS_PER_GROUP):
            n += 1
            out.append((group, f"ES-{n:02d}"))
    return out


def build_inventory():
    rows = []

    def add(tag_id, itype, meas, units, rmin, rmax, subsystem,
            group=None, stack=None, cell=None, sclass="analog",
            source="wincc", page=None, dgroup=None):
        rows.append(dict(
            tag_id=tag_id, source_tag_id=None, instrument_type=itype,
            measurement=meas, units=units, range_min=rmin, range_max=rmax,
            subsystem=subsystem, stack_group=group, stack_id=stack,
            cell_number=cell, signal_class=sclass, data_source=source,
            display_page=page, display_group=dgroup,
        ))

    # --- C2C voltage: 24 stacks x 52 cells = 1,248 (electrical system, not P&ID) ---
    for group, stack in stack_ids():
        for cell in range(1, CELLS_PER_STACK + 1):
            add(f"V-{stack}-C{cell:02d}", "V", "cell_voltage", "V", 1.5, 3.5,
                "electrolyzer", group, stack, cell,
                source="windaq", page="voltage", dgroup=f"c2c_{stack}")

    # --- B2B voltage: 1 per stack group = 4 ---
    for group in STACK_GROUPS:
        add(f"V-B2B-{group}", "V", "bus_to_bus_voltage", "V", 80, 200,
            "electrolyzer", group,
            source="windaq", page="voltage", dgroup=f"b2b_{group}")

    # --- Stack process tags: 4 PT + 2 TT + 2 FM per stack ---
    pt_roles = ["anode_inlet_pressure", "anode_outlet_pressure",
                "cathode_inlet_pressure", "cathode_outlet_pressure"]
    tt_roles = ["anode_outlet_temperature", "cathode_outlet_temperature"]
    fm_roles = ["anolyte_feed_flow", "catholyte_feed_flow"]

    for group, stack in stack_ids():
        for i, role in enumerate(pt_roles, 1):
            add(f"PT-{stack}-{i:02d}", "PT", role, "bar", 0, 6,
                "electrolyzer", group, stack, page="process", dgroup=f"pressure_{group}")
        for i, role in enumerate(tt_roles, 1):
            add(f"TT-{stack}-{i:02d}", "TT", role, "degC", 10, 60,
                "electrolyzer", group, stack, page="process", dgroup=f"temperature_{group}")
        for i, role in enumerate(fm_roles, 1):
            add(f"FM-{stack}-{i:02d}", "FM", role, "L/min", 0, 120,
                "electrolyzer", group, stack, page="process", dgroup=f"flow_{group}")

    # --- Intake: 5 PT, 2 TT, FM-012 (catholyte recycle), pHT 001 & 020 ---
    for i in range(1, 6):
        add(f"PT-IN-{i:02d}", "PT", "intake_pressure", "bar", 0, 6,
            "intake", page="process", dgroup="intake")
    for i in range(1, 3):
        add(f"TT-IN-{i:02d}", "TT", "intake_temperature", "degC", 5, 45,
            "intake", page="process", dgroup="intake")
    add("FM-012", "FM", "catholyte_recycle_flow", "m3/hr", 0, 150,
        "intake", page="process", dgroup="intake")
    for tag in PHT_INTAKE:
        add(tag, "pHT", "intake_ph", "pH", 6.0, 9.0,
            "intake", page="effluent", dgroup="intake_ph")

    # --- Main header: FM-007 ---
    add("FM-007", "FM", "main_header_flow", "m3/hr", 0, 150,
        "main_header", page="overview", dgroup="system")

    # --- Effluent pHT: 16 ---
    for tag in PHT_EFFLUENT:
        add(tag, "pHT", "effluent_ph", "pH", 5.5, 9.5,
            "effluent", page="effluent", dgroup="effluent_ph")

    # --- Level switches: 8, discrete -> state_events ---
    for tag in LS_TAGS:
        add(tag, "LS", "separator_level", None, None, None,
            "drainage", sclass="discrete", page="overview", dgroup="alarms")

    # --- EPC family: 72, control feedback; hidden until PV trending confirmed ---
    for group, stack in stack_ids():
        for i in range(1, EPC_PER_STACK + 1):
            add(f"EPC-{stack}-{i:02d}", "EPC", "regulated_pressure", "bar", 0, 8,
                "pressure_control", group, stack,
                sclass="control_feedback", page=None, dgroup=None)

    return rows


METRICS = [
    dict(metric_id="ce", name="CE", formula_ref="pending: Babette", units="%",
         display_page="overview", level="both"),
    dict(metric_id="cler", name="CLER", formula_ref="pending: Babette", units="%",
         display_page="process", level="2"),
    dict(metric_id="gcdr_day", name="gCDR_day", formula_ref="pending: Babette",
         units="kg CO2/day", display_page="carbonation", level="both"),
    dict(metric_id="uptime", name="uptime", formula_ref="pending: definition",
         units="%", display_page="overview", level="both"),
    dict(metric_id="dv_dt", name="dV_dT", formula_ref="LA acid flush analysis",
         units="mV/hr", display_page="process", level="2"),
    dict(metric_id="current_density", name="current_density",
         formula_ref="I / active area", units="A/m2",
         display_page="process", level="2"),
]


def summarize(rows):
    from collections import Counter
    by_type = Counter(r["instrument_type"] for r in rows)
    by_sub = Counter(r["subsystem"] for r in rows)
    print(f"Total tags: {len(rows)}")
    print("By instrument type:", dict(by_type))
    print("By subsystem:", dict(by_sub))
    print(f"Metrics: {len(METRICS)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = build_inventory()
    summarize(rows)

    if args.dry_run:
        return

    from sqlalchemy import create_engine, text
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://equatic:equatic_dev@localhost:5432/plant_dashboard")
    engine = create_engine(url)

    ins_inv = text("""
        INSERT INTO sensor_inventory VALUES
        (:tag_id, :source_tag_id, :instrument_type, :measurement, :units,
         :range_min, :range_max, :subsystem, :stack_group, :stack_id,
         :cell_number, :signal_class, :data_source, :display_page, :display_group)
        ON CONFLICT (tag_id) DO NOTHING""")
    ins_met = text("""
        INSERT INTO metric_registry VALUES
        (:metric_id, :name, :formula_ref, :units, :display_page, :level)
        ON CONFLICT (metric_id) DO NOTHING""")

    with engine.begin() as conn:
        conn.execute(ins_inv, rows)
        conn.execute(ins_met, METRICS)
    print("Seeded.")


if __name__ == "__main__":
    main()
