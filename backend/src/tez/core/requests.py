"""Per-request context: id, access log and the last-resort 500 handler."""

import logging
import secrets
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tez.core.errors import ErrorCode, error_response
from tez.core.logging import request_id_var

logger = logging.getLogger("tez.request")


class RequestContextMiddleware:
    """Gives each request an id (`X-Request-ID`), logs it, and turns crashes into 500s.

    Sits inside CORS, so even a 500 reaches the UI as a readable response. Only the path is
    logged, never the query string or headers, which may carry secrets.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = secrets.token_hex(8)
        reset = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            logger.exception("unhandled error", extra={"request_id": request_id})
            if response_started:
                raise
            response = error_response(
                ErrorCode.INTERNAL_UNEXPECTED, 500, {"request_id": request_id}
            )
            await response(scope, receive, send_with_id)
        finally:
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            request_id_var.reset(reset)
