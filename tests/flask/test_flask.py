import platform
import sys
import unittest.mock

import flask
import flask.typing

import apilytics
import apilytics.flask
import tests.conftest
from tests.flask.app import app

client = app.test_client()


def test_middleware_should_call_apilytics_api(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    response = client.get("/")
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 1

    call_args, call_kwargs = mocked_urlopen.call_args
    assert not call_args
    assert call_kwargs.keys() == {"url", "data"}

    api_request = call_kwargs["url"]

    assert api_request.full_url == "https://www.apilytics.io/api/v1/middleware"
    assert api_request.method == "POST"
    assert api_request.headers == {
        # urllib calls `capitalize()` on the header keys.
        "Content-type": "application/json",
        "X-api-key": "dummy-key",
        "Apilytics-version": f"apilytics-python-flask/{apilytics.__version__};python/{platform.python_version()};flask/{flask.__version__};{sys.platform}",
    }

    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data.keys() == {
        "path",
        "method",
        "statusCode",
        "requestSize",
        "responseSize",
        "userAgent",
        "timeMillis",
        *(
            ("cpuUsage", "memoryUsage", "memoryTotal")
            if platform.system() == "Linux"
            else ()
        ),
    }
    assert data["path"] == "/"
    assert data["method"] == "GET"
    assert data["statusCode"] == 200
    assert data["requestSize"] == 0
    assert data["responseSize"] > 0
    assert data["userAgent"].startswith("werkzeug")
    assert isinstance(data["timeMillis"], int)
    if platform.system() == "Linux":
        assert isinstance(data["cpuUsage"], float)
        assert isinstance(data["memoryUsage"], int)
        assert isinstance(data["memoryTotal"], int)


def test_middleware_should_send_query_params(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    response = client.post("/dummy/123/path/?param=foo&param2=bar")
    assert response.status_code == 201

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["method"] == "POST"
    assert data["path"] == "/dummy/123/path/"
    assert data["query"] == "param=foo&param2=bar"
    assert data["statusCode"] == 201
    assert data["requestSize"] == 0
    assert data["responseSize"] > 0
    assert isinstance(data["timeMillis"], int)


def test_middleware_should_send_user_agent(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    response = client.get("/dummy", headers={"User-Agent": "some agent"})
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["userAgent"] == "some agent"


def test_middleware_should_send_ip(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    response = client.get("/dummy", headers={"X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["ip"] == "127.0.0.1"

    response = client.get("/dummy", headers={"X-Forwarded-For": "127.0.0.2,127.0.0.3"})
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 2
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["ip"] == "127.0.0.2"


def test_middleware_should_handle_zero_request_and_response_sizes(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    response = client.post("/empty")
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["requestSize"] == 0
    assert data["responseSize"] == 0


def test_middleware_should_handle_non_zero_request_and_response_sizes(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    response = client.post("/dummy?some=query", json={"hello": "world"})
    assert response.status_code == 201

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["requestSize"] == 18
    assert data["responseSize"] == 7  # `len(b"created")`


def test_middleware_should_work_with_streaming_response(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    response = client.get("/streaming")
    assert response.status_code == 200
    content = b"".join(response.iter_encoded())
    assert content == b"first second"

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data.keys() == {
        "path",
        "method",
        "statusCode",
        "requestSize",
        "userAgent",
        "timeMillis",
        *(
            ("cpuUsage", "memoryUsage", "memoryTotal")
            if platform.system() == "Linux"
            else ()
        ),
    }
    assert data["path"] == "/streaming"
    assert data["method"] == "GET"
    assert data["statusCode"] == 200
    assert data["requestSize"] == 0
    assert data["userAgent"].startswith("werkzeug")
    assert isinstance(data["timeMillis"], int)
    if platform.system() == "Linux":
        assert isinstance(data["cpuUsage"], float)
        assert isinstance(data["memoryUsage"], int)
        assert isinstance(data["memoryTotal"], int)


def test_middleware_should_be_disabled_if_api_key_is_unset(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    fresh_app = flask.Flask(__name__)
    fresh_app = apilytics.flask.apilytics_middleware(fresh_app, api_key=None)
    fresh_client = fresh_app.test_client()

    @fresh_app.get("/")
    def route() -> flask.typing.ResponseReturnValue:
        return "", 200

    response = fresh_client.get("/")
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 0


def test_middleware_should_send_data_even_on_errors(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    try:
        client.get("/error")
    except RuntimeError:
        pass

    assert mocked_urlopen.call_count == 1

    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data.keys() == {
        "method",
        "path",
        "statusCode",
        "requestSize",
        "responseSize",
        "userAgent",
        "timeMillis",
        *(
            ("cpuUsage", "memoryUsage", "memoryTotal")
            if platform.system() == "Linux"
            else ()
        ),
    }
    assert data["method"] == "GET"
    assert data["path"] == "/error"
    assert data["statusCode"] == 500
    assert data["requestSize"] == 0
    assert data["responseSize"] > 0
    assert data["userAgent"].startswith("werkzeug")
    assert isinstance(data["timeMillis"], int)
    if platform.system() == "Linux":
        assert isinstance(data["cpuUsage"], float)
        assert isinstance(data["memoryUsage"], int)
        assert isinstance(data["memoryTotal"], int)
