import concurrent.futures
import json
import platform
import re
import sys
import time
import types
import urllib.error
import urllib.request
from typing import ClassVar, Optional, Tuple, Type

import apilytics

__all__ = ["ApilyticsSender"]


class ApilyticsSender:
    """
    Context manager that sends API analytics data to Apilytics (https://apilytics.io).

    Use as a context manager by wrapping a request handler in an HTTP middleware.
    Make sure to call ``set_response_info`` on the object received in the with-statement.

    The metrics will be sent in a fire-and-forget background task when the block ends.

    Examples:
        my_middleware.py::

            with ApilyticsSender(
                api_key="<your-api-key>",
                path=request.path,
                query=request.query_string,
                method=request.method,
                request_size=len(request.body),
                user_agent=request.headers.get("user-agent"),
                ip=request.headers.get("x-forwarded-for", "").split(",")[0].strip(),
            ) as sender:
                response = get_response(request)
                sender.set_response_info(
                    status_code=response.status_code,
                    response_size=len(response.body),
                )
    """

    _executor: ClassVar[concurrent.futures.Executor]

    _apilytics_version_template: ClassVar[
        str
    ] = f"{{integration}}/{apilytics.__version__};python/{platform.python_version()};{{library}};{sys.platform}"

    def __init__(
        self,
        *,
        api_key: str,
        path: str,
        method: str,
        query: Optional[str] = None,
        request_size: Optional[int] = None,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
        apilytics_integration: Optional[str] = None,
        integrated_library: Optional[str] = None,
    ) -> None:
        """
        Initialize the context manager with info from the HTTP request object.

        Args:
            api_key: The API key for your Apilytics origin.
            path: Path of the user's HTTP request, e.g. "/foo/bar/123".
            method: Method of the user's HTTP request, e.g. "GET".
            query: Optional query string of the user's HTTP request e.g. "key=val&other=123".
                An empty string and None are treated equally. Can have an optional "?" at the start.
            request_size: Size of the user's HTTP request's body in bytes.
            user_agent: Value of the `User-Agent` header from the user's HTTP request.
                An empty string and None are treated equally.
            ip: User's IP address (used for geolocation, never stored nor sent to 3rd parties).
                An empty string and None are treated equally.
            apilytics_integration: Name of the Apilytics integration that's calling this,
                e.g. "apilytics-python-django". No need to pass this when calling from user code.
            integrated_library: Name and version of the integration that this is used in,
                e.g. "django/3.2.1". No need to pass this when calling from user code.
        """
        self._api_key = api_key
        self._path = path
        self._method = method
        self._query = query
        self._request_size = request_size
        self._user_agent = user_agent
        self._ip = ip

        self._response_size: Optional[int] = None
        self._status_code: Optional[int] = None

        self._apilytics_version = self._apilytics_version_template.format(
            integration=apilytics_integration or "apilytics-python-core",
            library=integrated_library or "",
        )

    def __enter__(self) -> "ApilyticsSender":
        """Start the timer, measuring how long the ``with`` block takes to execute."""
        self._start_time_ns = time.perf_counter_ns()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ) -> None:
        """Send metrics to Apilytics in a fire-and-forget background task."""
        self._end_time_ns = time.perf_counter_ns()
        if not hasattr(self, "_executor"):
            # Use only a single background thread and share the pool to minimize
            # resource hogging.
            self.__class__._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1
            )
        self._executor.submit(self._send_metrics)

    def set_response_info(
        self, *, status_code: Optional[int] = None, response_size: Optional[int] = None
    ) -> None:
        """
        Update the context manager with info from the HTTP response object.

        Should be called before the context manager's block ends.

        Args:
            status_code: Status code for the HTTP response. Can be omitted (or None)
                if the middleware could not get the status code.
            response_size: Size of the sent HTTP response's body in bytes.
        """
        self._status_code = status_code
        self._response_size = response_size

    def _send_metrics(self) -> None:
        memory_usage, memory_total = _get_used_and_total_memory()
        cpu_usage = _get_cpu_usage()

        request = urllib.request.Request(
            url="https://www.apilytics.io/api/v1/middleware",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self._api_key,
                "Apilytics-Version": self._apilytics_version,
            },
        )
        data = {
            "path": self._path,
            "method": self._method,
            "timeMillis": (self._end_time_ns - self._start_time_ns) // 1_000_000,
            # Don't send empty strings.
            **({"query": self._query} if self._query else {}),
            **({"userAgent": self._user_agent} if self._user_agent else {}),
            **({"ip": self._ip} if self._ip else {}),
            **(
                {"statusCode": self._status_code}
                if self._status_code is not None
                else {}
            ),
            **(
                {"requestSize": self._request_size}
                if self._request_size is not None
                else {}
            ),
            **(
                {"responseSize": self._response_size}
                if self._response_size is not None
                else {}
            ),
            **({"cpuUsage": cpu_usage} if cpu_usage is not None else {}),
            **({"memoryUsage": memory_usage} if memory_usage is not None else {}),
            **({"memoryTotal": memory_total} if memory_total is not None else {}),
        }
        try:
            urllib.request.urlopen(url=request, data=json.dumps(data).encode())
        except urllib.error.URLError:
            pass


def _get_cpu_usage() -> Optional[float]:
    """
    Get the current CPU usage as a percentage.

    Returns:
        A percentage value between 0 and 1, or None if the CPU usage could not be
        determined (most likely because the system is not Linux).
    """
    if platform.system() != "Linux":
        return None

    def cpu_times() -> Tuple[int, int]:
        with open("/proc/stat") as f:
            stat = f.readline()

        # Ignore the `cpu` text from the start and the last two "guest" times.
        times = [int(val) for val in stat.split()[1:9]]

        total = sum(times)
        idle = times[3]

        try:
            # Include `iowait` time into idle time if available, as does:
            # https://github.com/torvalds/linux/blob/4f12b742eb2b3a850ac8be7dc4ed52976fc6cb0b/kernel/sched/cputime.c#L225
            idle += times[4]
        except IndexError:
            # `iowait` time is not available before Linux 2.5.41, quite unlikely
            # to happen but doesn't hurt to handle this anyway.
            pass

        return idle, total

    try:
        idle_start, total_start = cpu_times()

        # There is no such thing as CPU usage percentage on a single point of time.
        # At any discrete instant a CPU core is either fully used or fully idle.
        # This is why we need to measure the usage over a known time interval. An
        # interval of one second has been tested to provide quite consistent results.
        time.sleep(1)

        idle_end, total_end = cpu_times()
    except OSError:
        return None

    try:
        idle_percentage = (idle_end - idle_start) / (total_end - total_start)
    except ZeroDivisionError:
        return 0.0

    return 1 - idle_percentage


def _get_used_and_total_memory() -> Tuple[Optional[int], Optional[int]]:
    """
    Get information about the used and total system memory.

    Returns:
        A tuple containing the used and total system memory in bytes.
        (None, None) if the system is not Linux or if the reading fails.
        (None, int) if the used memory could not be determined.
    """
    used = None
    total = None

    if platform.system() == "Linux":
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
        except OSError:
            pass  # Prepare for everything and anything.
        else:
            total_match = re.search(r"MemTotal:\s*(\d+)", meminfo)
            available_match = re.search(r"MemAvailable:\s*(\d+)", meminfo)
            if total_match:
                total = int(total_match.group(1)) * 1024
                if available_match:
                    # If MemAvailable exists MemTotal will also exist.
                    # The reverse is not always true (MemAvailable came in Linux 3.14).
                    available = int(available_match.group(1)) * 1024
                    used = total - available

    return used, total
