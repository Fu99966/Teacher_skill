# Teacher Skill

教案助手 Teacher Skill 是一个面向教师备课的教育智能体工具。核心能力是读取 Word 模板中的占位符或表格字段，根据模板字段动态生成 JSON，再把内容写回 Word 文档，尽量保持原模板格式不变。

## 当前能力

1. 支持新手模式和专业模式。
2. 支持一句话备课、课程信息确认、模板选择、教材内容补充和 Word 下载。
3. 支持上传学校 Word 模板，也可以使用系统标准模板。
4. 支持动态模板字段，例如 `lesson_title`、`warm_up`、`safety_rules`、`assessment`。
5. 生成链路为模板解析、知识上下文、反重复提示、教案生成、教研审阅、二次修订、Word 渲染、历史记录。
6. 核心生成使用 DeepSeek API，默认模型为 `deepseek-v4-pro`。

## 快速开始

安装依赖：

```powershell
pip install -r requirements.txt
```

复制环境变量文件：

```powershell
copy .env.example .env
```

在 `.env` 中填写：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

启动网页：

```powershell
python -m teacher_agent.cli web
```

打开：

```text
http://127.0.0.1:8765
```

## Word 模板规则

推荐方式一：在 Word 模板中放入占位符：

```text
{{lesson_title}}
{{subject}}
{{grade}}
{{teaching_goals}}
{{teaching_process}}
```

推荐方式二：保留学校原表格。系统会识别左侧标签，并把内容填入同一行右侧空白单元格。

如果模板中有自定义字段，例如：

```text
{{warm_up}}
{{safety_rules}}
{{core_training}}
{{assessment}}
```

生成器会把这些字段直接传给大模型，并要求返回严格匹配这些 Key 的 JSON，不再固定为 12 个教案字段。

## 常用命令

扫描模板：

```powershell
python -m teacher_agent.cli scan-template templates\your_template.docx
```

用 JSON 填充模板：

```powershell
python -m teacher_agent.cli fill-template --template templates\your_template.docx --data outputs\lesson_fields.json --output outputs\lesson.docx
```

启动网页：

```powershell
python -m teacher_agent.cli web
```
