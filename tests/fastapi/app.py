"""Simple FastAPI app that's used in tests."""
from typing import NoReturn

import fastapi
import starlette.responses

import apilytics.fastapi

app = fastapi.FastAPI()

app.add_middleware(apilytics.fastapi.ApilyticsMiddleware, api_key="dummy-key")


@app.api_route("/error", methods=["GET"])
async def error_route(request: fastapi.Request) -> NoReturn:
    raise RuntimeError


@app.api_route("/empty", methods=["POST"])
async def no_body_route(request: fastapi.Request) -> fastapi.Response:
    return fastapi.Response(status_code=fastapi.status.HTTP_200_OK)


@app.api_route("/streaming", methods=["GET"])
async def streaming_route(
    request: fastapi.Request,
) -> starlette.responses.StreamingResponse:
    return starlette.responses.StreamingResponse(
        status_code=fastapi.status.HTTP_200_OK,
        content=iter([b"first", b" ", b"second"]),
        media_type="application/octet-stream",
    )


@app.api_route("/{path:path}", methods=["GET", "POST"])
async def ok_route(request: fastapi.Request) -> fastapi.Response:
    if request.method == "POST":
        return fastapi.Response(
            status_code=fastapi.status.HTTP_201_CREATED, content=b"created"
        )
    return fastapi.Response(status_code=fastapi.status.HTTP_200_OK, content=b"ok")
