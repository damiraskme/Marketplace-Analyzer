from pathlib import Path

import oracledb

from app.common.db import connect

DB_DIR = Path(__file__).resolve().parents[1] / "db"
MIGRATIONS_DIR = DB_DIR / "migrations"
PACKAGES_DIR = DB_DIR / "packages"

CREATE_TRACKING_TABLE = """
CREATE TABLE schema_migrations (
  name VARCHAR2(200) PRIMARY KEY,
  applied_at TIMESTAMP DEFAULT SYS_EXTRACT_UTC(SYSTIMESTAMP) NOT NULL
)
"""

RECOMPILE_INVALID = "BEGIN DBMS_UTILITY.COMPILE_SCHEMA(schema => USER, compile_all => FALSE); END;"

SELECT_COMPILE_ERRORS = """
SELECT name, type, line, text
  FROM user_errors
 WHERE attribute = 'ERROR'
 ORDER BY name, type, sequence
"""

TABLE_ALREADY_EXISTS = 955


def split_statements(text: str) -> list[str]:
    statements = []
    current = []
    for line in text.splitlines():
        if line.strip() == "/":
            statement = "\n".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(line)
    return statements


def run_file(cursor: oracledb.Cursor, file: Path) -> int:
    statements = split_statements(file.read_text(encoding="utf-8"))
    for number, statement in enumerate(statements, start=1):
        try:
            cursor.execute(statement)
        except oracledb.DatabaseError as error:
            cursor.connection.rollback()
            raise SystemExit(f"Failed in {file.name}, statement {number}: {error}")
    return len(statements)


def ensure_tracking_table(cursor: oracledb.Cursor) -> None:
    try:
        cursor.execute(CREATE_TRACKING_TABLE)
    except oracledb.DatabaseError as error:
        if error.args[0].code != TABLE_ALREADY_EXISTS:
            raise


def apply_migrations(cursor: oracledb.Cursor) -> None:
    ensure_tracking_table(cursor)
    cursor.execute("SELECT name FROM schema_migrations")
    applied = {row[0] for row in cursor}

    pending = [f for f in sorted(MIGRATIONS_DIR.glob("*.sql")) if f.name not in applied]
    if not pending:
        print("No new migrations, the tables are up to date.")
        return

    for file in pending:
        count = run_file(cursor, file)
        cursor.execute("INSERT INTO schema_migrations (name) VALUES (:1)", [file.name])
        cursor.connection.commit()
        print(f"Applied {file.name} ({count} statements)")


def compile_packages(cursor: oracledb.Cursor) -> None:
    for file in sorted(PACKAGES_DIR.glob("*.sql")):
        if run_file(cursor, file):
            print(f"Compiled {file.name}")

    cursor.execute(RECOMPILE_INVALID)
    cursor.execute(SELECT_COMPILE_ERRORS)
    errors = cursor.fetchall()
    if errors:
        for name, kind, line, text in errors:
            print(f"{kind} {name}, line {line}: {text.strip()}")
        raise SystemExit("PL/SQL compilation failed.")


def main() -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            apply_migrations(cursor)
            compile_packages(cursor)


if __name__ == "__main__":
    main()
