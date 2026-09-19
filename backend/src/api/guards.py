from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


MUTATING_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class ReadOnlyAPIMiddleware:
    """Reject client API mutations when the application is read-only."""

    def __init__(self, app: ASGIApp, *, enabled: bool) -> None:
        self.app = app
        self.enabled = enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            self.enabled
            and scope["type"] == "http"
            and scope.get("method", "").upper() in MUTATING_HTTP_METHODS
            and scope.get("path", "").startswith("/api/")
        ):
            response = JSONResponse(
                status_code=403,
                content={"detail": "Read-only mode: API mutations are disabled."},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
