from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.ledger import router as ledger_router
from app.modules.ledger.enums import LedgerAccount, LedgerEntrySide, LedgerEventType
from app.modules.ledger.exceptions import LedgerNotFoundError
from app.modules.ledger.model import JournalEntry, LedgerEntry
from app.modules.payments.enums import Currency
from app.modules.users.model import User

client = TestClient(app)


def journal(*, journal_id: int = 8, payment_id: int = 4) -> JournalEntry:
    timestamp = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    return JournalEntry(
        id=journal_id,
        payment_id=payment_id,
        event_type=LedgerEventType.PAYMENT_COMPLETED,
        amount=Decimal("12.50"),
        currency=Currency.ARS,
        occurred_at=timestamp,
        created_at=timestamp,
        entries=[
            LedgerEntry(
                id=10,
                side=LedgerEntrySide.DEBIT,
                account=LedgerAccount.PAYMENT_EXPENSE,
                amount=Decimal("12.50"),
                currency=Currency.ARS,
            ),
        ],
    )


@pytest.fixture(autouse=True)
def override_dependencies() -> MagicMock:
    db = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: User(id=7)
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


def test_list_journals_returns_owner_scoped_filtered_page(monkeypatch) -> None:
    list_journals = MagicMock(return_value=[journal()])
    monkeypatch.setattr(ledger_router, "list_journals", list_journals)

    response = client.get("/ledger/journals?limit=1&offset=2&currency=ARS")

    assert response.status_code == 200
    assert response.json()[0]["id"] == 8
    assert response.json()[0]["entries"][0]["account"] == "PAYMENT_EXPENSE"
    assert list_journals.call_args.args[1] == 7
    assert list_journals.call_args.args[2].limit == 1
    assert list_journals.call_args.args[2].offset == 2
    assert list_journals.call_args.args[2].currency is Currency.ARS


@pytest.mark.parametrize(
    ("path", "service_name", "service_argument"),
    [
        ("/ledger/journals/8", "get_journal", 8),
        ("/ledger/payments/4/journal", "get_payment_journal", 4),
    ],
)
def test_get_routes_return_owner_scoped_journal(
    monkeypatch, path: str, service_name: str, service_argument: int
) -> None:
    service = MagicMock(return_value=journal())
    monkeypatch.setattr(ledger_router, service_name, service)

    response = client.get(path)

    assert response.status_code == 200
    assert response.json()["id"] == 8
    assert service.call_args.args[1:] == (7, service_argument)


@pytest.mark.parametrize(
    "path",
    ["/ledger/journals", "/ledger/journals/8", "/ledger/payments/4/journal"],
)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_journal_reads_reject_missing_or_invalid_jwt(
    path: str, headers: dict[str, str]
) -> None:
    app.dependency_overrides.pop(get_current_user)

    response = client.get(path, headers=headers)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("path", "service_name"),
    [
        ("/ledger/journals/999", "get_journal"),
        ("/ledger/payments/999/journal", "get_payment_journal"),
    ],
)
def test_unknown_or_foreign_resources_are_not_disclosed(
    monkeypatch, path: str, service_name: str
) -> None:
    monkeypatch.setattr(
        ledger_router, service_name, MagicMock(side_effect=LedgerNotFoundError)
    )

    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "Asiento no encontrado"}


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "offset=-1", "currency=EUR", "account=CASH"],
)
def test_list_rejects_invalid_pagination_and_filters(query: str) -> None:
    response = client.get(f"/ledger/journals?{query}")

    assert response.status_code == 422
    assert response.json() == {"detail": "Solicitud inv\u00e1lida"}


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_journal_collection_rejects_mutations(method: str) -> None:
    response = getattr(client, method)("/ledger/journals")

    assert response.status_code == 405
