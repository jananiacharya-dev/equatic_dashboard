from flask import Flask

app = Flask(__name__)

from app import routes  # noqa: E402 -- must follow `app` definition; routes.py imports `app` on import
