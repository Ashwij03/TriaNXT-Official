# Connect Tria Engine to the existing CTMS PostgreSQL database

1. Copy `.env.postgres.example` to `.env`.
2. Replace `<DB_USER>`, `<DB_PASSWORD>`, `<DB_HOST>`, `<DB_PORT>`, and `<DB_NAME>` with the values used when the CTMS database was created.
3. Keep `USE_POSTGRES=true`.
4. Install dependencies:
   `pip install -r tria_engine/requirements/base.txt`
5. From the backend root, test the connection:
   `python scripts/check_postgres_connection.py`
6. Start the API:
   `uvicorn tria_engine.main:app --reload`

Important: this backend is being connected to an already-created PostgreSQL schema. Do not run the initial Alembic `70f65d974cc7_initial_schema_parity` migration against that database: it contains `op.create_table(...)` calls for tables that already exist. The CTMS SQL package is the schema source for this database.
