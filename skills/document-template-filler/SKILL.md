---
name: document-template-filler
description: 当用户需要把结构化 JSON 内容填入 Word docx 模板，并尽量保持原模板字体、段落、表格、页眉页脚和布局时使用。
---

# Document Template Filler

## 核心原则

Word 模板决定格式，AI 只提供内容。程序只识别字段并写入内容，不重建整份文档。

## 支持的模板

1. 占位符模板：

```text
{{lesson_title}}
{{teaching_goals}}
{{teaching_process}}
```

2. 学校原表格模板：

```text
教学目标    [空白单元格]
教学过程    [空白单元格]
作业设计    [空白单元格]
```

3. 混合模板：同一个 docx 中既有 `{{field}}`，也有表格标签。

## 填充报告

填充后必须输出：

- `filled_fields`
- `missing_fields`
- `remaining_placeholders`
- `placeholder_fields_filled`
- `table_fields_filled`

缺失字段不能删除原占位符，必须在报告中标记。

## 命令

```powershell
python -m teacher_agent.cli scan-template templates\your_template.docx
python -m teacher_agent.cli fill-template --template templates\your_template.docx --data outputs\lesson_fields.json --output outputs\lesson.docx
python -m teacher_agent.cli generate --template templates\your_template.docx --subject 语文 --grade 四年级 --title 桂林山水 --material-file examples\sample_material.md --output outputs\桂林山水教案.docx --no-strict-ai
```
