"""Read balances and a bounded history from Supabase."""


def fetch_log_rows(client, table_name, page_size=500):
    """Compatibility reader used only before the balance migration is installed."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    rows = []
    offset = 0
    while True:
        response = (
            client.table(table_name).select("*")
            .order("date_added").order("id")
            .range(offset, offset + page_size - 1).execute()
        )
        if not response.data:
            return rows
        rows.extend(response.data)
        offset += len(response.data)


def fetch_balances(client):
    """Return ({child_name: {points, money}}, migration_installed).

    Fall back only when the new table is missing, never on network/permission
    errors: those must remain visible instead of looking like a zero balance.
    """
    try:
        rows = (
            client.table("child_balances")
            .select("child_name,points_balance,money_balance").execute().data
        )
    except Exception as error:
        if getattr(error, "code", None) not in {"PGRST205", "42P01"}:
            raise
        balances = {}
        for table, column, kind in (
            ("points_log", "points_change", "points"),
            ("money_log", "amount", "money"),
        ):
            for row in fetch_log_rows(client, table):
                balance = balances.setdefault(row["child_name"], {"points": 0, "money": 0})
                balance[kind] += row[column] or 0
        return balances, False

    return {
        row["child_name"]: {
            "points": row["points_balance"],
            "money": row["money_balance"],
        }
        for row in rows
    }, True


def fetch_recent_log_rows(client, table_name, limit=20):
    """Fetch just the latest operations, with a deterministic order."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    return (
        client.table(table_name).select("*")
        .order("date_added", desc=True).order("id", desc=True)
        .limit(limit).execute().data
    )
