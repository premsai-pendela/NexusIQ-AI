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
The isolated `validated_v2` pilot flow has locally generated and indexed five
new-period headline-evidence PDFs, with exact PDF-to-SQL and index-to-SQL
checks passing against staging. These ignored local artifacts are not part of
production RAG, so the expansion is not yet a production dataset.

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

## Pilot Financial PDF Generator

`database.generate_pilot_financial_pdfs` is a document-alignment gate for the
loaded `enterprise_pilot_v1` dataset. It reads only the generated
`nexusiq_expansion_staging.sales_transactions` table, scoped to that dataset
ID. It never queries the combined view that can
include public live rows.

The generator covers only new reporting periods: FY 2021, FY 2022, FY 2023,
FY 2025, and H1 2026. It rejects any reporting period that overlaps 2024. Its
CLI output destination is fixed to the repository staging directory; it
validates all period results and renders temporary documents before atomically
publishing the completed directory, refusing any existing destination.

Inspect the output plan and read-only query templates locally:

```bash
python -m database.generate_pilot_financial_pdfs plan
python -m database.generate_pilot_financial_pdfs sql
```

No database connection or document write occurs in either command. A later
reviewed generation run must use the explicit staging-only acknowledgement:

```bash
python -m database.generate_pilot_financial_pdfs generate \
  --execute \
  --confirm-staging-only GENERATE_PILOT_PDFS_FROM_STAGING_ONLY
```

Generated files go to
`data/pdfs_staging/enterprise_pilot_v1/validated_v2/01_financial/`; they are deliberately
outside the production-aligned `data/pdfs/` archive and must not enter RAG
until numeric SQL-to-PDF evaluation passes. These pilot documents publish only
the transaction-count and total-revenue facts that are checked exactly.
Only the `validated_v2` path may be indexed; any earlier pilot PDF output is
superseded and must remain outside retrieval.

## Isolated Pilot RAG and Evaluation

`database.pilot_document_phase` keeps document ingestion and PDF-to-SQL
validation isolated from the current production retrieval collection. It
accepts only the five staged pilot financial PDFs and writes only to
`data/chroma_staging/enterprise_pilot_v1/validated_v2/financial_documents/` using the
collection `nexusiq_pilot_financial_docs_enterprise_pilot_v1_validated_v2`.

Review both plans without accessing Chroma or Supabase:

```bash
python -m database.pilot_document_phase plan-ingestion
python -m database.pilot_document_phase plan-alignment
python -m database.pilot_document_phase plan-index-alignment
```

Read-only validation first compares every fact published in the staged PDFs
with direct `nexusiq_expansion_staging.sales_transactions` aggregates:

```bash
python -m database.pilot_document_phase validate-alignment \
  --execute-remote \
  --confirm-staging-only VALIDATE_PILOT_PDFS_AGAINST_STAGING_SQL_ONLY
```

Isolated ingestion enforces that same PDF-to-SQL validation before it writes
anything, and atomically publishes a new staged index only after all five
documents are successfully embedded:

```bash
python -m database.pilot_document_phase ingest \
  --execute \
  --confirm-staging-only INGEST_PILOT_PDFS_TO_ISOLATED_STAGING_ONLY \
  --confirm-pdf-validation VALIDATE_PILOT_PDFS_AGAINST_STAGING_SQL_ONLY
```

The final evidence gate compares values retrieved from the isolated staged
index with the same direct staging SQL aggregates:

```bash
python -m database.pilot_document_phase validate-index-alignment \
  --execute-remote \
  --confirm-staging-only VALIDATE_PILOT_STAGING_INDEX_AGAINST_STAGING_SQL_ONLY
```

This phase does not read or update the production PDF archive, production
`data/chroma_db/` index, or the live `nexusiq_docs` collection. The current
production RAG experience remains untouched unless every staged validation
check passes and a separate promotion decision is made.

## Controlled Pilot Demo Mode

The application exposes the validated pilot through a separate Fusion Agent
workspace rather than switching the production data source. The live workspace
still defaults to the 2024 Supabase table and `nexusiq_docs`. The pilot
workspace is locked to the read-only combined staging view for SQL and the
`nexusiq_pilot_financial_docs_enterprise_pilot_v1_validated_v2` collection for
RAG. It does not permit live web routing or production-document retrieval.

Because `data/pdfs_staging/` and `data/chroma_staging/` are intentionally
ignored, the EC2 deploy path provisions them into separate persistent Docker
volumes before replacing the running app container. The deploy step uses the
same guarded PDF generation, isolated ingestion, and SQL validation commands;
later deployments validate existing evidence again. It refuses automatic
overwrite if only a partial artifact set exists. No production-promotion
decision is implied by enabling this demo workspace.
