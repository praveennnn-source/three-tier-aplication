import os
import mysql.connector
from mysql.connector import pooling

# Connection pool so the app tier doesn't open a fresh MySQL connection per request.
# In AWS this DB_HOST will point at your RDS endpoint, e.g.
# mydb.abc123xyz.us-east-1.rds.amazonaws.com

dbconfig = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "appuser"),
    "password": os.getenv("DB_PASSWORD", "changeme"),
    "database": os.getenv("DB_NAME", "appdb"),
}

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="app_pool",
            pool_size=5,
            **dbconfig
        )
    return _pool


def get_connection():
    return get_pool().get_connection()
