from typing import NoReturn

import django.http


def ok_view(request: django.http.HttpRequest) -> django.http.HttpResponse:
    if request.method == "POST":
        return django.http.HttpResponse(status=201)
    return django.http.HttpResponse(status=200)


def error_view(request: django.http.HttpRequest) -> NoReturn:
    raise RuntimeError
