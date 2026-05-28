from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .deepseek_client import DeepSeekError
from .docx_filler import fill_docx_template
from .lesson_generator import (
    DEFAULT_CLASS_TYPE,
    DEFAULT_GENERATION_DEPTH,
    DEFAULT_STUDENT_LEVEL,
    DEFAULT_TEACHING_STYLE,
    LessonGenerationError,
    build_lesson_prompt,
    draft_lesson_document_fields_with_source,
    write_lesson_json,
)
from .sample_template import create_sample_template
from .template_parser import analyze_template


def _read_text(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"教材文件不存在：{path}") from exc


def _load_json(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"JSON 数据文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 数据文件格式错误：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("JSON 数据必须是对象，不能是数组或纯文本。")
    return data


def _template_fields(template: str | None) -> tuple[list[str] | None, dict | None]:
    if not template:
        return None, None
    analysis = analyze_template(template)
    if analysis.get("needs_template_markers"):
        raise ValueError("; ".join(analysis.get("errors") or ["模板中未识别到可填字段。"]))
    return analysis["mapped_fields"], analysis


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_scan_template(args: argparse.Namespace) -> None:
    analysis = analyze_template(args.template)
    _print_json({"template": args.template, **analysis})


def cmd_fill_template(args: argparse.Namespace) -> None:
    data = _load_json(args.data)
    report = fill_docx_template(args.template, data, args.output)
    _print_json({"output": str(report.path), "fill_report": report.to_dict()})


def cmd_draft_lesson(args: argparse.Namespace) -> None:
    material = _read_text(args.material_file)
    template_fields, template_analysis = _template_fields(args.template)
    fields, backend = draft_lesson_document_fields_with_source(
        args.subject,
        args.grade,
        args.title,
        material,
        args.class_hour,
        args.class_type,
        args.teaching_style,
        args.student_level,
        args.generation_depth,
        template_fields,
        args.strict_ai,
        (template_analysis or {}).get("field_context"),
    )
    output = write_lesson_json(fields, args.output)
    _print_json(
        {
            "output": str(output),
            "generation_backend": backend,
            "template_fields": template_fields,
            "fields": fields,
        }
    )


def cmd_generate(args: argparse.Namespace) -> None:
    material = _read_text(args.material_file)
    template_fields, template_analysis = _template_fields(args.template)
    fields, backend = draft_lesson_document_fields_with_source(
        args.subject,
        args.grade,
        args.title,
        material,
        args.class_hour,
        args.class_type,
        args.teaching_style,
        args.student_level,
        args.generation_depth,
        template_fields,
        args.strict_ai,
        (template_analysis or {}).get("field_context"),
    )
    report = fill_docx_template(args.template, fields, args.output)
    _print_json(
        {
            "output": str(report.path),
            "generation_backend": backend,
            "template_fields": template_fields,
            "fields": fields,
            "fill_report": report.to_dict(),
        }
    )


def cmd_prompt(args: argparse.Namespace) -> None:
    material = _read_text(args.material_file)
    template_fields, template_analysis = _template_fields(args.template)
    prompt = build_lesson_prompt(
        args.subject,
        args.grade,
        args.title,
        material,
        args.class_hour,
        args.class_type,
        args.teaching_style,
        args.student_level,
        args.generation_depth,
        template_fields,
        (template_analysis or {}).get("field_context"),
    )
    print(prompt)


def cmd_create_sample_template(args: argparse.Namespace) -> None:
    output = create_sample_template(args.output)
    print(f"Created sample template: {output}")


def cmd_web(args: argparse.Namespace) -> None:
    from .web_app import run

    run(args.host, args.port)


def _add_lesson_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--subject", required=True)
    parser.add_argument("--grade", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--material-file", required=True)
    parser.add_argument("--class-hour", default="1课时")
    parser.add_argument("--class-type", default=DEFAULT_CLASS_TYPE)
    parser.add_argument("--teaching-style", default=DEFAULT_TEACHING_STYLE)
    parser.add_argument("--student-level", default=DEFAULT_STUDENT_LEVEL)
    parser.add_argument("--generation-depth", default=DEFAULT_GENERATION_DEPTH)
    strict = parser.add_mutually_exclusive_group()
    strict.add_argument("--strict-ai", dest="strict_ai", action="store_true", help="DeepSeek 失败时直接报错")
    strict.add_argument("--no-strict-ai", dest="strict_ai", action="store_false", help="DeepSeek 失败时使用本地 fallback")
    parser.set_defaults(strict_ai=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Teacher Skill document tools")
    subparsers = parser.add_subparsers(required=True)

    scan = subparsers.add_parser("scan-template", help="scan placeholders and table fields in a docx template")
    scan.add_argument("template")
    scan.set_defaults(func=cmd_scan_template)

    fill = subparsers.add_parser("fill-template", help="fill a docx template with JSON data")
    fill.add_argument("--template", required=True)
    fill.add_argument("--data", required=True)
    fill.add_argument("--output", required=True)
    fill.set_defaults(func=cmd_fill_template)

    draft = subparsers.add_parser("draft-lesson", help="draft lesson fields JSON")
    _add_lesson_args(draft)
    draft.add_argument("--template", help="optional docx template; dynamic fields come from this template")
    draft.add_argument("--output", required=True)
    draft.set_defaults(func=cmd_draft_lesson)

    generate = subparsers.add_parser("generate", help="scan template, draft fields, fill Word, and report")
    _add_lesson_args(generate)
    generate.add_argument("--template", required=True)
    generate.add_argument("--output", required=True)
    generate.set_defaults(func=cmd_generate)

    prompt = subparsers.add_parser("lesson-prompt", help="print an LLM prompt for lesson JSON")
    _add_lesson_args(prompt)
    prompt.add_argument("--template", help="optional docx template; dynamic fields come from this template")
    prompt.set_defaults(func=cmd_prompt)

    sample = subparsers.add_parser("create-sample-template", help="create a sample placeholder docx")
    sample.add_argument("--output", required=True)
    sample.set_defaults(func=cmd_create_sample_template)

    web = subparsers.add_parser("web", help="start the teacher web app")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.set_defaults(func=cmd_web)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, DeepSeekError, LessonGenerationError) as exc:
        print(f"错误：{getattr(exc, 'user_message', str(exc))}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
