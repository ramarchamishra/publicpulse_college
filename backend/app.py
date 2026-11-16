"""Run from backend/: python -m flask --app app run --port 5000 --no-reload"""
import atexit
import logging
import os
import sqlite3
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from api.errors import APIError
from api.routes import api
from database.connection import database_path
from services.analysis.job_service import JobService

BASE = Path(__file__).resolve().parent


def resolve_path(value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (BASE / path).resolve()


def create_app(config=None):
    load_dotenv(BASE / ".env")
    app = Flask(__name__)
    app.config.update(
        DATABASE=str(resolve_path(os.getenv("PUBLICPULSE_DATABASE", "database/publicpulse.db"))),
        JOB_DATABASE=str(resolve_path(os.getenv("PUBLICPULSE_JOB_DATABASE", "instance/jobs.sqlite3"))),
        MAX_PENDING_JOBS=int(os.getenv("PUBLICPULSE_MAX_PENDING_JOBS", "8")),
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if config:
        app.config.update(config)
    # Model initialization is deliberately absent from application startup.
    options = {}
    if app.config.get("JOB_RUNNER"):
        options["runner"] = app.config["JOB_RUNNER"]
    app.extensions["jobs"] = JobService(
        app.config["JOB_DATABASE"], app.config["DATABASE"], app.config["MAX_PENDING_JOBS"], **options)
    atexit.register(app.extensions["jobs"].close)
    app.register_blueprint(api)

    @app.before_request
    def bind_database():
        g.database_token = database_path.set(app.config["DATABASE"])
        # Browser mutations are same-origin through Vite; reject cross-site requests.
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                raise APIError("Cross-site requests are not allowed.", 403, "forbidden")

    @app.teardown_request
    def release_database(_error):
        token = g.pop("database_token", None)
        if token is not None:
            database_path.reset(token)

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.errorhandler(APIError)
    def api_error(error):
        return jsonify(error={"code": error.code, "message": error.message}), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error={"code": error.name.lower().replace(" ", "_"),
                              "message": error.description}), error.code

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception("Database operation failed")
        return jsonify(error={"code": "database_unavailable",
                              "message": "The database is unavailable. Check the server configuration."}), 503

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Request failed")
        return jsonify(error={"code": "internal_error", "message": "The request failed. Check the server log."}), 500

    @app.cli.command("init-db")
    def init_db():
        """Explicitly create missing original tables; never drops existing data."""
        from database.schema import create_tables
        Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
        token = database_path.set(app.config["DATABASE"])
        try:
            create_tables()
        finally:
            database_path.reset(token)
        click.echo("Missing tables created; existing records preserved.")

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="127.0.0.1", port=5000, use_reloader=False)
