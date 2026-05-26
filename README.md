# Teacher_skill

这是一个面向教师工作的智能体项目，设计思路参考 AgentSkills Runtime：把教师常用工作拆成多个可复用 Skill，再由 Agent 按任务调用。

当前版本聚焦教师备课文档的 V4 工作流：

1. 根据教材内容生成教案字段。
2. 通过课型、教学法、学生层次、生成深度控制生成风格，避免内容单一。
3. 根据年级自动识别小学、中学或大学学段，调整教学目标、课堂活动和作业深度。
4. 让教师在网页中检查和修改每个字段。
5. 支持字段级局部 AI 微调，例如“深化探究”“降低难度”“增加互动”。
6. 读取 Word 模板里的 `{{field_name}}` 占位符。
7. 如果模板没有占位符，自动识别表格中的“课题、教学目标、教学过程”等标签，把内容填入右侧单元格。
8. 把确认后的教案字段填入模板，尽量保留原模板的字体、表格、页眉页脚、段落样式。

## 项目结构

```text
teacher-agent-skills/
  agent.yaml
  requirements.txt
  teacher_agent/
    cli.py
    docx_filler.py
    lesson_generator.py
    preview_renderer.py
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

网页中按这个顺序使用：

```text
上传学校 Word 模板
填写学科、年级、课题和教材内容
选择课型、教学法、学生层次和生成深度
点击“生成内容”
在右侧修改教案各栏
需要时点击字段旁的局部优化按钮
点击“生成 Word”
下载生成好的教案
```

右侧内容如果在生成 Word 后又被修改，旧下载链接会自动失效，需要重新点击“生成 Word”。这样可保证下载文件与网页编辑区内容一致。

扫描 Word 模板，查看占位符和表格映射结果：

```powershell
python -m teacher_agent.cli scan-template templates\your_template.docx
```

根据 JSON 填充 Word 模板：

```powershell
python -m teacher_agent.cli fill-template --template templates\your_template.docx --data outputs\lesson_fields.json --output outputs\教案.docx
```

先生成一份教案字段 JSON：

```powershell
python -m teacher_agent.cli draft-lesson --subject 语文 --grade 四年级 --title 观潮 --material-file your_material.txt --class-type 探究/实验课 --teaching-style 5E探究模型 --student-level 基础薄弱/补弱导向 --generation-depth 深度 --output outputs\lesson_fields.json
```

再填入模板：

```powershell
python -m teacher_agent.cli fill-template --template templates\your_template.docx --data outputs\lesson_fields.json --output outputs\观潮教案.docx
```

## Word 模板要求

推荐方式一：在学校原有教案模板中放入占位符，例如：

```text
课题：{{lesson_title}}
年级：{{grade}}
学科：{{subject}}
教学目标：{{teaching_goals}}
教学过程：{{teaching_process}}
```

建议把每个占位符单独放在一个位置，不要把 `{{` 和 `}}` 分开设置不同字体。这样最容易保持原格式。

方式二：如果学校模板不方便加占位符，也可以保留原表格。系统会自动识别左侧标签，并把内容写入同一行右侧单元格，例如：

```text
课题       [这里自动填课题]
学科       [这里自动填学科]
教学目标   [这里自动填教学目标]
教学过程   [这里自动填教学过程]
作业设计   [这里自动填作业]
```

网页会显示“占位符填充”或“表格映射填充”。如果本机安装了 LibreOffice，生成 Word 后还会提供 PDF 预览；没有安装时仍可正常下载 Word。

## 与 AgentSkills Runtime 的关系

`skills/` 目录中的每个文件夹都是一个 Agent Skill。后续可以把这些 Skill 挂到 AgentSkills Runtime 中，由 runtime 负责发现、加载和调度。

本项目中的 Python 代码负责确定性的文档处理，例如读取模板、识别占位符、填充 docx。AI 只负责生成结构化内容，不直接控制 Word 格式。
