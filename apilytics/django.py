from typing import Callable

import django
import django.conf
import django.core.exceptions
import django.http

import apilytics.core

__all__ = ["ApilyticsMiddleware"]


class ApilyticsMiddleware:
    """
    Django middleware that sends API analytics data to Apilytics (https://apilytics.io).

    This should ideally be the first middleware in your ``settings.MIDDLEWARE`` list.

    Requires your Apilytics origin's API key to be set as ``APILYTICS_API_KEY`` in
    ``settings.py`` for this to do anything. The variable can be unset (or ``None``)
    e.g. in a test environment where data should not be sent.

    Examples:
        settings.py::

            APILYTICS_API_KEY = "<your-api-key>"

            MIDDLEWARE = [
                "apilytics.django.ApilyticsMiddleware",
                # ...
            ]
    """

    def __init__(
        self,
        get_response: Callable[[django.http.HttpRequest], django.http.HttpResponse],
    ) -> None:
        self.get_response = get_response
        api_key = getattr(django.conf.settings, "APILYTICS_API_KEY", None)
        if not api_key:
            raise django.core.exceptions.MiddlewareNotUsed
        self.api_key = api_key

    def __call__(self, request: django.http.HttpRequest) -> django.http.HttpResponse:
        with apilytics.core.ApilyticsSender(
            api_key=self.api_key,
            path=request.path,
            query=request.META.get("QUERY_STRING"),
            method=request.method or "",  # Typed as Optional, should never be None.
            request_size=int(request.META.get("CONTENT_LENGTH", 0)),
            apilytics_integration="apilytics-python-django",
            integrated_library=f"django/{django.__version__}",
        ) as sender:
            response = self.get_response(request)
            sender.set_response_info(
                status_code=response.status_code,
                response_size=len(getattr(response, "content", ())),
            )
        return response
