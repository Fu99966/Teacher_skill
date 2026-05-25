---
name: document-template-filler
description: 当用户需要把 AI 生成的教案、试卷、通知或其他文本字段填入 Word docx 模板，并尽量保持原模板字体、表格、页眉页脚、段落样式不变时使用。
---

# Document Template Filler

## 核心原则

模板决定格式，AI 只提供内容，程序只替换占位符。

## 占位符格式

使用双大括号：

```text
{{lesson_title}}
{{teaching_goals}}
{{teaching_process}}
```

## 工作流程

1. 扫描 docx 模板，识别所有 `{{field_name}}`。
2. 检查 AI 输出 JSON 是否包含对应字段。
3. 将 JSON 值填入模板。
4. 输出新的 docx。
5. 不主动改变字体、字号、表格边框、页眉页脚。

## 模板制作建议

- 一个占位符尽量放在同一个 Word 文本片段中。
- 不要把 `{{`、字段名、`}}` 分别设置不同样式。
- 表格模板可以直接把占位符放在单元格里。
- 长文本字段建议独占一行或一个单元格。

## 对应脚本

使用项目中的命令：

```powershell
python -m teacher_agent.cli scan-template templates\your_template.docx
python -m teacher_agent.cli fill-template --template templates\your_template.docx --data outputs\lesson_fields.json --output outputs\教案.docx
```
