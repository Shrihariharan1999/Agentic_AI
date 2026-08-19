import io
import traceback

from contextlib import redirect_stdout
from dataclasses import dataclass


@dataclass
class ExecutionResult:

    success: bool
    output: str
    error: str | None = None


class PythonExecutor:

    def execute(self, code: str) -> ExecutionResult:

        stdout = io.StringIO()

        try:

            with redirect_stdout(stdout):
                exec(code, {})
                output = stdout.getvalue()
                
            print(f"Execution Output from executor :\n{output}")
            return ExecutionResult( success=True, output=stdout.getvalue(),error=None)
        

        except Exception:

            return ExecutionResult( success=False, output=stdout.getvalue(), error=traceback.format_exc())