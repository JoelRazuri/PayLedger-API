import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ledger.enums import LedgerAccount, LedgerEntrySide
from app.modules.ledger.model import JournalEntry
from app.modules.payments.enums import PaymentProcessScenario, PaymentStatus
from app.modules.payments.exceptions import PaymentStateConflictError
from app.modules.payments.provider import (
    PaymentProviderInput,
    ProviderResult,
    SandboxPaymentProvider,
)
from app.modules.payments.service import _complete_processing, process_payment
from tests.integration.test_payments_postgres import pending_payment, user

pytest_plugins = ("tests.integration.test_payments_postgres",)


class SessionInspectingProvider:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inputs: list[PaymentProviderInput] = []

    def process(
        self,
        input: PaymentProviderInput,
        scenario: PaymentProcessScenario,
    ) -> ProviderResult:
        self.inputs.append(input)
        assert self.db.in_transaction() is False
        return SandboxPaymentProvider().process(input, scenario)


def test_success_finalizes_payment_and_balanced_journal_atomically(sessions) -> None:
    db = sessions()
    try:
        owner = user(db, 20)
        payment = pending_payment(db, owner, "ledger-success")
        provider = SessionInspectingProvider(db)

        completed = process_payment(
            db,
            owner.id,
            payment.id,
            PaymentProcessScenario.SUCCESS,
            provider,
        )
        journal = db.scalar(
            select(JournalEntry).where(JournalEntry.payment_id == payment.id)
        )
        assert journal is not None
        journal_entries = [
            (entry.side, entry.account, entry.amount) for entry in journal.entries
        ]
        payment_id = payment.id
        payment_amount = payment.amount
        payment_currency = payment.currency
    finally:
        db.close()

    assert provider.inputs == [PaymentProviderInput(payment_id=payment_id)]
    assert completed.status is PaymentStatus.COMPLETED
    assert journal.amount == payment_amount
    assert journal.currency is payment_currency
    assert journal_entries == [
        (LedgerEntrySide.DEBIT, LedgerAccount.PAYMENT_EXPENSE, payment_amount),
        (LedgerEntrySide.CREDIT, LedgerAccount.EXTERNAL_FUNDS, payment_amount),
    ]


@pytest.mark.parametrize(
    "scenario,expected_status",
    [
        (PaymentProcessScenario.BUSINESS_REJECTION, PaymentStatus.REJECTED),
        (PaymentProcessScenario.TECHNICAL_FAILURE, PaymentStatus.FAILED),
    ],
)
def test_non_success_finalization_creates_no_journal(
    sessions, scenario, expected_status
) -> None:
    db = sessions()
    try:
        owner_number = (
            21 if scenario is PaymentProcessScenario.BUSINESS_REJECTION else 22
        )
        owner = user(db, owner_number)
        payment = pending_payment(db, owner, f"ledger-{scenario.value}")

        result = process_payment(
            db,
            owner.id,
            payment.id,
            scenario,
            SandboxPaymentProvider(),
        )
        journal = db.scalar(
            select(JournalEntry).where(JournalEntry.payment_id == payment.id)
        )
    finally:
        db.close()

    assert result.status is expected_status
    assert journal is None


class PostingFailureProvider:
    def process(
        self,
        input: PaymentProviderInput,
        scenario: PaymentProcessScenario,
    ) -> ProviderResult:
        return ProviderResult(status=PaymentStatus.COMPLETED)


def test_local_journal_failure_rolls_back_completed_transition(
    sessions, monkeypatch
) -> None:
    db = sessions()
    try:
        owner = user(db, 23)
        payment = pending_payment(db, owner, "ledger-rollback")

        def fail_postings(*_args, **_kwargs):
            raise RuntimeError("postings failed")

        monkeypatch.setattr(
            "app.modules.payments.service.record_completed_payment", fail_postings
        )
        with pytest.raises(RuntimeError, match="postings failed"):
            process_payment(
                db,
                owner.id,
                payment.id,
                PaymentProcessScenario.SUCCESS,
                PostingFailureProvider(),
            )
        db.expire_all()
        persisted = db.get(type(payment), payment.id)
        journal = db.scalar(
            select(JournalEntry).where(JournalEntry.payment_id == payment.id)
        )
    finally:
        db.close()

    assert persisted is not None
    assert persisted.status is PaymentStatus.PROCESSING
    assert journal is None


class BlockingSuccessProvider:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def process(
        self,
        input: PaymentProviderInput,
        scenario: PaymentProcessScenario,
    ) -> ProviderResult:
        self.entered.set()
        assert self.release.wait(timeout=5)
        return SandboxPaymentProvider().process(input, scenario)


def test_two_sessions_converge_to_one_completed_journal(sessions) -> None:
    setup = sessions()
    try:
        owner = user(setup, 24)
        payment = pending_payment(setup, owner, "ledger-concurrency")
        owner_id, payment_id = owner.id, payment.id
    finally:
        setup.close()

    provider = BlockingSuccessProvider()
    first, second = sessions(), sessions()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            winner = executor.submit(
                process_payment,
                first,
                owner_id,
                payment_id,
                PaymentProcessScenario.SUCCESS,
                provider,
            )
            assert provider.entered.wait(timeout=5)
            with pytest.raises(PaymentStateConflictError):
                process_payment(
                    second,
                    owner_id,
                    payment_id,
                    PaymentProcessScenario.SUCCESS,
                    SandboxPaymentProvider(),
                )
            provider.release.set()
            completed = winner.result(timeout=5)
        journal_count = (
            second.query(JournalEntry).filter_by(payment_id=payment_id).count()
        )
    finally:
        first.close()
        second.close()

    assert completed.status is PaymentStatus.COMPLETED
    assert journal_count == 1


def test_completed_retry_reuses_existing_journal_and_closes_lock_transaction(
    sessions,
) -> None:
    db = sessions()
    try:
        owner = user(db, 25)
        payment = pending_payment(db, owner, "ledger-retry")
        process_payment(
            db,
            owner.id,
            payment.id,
            PaymentProcessScenario.SUCCESS,
            SandboxPaymentProvider(),
        )

        retried = _complete_processing(
            db,
            owner.id,
            payment.id,
            ProviderResult(status=PaymentStatus.COMPLETED),
        )
        transaction_open = db.in_transaction()
        retried_status = retried.status
        journal_count = db.query(JournalEntry).filter_by(payment_id=payment.id).count()
    finally:
        db.close()

    assert retried_status is PaymentStatus.COMPLETED
    assert journal_count == 1
    assert transaction_open is False
