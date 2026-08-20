from dataclasses import dataclass
from typing import Protocol

from app.modules.payments.enums import PaymentProcessScenario, PaymentStatus


@dataclass(frozen=True)
class PaymentProviderInput:
    payment_id: int


@dataclass(frozen=True)
class ProviderResult:
    status: PaymentStatus
    provider_payment_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class PaymentProvider(Protocol):
    def process(
        self,
        input: PaymentProviderInput,
        scenario: PaymentProcessScenario,
    ) -> ProviderResult: ...


class SandboxPaymentProvider:
    def process(
        self,
        input: PaymentProviderInput,
        scenario: PaymentProcessScenario,
    ) -> ProviderResult:
        if scenario is PaymentProcessScenario.SUCCESS:
            return ProviderResult(
                status=PaymentStatus.COMPLETED,
                provider_payment_id=f"sandbox-{input.payment_id}",
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
