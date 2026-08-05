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

## Reset

```bash
docker compose down -v && docker compose up -d   # wipes data, re-applies schema
```

## How to add a sensor

Insert a row into `sensor_inventory` (or extend the loops in
`seed/seed_metadata.py` and rerun — it upserts). No application code changes.
The UI reads `display_page` / `display_group` to decide where everything renders.

## Layout

```
db/schema.sql                 all tables + indexes; auto-applied by Docker
seed/seed_metadata.py         generates the full tag inventory from plant structure
seed/generate_mock_data.py    mock readings / state events / metrics, routed by signal_class
app/                          Flask app (M2)
```

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
