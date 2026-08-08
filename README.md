# Equatic plant dashboard

Metadata-driven monitoring dashboard for the Singapore demo plant.
Runs locally on mock data; connects to the vendor database later through
a single adapter in the data access layer.

## Run it

```bash
docker compose up -d          # starts Postgres, applies db/schema.sql on first run
pip install -r requirements.txt
python seed/seed_metadata.py            # 1,551 tags + 6 metrics
python seed/generate_mock_data.py --hours 48
```

Sanity check: `python seed/seed_metadata.py --dry-run` prints tag counts
without touching the database.

## Run the app

```bash
flask --app app run --port 5050
```

Open [http://localhost:5050](http://localhost:5050) — it redirects to `/overview`:
KPI tiles, the CE trend chart, and the annotation feed, all driven by whatever
is in the DB from the seed step above. Range preset buttons (`1h`...`6m`)
re-request the page with `?range=`; nothing client-side needs a rebuild.

`DATABASE_URL` is read from `.env` (see `.env.example`) with a localhost
fallback matching the `docker-compose.yml` defaults, so a fresh clone works
without creating `.env` yourself.

Note: macOS's AirPlay Receiver often holds port 5000, Flask's default — if
`flask run` (no `--port`) fails to bind, that's usually why; either pick
another port or turn AirPlay Receiver off in System Settings.

## Reset

```bash
docker compose down -v && docker compose up -d   # wipes data, re-applies schema
```

## How to add or edit a sensor / metric

Extend the loops in `seed/seed_metadata.py` (or edit `METRICS` for a metric)
and rerun `python seed/seed_metadata.py` — both inserts are true upserts
(`ON CONFLICT ... DO UPDATE`), so editing an existing tag's or metric's fields
and rerunning updates that row in place. No application code changes.
The UI reads `display_page` / `display_group` to decide where everything renders.

Exception: `source_tag_id` on `sensor_inventory` is never overwritten by
reseeding once it's non-null in the DB — the script always passes `None` for
it, and the upsert preserves whatever value is already there. That column is
meant to hold vendor tag mappings that won't live in this script.

## Layout

```
db/schema.sql                 all tables + indexes; auto-applied by Docker
seed/seed_metadata.py         generates the full tag inventory from plant structure
seed/generate_mock_data.py    mock readings / state events / metrics, routed by signal_class
app/config.py                 loads .env, exposes DATABASE_URL
app/data_access.py            all SQL lives here; SQLAlchemy Core, no ORM
app/routes.py                 Flask routes; no SQL, calls data_access.py
app/templates/                Jinja templates (base.html tab bar + per-page content)
app/static/style.css          minimal CSS, no framework
```

M2 (overview page: KPI tiles, CE trend chart via Plotly, annotation feed) is
done. `voltage` / `process` / `effluent` / `carbonation` tabs exist in the
nav but have no routes yet — next up.

## Current tag inventory (per Suiri's doc, Jul 2026)

| Type | Count | Notes |
|---|---|---|
| V | 1,252 | 1,248 C2C (24 stacks x 52 cells) + 4 B2B |
| PT | 101 | 96 stack + 5 intake |
| TT | 50 | 48 stack + 2 intake |
| FM | 50 | 48 stack + FM-007 header + FM-012 recycle |
| pHT | 18 | 16 effluent + 2 intake (001, 020) |
| LS | 8 | discrete -> state_events |
| EPC | 72 | control feedback; hidden (display_page NULL) until PV trending confirmed |

## Open items

- EPC process-variable trending: confirm with vendor, then set `display_page`
- Vendor schema: when it arrives, populate `source_tag_id` and write the
  adapter in the data access layer (M4 timebox)
- Metric formulas: `metric_registry.formula_ref` marked pending (Babette)
