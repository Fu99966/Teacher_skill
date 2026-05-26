from __future__ import annotations

import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class EvaluationCheck:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationReport:
    passed: bool
    summary: str
    checks: list[EvaluationCheck]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "checks": [check.to_dict() for check in self.checks],
        }


def evaluate_lesson_output(
    *,
    fields: dict[str, Any],
    output_path: Path | None,
    download_url: str | None,
    template_analysis: dict[str, Any] | None,
) -> EvaluationReport:
    checks = [
        _check(bool(fields), "fields_present", "已返回教案字段。", "未返回教案字段。"),
        _check(bool(download_url), "download_url", "已生成下载链接。", "缺少下载链接。"),
        _check(bool(output_path and output_path.exists()), "word_file", "Word 文件已生成。", "Word 文件不存在。"),
        _check(_has_lesson_structure(fields), "lesson_structure", "教学过程包含师生活动。", "教学过程缺少教师活动或学生活动。"),
        _check(_has_layered_homework(fields), "layered_homework", "作业包含分层设计。", "作业未体现基础、提升、拓展分层。"),
        _check(_template_fields_filled(fields, template_analysis), "template_fields", "模板字段已在结果中覆盖。", "部分模板字段没有生成内容。"),
    ]

    if output_path and output_path.exists():
        has_placeholder = _docx_has_placeholders(output_path)
        checks.append(
            _check(
                not has_placeholder,
                "placeholder_cleanup",
                "Word 中没有残留模板占位符。",
                "Word 中仍可能残留 {{ }} 模板占位符。",
            )
        )

    passed = all(check.passed for check in checks)
    summary = "Agent 自动检查通过，可以交付给教师。" if passed else "Agent 自动检查发现问题，需要补充或重新生成。"
    return EvaluationReport(passed=passed, summary=summary, checks=checks)


def _check(condition: bool, name: str, ok: str, fail: str) -> EvaluationCheck:
    return EvaluationCheck(name=name, passed=condition, detail=ok if condition else fail)


def _has_lesson_structure(fields: dict[str, Any]) -> bool:
    process = str(fields.get("teaching_process") or "")
    return "教师活动" in process and "学生活动" in process


def _has_layered_homework(fields: dict[str, Any]) -> bool:
    homework = str(fields.get("homework") or "")
    return all(keyword in homework for keyword in ("基础", "提升")) and ("拓展" in homework or "探究" in homework)


def _template_fields_filled(fields: dict[str, Any], template_analysis: dict[str, Any] | None) -> bool:
    mapped = (template_analysis or {}).get("mapped_fields") or []
    return all(str(fields.get(field) or "").strip() for field in mapped)


def _docx_has_placeholders(path: Path) -> bool:
    pattern = re.compile(r"\{\{.*?\}\}")
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.startswith("word/") or not name.endswith(".xml"):
                    continue
                text = archive.read(name).decode("utf-8", errors="ignore")
                if pattern.search(text):
                    return True
    except zipfile.BadZipFile:
        return True
    return False
