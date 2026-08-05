from flask import redirect, render_template, request, url_for

from app import app
from app.data_access import get_latest_metrics, parse_range

PAGES = ["overview", "voltage", "process", "effluent", "carbonation"]
RANGE_PRESETS = ["1h", "24h", "48h", "1w", "1m", "3m", "6m"]
DEFAULT_RANGE = "24h"


@app.route("/")
def index():
    return redirect(url_for("overview"))


@app.route("/overview")
def overview():
    range_str = request.args.get("range", DEFAULT_RANGE)
    start, end = parse_range(range_str)
    metrics = get_latest_metrics()
    return render_template(
        "overview.html",
        pages=PAGES,
        range_presets=RANGE_PRESETS,
        current_page="overview",
        current_range=range_str,
        start=start,
        end=end,
        metrics=metrics.to_dict("records"),
    )
