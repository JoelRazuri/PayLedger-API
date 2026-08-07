import pytest

from app.modules.payments.enums import PaymentProcessScenario, PaymentStatus
from app.modules.payments.model import Payment
from app.modules.payments.provider import SandboxPaymentProvider


@pytest.mark.parametrize(
    ("scenario", "status", "provider_id", "failure_code"),
    [
        (
            PaymentProcessScenario.SUCCESS,
            PaymentStatus.COMPLETED,
            "sandbox-8",
            None,
        ),
        (
            PaymentProcessScenario.BUSINESS_REJECTION,
            PaymentStatus.REJECTED,
            None,
            "business_rejection",
        ),
        (
            PaymentProcessScenario.TECHNICAL_FAILURE,
            PaymentStatus.FAILED,
            None,
            "technical_failure",
        ),
    ],
)
def test_sandbox_provider_returns_only_controlled_outcomes(
    scenario: PaymentProcessScenario,
    status: PaymentStatus,
    provider_id: str | None,
    failure_code: str | None,
) -> None:
    result = SandboxPaymentProvider().process(Payment(id=8), scenario)

    assert result.status is status
    assert result.provider_payment_id == provider_id
    assert result.failure_code == failure_code
    assert result.failure_message is None or "sandbox" in result.failure_message
    assert not hasattr(result, "raw_payload")
