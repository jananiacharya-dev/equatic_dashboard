from app import app
from app.data_access import count_tags


@app.route("/")
def index():
    count = count_tags()
    return f"{count} tags"
