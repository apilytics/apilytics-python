import concurrent.futures
import json
import platform
import time
import types
import urllib.error
import urllib.request
from typing import ClassVar, Optional, Type

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
            ) as sender:
                response = get_response(request)
                sender.set_response_info(status_code=response.status_code)
    """

    _executor: ClassVar[concurrent.futures.Executor]

    _apilytics_version_template: ClassVar[
        str
    ] = f"{{integration}}/{apilytics.__version__};python/{platform.python_version()}"

    def __init__(
        self,
        *,
        api_key: str,
        path: str,
        method: str,
        query: Optional[str] = None,
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
            apilytics_integration: Name of the Apilytics integration that's calling this,
                e.g. "apilytics-python-django". No need to pass this when calling from user code.
            integrated_library: Name and version of the integration that this is used in,
                e.g. "django/3.2.1". No need to pass this when calling from user code.
        """
        self._api_key = api_key
        self._path = path
        self._method = method
        self._query = query
        self._status_code: Optional[int] = None

        self._apilytics_version = self._apilytics_version_template.format(
            integration=apilytics_integration or "apilytics-python-core"
        )
        if integrated_library:
            self._apilytics_version += f";{integrated_library}"

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

    def set_response_info(self, *, status_code: Optional[int] = None) -> None:
        """
        Update the context manager with info from the HTTP response object.

        Should be called before the context manager's block ends.

        Args:
            status_code: Status code for the HTTP response. Can be omitted (or None)
                if the middleware could not get the status code.
        """
        self._status_code = status_code

    def _send_metrics(self) -> None:
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
            **({"query": self._query} if self._query else {}),  # Don't send empty str.
            **(
                {"statusCode": self._status_code}
                if self._status_code is not None
                else {}
            ),
        }
        try:
            urllib.request.urlopen(url=request, data=json.dumps(data).encode())
        except urllib.error.URLError:
            pass
