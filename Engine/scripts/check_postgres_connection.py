from sqlalchemy import text
from tria_engine.core.database import engine

with engine.connect() as conn:
    version = conn.execute(text("SELECT version()")).scalar_one()
    table_count = conn.execute(text("""
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'public'
    """)).scalar_one()
    print("DATABASE CONNECTION: OK")
    print("PostgreSQL:", version)
    print("Public tables:", table_count)
