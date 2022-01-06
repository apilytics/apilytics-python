"""Simple FastAPI app that's used in tests."""
from typing import NoReturn

import fastapi

import apilytics.fastapi

app = fastapi.FastAPI()

app.add_middleware(apilytics.fastapi.ApilyticsMiddleware, api_key="dummy-key")


@app.api_route("/error", methods=["GET"])
async def error_route(request: fastapi.Request) -> NoReturn:
    raise RuntimeError


@app.api_route("/{path:path}", methods=["GET", "POST"])
async def ok_route(request: fastapi.Request) -> fastapi.Response:
    if request.method == "POST":
        return fastapi.Response(status_code=fastapi.status.HTTP_201_CREATED)
    return fastapi.Response(status_code=fastapi.status.HTTP_200_OK)
