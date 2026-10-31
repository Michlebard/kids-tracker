import unittest
from types import SimpleNamespace

from data_access import fetch_log_rows


class FakeClient:
    def __init__(self, rows, cap=1000):
        self.rows = rows
        self.cap = cap
        self.requests = []

    def table(self, name):
        self.table_name = name
        self.sort_columns = []
        return self

    def select(self, columns):
        return self

    def order(self, column):
        self.sort_columns.append(column)
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def execute(self):
        self.requests.append((self.table_name, self.start, self.end))
        rows = sorted(
            self.rows, key=lambda row: tuple(row[key] for key in self.sort_columns)
        )
        stop = min(self.end + 1, self.start + self.cap)
        return SimpleNamespace(data=rows[self.start:stop])


class FetchLogRowsTests(unittest.TestCase):
    def test_complete_history_and_balance_across_page_boundaries(self):
        for table in ("points_log", "money_log"):
            for size in (0, 499, 500, 501, 1000, 1012, 1500):
                with self.subTest(table=table, size=size):
                    rows = [
                        {"id": i, "date_added": "2026-10-31", "change": 1}
                        for i in reversed(range(size))
                    ]
                    client = FakeClient(rows)
                    result = fetch_log_rows(client, table)
                    self.assertEqual([row["id"] for row in result], list(range(size)))
                    self.assertEqual(sum(row["change"] for row in result), size)
                    self.assertTrue(all(call[0] == table for call in client.requests))

    def test_server_cap_smaller_than_requested_page_does_not_truncate(self):
        rows = [{"id": i, "date_added": "2026-10-31"} for i in range(7)]
        client = FakeClient(rows, cap=2)
        self.assertEqual(fetch_log_rows(client, "points_log"), rows)
        self.assertEqual([call[1] for call in client.requests], [0, 2, 4, 6, 7])

    def test_recent_history_uses_date_then_id(self):
        rows = [
            {"id": 3, "date_added": "2026-10-30"},
            {"id": 2, "date_added": "2026-10-31"},
            {"id": 1, "date_added": "2026-10-31"},
        ]
        result = fetch_log_rows(FakeClient(rows), "points_log", page_size=1)
        self.assertEqual([row["id"] for row in result[::-1]], [2, 1, 3])

    def test_invalid_page_size(self):
        with self.assertRaises(ValueError):
            fetch_log_rows(FakeClient([]), "points_log", page_size=0)


if __name__ == "__main__":
    unittest.main()
