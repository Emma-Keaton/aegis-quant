"""Generate idempotent PostgreSQL DDL from SQLAlchemy metadata.

Emits `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` so the output
can be re-applied to Supabase any number of times without error.

`CreateTable` deliberately omits Python-side column defaults, because the
application supplies them. That is correct for `create_all` at runtime but wrong
for a schema an operator applies by hand: a `NOT NULL` column with no server
default rejects any insert that omits it. Defaults are therefore rendered here.
"""

from sqlalchemy.dialects import postgresql


def _render_default(column) -> str | None:
    """Server-side DEFAULT literal for a column, or None."""
    if column.server_default is not None:
        return str(column.server_default.arg)

    default = column.default
    if default is None:
        return None

    if default.is_callable:
        # Callables the application would otherwise supply. Rendered as the
        # equivalent database function so the schema works for a raw insert.
        name = getattr(default.arg, "__name__", "")
        if name in {"uuid4", "uuid1"}:
            return "gen_random_uuid()"
        if name in {"utcnow", "now", "utc"}:
            return "now()"
        return None

    if default.is_clause_element:
        return str(default.arg)

    if default.is_scalar:
        value = default.arg
    else:  # pragma: no cover - defensive
        return None

    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return None


def _create_table(table, dialect) -> str:
    """CreateTable, with DEFAULT clauses injected where the ORM has none.

    Processed line by line: the compiler pads each column line with a trailing
    space before the comma (``NOT NULL, \\n``), so searching for a literal
    separator in the joined string is unreliable.
    """
    from sqlalchemy.schema import CreateTable

    ddl = str(CreateTable(table, if_not_exists=True).compile(dialect=dialect))
    lines = ddl.split("\n")

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or "DEFAULT" in stripped.upper():
            continue
        name = stripped.split(" ", 1)[0].strip()
        column = table.columns.get(name)
        if column is None:
            continue
        rendered = _render_default(column)
        if rendered is None:
            continue
        # Preserve the column name, type, and constraints; append the default
        # after them, before any trailing comma.
        body = line.rstrip()
        if body.endswith(","):
            body = body[:-1].rstrip()
        indent = line[: len(line) - len(line.lstrip())]
        lines[index] = f"{indent}{body} DEFAULT {rendered},"

    return "\n".join(lines)


def generate(metadata, dialect_name: str = "postgresql") -> str:
    dialect = postgresql.dialect()
    tables = sorted(metadata.tables.values(), key=lambda t: t.name)
    lines = [
        "-- Generated from SQLAlchemy metadata. Do not hand-edit.",
        "--",
        "-- Idempotent: every statement is IF NOT EXISTS, so this can be re-applied",
        "-- to an existing database any number of times.",
        "",
    ]
    for table in tables:
        lines.append(_create_table(table, dialect).strip() + ";")
        lines.append("")

    for table in tables:
        for index in sorted(table.indexes, key=lambda i: i.name or ""):
            from sqlalchemy.schema import CreateIndex

            ddl = str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect)).strip()
            lines.append(ddl + ";")
        lines.append("")
    return "\n".join(lines)