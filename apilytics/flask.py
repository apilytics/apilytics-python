from typing import Optional, TypeVar, cast

import flask

import apilytics.core

__all__ = ["apilytics_middleware"]

T = TypeVar("T", bound=flask.Flask)


def apilytics_middleware(app: T, api_key: Optional[str]) -> T:
    """
    Flask middleware that sends API analytics data to Apilytics (https://apilytics.io).

    Ideally wrap your app with this before you do anything else with it.

    Args:
        app: The Flask app to wrap.
        api_key: Your Apilytics origin's API key. You can pass ``None``
            e.g. in a test environment where data should not be sent.

    Returns:
        The passed app with the middleware added onto it.

    Examples:
        app.py::

            from apilytics.flask import apilytics_middleware
            from flask import Flask

            app = Flask(__name__)

            app = apilytics_middleware(app, api_key="<your-api-key>")
    """
    if not api_key:
        return app

    @app.before_request
    def set_request_info() -> None:
        with apilytics.core.ApilyticsSender(
            api_key=cast(str, api_key),  # Type not inferred from the early return.
            path=flask.request.path,
            query=flask.request.query_string.decode(flask.request.url_charset),
            method=flask.request.method,
            request_size=len(flask.request.data),
            user_agent=flask.request.headers.get("user-agent"),
            ip=flask.request.headers.get("x-forwarded-for", "").split(",")[0].strip(),
            apilytics_integration="apilytics-python-flask",
            integrated_library=f"flask/{flask.__version__}",
            prevent_send_on_exit=True,
        ) as sender:
            flask.g.apilytics_sender = sender

    @app.after_request
    def set_response_info(response: flask.Response) -> flask.Response:
        sender = flask.g.apilytics_sender
        size = response.headers.get("content-length")
        sender.set_response_info(
            status_code=response.status_code,
            response_size=int(size) if size is not None else None,
        )
        return response

    @app.teardown_request
    def send_metrics(exc: Optional[BaseException]) -> None:
        sender = flask.g.apilytics_sender
        sender.send()

    return app
