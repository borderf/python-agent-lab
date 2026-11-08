"""Reproduce optimistic concurrency using two real PostgreSQL sessions."""
import os
from uuid import uuid4

import psycopg
from psycopg import sql


def main():
    dsn = os.getenv("LAB_POSTGRES_DSN")
    if not dsn:
        raise SystemExit("Set LAB_POSTGRES_DSN to an isolated PostgreSQL teaching database")
    schema = sql.Identifier("course_" + uuid4().hex)
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
        try:
            admin.execute(sql.SQL("CREATE TABLE {}.tasks (id text primary key, version int not null)").format(schema))
            admin.execute(sql.SQL("INSERT INTO {}.tasks VALUES ('T1', 7)").format(schema))
            with psycopg.connect(dsn) as first, psycopg.connect(dsn) as second:
                read = sql.SQL("SELECT version FROM {}.tasks WHERE id='T1'").format(schema)
                assert first.execute(read).fetchone() == second.execute(read).fetchone() == (7,)
                update = sql.SQL("UPDATE {}.tasks SET version=version+1 WHERE id='T1' AND version=7").format(schema)
                assert first.execute(update).rowcount == 1
                first.commit()
                assert second.execute(update).rowcount == 0
                second.commit()
                assert second.execute(read).fetchone() == (8,)
            print("PASS: two real sessions read v7, one conditional update succeeds, one detects conflict")
        finally:
            # Only the unique schema created by this invocation is removed.
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(schema))


if __name__ == "__main__":
    main()
