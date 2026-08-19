from pydantic import BaseModel


class HumanIntervention(BaseModel):
    required: bool = False
    reason: str = ""
    instructions: str = ""
    response: str = ""


class HealingAttempt(BaseModel):
    attempt_number: int
    reason: str
    action: str
    successful: bool = False


class WorkflowError(BaseModel):
    component: str
    message: str
    recoverable: bool = False