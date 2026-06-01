import unittest

from agents.sql_agent import SQLAgent


class SQLSafetyValidationTest(unittest.TestCase):
    def setUp(self):
        self.agent = SQLAgent.__new__(SQLAgent)

    def test_allows_safe_identifier_containing_forbidden_word(self):
        query = """
        SELECT COUNT(sc.id) AS total_support_cases
        FROM support_cases AS sc
        WHERE sc.created_at >= '2024-10-01'
          AND sc.created_at <= '2024-12-31';
        """

        is_safe, error = self.agent._validate_query(query)

        self.assertTrue(is_safe)
        self.assertEqual(error, "")

    def test_allows_safe_identifiers_containing_forbidden_word_stems(self):
        safe_identifiers = [
            "created_at",
            "updated_at",
            "deleted_flag",
            "dropoff_rate",
            "truncated_label",
            "inserted_by",
            "altered_status",
            "customer_create_date",
            "last_update_time",
            "predelete_status",
            "postinsert_metric",
            "drop_ship_count",
        ]

        for identifier in safe_identifiers:
            with self.subTest(identifier=identifier):
                query = f"SELECT sc.{identifier} FROM support_cases AS sc LIMIT 1;"

                is_safe, error = self.agent._validate_query(query)

                self.assertTrue(is_safe)
                self.assertEqual(error, "")

    def test_blocks_real_forbidden_statements(self):
        forbidden_queries = [
            ("DELETE", "DELETE FROM unsafe_table"),
            ("DROP", "DROP TABLE unsafe_table"),
            ("TRUNCATE", "TRUNCATE TABLE unsafe_table"),
            ("UPDATE", "UPDATE unsafe_table SET id = 1"),
            ("INSERT", "INSERT INTO unsafe_table (id) VALUES (1)"),
            ("ALTER", "ALTER TABLE unsafe_table ADD COLUMN name text"),
            ("CREATE", "CREATE TABLE unsafe_table (id int)"),
        ]

        for keyword, query in forbidden_queries:
            with self.subTest(keyword=keyword):
                is_safe, error = self.agent._validate_query(query)

                self.assertFalse(is_safe)
                self.assertEqual(error, f"Forbidden statement type: {keyword}")

    def test_blocks_create_after_select_in_multi_statement_query(self):
        query = "SELECT 1; CREATE TABLE unsafe_table (id int);"

        is_safe, error = self.agent._validate_query(query)

        self.assertFalse(is_safe)
        self.assertEqual(error, "Forbidden statement type: CREATE")

    def test_allows_safe_cte_query(self):
        query = """
        WITH q4 AS (
            SELECT region, SUM(revenue) AS total_revenue
            FROM sales_transactions
            WHERE created_at >= '2024-10-01'
            GROUP BY region
        )
        SELECT region, total_revenue
        FROM q4
        ORDER BY total_revenue DESC
        LIMIT 5;
        """

        is_safe, error = self.agent._validate_query(query)

        self.assertTrue(is_safe)
        self.assertEqual(error, "")

    def test_allows_forbidden_words_inside_string_literals(self):
        query = "SELECT 'CREATE TABLE is only text' AS note, created_at FROM sales_transactions LIMIT 1;"

        is_safe, error = self.agent._validate_query(query)

        self.assertTrue(is_safe)
        self.assertEqual(error, "")

    def test_blocks_multiple_read_only_statements(self):
        query = "SELECT 1; SELECT 2;"

        is_safe, error = self.agent._validate_query(query)

        self.assertFalse(is_safe)
        self.assertEqual(error, "Only one SQL statement allowed")

    def test_blocks_non_select_command(self):
        query = "SHOW TABLES;"

        is_safe, error = self.agent._validate_query(query)

        self.assertFalse(is_safe)
        self.assertEqual(error, "Only SELECT or WITH queries allowed")


if __name__ == "__main__":
    unittest.main()
