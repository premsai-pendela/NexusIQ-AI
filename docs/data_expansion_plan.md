# NexusIQ Enterprise Data Expansion

## Goal

Grow the portfolio dataset beyond the validated 2024 Supabase baseline without
silently replacing deployed truth. The expansion represents a US multi-channel
retailer from 2021 through June 2026 and adds operational facts needed for
forecasting, segmentation, return analysis, and evidence-backed AI answers.

## Safety Boundary

`database.generate_enterprise_expansion` is an offline staging generator. It
does not import application settings, does not connect to `DATABASE_URL`, and
does not insert into the live `sales_transactions`, `customers`, or
`inventory` tables.

Generated CSV files are written under `data/expansion/`, which is ignored by
Git. Each dataset includes a `manifest.json` with expected row counts and KPI
totals. Any future Supabase loader must load into a separate
`nexusiq_expansion_staging` namespace, validate it, and require a reviewed
promotion step before it can affect application queries.

The current 100,000 live 2024 sales transactions are preserved exactly because
the existing PDFs and public demo answers validate against them. The portfolio
extract generates 4,900,000 additional transaction rows outside 2024; a later
reviewed staging load combines those rows with the untouched 2024 baseline to
reach the 5,000,000-row unified target.

## Portfolio Profile

| Table | Rows | Why It Exists |
| --- | ---: | --- |
| `business_events` | 6 | Timeline anchors for causal analysis and RAG documents |
| `stores` | 100 | Geographic and store-format comparisons |
| `vendors` | 250 | Supplier delay and risk questions |
| `products` | 5,000 | SKU performance and recommendation features |
| `customers` | 250,000 | Segmentation, loyalty, and churn modeling |
| `promotions` | 240 | Campaign lift and discount leakage |
| `sales_transactions` | 5,000,000 total: 100,000 preserved + 4,900,000 generated | Multi-year revenue and demand history |
| `returns` | Derived | Refund and quality-root-cause analysis |
| `inventory_snapshots` | 1,200,000 | Stockout and replenishment forecasting |
| `support_cases` | 80,000 | Text classification and sentiment use cases |

## Timeline

| Period | Event | Questions It Supports |
| --- | --- | --- |
| 2021 | National ecommerce rollout | Channel migration and regional adoption |
| 2022 | Appliance supplier delays | Stockouts, lead times, and margin pressure |
| 2023 | Loyalty program launch | Retention and customer segment performance |
| 2024 | Validated demo baseline | SQL-to-PDF cross-validation continuity |
| 2025 | Competitor electronics campaign | Pricing pressure and margin response |
| Jan-Jun 2026 | Demand forecasting pilot | Forecasting and inventory intervention |

## Commands

Preview the full planned dataset without writing any files:

```bash
python -m database.generate_enterprise_expansion plan --profile portfolio
```

Generate a smaller linked pilot extract for validation:

```bash
python -m database.generate_enterprise_expansion generate --profile pilot
python -m database.generate_enterprise_expansion validate --dataset-dir data/expansion/enterprise_pilot_v1
```

After the staging workflow and validation checks exist, generate the
portfolio-scale extracts:

```bash
python -m database.generate_enterprise_expansion generate --profile portfolio
```

Never load generated extracts directly into the current production tables.

## SQL-to-PDF Alignment Gate

The generated extracts are internally validated, but they do not by themselves
prove that future documents agree with future SQL. The application can only
claim SQL-to-PDF alignment after this release gate completes:

1. Validate the generated extract with the `validate` command. It fails if any
   generated sales row enters the protected 2024 period.
2. Load new rows into a separate Supabase staging namespace and copy the live
   2024 baseline into the staged unified view without changing its values.
3. Re-run the 2024 truth queries against both the live baseline and staged
   unified view. Counts and dollar amounts must match exactly for 2024.
4. Generate any new 2021-2023 or 2025-2026 financial PDFs from staged SQL
   aggregates, never from manually typed numbers.
5. Ingest those generated PDFs into a staged RAG collection and run numeric
   SQL-to-PDF golden evaluations for each published reporting period.
6. Switch application queries to the expanded dataset only after every required
   metric passes; otherwise leave the current Supabase source active.

Current status: existing 2024 PDFs are backed by the live Supabase baseline.
No new-period PDFs have been generated yet, so the expansion is validated
staging data, not yet a document-aligned production dataset.

## Staging Loader

The loader in `database.load_enterprise_staging` accepts only a validated
generated package and writes only into the isolated
`nexusiq_expansion_staging` schema. Its combined sales view reads
`public.sales_transactions` for the preserved baseline; it does not update,
delete, or replace public tables.

Review the pilot load plan and generated DDL locally first:

```bash
python -m database.load_enterprise_staging plan --dataset-dir data/expansion/enterprise_pilot_v1
python -m database.load_enterprise_staging ddl --dataset-dir data/expansion/enterprise_pilot_v1
```

A staging write requires an explicit acknowledgement token:

```bash
python -m database.load_enterprise_staging execute \
  --dataset-dir data/expansion/enterprise_pilot_v1 \
  --execute \
  --confirm-staging-only LOAD_INTO_NEXUSIQ_EXPANSION_STAGING_ONLY
```

Always load and verify the 23 MB pilot before attempting the 697 MB portfolio
extract. A dataset ID is immutable after loading; generate a new dataset ID
for another trial instead of overwriting staged facts.
