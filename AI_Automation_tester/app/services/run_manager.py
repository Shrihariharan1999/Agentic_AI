"""
Run Manager Service
===================
Centralized state manager and event broadcaster for active test runs.
Provides real-time state tracking, log streaming, and persistence fallback.
"""

from datetime import datetime
from typing import Any
from app.database.connection import SessionLocal
from app.database.repositories.test_runs import TestRunRepository


class RunManager:
    """
    Manages in-memory live state and syncs with MySQL DB.
    """

    def __init__(self):
        self._runs: dict[str, dict] = {}
        self._db_available: bool | None = None

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def _now_time(self) -> str:
        return datetime.utcnow().strftime("%H:%M:%S")

    def _dump(self, value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, list):
            return [self._dump(item) for item in value]
        if isinstance(value, dict):
            return {k: self._dump(v) for k, v in value.items()}
        return value

    def init_run(self, run_id: str, target_url: str, environment: str = "development") -> dict:
        data = {
            "id": run_id,
            "run_id": run_id,
            "target_url": target_url,
            "environment": environment,
            "status": "created",
            "current_stage": "Initializing",
            "progress_percent": 3,
            "website_map": None,
            "test_plan": None,
            "test_results": [],
            "healing_attempts": [],
            "errors": [],
            "logs": [],
            "final_summary": None,
            "html_report_path": None,
            "stats": {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "pass_rate": 0},
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        self._runs[run_id] = data
        self.add_log(run_id, f"Session initialized for target: {target_url}", level="info", stage="Initialization")

        if self._db_available is not False:
            try:
                with SessionLocal() as db:
                    repo = TestRunRepository(db)
                    repo.create(run_id=run_id, target_url=target_url, environment=environment)
                    self._db_available = True
            except Exception as e:
                self._db_available = False
                print(f"[RunManager Warning] Database persistence unavailable: {e}")

        return data

    def get_run(self, run_id: str) -> dict | None:
        run = self._runs.get(run_id)
        if run:
            return run

        # Fallback to database lookup
        if self._db_available is not False:
            try:
                with SessionLocal() as db:
                    repo = TestRunRepository(db)
                    record = repo.get_by_id(run_id)
                    if record:
                        self._db_available = True
                        return {
                            "id": record.id,
                            "run_id": record.id,
                            "target_url": record.target_url,
                            "environment": record.environment,
                            "status": record.status,
                            "current_stage": "Completed" if record.status == "completed" else record.status,
                            "progress_percent": 100 if record.status in ("completed", "failed", "cancelled") else 50,
                            "website_map": record.website_map,
                            "test_plan": record.test_plan,
                            "test_results": [
                                {
                                    "test_case_id": tc.test_case_id,
                                    "status": tc.status,
                                    "actual_result": tc.actual_result,
                                    "failure": tc.failure_data,
                                    "completed_at": tc.completed_at.isoformat() if tc.completed_at else None,
                                    "evidence": []
                                }
                                for tc in record.test_cases
                            ],
                            "healing_attempts": [],
                            "logs": [],
                            "final_summary": record.final_summary,
                            "html_report_path": f"/reports/report_{record.id}.html",
                            "stats": self._calculate_stats(record.test_plan, record.test_cases),
                            "created_at": record.created_at.isoformat() if record.created_at else self._now(),
                            "updated_at": record.updated_at.isoformat() if record.updated_at else self._now(),
                        }
            except Exception as e:
                self._db_available = False
                print(f"[RunManager Warning] Database lookup error: {e}")

        return None

    def list_runs(self, limit: int = 50) -> list[dict]:
        # Try database first
        if self._db_available is not False:
            try:
                with SessionLocal() as db:
                    repo = TestRunRepository(db)
                    records = repo.get_all(limit=limit)
                    self._db_available = True
                    return [
                        {
                            "id": r.id,
                            "run_id": r.id,
                            "target_url": r.target_url,
                            "environment": r.environment,
                            "status": r.status,
                            "created_at": r.created_at.isoformat() if r.created_at else self._now(),
                        }
                        for r in records
                    ]
            except Exception as e:
                self._db_available = False
                print(f"[RunManager Warning] Database history query error: {e}")

        # Fallback to memory
        sorted_runs = sorted(self._runs.values(), key=lambda r: r.get("created_at", ""), reverse=True)
        return [
            {
                "id": r["id"],
                "run_id": r["id"],
                "target_url": r["target_url"],
                "environment": r["environment"],
                "status": r["status"],
                "created_at": r["created_at"],
            }
            for r in sorted_runs[:limit]
        ]

    def add_log(self, run_id: str, message: str, level: str = "info", stage: str = ""):
        run = self._runs.get(run_id)
        if not run:
            return
        log_entry = {
            "time": self._now_time(),
            "stage": stage or run.get("current_stage", "Pipeline"),
            "level": level,
            "message": message,
        }
        run["logs"].append(log_entry)
        run["updated_at"] = self._now()
        # Keep logs manageable
        if len(run["logs"]) > 200:
            run["logs"] = run["logs"][-200:]

    def update_stage(self, run_id: str, status: str, stage: str, progress_percent: int):
        run = self._runs.get(run_id)
        if not run:
            return
        run["status"] = status
        run["current_stage"] = stage
        run["progress_percent"] = progress_percent
        run["updated_at"] = self._now()
        self.add_log(run_id, f"Transitioned to stage: {stage} ({progress_percent}%)", level="info", stage=stage)

        if self._db_available is not False:
            try:
                with SessionLocal() as db:
                    repo = TestRunRepository(db)
                    repo.update_status(run_id, status)
            except Exception:
                pass

    def update_website_map(self, run_id: str, website_map: Any):
        run = self._runs.get(run_id)
        if not run:
            return
        dumped = self._dump(website_map)
        run["website_map"] = dumped
        run["updated_at"] = self._now()
        links_cnt = len(dumped.get("links", [])) if isinstance(dumped, dict) else 0
        forms_cnt = len(dumped.get("forms", [])) if isinstance(dumped, dict) else 0
        buttons_cnt = len(dumped.get("buttons", [])) if isinstance(dumped, dict) else 0
        self.add_log(
            run_id,
            f"Site map extracted: {links_cnt} links, {buttons_cnt} buttons, {forms_cnt} forms detected.",
            level="success",
            stage="Discovery"
        )

    def update_test_plan(self, run_id: str, test_plan: Any):
        run = self._runs.get(run_id)
        if not run:
            return
        dumped = self._dump(test_plan)
        run["test_plan"] = dumped
        cases = dumped.get("test_cases", []) if isinstance(dumped, dict) else []
        run["stats"]["total"] = len(cases)
        run["updated_at"] = self._now()
        self.add_log(
            run_id,
            f"Generated test plan with {len(cases)} test cases.",
            level="success",
            stage="Planning"
        )

    def update_case_progress(self, run_id: str, case_id: str, status: str, result: Any, current_idx: int, total_cases: int):
        run = self._runs.get(run_id)
        if not run:
            return
        # Calculate dynamic execution progress percent (between 75% and 95%)
        pct = 75 + int((current_idx / max(total_cases, 1)) * 18)
        run["progress_percent"] = pct
        run["current_stage"] = f"Executing {case_id} ({current_idx}/{total_cases})"
        run["updated_at"] = self._now()

        if result:
            dumped_res = self._dump(result)
            # Check if this result is already in test_results
            existing_idx = next((i for i, r in enumerate(run["test_results"]) if r.get("test_case_id") == case_id), -1)
            if existing_idx >= 0:
                run["test_results"][existing_idx] = dumped_res
            else:
                run["test_results"].append(dumped_res)

            # Update stats
            passed = sum(1 for r in run["test_results"] if str(r.get("status", "")).lower() == "passed")
            failed = sum(1 for r in run["test_results"] if str(r.get("status", "")).lower() == "failed")
            blocked = sum(1 for r in run["test_results"] if str(r.get("status", "")).lower() == "blocked")
            total = len(run.get("test_plan", {}).get("test_cases", [])) or len(run["test_results"])
            run["stats"] = {
                "total": total,
                "passed": passed,
                "failed": failed,
                "blocked": blocked,
                "pass_rate": round((passed / total * 100) if total > 0 else 0, 1)
            }

            self.add_log(
                run_id,
                f"Test case {case_id} completed with status: {status.upper()}",
                level="success" if status == "passed" else "warning" if status == "blocked" else "error",
                stage="Execution"
            )
        else:
            self.add_log(
                run_id,
                f"Started browser execution for test case {case_id} ({current_idx}/{total_cases})",
                level="info",
                stage="Execution"
            )

    def complete_run(self, run_id: str, final_summary: str, healing_attempts: list = None):
        run = self._runs.get(run_id)
        if not run:
            return
        run["status"] = "completed"
        run["current_stage"] = "Completed"
        run["progress_percent"] = 100
        run["final_summary"] = final_summary
        run["html_report_path"] = f"/reports/report_{run_id}.html"
        if healing_attempts:
            run["healing_attempts"] = self._dump(healing_attempts)
        run["updated_at"] = self._now()
        self.add_log(
            run_id,
            "All pipeline stages finished. Executive summary & HTML report generated.",
            level="success",
            stage="Summary"
        )

    def fail_run(self, run_id: str, error_message: str):
        run = self._runs.get(run_id)
        if not run:
            return
        run["status"] = "failed"
        run["current_stage"] = "Failed"
        run["progress_percent"] = 100
        run["errors"].append({"message": error_message, "time": self._now_time()})
        run["updated_at"] = self._now()
        self.add_log(run_id, f"Run encountered error: {error_message}", level="error", stage="Failed")

    def _calculate_stats(self, test_plan: Any, test_cases: list) -> dict:
        total = len(test_plan.get("test_cases", [])) if isinstance(test_plan, dict) else len(test_cases)
        passed = sum(1 for tc in test_cases if getattr(tc, "status", "") == "passed")
        failed = sum(1 for tc in test_cases if getattr(tc, "status", "") == "failed")
        blocked = sum(1 for tc in test_cases if getattr(tc, "status", "") == "blocked")
        pass_rate = round((passed / total * 100) if total > 0 else 0, 1)
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "pass_rate": pass_rate
        }


# Singleton instance
run_manager = RunManager()
