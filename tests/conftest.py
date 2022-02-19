"""General helpers that can be used in any tests."""
import concurrent.futures
import json
import unittest.mock
from typing import Any, Callable, Generator, TypeVar

import pytest

__all__ = ["decode_request_data"]

T = TypeVar("T")


def decode_request_data(data: bytes) -> Any:
    return json.loads(data.decode())


@pytest.fixture
def mocked_urlopen() -> Generator[unittest.mock.MagicMock, None, None]:
    with unittest.mock.patch("apilytics.core.urllib.request.urlopen") as mocked:
        yield mocked


class _MockedExecutor(concurrent.futures.ThreadPoolExecutor):
    # Ignore: Parent is typed to return a `Future[T]`.
    def submit(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:  # type: ignore[override]
        """Overridden to make this synchronous during tests."""
        return super().submit(fn, *args, **kwargs).result()


@pytest.fixture(scope="session", autouse=True)
def mocked_executor() -> Generator[None, None, None]:
    with unittest.mock.patch(
        "apilytics.core.concurrent.futures.ThreadPoolExecutor",
        new=_MockedExecutor,
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
def mocked_sleep() -> Generator[None, None, None]:
    with unittest.mock.patch("apilytics.core.time.sleep", new=lambda secs: None):
        yield
