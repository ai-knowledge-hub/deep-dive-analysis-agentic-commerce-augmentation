"""Runtime service errors kept separate from orchestration mechanics."""


class AgentRuntimeError(ValueError):
    pass


class RunNotFoundError(AgentRuntimeError):
    pass


class PlanOnlyModeError(AgentRuntimeError):
    pass


class RunBusyError(AgentRuntimeError):
    pass


class NoApprovedActionError(AgentRuntimeError):
    pass


__all__ = [
    "AgentRuntimeError",
    "NoApprovedActionError",
    "PlanOnlyModeError",
    "RunBusyError",
    "RunNotFoundError",
]
