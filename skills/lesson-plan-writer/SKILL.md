---
name: lesson-plan-writer
description: 当用户需要根据教材、课文、知识点、学科、年级或课时生成结构化教案内容时使用。输出必须是可填入模板的字段内容，而不是直接排版 Word 文档。
---

# Lesson Plan Writer

## 目标

生成可填入教案模板的结构化内容。AI 只负责内容，不决定 Word 格式。

## 输入

- 学科
- 年级
- 课题
- 课时
- 教材内容或知识点
- 教师补充要求

## 输出字段

必须优先输出 JSON：

```json
{
  "lesson_title": "",
  "subject": "",
  "grade": "",
  "class_hour": "",
  "teaching_goals": "",
  "key_points": "",
  "difficult_points": "",
  "teaching_preparation": "",
  "teaching_process": "",
  "blackboard_design": "",
  "homework": "",
  "reflection": ""
}
```

## 工作流程

1. 识别学科、年级、课题和课时。
2. 阅读教材内容，提取知识点和学习任务。
3. 生成教学目标、重难点和教学过程。
4. 使用清晰的段落和编号，便于填入 Word 模板。
5. 不输出 Markdown 表格，不输出 Word 样式说明。

## 质量要求

- 教学目标要包含知识、能力、情感或核心素养维度。
- 教学过程要有导入、探究、练习、总结。
- 内容不能空泛，要贴合课题。
- 如果材料不足，先生成通用草稿，并标明可补充教材内容继续优化。
