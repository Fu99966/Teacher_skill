from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_FIELDS = PROJECT_ROOT / "examples" / "sample_lesson_fields.json"


@dataclass
class KnowledgeContext:
    """Small local RAG-style context package for the lesson workflow.

    This is intentionally lightweight. It gives the workflow a stable place to
    attach textbook chunks, template hints, and future vector search results.
    """

    chunks: list[str]
    few_shot_notes: list[str]
    source_summary: str

    def to_dict(self) -> dict:
        return asdict(self)

    def enhanced_material(self, material: str) -> str:
        sections = [material.strip()]
        if self.chunks:
            sections.append("# 系统检索到的教材重点片段\n" + "\n\n".join(self.chunks))
        if self.few_shot_notes:
            sections.append("# 优秀教案库提示\n" + "\n".join(f"- {note}" for note in self.few_shot_notes))
        return "\n\n".join(section for section in sections if section)


def _split_material(material: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n|[。！？]\s*", material) if part.strip()]
    return [paragraph for paragraph in paragraphs if len(paragraph) >= 8]


def _score_chunk(chunk: str, subject: str, title: str, class_type: str, teaching_style: str) -> int:
    score = min(len(chunk), 220)
    for marker in (subject, title, class_type, teaching_style):
        marker = marker.strip()
        if marker and marker in chunk:
            score += 90
    for keyword in ("目标", "重点", "难点", "探究", "实验", "习题", "活动", "评价", "课程标准"):
        if keyword in chunk:
            score += 20
    return score


def _load_few_shot_notes(class_type: str, teaching_style: str) -> list[str]:
    notes = [
        "教学过程需要同时写清教师活动和学生活动，便于直接落地到课堂。",
        "作业设计保持基础、提升、拓展三层结构，避免只给单一练习。",
    ]
    if "探究" in class_type or "5E" in teaching_style:
        notes.append("探究型课堂要保留提出问题、证据收集、解释建构和迁移评价四类动作。")
    if "讲评" in class_type:
        notes.append("讲评课要体现错因分析、典型错误归类和变式训练。")
    if "项目" in teaching_style or "PBL" in teaching_style:
        notes.append("项目式课堂要明确真实任务、成果标准、分工协作和展示评价。")

    if not EXAMPLE_FIELDS.exists():
        return notes

    try:
        data = json.loads(EXAMPLE_FIELDS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return notes

    process = str(data.get("teaching_process") or "").strip()
    if process:
        notes.append("优秀样例启发：" + process[:180].replace("\n", "；"))
    return notes[:5]


def build_knowledge_context(
    material: str,
    *,
    subject: str,
    title: str,
    class_type: str,
    teaching_style: str,
) -> KnowledgeContext:
    chunks = _split_material(material)
    ranked = sorted(
        chunks,
        key=lambda chunk: _score_chunk(chunk, subject, title, class_type, teaching_style),
        reverse=True,
    )
    selected = ranked[:4]
    few_shot_notes = _load_few_shot_notes(class_type, teaching_style)
    summary = f"已从教材内容中抽取 {len(selected)} 个重点片段，并注入 {len(few_shot_notes)} 条优秀教案提示。"
    return KnowledgeContext(chunks=selected, few_shot_notes=few_shot_notes, source_summary=summary)
