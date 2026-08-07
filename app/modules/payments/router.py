from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.payments.exceptions import (
    PaymentIdempotencyConflictError,
    PaymentNotFoundError,
    PaymentStateConflictError,
)
from app.modules.payments.model import Payment
from app.modules.payments.provider import PaymentProvider, SandboxPaymentProvider
from app.modules.payments.schema import (
    PaymentCreate,
    PaymentListQuery,
    PaymentProcessRequest,
    PaymentResponse,
)
from app.modules.payments.service import (
    cancel_payment,
    create_payment,
    get_payment,
    list_payments,
    process_payment,
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
                    content={"detail": "Solicitud inv\u00e1lida"},
                )

        return spanish_validation_handler


router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
    route_class=SpanishValidationRoute,
)


def get_payment_provider() -> PaymentProvider:
    return SandboxPaymentProvider()


def payment_http_error(error: Exception) -> HTTPException:
    if isinstance(error, PaymentNotFoundError):
        return HTTPException(status_code=404, detail="Pago no encontrado")
    if isinstance(error, PaymentIdempotencyConflictError):
        return HTTPException(
            status_code=409,
            detail="La clave de idempotencia ya fue utilizada con otra solicitud",
        )
    return HTTPException(
        status_code=409,
        detail="El pago no está disponible para esta acción",
    )


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment_route(
    request: PaymentCreate,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Payment:
    try:
        created = create_payment(db, current_user.id, idempotency_key, request)
    except PaymentIdempotencyConflictError as error:
        raise payment_http_error(error) from error
    if created.replayed:
        response.status_code = status.HTTP_200_OK
    return created.payment


@router.get("", response_model=list[PaymentResponse])
def list_payment_routes(
    filters: Annotated[PaymentListQuery, Depends()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Payment]:
    return list_payments(db, current_user.id, filters)


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment_route(
    payment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Payment:
    try:
        return get_payment(db, current_user.id, payment_id)
    except PaymentNotFoundError as error:
        raise payment_http_error(error) from error


@router.post("/{payment_id}/process", response_model=PaymentResponse)
def process_payment_route(
    payment_id: int,
    request: PaymentProcessRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[PaymentProvider, Depends(get_payment_provider)],
) -> Payment:
    try:
        return process_payment(
            db,
            current_user.id,
            payment_id,
            request.simulation_scenario,
            provider,
        )
    except (PaymentNotFoundError, PaymentStateConflictError) as error:
        raise payment_http_error(error) from error


@router.post("/{payment_id}/cancel", response_model=PaymentResponse)
def cancel_payment_route(
    payment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Payment:
    try:
        return cancel_payment(db, current_user.id, payment_id)
    except (PaymentNotFoundError, PaymentStateConflictError) as error:
        raise payment_http_error(error) from error
