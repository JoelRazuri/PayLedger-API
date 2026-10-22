from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.audit.exceptions import AuditEventNotFoundError
from app.modules.audit.model import AuditEvent
from app.modules.audit.schema import AuditEventListQuery, AuditEventResponse
from app.modules.audit.service import get_audit_event, list_audit_events
from app.modules.auth.dependencies import get_current_user
from app.modules.users.model import User


class SpanishValidationRoute(APIRoute):
    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await route_handler(request)
            except RequestValidationError, ValidationError:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    content={"detail": "Solicitud inv\u00e1lida"},
                )

        return handler


router = APIRouter(
    prefix="/audit-events", tags=["Audit"], route_class=SpanishValidationRoute
)


def _not_found(error: AuditEventNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=404, detail="Evento de auditor\u00eda no encontrado"
    )


@router.get("", response_model=list[AuditEventResponse])
def list_audit_event_routes(
    filters: Annotated[AuditEventListQuery, Depends()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AuditEvent]:
    return list_audit_events(db, current_user.id, filters)


@router.get("/{audit_event_id}", response_model=AuditEventResponse)
def get_audit_event_route(
    audit_event_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditEvent:
    try:
        return get_audit_event(db, current_user.id, audit_event_id)
    except AuditEventNotFoundError as error:
        raise _not_found(error) from error
