from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.ledger.exceptions import LedgerNotFoundError
from app.modules.ledger.model import JournalEntry
from app.modules.ledger.schema import JournalResponse, LedgerListQuery
from app.modules.ledger.service import get_journal, get_payment_journal, list_journals
from app.modules.users.model import User


class SpanishValidationRoute(APIRoute):
    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def spanish_validation_handler(request: Request) -> Response:
            try:
                return await route_handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    content={"detail": "Solicitud inv\u00e1lida"},
                )

        return spanish_validation_handler


router = APIRouter(
    prefix="/ledger",
    tags=["Ledger"],
    route_class=SpanishValidationRoute,
)


def ledger_not_found(error: LedgerNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail="Asiento no encontrado")


@router.get("/journals", response_model=list[JournalResponse])
def list_journal_routes(
    filters: Annotated[LedgerListQuery, Depends()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[JournalEntry]:
    return list_journals(db, current_user.id, filters)


@router.get("/journals/{journal_id}", response_model=JournalResponse)
def get_journal_route(
    journal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JournalEntry:
    try:
        return get_journal(db, current_user.id, journal_id)
    except LedgerNotFoundError as error:
        raise ledger_not_found(error) from error


@router.get("/payments/{payment_id}/journal", response_model=JournalResponse)
def get_payment_journal_route(
    payment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JournalEntry:
    try:
        return get_payment_journal(db, current_user.id, payment_id)
    except LedgerNotFoundError as error:
        raise ledger_not_found(error) from error
