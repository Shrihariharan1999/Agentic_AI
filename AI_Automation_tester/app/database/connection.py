"""
Database Connection
===================
Sets up the SQLAlchemy connection to MySQL.

WHAT IS SQLAlchemy?
SQLAlchemy is a Python ORM (Object-Relational Mapper).
It lets you interact with a database using Python objects and methods
instead of writing raw SQL queries.

  Without ORM:  cursor.execute("INSERT INTO test_runs (id, url) VALUES (?, ?)", [id, url])
  With ORM:     session.add(TestRunRecord(id=id, target_url=url)); session.commit()

WHAT IS A SESSION?
A session is a "unit of work" — a context in which database operations happen.
Think of it like a shopping cart: you add items (changes), then checkout (commit).
If something goes wrong, you can empty the cart (rollback) without any changes being saved.

CONNECTION POOLING:
SQLAlchemy maintains a POOL of database connections.
Instead of opening a new TCP connection for every query (which is slow),
it reuses existing connections from the pool. create_engine() manages this.
"""

from sqlalchemy import create_engine          # Creates the database engine (connection manager)
from sqlalchemy.orm import DeclarativeBase    # Base class for all ORM table models
from sqlalchemy.orm import sessionmaker       # Factory that produces database sessions

from app.config.settings import settings     # Our Pydantic settings (reads .env)


# -------------------------------------------------------------------------
# DECLARATIVE BASE
# All ORM model classes (in models.py) must inherit from this Base.
# SQLAlchemy uses it to track which Python classes map to which tables.
# When you call Base.metadata.create_all(engine), it creates all tables
# that have been defined by inheriting from this Base.
# -------------------------------------------------------------------------
class Base(DeclarativeBase):
    """
    The base class for all SQLAlchemy ORM table models.

    Every model in database/models.py will inherit from this class:
        class TestRunRecord(Base):  ← "I am a database table"
            __tablename__ = "test_runs"
            ...
    """
    pass  # No additional logic needed — DeclarativeBase handles everything


# -------------------------------------------------------------------------
# DATABASE ENGINE
# The engine is the core of SQLAlchemy — it manages the database connection pool.
#
# settings.mysql_url builds the connection string:
#   "mysql+pymysql://root:password@localhost:3306/ai_web_tester"
#    └──────┬───────┘ └──┬──┘ └──┬──┘ └──────┬──┘ └─┬─┘ └───────┬───────┘
#           │             │       │            │      │           │
#      dialect+driver   user  password       host   port      database
#
# echo=False: don't print SQL statements to the console
# Set echo=True during debugging to see every SQL query executed
#
# pool_pre_ping=True: before using a connection from the pool,
# send a "ping" to check it's still alive (handles server disconnects)
#
# pool_recycle=3600: after 1 hour, replace old connections in the pool
# (prevents "MySQL server has gone away" errors on long-running apps)
# -------------------------------------------------------------------------
engine = create_engine(
    settings.mysql_url,   # The full database connection URL
    echo=False,           # Set to True to debug SQL queries
    pool_pre_ping=True,   # Check connection health before using it
    pool_recycle=3600,    # Recycle connections every hour
)

# -------------------------------------------------------------------------
# SESSION FACTORY
# sessionmaker() creates a FACTORY that produces Session objects.
# Every time you call SessionLocal(), you get a fresh database session.
#
# autocommit=False: Changes are NOT saved until you explicitly call session.commit()
#   (This gives you a chance to rollback if something fails mid-operation)
#
# autoflush=False: Changes are NOT sent to the DB until commit
#   (Better performance for bulk inserts — batches multiple changes into one flush)
#
# bind=engine: All sessions from this factory connect through our engine
# -------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,  # Explicit commit required to save changes
    autoflush=False,   # Don't auto-sync with DB before queries
    bind=engine,       # Use our configured engine
)


def get_db():
    """
    Generator function that provides a database session for the duration of a request.

    HOW PYTHON GENERATORS WORK HERE:
    A generator function uses 'yield' instead of 'return'.
    The caller gets the yielded value, does their work, then the generator continues.
    The 'finally' block runs when the caller is done, even if an exception occurred.

    FASTAPI DEPENDENCY INJECTION:
    FastAPI uses this pattern for "dependencies" — it calls get_db(),
    uses the yielded session for the request, then the finally block cleans up:

        @router.get("/test-runs")
        def list_runs(db: Session = Depends(get_db)):
            return db.query(TestRunRecord).all()

    Yields:
        Session: An active SQLAlchemy database session

    The session is automatically closed after the caller finishes.
    """

    # Create a new session from the factory
    db = SessionLocal()

    try:
        yield db          # Give the session to whoever called get_db()
                          # The code INSIDE the `with` or function using this runs here

    finally:
        db.close()        # ALWAYS close the session — even if an exception occurred
                          # Closing returns the connection back to the pool


def create_tables() -> None:
    """
    Creates all database tables defined by ORM models in models.py.

    IMPORTANT:
    - This function is IDEMPOTENT — safe to call multiple times
    - It will NOT drop or modify existing tables
    - It only creates tables that don't exist yet

    IN PRODUCTION:
    Use Alembic for proper database migrations instead of create_all().
    create_all() can't handle schema changes (adding/removing columns).
    Alembic generates versioned migration scripts for that.

    This is called at application startup in main.py.
    """

    # This import triggers the ORM model class definitions
    # SQLAlchemy's Base.metadata tracks all models that inherit from Base
    # Without this import, Base.metadata would be empty and no tables would be created
    from app.database import models  # noqa: F401  ← "noqa" silences "unused import" lint warning

    # Create all tables registered in Base.metadata
    # checkfirst=True is implied — it won't fail if tables already exist
    Base.metadata.create_all(bind=engine)
