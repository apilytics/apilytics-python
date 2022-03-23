from typing import Awaitable, Callable, Optional

import fastapi
import starlette.middleware.base

import apilytics.core

__all__ = ["ApilyticsMiddleware"]


class ApilyticsMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    """
    FastAPI middleware that sends API analytics data to Apilytics (https://apilytics.io).

    This should ideally be the first middleware you add to your app.

    Examples:
        main.py::

            from apilytics.fastapi import ApilyticsMiddleware
            from fastapi import FastAPI

            app = FastAPI()

            app.add_middleware(ApilyticsMiddleware, api_key="<your-api-key>")
    """

    def __init__(self, app: fastapi.FastAPI, api_key: Optional[str]) -> None:
        """
        Args:
            api_key: Your Apilytics origin's API key. You can pass ``None``
                e.g. in a test environment where data should not be sent.
        """
        super().__init__(app=app)

        if not api_key:

            async def skipped_dispatch(
                request: fastapi.Request,
                call_next: Callable[[fastapi.Request], Awaitable[fastapi.Response]],
            ) -> fastapi.Response:
                return await call_next(request)

            self.dispatch_func = skipped_dispatch
        else:
            self.api_key = api_key

    async def dispatch(
        self,
        request: fastapi.Request,
        call_next: Callable[[fastapi.Request], Awaitable[fastapi.Response]],
    ) -> fastapi.Response:
        with apilytics.core.ApilyticsSender(
            api_key=self.api_key,
            path=request.url.path,
            query=request.url.query,
            method=request.method,
            request_size=len(await request.body()),
            user_agent=request.headers.get("user-agent"),
            ip=request.headers.get("x-forwarded-for", "").split(",")[0].strip(),
            apilytics_integration="apilytics-python-fastapi",
            integrated_library=f"fastapi/{fastapi.__version__}",
        ) as sender:
            response = await call_next(request)
            size = response.headers.get("content-length")
            sender.set_response_info(
                status_code=response.status_code,
                response_size=int(size) if size is not None else None,
            )
        return response
