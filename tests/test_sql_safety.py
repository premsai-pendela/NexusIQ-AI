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
        forbidden_keywords = [
            "DELETE",
            "DROP",
            "TRUNCATE",
            "UPDATE",
            "INSERT",
            "ALTER",
            "CREATE",
        ]

        for keyword in forbidden_keywords:
            with self.subTest(keyword=keyword):
                query = f"SELECT 1; {keyword} TABLE unsafe_table;"

                is_safe, error = self.agent._validate_query(query)

                self.assertFalse(is_safe)
                self.assertEqual(error, f"Forbidden keyword: {keyword}")

    def test_blocks_create_after_select_in_multi_statement_query(self):
        query = "SELECT 1; CREATE TABLE unsafe_table (id int);"

        is_safe, error = self.agent._validate_query(query)

        self.assertFalse(is_safe)
        self.assertEqual(error, "Forbidden keyword: CREATE")


if __name__ == "__main__":
    unittest.main()
