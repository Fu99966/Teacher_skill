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
