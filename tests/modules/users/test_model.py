from sqlalchemy import Boolean, String, create_mock_engine

from app.core.database import Base
from app.modules.users.model import User


def test_user_model_maps_required_credentials_and_active_default() -> None:
    table = User.__table__

    assert isinstance(table.c.hashed_password.type, String)
    assert table.c.hashed_password.type.length == 255
    assert table.c.hashed_password.nullable is False
    assert isinstance(table.c.is_active.type, Boolean)
    assert table.c.is_active.nullable is False
    assert table.c.is_active.default.arg is True


def test_user_table_is_discoverable_from_base_metadata() -> None:
    assert Base.metadata.tables["users"] is User.__table__

    emitted_sql: list[str] = []
    engine = create_mock_engine(
        "postgresql+psycopg://",
        lambda sql, *args, **kwargs: emitted_sql.append(str(sql.compile())),
    )
    Base.metadata.create_all(engine)

    assert any("hashed_password" in statement for statement in emitted_sql)
    assert any("is_active" in statement for statement in emitted_sql)
