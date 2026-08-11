from flask import redirect, render_template, request, url_for

from app import app
from app.data_access import (
    get_annotations,
    get_latest_metrics,
    get_metric_series,
    parse_range,
    resolution_for_range,
)

PAGES = ["overview", "voltage", "process", "effluent", "carbonation"]
RANGE_PRESETS = ["1h", "24h", "48h", "1w", "1m", "3m", "6m"]
DEFAULT_RANGE = "24h"


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
    )
