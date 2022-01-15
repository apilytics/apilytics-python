import platform
import unittest.mock

import django.test

import apilytics
import tests.conftest

client = django.test.client.Client()


def test_middleware_should_call_apilytics_api(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    # Refresh middleware to call `__init__` again making sure `MiddlewareNotUsed`
    # is ether called or not called properly.
    client.handler.load_middleware()
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
        "Apilytics-version": f"apilytics-python-django/{apilytics.__version__};python/{platform.python_version()};django/{django.__version__}",
    }

    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data.keys() == {"path", "method", "statusCode", "timeMillis"}
    assert data["path"] == "/"
    assert data["method"] == "GET"
    assert data["statusCode"] == 200
    assert isinstance(data["timeMillis"], int)


def test_middleware_should_not_send_query_params(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    client.handler.load_middleware()
    response = client.post("/dummy/123/path/?param=foo&param2=bar")
    assert response.status_code == 201

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["method"] == "POST"
    assert data["path"] == "/dummy/123/path/"
    assert data["statusCode"] == 201
    assert isinstance(data["timeMillis"], int)


@django.test.override_settings(APILYTICS_API_KEY=None)
def test_middleware_should_be_disabled_if_api_key_is_unset(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    client.handler.load_middleware()
    response = client.get("/")
    assert response.status_code == 200

    assert mocked_urlopen.call_count == 0


def test_middleware_should_send_data_even_on_errors(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    client.handler.load_middleware()
    try:
        client.get("/error")
    except RuntimeError:
        pass

    assert mocked_urlopen.call_count == 1

    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["method"] == "GET"
    assert data["path"] == "/error"
    assert data["statusCode"] == 500
    assert isinstance(data["timeMillis"], int)
