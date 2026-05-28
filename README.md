# Teacher Skill

Teacher Skill 是一个面向教师备课的 Word 教案模板填充工具。核心原则是：**Word 模板决定格式，AI 只生成内容**。

## 能做什么

1. 老师上传学校原始 `.docx` 教案模板。
2. 系统自动识别模板中的 `{{field_name}}` 占位符和常见表格标签。
3. DeepSeek 根据学科、年级、课题、课时、教材内容和补充要求生成严格 JSON。
4. 系统把 JSON 写回模板对应位置，尽量保留原模板字体、字号、段落、表格、页眉页脚和布局。
5. 如果不上传模板，Web 端可使用系统默认模板生成标准教案。

## 模板写法

### 方式一：占位符模板

在 Word 中写：

```text
{{lesson_title}}
{{teaching_goals}}
{{teaching_process}}
{{homework}}
```

占位符字段可以是标准字段，也可以是自定义字段，例如：

```text
{{warm_up}}
{{safety_rules}}
{{core_training}}
{{assessment}}
```

系统会要求 AI 只返回这些字段，不允许新增模板外字段。

### 方式二：学校原表格模板

如果模板没有占位符，也可以保留学校原表格。例如左侧单元格是：

```text
课题
教学目标
教学过程
作业设计
教学反思
```

右侧为空时，系统会把内容写入右侧单元格；如果标签和空白区域在同一单元格，会在标签后追加内容。

目前支持的常见标签包括：课题、授课内容、学科、年级、班级、课时、教学目标、核心素养目标、知识目标、能力目标、情感目标、教学重点、教学难点、教学重难点、教学准备、教具准备、学情分析、教学过程、教学流程、教学环节、教学活动、教师活动、学生活动、设计意图、板书设计、作业设计、教学反思。

## DeepSeek 配置

复制环境变量文件：

```powershell
copy .env.example .env
```

填写：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

## 常用命令

安装依赖：

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

扫描模板：

```powershell
python -m teacher_agent.cli scan-template templates\sample_lesson_template.docx
```

一步生成 Word：

```powershell
python -m teacher_agent.cli generate --template templates\sample_lesson_template.docx --subject 语文 --grade 四年级 --title 桂林山水 --material-file examples\sample_material.md --output outputs\桂林山水教案.docx --no-strict-ai
```

只生成 JSON：

```powershell
python -m teacher_agent.cli draft-lesson --template templates\sample_lesson_template.docx --subject 语文 --grade 四年级 --title 桂林山水 --material-file examples\sample_material.md --output outputs\lesson_fields.json --no-strict-ai
```

用 JSON 填充模板：

```powershell
python -m teacher_agent.cli fill-template --template templates\sample_lesson_template.docx --data outputs\lesson_fields.json --output outputs\桂林山水教案.docx
```

启动网页：

```powershell
python -m teacher_agent.cli web
```

打开：

```text
http://127.0.0.1:8765
```

## strict_ai 与 fallback

- `--strict-ai`：DeepSeek 未配置或调用失败时直接报错，不生成伪造教案。
- `--no-strict-ai`：DeepSeek 不可用时生成本地结构化占位草稿，并明确返回 `generation_backend="local_fallback"`。

Web 端同样会返回 `generation_backend`、`fill_report` 和自动检查结果。

## 格式保持边界

系统不会重建整个 Word 文档，也不会让 AI 决定 Word 样式。它会尽量保留原模板格式。

可稳定保持：原表格结构、边框、列宽、页眉页脚、段落样式、单元格布局。

可能无法完全保持：一个占位符被 Word 拆成多个 run 且每个 run 使用不同局部样式时，系统会以第一个有效 run 样式承载替换内容。

## 验证

```powershell
python -m compileall teacher_agent
pytest
node --check web\static\app.js
```
