# Project context
Flask dashboard for an electrolyzer plant, metadata-driven: pages render from
sensor_inventory/metric_registry tables, never hardcoded tag names. Postgres 16
in Docker (docker-compose.yml), schema in db/schema.sql, seeded by
seed/seed_metadata.py (1,551 tags) and seed/generate_mock_data.py.

# Hard rules
- SQLAlchemy Core with raw SQL via text() — NO ORM, NO Flask-SQLAlchemy
- All SQL lives in app/data_access.py only; routes never contain SQL
- data_access.py must be importable/testable without Flask running
- Server-rendered Jinja templates + Plotly JS; no REST API, no JS framework
- Explicit column lists in all INSERT statements
- engine = create_engine(...) once at module level in data_access.py
- DATABASE_URL from .env via python-dotenv, with a localhost fallback
- After each task: explain key decisions in 3-5 bullets so I can defend them