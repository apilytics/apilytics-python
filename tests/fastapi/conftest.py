import contextlib
from typing import Generator, List

import fastapi
import fastapi.middleware

__all__ = ["override_middleware"]


@contextlib.contextmanager
def override_middleware(
    app: fastapi.FastAPI, middleware: List[fastapi.middleware.Middleware]
) -> Generator[None, None, None]:
    """Temporarily override the middleware stack of a FastAPI app."""
    orig_middleware = app.user_middleware
    try:
        app.user_middleware = middleware
        app.middleware_stack = app.build_middleware_stack()
        yield
    finally:
        app.user_middleware = orig_middleware
        app.middleware_stack = app.build_middleware_stack()
