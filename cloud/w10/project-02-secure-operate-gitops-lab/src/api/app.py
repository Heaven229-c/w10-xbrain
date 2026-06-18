import os
import random
from hashlib import sha256
from pathlib import Path

from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
PrometheusMetrics(app)

ERROR_RATE = float(os.getenv("ERROR_RATE", "0"))
VERSION = os.getenv("VERSION", "v1")
DB_PASSWORD_FILE = Path(os.getenv("DB_PASSWORD_FILE", "/var/run/secrets/w10-db/password"))


def read_db_password_status():
    if not DB_PASSWORD_FILE.exists():
        return {
            "mounted": False,
            "path": str(DB_PASSWORD_FILE),
            "message": "db password secret file is not mounted yet",
        }

    password = DB_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    return {
        "mounted": True,
        "path": str(DB_PASSWORD_FILE),
        "length": len(password),
        "sha256_prefix": sha256(password.encode("utf-8")).hexdigest()[:12],
    }


@app.get("/")
def index():
    if random.random() < ERROR_RATE:
        return jsonify(error="injected", version=VERSION), 500
    return jsonify(ok=True, version=VERSION)


@app.get("/healthz")
def healthz():
    return "ok", 200


@app.get("/db-password-status")
def db_password_status():
    return jsonify(version=VERSION, db_password=read_db_password_status())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
