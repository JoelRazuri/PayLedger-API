import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users import router as users_router

client = TestClient(app)


@pytest.mark.parametrize(
    ("full_name", "expected_message"),
    [
        ("", "El nombre completo debe tener al menos 2 caracteres"),
        ("   ", "El nombre completo debe tener al menos 2 caracteres"),
        ("A", "El nombre completo debe tener al menos 2 caracteres"),
        ("x" * 256, "El nombre completo no puede superar los 255 caracteres"),
    ],
)
def test_create_user_rejects_invalid_full_name(
    monkeypatch: pytest.MonkeyPatch,
    full_name: str,
    expected_message: str,
) -> None:
    def fail_if_service_is_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("El service no debe recibir un nombre inválido")

    monkeypatch.setattr(users_router, "create_user", fail_if_service_is_called)

    response = client.post(
        "/users",
        json={"email": "ana@example.com", "full_name": full_name},
    )

    assert response.status_code == 422
    assert expected_message in response.text
