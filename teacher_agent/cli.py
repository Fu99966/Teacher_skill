from __future__ import annotations

import argparse
import json
from pathlib import Path

from .docx_filler import fill_docx_template
from .lesson_generator import (
    DEFAULT_CLASS_TYPE,
    DEFAULT_GENERATION_DEPTH,
    DEFAULT_STUDENT_LEVEL,
    DEFAULT_TEACHING_STYLE,
    build_lesson_prompt,
    draft_lesson_fields,
    write_lesson_json,
)
from .sample_template import create_sample_template
from .template_parser import analyze_template


def _read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def cmd_scan_template(args: argparse.Namespace) -> None:
    analysis = analyze_template(args.template)
    print(json.dumps({"template": args.template, **analysis}, ensure_ascii=False, indent=2))


def cmd_fill_template(args: argparse.Namespace) -> None:
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    output = fill_docx_template(args.template, data, args.output)
    print(f"Created: {output}")


def cmd_draft_lesson(args: argparse.Namespace) -> None:
    material = _read_text(args.material_file)
    fields = draft_lesson_fields(
        args.subject,
        args.grade,
        args.title,
        material,
        args.class_hour,
        args.class_type,
        args.teaching_style,
        args.student_level,
        args.generation_depth,
    )
    output = write_lesson_json(fields, args.output)
    print(f"Created lesson fields: {output}")


def cmd_prompt(args: argparse.Namespace) -> None:
    material = _read_text(args.material_file)
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
    )
    print(prompt)


def cmd_create_sample_template(args: argparse.Namespace) -> None:
    output = create_sample_template(args.output)
    print(f"Created sample template: {output}")


def cmd_web(args: argparse.Namespace) -> None:
    from .web_app import run

    run(args.host, args.port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Teacher document agent tools")
    subparsers = parser.add_subparsers(required=True)

    scan = subparsers.add_parser("scan-template", help="scan placeholders in a docx template")
    scan.add_argument("template")
    scan.set_defaults(func=cmd_scan_template)

    fill = subparsers.add_parser("fill-template", help="fill a docx template with JSON data")
    fill.add_argument("--template", required=True)
    fill.add_argument("--data", required=True)
    fill.add_argument("--output", required=True)
    fill.set_defaults(func=cmd_fill_template)

    draft = subparsers.add_parser("draft-lesson", help="draft lesson fields JSON")
    draft.add_argument("--subject", required=True)
    draft.add_argument("--grade", required=True)
    draft.add_argument("--title", required=True)
    draft.add_argument("--material-file", required=True)
    draft.add_argument("--class-hour", default="1课时")
    draft.add_argument("--class-type", default=DEFAULT_CLASS_TYPE)
    draft.add_argument("--teaching-style", default=DEFAULT_TEACHING_STYLE)
    draft.add_argument("--student-level", default=DEFAULT_STUDENT_LEVEL)
    draft.add_argument("--generation-depth", default=DEFAULT_GENERATION_DEPTH)
    draft.add_argument("--output", required=True)
    draft.set_defaults(func=cmd_draft_lesson)

    prompt = subparsers.add_parser("lesson-prompt", help="print an LLM prompt for lesson JSON")
    prompt.add_argument("--subject", required=True)
    prompt.add_argument("--grade", required=True)
    prompt.add_argument("--title", required=True)
    prompt.add_argument("--material-file", required=True)
    prompt.add_argument("--class-hour", default="1课时")
    prompt.add_argument("--class-type", default=DEFAULT_CLASS_TYPE)
    prompt.add_argument("--teaching-style", default=DEFAULT_TEACHING_STYLE)
    prompt.add_argument("--student-level", default=DEFAULT_STUDENT_LEVEL)
    prompt.add_argument("--generation-depth", default=DEFAULT_GENERATION_DEPTH)
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
    args.func(args)


if __name__ == "__main__":
    main()
