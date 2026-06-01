# SQL Parser Guardrails

NexusIQ generates SQL from natural language, but generated SQL is never executed
blindly. Every query must pass a read-only safety gate first.

## Current Guardrail

The SQL Agent now uses `sqlglot` to parse generated SQL before execution.

Allowed:

- one SQL statement only
- read-only `SELECT`
- read-only `WITH ... SELECT`
- read-only set operations such as `UNION`, `EXCEPT`, and `INTERSECT`

Blocked:

- `DELETE`
- `DROP`
- `TRUNCATE`
- `UPDATE`
- `INSERT`
- `ALTER`
- `CREATE`
- multiple statements, even if they are both read-only
- unsupported commands such as `SHOW TABLES`
- SQL that cannot be parsed

## Why Parser-Based Guardrails Matter

The previous safety check was conservative text matching. That is useful as a
fallback, but it can confuse a dangerous command with a harmless identifier or
string.

Examples:

```sql
SELECT created_at FROM sales_transactions LIMIT 1;
```

This is safe even though `created_at` contains the word `create`.

```sql
SELECT 'CREATE TABLE is only text' AS note;
```

This is also safe because `CREATE TABLE` is inside a string literal.

```sql
SELECT 1; CREATE TABLE unsafe_table (id int);
```

This is unsafe because the second statement is a real schema-changing command.

`sqlglot` lets NexusIQ tell those cases apart by reading the SQL structure.

## Fallback Behavior

If `sqlglot` is unavailable, NexusIQ falls back to the older conservative
keyword validator. That fallback may block some harmless queries, but it keeps
the system safe rather than permissive.

## Test Coverage

Safety tests live in:

```text
tests/test_sql_safety.py
```

They cover:

- safe identifiers containing forbidden word stems
- safe CTEs
- forbidden words inside string literals
- write/schema statements
- multi-statement attacks
- unsupported non-SELECT commands
