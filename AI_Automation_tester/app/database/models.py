"""
Database ORM Models
===================
These Python classes define the MySQL database table structure.

HOW ORM MODELS WORK:
Each class here represents ONE database table.
Each class attribute (with mapped_column) represents ONE column in that table.

SQLAlchemy reads these class definitions and:
  1. Knows what tables exist (for create_tables())
  2. Maps Python objects ↔ database rows automatically
  3. Handles INSERT, SELECT, UPDATE, DELETE through ORM methods

RELATIONSHIP BETWEEN TABLES:
  TestRunRecord (1) ─────────────────────────→ (many) TestCaseRecord
  One test run can have many test case results

DATABASE SCHEMA OVERVIEW:
  test_runs          → stores the top-level run (URL, status, plan, summary)
  test_case_results  → stores each individual test case execution result
"""

import uuid                  # For generating UUID primary keys
from datetime import datetime  # For timestamp columns

from sqlalchemy import (
    JSON,         # Column type for storing JSON data (dicts, lists)
    Boolean,      # True/False column
    DateTime,     # Date + time column
    ForeignKey,   # Defines a foreign key constraint (link between tables)
    Integer,      # Integer column
    String,       # Variable-length string (VARCHAR in MySQL)
    Text,         # Unlimited-length text (TEXT in MySQL)
)
from sqlalchemy.orm import (
    Mapped,         # Type hint for ORM-mapped attributes
    mapped_column,  # Declares a column with its type and constraints
    relationship,   # Declares a relationship between two tables
)

from app.database.connection import Base  # The Base class all models must inherit from


class TestRunRecord(Base):
    """
    Stores a complete test run session from start to finish.

    A test run is created when a user provides a URL and says "test this."
    It tracks the entire workflow: discovery → planning → execution → summary.

    Maps to MySQL table: test_runs
    """

    # __tablename__ tells SQLAlchemy the actual MySQL table name
    __tablename__ = "test_runs"

    # -------------------------------------------------------------------------
    # PRIMARY KEY
    # We use UUID strings instead of auto-increment integers because:
    # - UUIDs are globally unique (safe for distributed systems)
    # - You can generate them in Python before saving to DB
    # - They don't leak information about record count
    #
    # String(36) → VARCHAR(36) in MySQL (a UUID is exactly 36 chars with dashes)
    # -------------------------------------------------------------------------
    id: Mapped[str] = mapped_column(
        String(36),                           # VARCHAR(36)
        primary_key=True,                     # This column is the table's primary key
        default=lambda: str(uuid.uuid4()),    # Auto-generate UUID when a new record is created
    )

    # The URL of the website being tested (e.g. "https://example.com")
    # String(2048) because URLs can be very long (query strings, encoded params)
    target_url: Mapped[str] = mapped_column(String(2048))

    # Which environment was tested: "development", "staging", "production"
    environment: Mapped[str] = mapped_column(
        String(100),
        default="development",  # Default value if not specified
    )

    # Current status of the run (maps to TestRunStatus enum values as strings)
    # e.g. "created", "discovering", "planning", "executing", "completed", "failed"
    status: Mapped[str] = mapped_column(String(50), default="created")

    # Optional: ID of the user who triggered this run
    # nullable=True means this column can be NULL in MySQL (no user tracking = NULL)
    user_id: Mapped[str] = mapped_column(String(100), nullable=True)

    # The discovered website structure stored as JSON
    # JSON type in SQLAlchemy → JSON column in MySQL (MySQL 5.7+)
    # This lets us store the entire WebsiteMap without creating separate tables
    website_map: Mapped[dict] = mapped_column(JSON, nullable=True)

    # The test plan (objective, strategy, test cases) stored as JSON
    # Storing as JSON is simpler than normalizing into many related tables
    test_plan: Mapped[dict] = mapped_column(JSON, nullable=True)

    # The Markdown summary report from the Summarizer agent
    # Text (not String) because Markdown reports can be very long
    final_summary: Mapped[str] = mapped_column(Text, nullable=True)

    # When was this record created?
    # default=datetime.utcnow: automatically set to current UTC time on INSERT
    # Note: utcnow is a function reference (not a call) — SQLAlchemy calls it
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    # When was this record last updated?
    # onupdate=datetime.utcnow: automatically updated to current time on UPDATE
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # -------------------------------------------------------------------------
    # RELATIONSHIP
    # This tells SQLAlchemy that one TestRunRecord can have many TestCaseRecords.
    # SQLAlchemy will automatically handle the SQL JOIN when you access .test_cases
    #
    # back_populates="test_run": TestCaseRecord also has a .test_run attribute
    # cascade="all, delete-orphan": if a TestRun is deleted, delete its TestCaseRecords too
    # -------------------------------------------------------------------------
    test_cases: Mapped[list["TestCaseRecord"]] = relationship(
        "TestCaseRecord",             # The related model class name (as a string)
        back_populates="test_run",    # The attribute name on the other side
        cascade="all, delete-orphan", # Delete child records when parent is deleted
    )


class TestCaseRecord(Base):
    """
    Stores the execution result of a single test case within a test run.

    One TestRunRecord has many TestCaseRecords (one per test case executed).

    Maps to MySQL table: test_case_results
    """

    __tablename__ = "test_case_results"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # -------------------------------------------------------------------------
    # FOREIGN KEY
    # This links each TestCaseRecord to its parent TestRunRecord.
    # ForeignKey("test_runs.id") → the `id` column in the `test_runs` table
    # ondelete="CASCADE" → if the parent TestRun is deleted, delete this record too
    # -------------------------------------------------------------------------
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("test_runs.id", ondelete="CASCADE"),  # Link to parent run
    )

    # The test case ID from the TestPlan schema (e.g. "TC-001")
    # This is NOT a foreign key to another table — it's a plan-level identifier
    test_case_id: Mapped[str] = mapped_column(String(100))

    # Execution status: "passed", "failed", "blocked", "running"
    status: Mapped[str] = mapped_column(String(50))

    # What the executor agent actually observed (free-form text)
    # e.g. "PASS: Login button clicked, user redirected to dashboard"
    actual_result: Mapped[str] = mapped_column(Text, nullable=True)

    # Failure details stored as JSON (only populated when status="failed")
    # Contains: failure_type, message, root_cause, confidence, recoverable
    failure_data: Mapped[dict] = mapped_column(JSON, nullable=True)

    # When did this specific test case start running?
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # When did this test case finish (passed or failed)?
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # -------------------------------------------------------------------------
    # BACK-REFERENCE RELATIONSHIP
    # This lets us access the parent TestRun from a TestCaseRecord:
    #   record = session.query(TestCaseRecord).first()
    #   print(record.test_run.target_url)  ← accesses parent automatically
    # -------------------------------------------------------------------------
    test_run: Mapped["TestRunRecord"] = relationship(
        "TestRunRecord",         # The parent model
        back_populates="test_cases",  # The matching attribute on TestRunRecord
    )
