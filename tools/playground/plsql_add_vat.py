import oracledb

from app.common.config import get_settings

CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION add_vat(p_amount IN NUMBER, p_rate_pct IN NUMBER) RETURN NUMBER IS
BEGIN
  RETURN ROUND(p_amount * (1 + p_rate_pct / 100), 2);
END;
"""

settings = get_settings()

with oracledb.connect(
    user=settings.oracle_user, password=settings.oracle_password, dsn=settings.oracle_dsn
) as connection:
    with connection.cursor() as cursor:
        cursor.execute(CREATE_FUNCTION)

        cursor.execute("SELECT add_vat(1000, 16) FROM dual")
        print("Called from SQL:", cursor.fetchone()[0])

        print("Called from Python:", cursor.callfunc("add_vat", oracledb.NUMBER, [1000, 16]))

        cursor.execute("DROP FUNCTION add_vat")
