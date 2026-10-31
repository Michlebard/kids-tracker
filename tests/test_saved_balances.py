import unittest
from types import SimpleNamespace

from data_access import fetch_balances, fetch_recent_log_rows


class APIError(Exception):
    def __init__(self, code):
        self.code = code


class FakeClient:
    def __init__(self, tables, balance_error=None):
        self.tables = tables
        self.balance_error = balance_error
        self.reads = []

    def table(self, name):
        self.name = name
        self.orders = []
        self.start, self.stop = 0, 1000
        return self

    def select(self, columns):
        return self

    def order(self, column, desc=False):
        self.orders.append((column, desc))
        return self

    def range(self, start, end):
        self.start, self.stop = start, end + 1
        return self

    def limit(self, size):
        self.stop = size
        return self

    def execute(self):
        self.reads.append((self.name, self.start, self.stop))
        if self.name == "child_balances" and self.balance_error:
            raise APIError(self.balance_error)
        rows = self.tables[self.name][:]
        for column, desc in reversed(self.orders):
            rows.sort(key=lambda row: row[column], reverse=desc)
        return SimpleNamespace(data=rows[self.start:self.stop])


class SavedBalancesTests(unittest.TestCase):
    def test_dashboard_reads_only_saved_balances(self):
        client = FakeClient({"child_balances": [
            {"child_name": "A", "points_balance": 15, "money_balance": 8.5},
            {"child_name": "B", "points_balance": -2, "money_balance": 0},
        ]})
        balances, installed = fetch_balances(client)
        self.assertTrue(installed)
        self.assertEqual(balances, {
            "A": {"points": 15, "money": 8.5},
            "B": {"points": -2, "money": 0},
        })
        self.assertEqual([read[0] for read in client.reads], ["child_balances"])

    def test_pre_migration_fallback_reads_complete_history(self):
        for code in ("PGRST205", "42P01"):
            with self.subTest(code=code):
                client = FakeClient({
                    "points_log": [
                        {"id": i, "date_added": "2026-10-31", "child_name": "A", "points_change": 1}
                        for i in range(1012)
                    ],
                    "money_log": [
                        {"id": 1, "date_added": "2026-10-31", "child_name": "B", "amount": 3.5}
                    ],
                }, balance_error=code)
                balances, installed = fetch_balances(client)
                self.assertFalse(installed)
                self.assertEqual(balances["A"], {"points": 1012, "money": 0})
                self.assertEqual(balances["B"], {"points": 0, "money": 3.5})

    def test_access_or_server_errors_do_not_look_like_empty_balances(self):
        for code in ("42501", "PGRST301", "500"):
            with self.subTest(code=code):
                client = FakeClient({}, balance_error=code)
                with self.assertRaises(APIError):
                    fetch_balances(client)
                self.assertEqual(len(client.reads), 1)

    def test_admin_fetches_only_latest_twenty_rows(self):
        for table in ("points_log", "money_log"):
            with self.subTest(table=table):
                rows = [{"id": i, "date_added": "2026-10-31"} for i in range(1012)]
                client = FakeClient({table: rows})
                recent = fetch_recent_log_rows(client, table)
                self.assertEqual([row["id"] for row in recent], list(range(1011, 991, -1)))
                self.assertEqual(client.reads, [(table, 0, 20)])

    def test_invalid_recent_limit(self):
        with self.assertRaises(ValueError):
            fetch_recent_log_rows(FakeClient({}), "points_log", limit=0)


if __name__ == "__main__":
    unittest.main()
