from app.modules.ledger.schema import LedgerListQuery


def test_ledger_list_query_defaults_and_accepts_supported_filters() -> None:
    query = LedgerListQuery(currency="USD", account="EXTERNAL_FUNDS")

    assert (query.limit, query.offset) == (20, 0)
