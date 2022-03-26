"""Simple Flask app that's used in tests."""
from typing import NoReturn

import flask
import flask.typing

import apilytics.flask

app = flask.Flask(__name__)

app = apilytics.flask.apilytics_middleware(app, api_key="dummy-key")


@app.get("/error")
def error_route() -> NoReturn:
    raise RuntimeError


@app.post("/empty")
def no_body_route() -> flask.typing.ResponseReturnValue:
    return "", 200


@app.get("/streaming")
def streaming_route() -> flask.typing.ResponseReturnValue:
    return app.response_class(
        iter([b"first", b" ", b"second"]), mimetype="application/octet-stream"
    )


@app.route("/", methods=["GET", "POST"], defaults={"path": ""})
@app.route("/<path:path>", methods=["GET", "POST"])
def ok_route(path: str) -> flask.typing.ResponseReturnValue:
    if flask.request.method == "POST":
        return b"created", 201
    return b"ok", 200
