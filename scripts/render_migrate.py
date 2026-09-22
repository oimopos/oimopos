"""Initialize an empty database, then apply only unapplied migrations."""
import os
from pathlib import Path
import subprocess

import psycopg

root = Path(__file__).resolve().parent
if not (root / "database").exists():
    root = root.parent
url = os.environ["DATABASE_URL"]
parameters = psycopg.conninfo.conninfo_to_dict(url)
env = dict(os.environ)
for parameter, variable in {"host": "PGHOST", "port": "PGPORT", "dbname": "PGDATABASE", "user": "PGUSER", "password": "PGPASSWORD", "sslmode": "PGSSLMODE", "connect_timeout": "PGCONNECT_TIMEOUT"}.items():
    if parameter in parameters:
        env[variable] = parameters[parameter]
with psycopg.connect(url, autocommit=True) as connection:
    # Serialize deploys without placing credentials in the command line.
    connection.execute("SELECT pg_advisory_lock(783619402)")
    try:
        initialized = connection.execute("SELECT to_regclass('public.branches') IS NOT NULL").fetchone()[0]
        if not initialized:
            subprocess.run(["psql", "-X", "-v", "ON_ERROR_STOP=1", "-f", str(root / "database/init/001_schema.sql")], env=env, check=True)
        subprocess.run(["psql", "-X", "-v", "ON_ERROR_STOP=1", "-f", str(root / "database/migrations/apply.sql")], env=env, check=True)
    finally:
        connection.execute("SELECT pg_advisory_unlock(783619402)")
print("Database migrations completed")
