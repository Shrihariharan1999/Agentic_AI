"""
Reports Service
===============
Generates and writes physical test report files (HTML/JSON) to disk.

WHY DO WE NEED A REPORTS SERVICE?
While the Summarizer Agent creates Markdown text for logging/dashboard display,
users often want downloadable HTML test reports or JSON records for CI/CD integrations.

The ReportsService handles exporting run histories into static files.
"""

import os                                               # Filesystem operations
import json                                             # JSON serialization
from datetime import datetime                           # Timestamps
from app.schemas.test_case import TestPlan              # TestPlan schema
from app.schemas.test_result import TestResult          # TestResult schema


class ReportsService:
    """
    Handles file serialization and layout exporting for automated test runs.
    """

    def __init__(self, output_dir: str = "data/reports"):
        """
        Initializes the reports service directory.
        """
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_json_report(
        self,
        run_id: str,
        target_url: str,
        test_plan: TestPlan,
        results: list[TestResult]
    ) -> str:
        """
        Generates a comprehensive JSON summary and saves it to disk.

        Args:
            run_id: Unique test run ID.
            target_url: URL under test.
            test_plan: Generated test plan.
            results: Test outcomes.

        Returns:
            The absolute filepath to the saved JSON report.
        """
        report_data = {
            "run_id": run_id,
            "target_url": target_url,
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_tests": len(test_plan.test_cases),
                "passed": sum(1 for r in results if r.status.value == "passed"),
                "failed": sum(1 for r in results if r.status.value == "failed"),
                "blocked": sum(1 for r in results if r.status.value == "blocked"),
            },
            "test_cases": [
                {
                    "id": tc.id,
                    "title": tc.title,
                    "description": tc.description,
                    "expected_result": tc.expected_result,
                    "status": next((r.status.value for r in results if r.test_case_id == tc.id), "not_run"),
                    "actual_result": next((r.actual_result for r in results if r.test_case_id == tc.id), ""),
                }
                for tc in test_plan.test_cases
            ]
        }

        filepath = os.path.abspath(os.path.join(self.output_dir, f"report_{run_id}.json"))
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        return filepath

    def generate_html_report(
        self,
        run_id: str,
        target_url: str,
        test_plan: TestPlan,
        results: list[TestResult]
    ) -> str:
        """
        Generates an HTML dashboard view of the test run outcomes.

        Args:
            run_id: Unique test run ID.
            target_url: URL under test.
            test_plan: Generated test plan.
            results: Test outcomes.

        Returns:
            The absolute filepath to the saved HTML report.
        """
        # Count outcomes
        total = len(test_plan.test_cases)
        passed = sum(1 for r in results if r.status.value == "passed")
        failed = sum(1 for r in results if r.status.value == "failed")
        blocked = sum(1 for r in results if r.status.value == "blocked")
        pass_rate = (passed / total * 100) if total > 0 else 0

        # Build rows of results
        rows_html = ""
        for tc in test_plan.test_cases:
            res = next((r for r in results if r.test_case_id == tc.id), None)
            status = res.status.value if res else "not run"
            actual = res.actual_result if res else ""
            
            status_class = "pass" if status == "passed" else "fail" if status == "failed" else "blocked"
            
            rows_html += f"""
            <tr>
                <td><strong>{tc.id}</strong></td>
                <td>{tc.title}</td>
                <td><span class="badge {status_class}">{status.upper()}</span></td>
                <td>{actual}</td>
            </tr>
            """

        # Generate full HTML template
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>AI Automation Test Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; background-color: #f8f9fa; color: #333; }}
        h1 {{ color: #007bff; }}
        .summary-card {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .stats {{ display: flex; gap: 20px; margin-top: 15px; }}
        .stat-item {{ background: #f1f3f5; padding: 15px 25px; border-radius: 6px; text-align: center; }}
        .stat-val {{ font-size: 24px; font-weight: bold; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 25px; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background-color: #007bff; color: white; }}
        tr:hover {{ background-color: #f1f3f5; }}
        .badge {{ padding: 5px 10px; border-radius: 4px; font-size: 12px; font-weight: bold; color: #fff; }}
        .pass {{ background-color: #28a745; }}
        .fail {{ background-color: #dc3545; }}
        .blocked {{ background-color: #ffc107; color: #333; }}
    </style>
</head>
<body>
    <h1>AI Automation Test Report</h1>
    <div class="summary-card">
        <h3>Run Details</h3>
        <p><strong>Run ID:</strong> {run_id}</p>
        <p><strong>Target URL:</strong> <a href="{target_url}" target="_blank">{target_url}</a></p>
        <p><strong>Timestamp:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
        
        <div class="stats">
            <div class="stat-item">Total Tests<div class="stat-val">{total}</div></div>
            <div class="stat-item">Passed<div class="stat-val" style="color: #28a745;">{passed}</div></div>
            <div class="stat-item">Failed<div class="stat-val" style="color: #dc3545;">{failed}</div></div>
            <div class="stat-item">Blocked<div class="stat-val" style="color: #ffc107;">{blocked}</div></div>
            <div class="stat-item">Pass Rate<div class="stat-val">{pass_rate:.1f}%</div></div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Test ID</th>
                <th>Title</th>
                <th>Status</th>
                <th>Actual Result</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>
"""

        filepath = os.path.abspath(os.path.join(self.output_dir, f"report_{run_id}.html"))
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        return filepath


# Singleton instance
reports_service = ReportsService()
