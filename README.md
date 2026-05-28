# Teacher_skill

## V8 DeepSeek 诊断与严格 AI 模式

V8 增加了 AI 服务诊断、严格 AI 模式、教学设计蓝图、历史反重复和优秀教案样例注入。

1. 复制 `.env.example` 为 `.env`，把你的真实 DeepSeek Key 填入 `DEEPSEEK_API_KEY`。不要把 `.env` 提交到 GitHub。
2. 打开网页后，顶部会显示 `AI 服务` 状态；点击 `诊断` 可以看到未配置、密钥错误、余额不足、模型错误、限流、网络错误等原因。
3. 新手模式默认开启 `严格 AI 模式`：DeepSeek 失败时会停止并显示原因，不再静默使用本地模板草稿。
4. 如需离线演示，可关闭严格 AI 模式，系统会回落到本地草稿生成器。
5. 生成时会自动读取近期相似历史教案，提示模型避开重复导入、活动顺序、作业和板书结构。

这是一个面向教师工作的智能体项目，设计思路参考 AgentSkills Runtime：把教师常用工作拆成多个可复用 Skill，再由 Agent 按任务调用。

当前版本聚焦教师备课文档的 V6 Agent 工作流，采用 Dify-inspired 的“自然语言任务入口 + Agent Core + 工作流编排 + 多 Agent + 文档工具 + 历史记录”结构：

1. 支持教师用自然语言下达任务，例如“帮我生成四年级语文《观潮》的探究课教案”。
2. Agent Core 自动识别任务类型、学科、年级、课题、课型和教学法。
3. Planner 把任务拆成生成、导出、检查、保存历史、保存记忆等步骤。
4. Tool Registry 调用现有 V5 教案工作流，不重写稳定模块。
5. Evaluator 自动检查字段、Word 文件、模板占位符、教学过程和分层作业。
6. 根据教材内容生成教案字段。
7. 通过课型、教学法、学生层次、生成深度控制生成风格，避免内容单一。
8. 自动抽取教材重点片段，作为轻量 RAG 上下文注入生成流程。
9. 使用“执教老师 Agent + 教研组长 Agent + 二次修订 Agent”的内部教研链提升质量。
10. 支持字段级局部 AI 微调，例如“深化探究”“降低难度”“增加互动”。
11. 支持由模板反向定义生成字段，例如 `{{warm_up}}`、`{{safety_precautions}}`、`{{assessment}}`。
12. 把确认后的教案字段填入模板，尽量保留原模板的字体、表格、页眉页脚、段落样式。

## 项目结构

```text
teacher-agent-skills/
  agent.yaml
  requirements.txt
  teacher_agent/
    agent_core/
      executor.py
      evaluator.py
      memory.py
      planner.py
      task_router.py
      tool_registry.py
    cli.py
    docx_filler.py
    history_store.py
    lesson_generator.py
    preview_renderer.py
    rag_context.py
    teacher_agents.py
    template_parser.py
    workflow.py
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
    v5_dify_framework.md
```

## 快速使用

安装依赖：

```powershell
pip install -r requirements.txt
```

启用真实 DeepSeek 生成：

```powershell
copy .env.example .env
```

然后在 `.env` 中填写：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_MODEL=deepseek-v4-pro
```

如果没有配置 `DEEPSEEK_API_KEY`，系统会自动使用本地草稿生成器，方便离线演示。

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
在 Agent 指令中输入自然语言任务，或手动填写学科、年级、课题和教材内容
选择课型、教学法、学生层次和生成深度（自然语言中写清楚时可自动识别）
点击“Agent 执行”或“生成内容”
查看智能体框架、教研审阅报告和生成字段
在右侧修改教案各栏
需要时点击字段旁的局部优化按钮
点击“生成 Word”
下载生成好的教案
```

自然语言示例：

```text
帮我生成一份四年级语文《观潮》的探究课教案，要适合公开课并包含分层作业
```

V6 Agent Core 会自动完成：

```text
任务识别 → 制定计划 → 调用 V5 工作流 → 导出 Word → 自动检查 → 保存历史和记忆
```

V5 架构图见：

```text
docs/v5_dify_framework.md
```

V6 实施计划见：

```text
docs/plans/2026-05-26-agent-core-v6.md
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
