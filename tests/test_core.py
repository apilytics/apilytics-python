import platform
import sys
import textwrap
import time
import unittest.mock
import urllib.error

import apilytics.core
import tests.conftest


# Restore the real sleep behavior for this one test for thoroughness.
@unittest.mock.patch("apilytics.core.time.sleep", new=time.sleep)
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
        "Apilytics-version": f"apilytics-python-core/{apilytics.__version__};python/{platform.python_version()};;{sys.platform}",
    }

    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data.keys() == {
        "path",
        "method",
        "statusCode",
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
    assert isinstance(data["timeMillis"], int)
    if platform.system() == "Linux":
        assert 0 <= data["cpuUsage"] <= 1
        assert data["memoryUsage"] > 0
        assert data["memoryTotal"] > data["memoryUsage"]


def test_apilytics_sender_should_send_query_params(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    with apilytics.core.ApilyticsSender(
        api_key="dummy-key",
        path="/path",
        query="key=value?other=123",
        method="PUT",
    ) as sender:
        sender.set_response_info(status_code=200)

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["path"] == "/path"
    assert data["query"] == "key=value?other=123"


def test_apilytics_sender_should_not_send_empty_query_params(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    with apilytics.core.ApilyticsSender(
        api_key="dummy-key",
        path="/",
        query="",
        method="GET",
    ) as sender:
        sender.set_response_info(status_code=200)

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert "query" not in data

    with apilytics.core.ApilyticsSender(
        api_key="dummy-key",
        path="/",
        query=None,
        method="GET",
    ) as sender:
        sender.set_response_info(status_code=200)

    assert mocked_urlopen.call_count == 2
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert "query" not in data


def test_apilytics_sender_should_handle_empty_values_correctly(
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    with apilytics.core.ApilyticsSender(
        api_key="dummy-key",
        path="",
        method="",
        query="",
        request_size=None,
        user_agent=None,
        apilytics_integration=None,
        integrated_library=None,
    ) as sender:
        sender.set_response_info(status_code=None, response_size=None)

    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data.keys() == {
        "path",
        "method",
        "timeMillis",
        *(
            ("cpuUsage", "memoryUsage", "memoryTotal")
            if platform.system() == "Linux"
            else ()
        ),
    }
    assert data["path"] == ""
    assert data["method"] == ""
    assert isinstance(data["timeMillis"], int)
    if platform.system() == "Linux":
        assert isinstance(data["cpuUsage"], float)
        assert isinstance(data["memoryUsage"], int)
        assert isinstance(data["memoryTotal"], int)


@unittest.mock.patch("apilytics.core.platform.system", return_value="Linux")
@unittest.mock.patch("apilytics.core._get_used_and_total_memory", return_value=(0, 0))
def test_apilytics_sender_should_read_proc_stat_on_linux(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_memory: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    mocked_stat_start = textwrap.dedent(
        """\
        cpu  27133 0 33621 13668027 1459 0 508 10 100 100
        cpu0 7260 0 7391 3420134 484 0 80 0 0 0
        cpu1 7346 0 9306 3412338 138 0 82 0 0 0
        """  # The real file is longer.
    )
    mocked_stat_end = textwrap.dedent(
        """\
        cpu  28869 0 33657 13680890 1460 0 508 20 200 200
        cpu0 7263 0 7398 3423775 484 0 80 0 0 0
        cpu1 9069 0 9314 3414266 138 0 82 0 0 0
        """
    )
    with unittest.mock.patch(
        "builtins.open",
        new=unittest.mock.mock_open(read_data=mocked_stat_start),
    ) as mocked_open:
        mocked_open.side_effect = (
            mocked_open.return_value,
            unittest.mock.mock_open(read_data=mocked_stat_end).return_value,
        )
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 2
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    # Totals ignore last two "guest" fields.
    total_start = 27133 + 0 + 33621 + 13668027 + 1459 + 0 + 508 + 10
    total_end = 28869 + 0 + 33657 + 13680890 + 1460 + 0 + 508 + 20
    # Idles combine idle and iowait.
    idle_start = 13668027 + 1459
    idle_end = 13680890 + 1460
    assert data["cpuUsage"] == 1 - (idle_end - idle_start) / (total_end - total_start)
    assert data["cpuUsage"] == 0.12167144612863579


@unittest.mock.patch("apilytics.core.platform.system", return_value="Linux")
@unittest.mock.patch("apilytics.core._get_used_and_total_memory", return_value=(0, 0))
def test_apilytics_sender_should_handle_proc_stat_read_failure(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_memory: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    with unittest.mock.patch("builtins.open", side_effect=OSError) as mocked_open:
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 1
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert "cpuUsage" not in data


@unittest.mock.patch("apilytics.core.platform.system", return_value="Linux")
@unittest.mock.patch("apilytics.core._get_used_and_total_memory", return_value=(0, 0))
def test_apilytics_sender_should_handle_proc_stat_iowait_missing(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_memory: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    mocked_stat_start = "cpu  27133 0 33621 13668027"
    mocked_stat_end = "cpu  28869 0 33657 13680890"
    with unittest.mock.patch(
        "builtins.open",
        new=unittest.mock.mock_open(read_data=mocked_stat_start),
    ) as mocked_open:
        mocked_open.side_effect = (
            mocked_open.return_value,
            unittest.mock.mock_open(read_data=mocked_stat_end).return_value,
        )
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 2
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    total_start = 27133 + 0 + 33621 + 13668027
    total_end = 28869 + 0 + 33657 + 13680890
    idle_start = 13668027
    idle_end = 13680890
    assert data["cpuUsage"] == 1 - (idle_end - idle_start) / (total_end - total_start)
    assert data["cpuUsage"] == 0.12107960368978476


@unittest.mock.patch("apilytics.core.platform.system", return_value="Linux")
@unittest.mock.patch("apilytics.core._get_used_and_total_memory", return_value=(0, 0))
def test_apilytics_sender_should_handle_proc_stat_timers_not_increased_zero_division(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_memory: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    mocked_stat = "cpu  27133 0 33621 13668027"
    with unittest.mock.patch(
        "builtins.open",
        new=unittest.mock.mock_open(read_data=mocked_stat),
    ) as mocked_open:
        mocked_open.side_effect = (
            mocked_open.return_value,
            unittest.mock.mock_open(read_data=mocked_stat).return_value,
        )
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 2
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["cpuUsage"] == 0.0


@unittest.mock.patch("apilytics.core.platform.system", return_value="Windows")
@unittest.mock.patch("apilytics.core._get_used_and_total_memory", return_value=(0, 0))
def test_apilytics_sender_should_not_read_proc_stat_when_not_on_linux(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_memory: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    with unittest.mock.patch("builtins.open") as mocked_open:
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 0
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert "cpuUsage" not in data


@unittest.mock.patch("apilytics.core.platform.system", return_value="Linux")
@unittest.mock.patch("apilytics.core._get_cpu_usage", return_value=0.0)
def test_apilytics_sender_should_read_proc_meminfo_on_linux(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_cpu_usage: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    memory_total = 4_125_478_912
    memory_available = 3_360_526_336

    mocked_meminfo = textwrap.dedent(
        f"""\
        MemTotal:        {memory_total // 1024} kB
        MemFree:          789940 kB
        MemAvailable:    {memory_available // 1024} kB
        Buffers:         2450168 kB
        """  # The real file is longer.
    )
    with unittest.mock.patch(
        "builtins.open", new=unittest.mock.mock_open(read_data=mocked_meminfo)
    ) as mocked_open:
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 1
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert data["memoryUsage"] == memory_total - memory_available
    assert data["memoryTotal"] == memory_total


@unittest.mock.patch("apilytics.core.platform.system", return_value="Linux")
@unittest.mock.patch("apilytics.core._get_cpu_usage", return_value=0.0)
def test_apilytics_sender_should_handle_proc_meminfo_read_failure(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_cpu_usage: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    with unittest.mock.patch("builtins.open", side_effect=OSError) as mocked_open:
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 1
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert "memoryUsage" not in data
    assert "memoryTotal" not in data


@unittest.mock.patch("apilytics.core.platform.system", return_value="Linux")
@unittest.mock.patch("apilytics.core._get_cpu_usage", return_value=0.0)
def test_apilytics_sender_should_handle_proc_meminfo_total_missing(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_cpu_usage: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    with unittest.mock.patch(
        "builtins.open", new=unittest.mock.mock_open(read_data="")
    ) as mocked_open:
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 1
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert "memoryUsage" not in data
    assert "memoryTotal" not in data


@unittest.mock.patch("apilytics.core.platform.system", return_value="Linux")
@unittest.mock.patch("apilytics.core._get_cpu_usage", return_value=0.0)
def test_apilytics_sender_should_handle_proc_meminfo_available_missing(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_cpu_usage: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    memory_total = 1048576
    with unittest.mock.patch(
        "builtins.open",
        new=unittest.mock.mock_open(read_data=f"MemTotal: {memory_total // 1024}"),
    ) as mocked_open:
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 1
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert "memoryUsage" not in data
    assert data["memoryTotal"] == memory_total


@unittest.mock.patch("apilytics.core.platform.system", return_value="Windows")
@unittest.mock.patch("apilytics.core._get_cpu_usage", return_value=0.0)
def test_apilytics_sender_should_not_read_proc_meminfo_when_not_on_linux(
    _mocked_system: unittest.mock.MagicMock,
    _mocked_cpu_usage: unittest.mock.MagicMock,
    mocked_urlopen: unittest.mock.MagicMock,
) -> None:
    with unittest.mock.patch("builtins.open") as mocked_open:
        with apilytics.core.ApilyticsSender(
            api_key="dummy-key",
            path="/",
            method="GET",
        ) as sender:
            sender.set_response_info(status_code=200)

    assert mocked_open.call_count == 0
    assert mocked_urlopen.call_count == 1
    __, call_kwargs = mocked_urlopen.call_args
    data = tests.conftest.decode_request_data(call_kwargs["data"])
    assert "memoryUsage" not in data
    assert "memoryTotal" not in data


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
