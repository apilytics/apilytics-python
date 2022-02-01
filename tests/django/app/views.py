from typing import NoReturn

import django.http


def error_view(request: django.http.HttpRequest) -> NoReturn:
    raise RuntimeError


def no_body_view(request: django.http.HttpRequest) -> django.http.HttpResponse:
    return django.http.HttpResponse(status=200)


def streaming_view(
    request: django.http.HttpRequest,
) -> django.http.StreamingHttpResponse:
    return django.http.StreamingHttpResponse(
        status=200, streaming_content=(b"first", b" ", b"second")
    )


def ok_view(request: django.http.HttpRequest) -> django.http.HttpResponse:
    if request.method == "POST":
        return django.http.HttpResponse(status=201, content=b"created")
    return django.http.HttpResponse(status=200, content=b"ok")
