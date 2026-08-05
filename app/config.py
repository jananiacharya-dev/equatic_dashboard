import os
from dotenv import load_dotenv

load_dotenv()  # reads .env into environment variables

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://equatic:equatic_dev@localhost:5432/plant_dashboard",
)