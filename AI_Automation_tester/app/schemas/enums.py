from enum import Enum


class TestRunStatus(str, Enum):
    CREATED = "created"
    DISCOVERING = "discovering"
    PLANNING = "planning"
    TEST_GENERATION = "test_generation"
    HUMAN_REVIEW = "human_review"
    EXECUTING = "executing"
    WAITING_FOR_HUMAN = "waiting_for_human"
    ANALYZING_FAILURE = "analyzing_failure"
    HEALING = "healing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestCaseStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class FailureType(str, Enum):
    APPLICATION = "application"
    TEST = "test"
    ENVIRONMENT = "environment"
    NETWORK = "network"
    BROWSER = "browser"
    MCP = "mcp"
    UNKNOWN = "unknown"


class HumanAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    CONTINUE = "continue"
    CANCEL = "cancel"