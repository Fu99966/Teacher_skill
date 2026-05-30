"""AgentRunState – single source of truth for agent execution state."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentArtifact:
    name: str
    path: str | None = None
    url: str | None = None
    kind: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRunState:
    session_id: str
    status: str  # one of STATUS_VALUES
    task: dict[str, Any]
    current_node: str
    next_action: str
    template_path: str | None = None
    template_id: str | None = None
    template_analysis: dict[str, Any] | None = None
    template_profile: dict[str, Any] | None = None
    fields: dict[str, Any] | None = None
    teacher_edits: dict[str, Any] | None = None
    review_report: dict[str, Any] | None = None
    export_result: dict[str, Any] | None = None
    evaluation_report: dict[str, Any] | None = None
    teacher_report: dict[str, Any] | None = None
    artifacts: list[AgentArtifact] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 1

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["artifacts"] = [a.to_dict() for a in self.artifacts]
        return d


STATUS_VALUES = (
    "initialized",
    "template_diagnosed",
    "fields_generated",
    "waiting_teacher_review",
    "exporting",
    "evaluating",
    "repairing",
    "completed",
    "failed",
)

ROUTE_NODES = (
    "route_task",
    "diagnose_template",
    "plan_fields",
    "draft_fields",
    "pedagogy_review",
    "revise_fields",
    "teacher_review_gate",
    "export_docx",
    "evaluate_delivery",
    "repair_if_needed",
    "generate_teacher_report",
    "save_history",
    "save_memory",
)
