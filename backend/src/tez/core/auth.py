"""Bearer-token check for every HTTP request.

The API listens on 127.0.0.1 only, but any local program (or a web page via the browser)
can reach that port; the per-launch token is what makes a caller the TEz UI or CLI.
"""

import hmac
from collections.abc import Iterable

from fastapi.security import HTTPBearer
from starlette.types import ASGIApp, Receive, Scope, Send

from tez.core.errors import ErrorCode, error_response

# Declares the scheme in OpenAPI (and Swagger's "Authorize" button); enforcement is below.
bearer_scheme = HTTPBearer(auto_error=False)


class TokenAuthMiddleware:
    """Rejects requests without `Authorization: Bearer <token>`, before routing.

    CORS preflights never get here: the outer CORS middleware answers them itself.
    """

    def __init__(self, app: ASGIApp, *, token: str, public_paths: Iterable[str] = ()) -> None:
        if not token:
            raise ValueError("API token must not be empty")
        self.app = app
        self._token = token.encode()
        self._public_paths = frozenset(public_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan" or scope["path"] in self._public_paths:
            await self.app(scope, receive, send)
            return
        if not self._authorized(scope):
            response = error_response(
                ErrorCode.AUTH_INVALID_TOKEN, 401, headers={"WWW-Authenticate": "Bearer"}
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _authorized(self, scope: Scope) -> bool:
        for name, value in scope["headers"]:
            if name == b"authorization":
                scheme, _, credentials = value.partition(b" ")
                return scheme.lower() == b"bearer" and hmac.compare_digest(credentials, self._token)
        return False
