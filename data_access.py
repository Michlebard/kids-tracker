"""Read complete transaction histories despite the Supabase response limit."""


def fetch_log_rows(client, table_name, page_size=500):
    """Return all log rows in chronological order, using inclusive ranges."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")

    rows = []
    offset = 0
    while True:
        response = (
            client.table(table_name)
            .select("*")
            .order("date_added")
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        page = response.data
        if not page:
            return rows
        rows.extend(page)
        # The server may return fewer rows than requested due to its own cap.
        offset += len(page)
