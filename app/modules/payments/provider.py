from dataclasses import dataclass
from typing import Protocol

from app.modules.payments.enums import PaymentProcessScenario, PaymentStatus
from app.modules.payments.model import Payment


@dataclass(frozen=True)
class ProviderResult:
    status: PaymentStatus
    provider_payment_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class PaymentProvider(Protocol):
    def process(
        self,
        payment: Payment,
        scenario: PaymentProcessScenario,
    ) -> ProviderResult: ...


class SandboxPaymentProvider:
    def process(
        self,
        payment: Payment,
        scenario: PaymentProcessScenario,
    ) -> ProviderResult:
        if scenario is PaymentProcessScenario.SUCCESS:
            return ProviderResult(
                status=PaymentStatus.COMPLETED,
                provider_payment_id=f"sandbox-{payment.id}",
            )
        if scenario is PaymentProcessScenario.BUSINESS_REJECTION:
            return ProviderResult(
                status=PaymentStatus.REJECTED,
                failure_code="business_rejection",
                failure_message="Rejected by sandbox",
            )
        return ProviderResult(
            status=PaymentStatus.FAILED,
            failure_code="technical_failure",
            failure_message="Technical failure in sandbox",
        )
