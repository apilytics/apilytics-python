import platform
import unittest.mock
import urllib.error

import apilytics.core
import tests.conftest


def test_apilytics_sender_should_call_apilytics_api(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    with apilytics.core.ApilyticsSender(
        api_key="dummy-key",
        path="/",
        method="GET",
    ) as sender:
        sender.set_response_info(status_code=200)

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
        "Apilytics-version": f"apilytics-python-core/{apilytics.__version__};python/{platform.python_version()}",
    }

    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data.keys() == {"path", "method", "statusCode", "timeMillis"}
    assert data["path"] == "/"
    assert data["method"] == "GET"
    assert data["statusCode"] == 200
    assert isinstance(data["timeMillis"], int)


@unittest.mock.patch(
    "apilytics.core.urllib.request.urlopen",
    side_effect=urllib.error.URLError("testing"),
)
def test_apilytics_sender_should_hide_http_errors(
    mocked_erroring_urlopen: unittest.mock.MagicMock,
) -> None:
    with apilytics.core.ApilyticsSender(
        api_key="dummy-key",
        path="/",
        method="GET",
    ) as sender:
        sender.set_response_info(status_code=200)

    assert mocked_erroring_urlopen.call_count == 1
