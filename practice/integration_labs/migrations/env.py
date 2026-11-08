from alembic import context

from practice.integration_labs.database import Base, make_engine

engine = make_engine(context.config.get_main_option("sqlalchemy.url"))
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
