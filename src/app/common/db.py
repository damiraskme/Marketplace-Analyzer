import oracledb

from app.common.config import get_settings

oracledb.defaults.fetch_decimals = True


def connect() -> oracledb.Connection:
    settings = get_settings()
    return oracledb.connect(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=settings.oracle_dsn,
    )
