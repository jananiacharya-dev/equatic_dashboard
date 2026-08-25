from datetime import datetime, timezone

import pandas as pd
from flask import jsonify, redirect, render_template, request, url_for

from app import app
from app.data_access import (
    add_annotation,
    get_annotations,
    get_b2b_tags,
    get_c2c_tags,
    get_cell_series,
    get_latest_metrics,
    get_metric_series,
    parse_range,
    resolution_for_range,
)

ANNOTATION_EVENT_TYPES = ["flush", "outage", "config_change", "note"]

PAGES = ["overview", "voltage", "process", "effluent", "carbonation"]
RANGE_PRESETS = ["1h", "24h", "48h", "1w", "1m", "3m", "6m"]
DEFAULT_RANGE = "24h"
STACK_GROUPS = ["SG-1", "SG-2", "SG-3", "SG-4"]


@app.route("/")
def index():
    return redirect(url_for("overview"))


@app.route("/overview")
def overview():
    range_str = request.args.get("range", DEFAULT_RANGE)
    offset = max(0, request.args.get("offset", 0, type=int))
    start, end = parse_range(range_str, offset=offset)

    metrics = get_latest_metrics().to_dict("records")
    ce_meta = next((m for m in metrics if m["metric_id"] == "ce"), None)
    ce_name = ce_meta["name"] if ce_meta else "ce"
    ce_units = ce_meta["units"] if ce_meta else ""

    ce_series = get_metric_series("ce", start, end, resolution=resolution_for_range(range_str))
    ce_x = [ts.isoformat() for ts in ce_series["ts_utc"]]
    ce_y = ce_series["value"].tolist()

    annotations = [
        {
            "annotation_id": row["annotation_id"],
            "ts_iso": row["ts_utc"].isoformat(),
            "ts_display": row["ts_utc"].strftime("%Y-%m-%d %H:%M UTC"),
            "event_type": row["event_type"],
            "description": row["description"],
        }
        for row in get_annotations(start, end).to_dict("records")
    ]

    return render_template(
        "overview.html",
        pages=PAGES,
        range_presets=RANGE_PRESETS,
        current_page="overview",
        current_range=range_str,
        current_offset=offset,
        window_display=f"{start.strftime('%Y-%m-%d %H:%M')} – {end.strftime('%Y-%m-%d %H:%M')} UTC",
        metrics=metrics,
        ce_name=ce_name,
        ce_units=ce_units,
        ce_x=ce_x,
        ce_y=ce_y,
        ce_range=[start.isoformat(), end.isoformat()],
        annotations=annotations,
        event_types=ANNOTATION_EVENT_TYPES,
    )


@app.route("/voltage")
def voltage():
    range_str = request.args.get("range", DEFAULT_RANGE)
    offset = max(0, request.args.get("offset", 0, type=int))
    start, end = parse_range(range_str, offset=offset)

    tree = {}
    for row in get_c2c_tags().to_dict("records"):
        tree.setdefault(row["stack_group"], {}) \
            .setdefault(row["stack_id"], []) \
            .append({"cell_number": row["cell_number"], "tag_id": row["tag_id"]})

    b2b_tags = []
    for group in STACK_GROUPS:
        df = get_b2b_tags(group)
        if not df.empty:
            b2b_tags.append({"group": group, "tag_id": df.iloc[0]["tag_id"]})

    return render_template(
        "voltage.html",
        pages=PAGES,
        range_presets=RANGE_PRESETS,
        current_page="voltage",
        current_range=range_str,
        current_offset=offset,
        window_display=f"{start.strftime('%Y-%m-%d %H:%M')} – {end.strftime('%Y-%m-%d %H:%M')} UTC",
        chart_range=[start.isoformat(), end.isoformat()],
        tree=tree,
        b2b_tags=b2b_tags,
    )


@app.route("/voltage/series")
def voltage_series():
    tag_ids = request.args.getlist("tag_ids")
    range_str = request.args.get("range", DEFAULT_RANGE)
    offset = max(0, request.args.get("offset", 0, type=int))

    if not tag_ids:
        return jsonify(series=[])

    start, end = parse_range(range_str, offset=offset)
    df = get_cell_series(tag_ids, start, end)

    series = []
    for tag_id, group in df.groupby("tag_id", sort=False):
        stack_id = group["stack_id"].iloc[0]
        cell_number = group["cell_number"].iloc[0]
        series.append({
            "tag_id": tag_id,
            "stack_group": group["stack_group"].iloc[0],
            "stack_id": None if pd.isna(stack_id) else stack_id,
            "cell_number": None if pd.isna(cell_number) else int(cell_number),
            "x": [ts.isoformat() for ts in group["ts_utc"]],
            "y": group["value_avg"].tolist(),
        })
    return jsonify(series=series)


@app.route("/overview/annotations", methods=["POST"])
def add_annotation_route():
    range_str = request.form.get("range", DEFAULT_RANGE)
    offset = request.form.get("offset", 0, type=int)

    ts_iso = request.form.get("ts_iso", "")
    event_type = request.form.get("event_type", "")
    description = request.form.get("description", "").strip() or None

    if event_type in ANNOTATION_EVENT_TYPES:
        try:
            ts_utc = datetime.fromisoformat(ts_iso).astimezone(timezone.utc)
        except ValueError:
            ts_utc = None
        if ts_utc is not None:
            add_annotation(ts_utc, event_type, description)

    return redirect(url_for("overview", range=range_str, offset=offset))
