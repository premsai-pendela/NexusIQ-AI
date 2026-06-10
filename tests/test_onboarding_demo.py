"""Tests for the onboarding demo's pure helpers."""

import unittest

from context.business_context import BusinessContextEntry
from scripts.onboarding_demo import mask_database_url, summarize_glossary


class MaskDatabaseUrlTest(unittest.TestCase):
    def test_masks_credentials_and_host(self):
        url = "postgresql://user:secretpass@db.example.supabase.co:5432/postgres"
        masked = mask_database_url(url)
        self.assertNotIn("secretpass", masked)
        self.assertNotIn("db.example.supabase.co", masked)
        self.assertTrue(masked.startswith("postgresql://"))

    def test_empty_url_safe(self):
        self.assertEqual(mask_database_url(""), "(not configured)")


class SummarizeGlossaryTest(unittest.TestCase):
    def test_groups_by_category(self):
        entries = [
            BusinessContextEntry(id="net_revenue", term="net revenue", definition="d", category="metric"),
            BusinessContextEntry(id="fiscal_year", term="fiscal year", definition="d", category="policy"),
            BusinessContextEntry(id="aov", term="aov", definition="d", category="metric"),
        ]
        summary = summarize_glossary(entries)
        self.assertEqual(summary["entries"], 3)
        self.assertEqual(summary["by_category"]["metric"], ["aov", "net_revenue"])
        self.assertEqual(summary["by_category"]["policy"], ["fiscal_year"])


if __name__ == "__main__":
    unittest.main()
