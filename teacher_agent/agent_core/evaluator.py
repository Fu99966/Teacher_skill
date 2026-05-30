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
    fill_report: dict[str, Any] | None = None,
) -> EvaluationReport:
    template_field_count = len((template_analysis or {}).get("mapped_fields") or [])
    non_empty_field_count = sum(1 for value in (fields or {}).values() if str(value or "").strip())
    checks = [
        _check(bool(fields), "fields_present", "已返回文档字段。", "未返回文档字段。"),
        _check(bool(download_url), "download_url", "已生成下载链接。", "缺少下载链接。"),
        _check(bool(output_path and output_path.exists()), "word_file", "Word 文件已生成。", "Word 文件不存在。"),
        _check(_template_fields_filled(fields, template_analysis), "template_fields", "模板字段已在结果中覆盖。", "部分模板字段没有生成内容。"),
        _check(
            not (template_field_count > 0 and non_empty_field_count == 0),
            "blank_template_precheck",
            "生成字段中存在非空内容。",
            "生成失败：检测到输出可能为空白模板，未生成任何非空字段。",
        ),
    ]

    if fill_report:
        fill_errors = fill_report.get("errors") or []
        fill_warnings = fill_report.get("warnings") or []
        checks.append(
            _check(
                not fill_errors,
                "fill_report_errors",
                "Word 填充报告没有错误。",
                "; ".join(str(item) for item in fill_errors),
            )
        )
        checks.append(
            _check(
                not fill_report.get("missing_fields"),
                "fill_missing_fields",
                "Word 填充没有缺失字段。",
                f"Word 填充缺失字段：{', '.join(fill_report.get('missing_fields') or [])}",
            )
        )
        checks.append(
            _check(
                not fill_report.get("remaining_placeholders"),
                "fill_remaining_placeholders",
                "Word 中没有残留模板占位符。",
                f"Word 中仍有占位符：{', '.join(fill_report.get('remaining_placeholders') or [])}",
            )
        )
        checks.append(
            _check(
                int(fill_report.get("filled_non_empty_count") or 0) > 0,
                "filled_non_empty_count",
                "Word 已写入非空字段。",
                "生成失败：检测到输出可能为空白模板，未写入任何非空字段。",
            )
        )
        if fill_warnings:
            checks.append(EvaluationCheck("fill_report_warnings", True, "; ".join(str(item) for item in fill_warnings)))

    if output_path and output_path.exists():
        has_placeholder = _docx_has_placeholders(output_path)
        checks.append(
            _check(
                not has_placeholder,
                "placeholder_cleanup",
                "Word 中没有残留 {{ }} 模板占位符。",
                "Word 中仍可能残留 {{ }} 模板占位符。",
            )
        )

    passed = all(check.passed for check in checks)
    summary = "自动检查通过，可以交付给教师。" if passed else "自动检查发现问题，需要补充或重新生成。"
    return EvaluationReport(passed=passed, summary=summary, checks=checks)


def _check(condition: bool, name: str, ok: str, fail: str) -> EvaluationCheck:
    return EvaluationCheck(name=name, passed=condition, detail=ok if condition else fail)


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


# ── New: Delivery + Pedagogy split ──

def evaluate_delivery(
    *,
    fields: dict[str, Any],
    output_path: Path | None,
    download_url: str | None,
    template_analysis: dict[str, Any] | None,
    fill_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check technical delivery: file exists, fields written, no placeholders."""
    checks: list[dict[str, Any]] = []
    score = 100

    def _c(name: str, ok: bool, fail_msg: str) -> None:
        nonlocal score
        checks.append({"name": name, "passed": ok, "detail": "" if ok else fail_msg})
        if not ok:
            score -= 15

    _c("fields_present", bool(fields), "未返回文档字段")
    _c("download_url", bool(download_url), "缺少下载链接")
    _c("word_file", bool(output_path and output_path.exists()), "Word文件不存在")

    if fill_report:
        _c("no_fill_errors", not fill_report.get("errors"), "; ".join(fill_report.get("errors") or []))
        _c("no_missing", not fill_report.get("missing_fields"), "缺失字段: " + ", ".join(fill_report.get("missing_fields") or []))
        _c("no_placeholders", not fill_report.get("remaining_placeholders"), "残留占位符: " + ", ".join(fill_report.get("remaining_placeholders") or []))
        _c("filled_count", int(fill_report.get("filled_non_empty_count") or 0) > 0, "未写入任何非空字段")
        fwc = fill_report.get("field_write_counts", {})
        _c("teaching_process_written", fwc.get("teaching_process", 0) > 0, "主要教学内容未写入")
        _c("teaching_method_written", fwc.get("teaching_method", 0) > 0, "教学方法未写入")

    if output_path and output_path.exists():
        _c("no_docx_placeholders", not _docx_has_placeholders(output_path), "Word中仍残留占位符")

    score = max(0, score)
    passed = all(c["passed"] for c in checks)
    return {
        "passed": passed, "delivery_score": score,
        "delivery_checks": checks,
        "summary": "交付检查通过" if passed else f"交付检查未通过 ({score}分)",
    }


def evaluate_pedagogy_quality(fields: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    """Rule-based pedagogy quality check (no LLM needed)."""
    checks: list[dict[str, Any]] = []
    score = 100
    suggestions: list[str] = []

    goals = str(fields.get("teaching_goals", ""))
    process = str(fields.get("teaching_process", ""))
    homework = str(fields.get("homework", ""))
    reflection = str(fields.get("reflection", ""))

    def _c(name: str, ok: bool, hint: str) -> None:
        nonlocal score
        checks.append({"name": name, "passed": ok, "detail": "" if ok else hint})
        if not ok:
            score -= 10
            suggestions.append(hint)

    # Goals check
    _c("goals_specific", len(goals) > 30 and any(k in goals for k in ("理解", "掌握", "能")),
       "教学目标建议更具体，包含知识、能力、素养三个维度")

    # Key-difficult check
    kd = str(fields.get("teaching_key_difficult", ""))
    _c("key_difficult_clear", "重点" in kd or "难点" in kd or len(kd) > 20,
       "重点难点建议明确标注'重点：'和'难点：'")

    # Process structure
    proc_parts = ["导入", "新授", "练习", "总结", "探究", "讨论", "实践"]
    found_parts = sum(1 for p in proc_parts if p in process)
    _c("process_structure", found_parts >= 2,
       f"教学过程建议包含导入/新授/练习/总结等环节（当前识别到{found_parts}个）")

    # Method check
    method = str(fields.get("teaching_method", ""))
    _c("method_specific", len(method) > 15,
       "教学方法建议写具体方式，如'案例教学+小组讨论'")

    # Homework layers
    hw_parts = ["基础", "提升", "拓展", "必做", "选做"]
    hw_found = sum(1 for p in hw_parts if p in homework)
    _c("homework_layered", len(homework) > 20 or hw_found >= 1,
       "作业建议分层（基础/提升/拓展）")

    # Reflection check
    _c("reflection_meaningful", len(reflection) > 15 and not _has_ai_filler(reflection),
       "课后小记建议写具体观察点，避免套话")

    score = max(0, score)
    passed = score >= 60
    return {
        "passed": passed, "score": score,
        "pedagogy_checks": checks,
        "suggestions": suggestions,
        "summary": f"教研审查{'通过' if passed else '未通过'}（{score}分）",
    }


def _has_ai_filler(text: str) -> bool:
    fillers = ["课后重点观察", "根据反馈调整", "是否能在", "完成情况"]
    return sum(1 for f in fillers if f in text) >= 2
