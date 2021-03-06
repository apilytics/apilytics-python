import platform
import sys
import unittest.mock

import django.test

import apilytics
import tests.conftest


def test_middleware_should_call_apilytics_api(
    mocked_urlopen: unittest.mock.MagicMock, client: django.test.client.Client
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
        "Apilytics-version": f"apilytics-python-django/{apilytics.__version__};python/{platform.python_version()};django/{django.__version__};{sys.platform}",
    }

    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data.keys() == {
        "path",
        "method",
        "statusCode",
        "requestSize",
        "responseSize",
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
    assert isinstance(data["timeMillis"], int)
    if platform.system() == "Linux":
        assert isinstance(data["cpuUsage"], float)
        assert isinstance(data["memoryUsage"], int)
        assert isinstance(data["memoryTotal"], int)


def test_middleware_should_send_query_params(
    mocked_urlopen: unittest.mock.MagicMock, client: django.test.client.Client
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
    assert data["requestSize"] == 20  # Empty form data POST adds a 20 boundary string.
    assert data["responseSize"] > 0
    assert isinstance(data["timeMillis"], int)


def test_middleware_should_send_user_agent(
    mocked_urlopen: unittest.mock.MagicMock, client: django.test.client.Client
) -> None:
    response = client.get("/dummy", HTTP_USER_AGENT="some agent")
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["userAgent"] == "some agent"


def test_middleware_should_send_ip(
    mocked_urlopen: unittest.mock.MagicMock, client: django.test.client.Client
) -> None:
    response = client.get("/dummy", HTTP_X_FORWARDED_FOR="127.0.0.1")
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["ip"] == "127.0.0.1"

    response = client.get("/dummy", HTTP_X_FORWARDED_FOR="127.0.0.2,127.0.0.3")
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 2
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["ip"] == "127.0.0.2"


def test_middleware_should_handle_zero_request_and_response_sizes(
    mocked_urlopen: unittest.mock.MagicMock, client: django.test.client.Client
) -> None:
    response = client.post("/empty?some=query", content_type="application/json")
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["requestSize"] == 2  # Django makes it `b"{}"` for empty JSON POSTs.
    assert data["responseSize"] == 0


def test_middleware_should_handle_non_zero_request_and_response_sizes(
    mocked_urlopen: unittest.mock.MagicMock, client: django.test.client.Client
) -> None:
    response = client.post(
        "/dummy?some=query", data={"hello": "world"}, content_type="application/json"
    )
    assert response.status_code == 201

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["requestSize"] == 18
    assert data["responseSize"] == 7  # `len(b"created")`


def test_middleware_should_work_with_streaming_response(
    mocked_urlopen: unittest.mock.MagicMock, client: django.test.client.Client
) -> None:
    response = client.get("/streaming")
    assert response.status_code == 200
    # Ignore: The attribute *does* exist on StreamingHTTPResponse.
    content = b"".join(response.streaming_content)  # type: ignore[attr-defined]
    assert content == b"first second"

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data.keys() == {
        "path",
        "method",
        "statusCode",
        "requestSize",
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
    assert isinstance(data["timeMillis"], int)
    if platform.system() == "Linux":
        assert isinstance(data["cpuUsage"], float)
        assert isinstance(data["memoryUsage"], int)
        assert isinstance(data["memoryTotal"], int)


@django.test.override_settings(APILYTICS_API_KEY=None)
def test_middleware_should_be_disabled_if_api_key_is_unset(
    mocked_urlopen: unittest.mock.MagicMock, client: django.test.client.Client
) -> None:
    response = client.get("/")
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 0


def test_middleware_should_send_data_even_on_errors(
    mocked_urlopen: unittest.mock.MagicMock, client: django.test.client.Client
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
        "timeMillis",
        "statusCode",
        "requestSize",
        "responseSize",
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
    assert isinstance(data["timeMillis"], int)
    if platform.system() == "Linux":
        assert isinstance(data["cpuUsage"], float)
        assert isinstance(data["memoryUsage"], int)
        assert isinstance(data["memoryTotal"], int)
