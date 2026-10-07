from pathlib import Path

from app.main import app


def test_main_registers_reconciliation_action_and_query_routes() -> None:
    route_paths = {route.path for route in app.routes}

    assert {
        "/external-transactions",
        "/external-transactions/{external_transaction_id}",
        "/external-transactions/{external_transaction_id}/reconcile",
        "/reconciliations",
        "/reconciliations/{reconciliation_id}",
    }.issubset(route_paths)


def test_alembic_environment_imports_reconciliation_metadata() -> None:
    environment_path = Path(__file__).parents[3] / "alembic" / "env.py"
    source = environment_path.read_text(encoding="utf-8")

    expected_import = (
        "from app.modules.reconciliation import model as reconciliation_model"
    )
    assert expected_import in source
