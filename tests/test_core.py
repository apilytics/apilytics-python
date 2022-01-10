import unittest.mock
import urllib.error

import apilytics.core


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
