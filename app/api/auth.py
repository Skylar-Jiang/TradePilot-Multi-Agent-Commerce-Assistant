from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import SharedAccessDeniedError

_bearer = HTTPBearer(auto_error=False)


async def require_shared_access(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    expected = request.app.state.settings.app_api_key
    if not expected:
        return
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise SharedAccessDeniedError()
    if not compare_digest(credentials.credentials.encode("utf-8"), expected.encode("utf-8")):
        raise SharedAccessDeniedError()
