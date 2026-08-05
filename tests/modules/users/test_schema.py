import pytest
from pydantic import ValidationError

from app.modules.users.schema import UserCreate


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [
        ("  Ana Pérez  ", "Ana Pérez"),
        ("Ana   Pérez", "Ana   Pérez"),
        ("AB", "AB"),
        ("x" * 255, "x" * 255),
        ("Renée O'Connor-Smith", "Renée O'Connor-Smith"),
    ],
)
def test_user_create_accepts_and_normalizes_valid_full_name(
    full_name: str,
    expected: str,
) -> None:
    user = UserCreate(email="ana@example.com", full_name=full_name)

    assert user.full_name == expected


@pytest.mark.parametrize(
    ("full_name", "expected_message"),
    [
        ("", "El nombre completo debe tener al menos 2 caracteres"),
        ("   ", "El nombre completo debe tener al menos 2 caracteres"),
        ("A", "El nombre completo debe tener al menos 2 caracteres"),
        ("x" * 256, "El nombre completo no puede superar los 255 caracteres"),
    ],
)
def test_user_create_rejects_invalid_full_name(
    full_name: str,
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        UserCreate(email="ana@example.com", full_name=full_name)

    assert expected_message in str(error.value)
