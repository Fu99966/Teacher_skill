# Teacher Agent Skills

这是一个面向教师工作的智能体项目骨架，设计思路参考 AgentSkills Runtime：把教师常用工作拆成多个可复用 Skill，再由 Agent 按任务调用。

当前版本先聚焦一个最关键能力：

1. 根据教材内容生成教案字段。
2. 读取 Word 模板里的 `{{field_name}}` 占位符。
3. 把教案字段填入模板。
4. 尽量保留原模板的字体、表格、页眉页脚、段落样式。

## 项目结构

```text
teacher-agent-skills/
  agent.yaml
  requirements.txt
  teacher_agent/
    cli.py
    docx_filler.py
    lesson_generator.py
    template_parser.py
  skills/
    lesson-plan-writer/
    document-template-filler/
    document-editor/
    worksheet-generator/
  templates/
    lesson_template_placeholders.md
  examples/
    sample_material.md
    sample_lesson_fields.json
  outputs/
  docs/
    workflow.md
```

## 快速使用

安装依赖：

```powershell
pip install -r requirements.txt
```

启动网页：

```powershell
python -m teacher_agent.cli web
```

然后打开：

```text
http://127.0.0.1:8765
```

扫描 Word 模板里的占位符：

```powershell
python -m teacher_agent.cli scan-template templates\your_template.docx
```

根据示例 JSON 填充 Word 模板：

```powershell
python -m teacher_agent.cli fill-template --template templates\your_template.docx --data examples\sample_lesson_fields.json --output outputs\教案.docx
```

先生成一份教案字段 JSON：

```powershell
python -m teacher_agent.cli draft-lesson --subject 语文 --grade 四年级 --title 观潮 --material-file examples\sample_material.md --output outputs\lesson_fields.json
```

再填入模板：

```powershell
python -m teacher_agent.cli fill-template --template templates\your_template.docx --data outputs\lesson_fields.json --output outputs\观潮教案.docx
```

## Word 模板要求

在学校原有教案模板中放入占位符即可，例如：

```text
课题：{{lesson_title}}
年级：{{grade}}
学科：{{subject}}
教学目标：{{teaching_goals}}
教学过程：{{teaching_process}}
```

建议把每个占位符单独放在一个位置，不要把 `{{` 和 `}}` 分开设置不同字体。这样最容易保持原格式。

## 与 AgentSkills Runtime 的关系

`skills/` 目录中的每个文件夹都是一个 Agent Skill。后续可以把这些 Skill 挂到 AgentSkills Runtime 中，由 runtime 负责发现、加载和调度。

本项目中的 Python 代码负责确定性的文档处理，例如读取模板、识别占位符、填充 docx。AI 只负责生成结构化内容，不直接控制 Word 格式。
