from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.reconciliation.exceptions import (
    ExternalTransactionConflictError,
    ExternalTransactionNotFoundError,
)
from app.modules.reconciliation.model import ExternalTransaction
from app.modules.reconciliation.schema import (
    ExternalTransactionCreate,
    ExternalTransactionListQuery,
    ExternalTransactionResponse,
)
from app.modules.reconciliation.service import (
    create_external_transaction,
    get_external_transaction,
    list_external_transactions,
)
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
                    content={"detail": "Solicitud inválida"},
                )

        return spanish_validation_handler


router = APIRouter(
    prefix="/external-transactions",
    tags=["Reconciliation"],
    route_class=SpanishValidationRoute,
)


def external_transaction_http_error(error: Exception) -> HTTPException:
    if isinstance(error, ExternalTransactionNotFoundError):
        return HTTPException(
            status_code=404, detail="Transacción externa no encontrada"
        )
    return HTTPException(
        status_code=409,
        detail="La transacción externa ya existe con datos diferentes",
    )


@router.post(
    "",
    response_model=ExternalTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_external_transaction_route(
    request: ExternalTransactionCreate,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExternalTransaction:
    try:
        created = create_external_transaction(db, current_user.id, request)
    except ExternalTransactionConflictError as error:
        raise external_transaction_http_error(error) from error
    if created.replayed:
        response.status_code = status.HTTP_200_OK
    return created.external_transaction


@router.get("", response_model=list[ExternalTransactionResponse])
def list_external_transaction_routes(
    filters: Annotated[ExternalTransactionListQuery, Depends()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ExternalTransaction]:
    return list_external_transactions(db, current_user.id, filters)


@router.get("/{external_transaction_id}", response_model=ExternalTransactionResponse)
def get_external_transaction_route(
    external_transaction_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExternalTransaction:
    try:
        return get_external_transaction(db, current_user.id, external_transaction_id)
    except ExternalTransactionNotFoundError as error:
        raise external_transaction_http_error(error) from error
