from sqlalchemy import create_engine, text

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)


def count_tags():
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM sensor_inventory")).scalar_one()
