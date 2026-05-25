from __future__ import annotations

import argparse
import json
from pathlib import Path

from .docx_filler import fill_docx_template
from .lesson_generator import build_lesson_prompt, draft_lesson_fields, write_lesson_json
from .sample_template import create_sample_template
from .template_parser import scan_template


def _read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def cmd_scan_template(args: argparse.Namespace) -> None:
    fields = scan_template(args.template)
    print(json.dumps({"template": args.template, "fields": fields}, ensure_ascii=False, indent=2))


def cmd_fill_template(args: argparse.Namespace) -> None:
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    output = fill_docx_template(args.template, data, args.output)
    print(f"已生成：{output}")


def cmd_draft_lesson(args: argparse.Namespace) -> None:
    material = _read_text(args.material_file)
    fields = draft_lesson_fields(args.subject, args.grade, args.title, material, args.class_hour)
    output = write_lesson_json(fields, args.output)
    print(f"已生成教案字段：{output}")


def cmd_prompt(args: argparse.Namespace) -> None:
    material = _read_text(args.material_file)
    prompt = build_lesson_prompt(args.subject, args.grade, args.title, material, args.class_hour)
    print(prompt)


def cmd_create_sample_template(args: argparse.Namespace) -> None:
    output = create_sample_template(args.output)
    print(f"已生成示例模板：{output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="教师文档智能体工具")
    subparsers = parser.add_subparsers(required=True)

    scan = subparsers.add_parser("scan-template", help="扫描 docx 模板中的占位符")
    scan.add_argument("template")
    scan.set_defaults(func=cmd_scan_template)

    fill = subparsers.add_parser("fill-template", help="用 JSON 数据填充 docx 模板")
    fill.add_argument("--template", required=True)
    fill.add_argument("--data", required=True)
    fill.add_argument("--output", required=True)
    fill.set_defaults(func=cmd_fill_template)

    draft = subparsers.add_parser("draft-lesson", help="生成一份教案字段 JSON 草稿")
    draft.add_argument("--subject", required=True)
    draft.add_argument("--grade", required=True)
    draft.add_argument("--title", required=True)
    draft.add_argument("--material-file", required=True)
    draft.add_argument("--class-hour", default="1课时")
    draft.add_argument("--output", required=True)
    draft.set_defaults(func=cmd_draft_lesson)

    prompt = subparsers.add_parser("lesson-prompt", help="生成可发给大模型的教案 JSON 提示词")
    prompt.add_argument("--subject", required=True)
    prompt.add_argument("--grade", required=True)
    prompt.add_argument("--title", required=True)
    prompt.add_argument("--material-file", required=True)
    prompt.add_argument("--class-hour", default="1课时")
    prompt.set_defaults(func=cmd_prompt)

    sample = subparsers.add_parser("create-sample-template", help="生成一个带占位符的示例 docx 教案模板")
    sample.add_argument("--output", required=True)
    sample.set_defaults(func=cmd_create_sample_template)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
