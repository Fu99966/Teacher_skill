# Teacher Skill 教案助手

[![Teacher Skill CI](https://github.com/2030731860-crypto/Teacher_skill/actions/workflows/test.yml/badge.svg)](https://github.com/2030731860-crypto/Teacher_skill/actions/workflows/test.yml)

Teacher Skill 是一个面向教师备课的 Word 教案智能体。核心原则是：**Word 模板决定格式，AI 只生成内容**。

## 当前能力

- 一句话生成教案；没有配置 DeepSeek 时自动使用本地 fallback 初稿。
- 可上传学校 `.docx` 教案模板，自动识别占位符和常见中文表格字段。
- 支持复杂表格、合并单元格、并列表头、重复教案表格的 `first_only / all` 填充策略。
- 支持系统标准模板导出，并为项目课生成真正的 Word 课时分配表。
- 支持教师可读的生成诊断报告：识别了什么、写入了什么、没写入什么、原因是什么。
- 支持教研审查后的自动修订：仅改进审查失败字段，并优先保留老师已记住的修改。
- 支持模板画像缓存，记住成功的模板字段映射。
- 支持“记住这次修改”，后续同类教案生成时会参考老师修改样例。
- 支持轻量教材 RAG：粘贴教材内容，或上传 txt / md / docx / 文本型 PDF；扫描版 PDF 需先进行 OCR。

## Web 使用

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m teacher_agent.cli web --port 8765
```

打开：

```text
http://127.0.0.1:8765/
```

基本流程：

1. 输入一句话需求，例如：`帮我生成一份24级物联网班 PCB板设计课的32课时教案`。
2. 可选：勾选“使用学校 Word 模板”并上传 `.docx`。
3. 可选：粘贴或上传教材资料。
4. 生成教案，预览并编辑字段。
5. 导出 Word。

## 模板写法

### 占位符模板

在 Word 中写：

```text
{{lesson_title}}
{{teaching_goals}}
{{teaching_process}}
{{teaching_method}}
{{homework}}
{{reflection}}
```

也支持中文占位符和自定义字段：

```text
{{教学目标}}
{{warm_up}}
{{assessment}}
```

### 学校原表格模板

如果模板没有占位符，只要表格中有常见标签，也会尽量识别：

```text
课题 / 授课班级 / 教学目的 / 重点难点 / 教具挂图
主要教学内容 / 教学方法的运用 / 作业 / 课后小记
```

并列表头也支持：

```text
主要教学内容 | 教学方法的运用
空白填写区   | 空白填写区
```

## CLI 示例

扫描模板：

```powershell
python -m teacher_agent.cli scan-template templates/sample_lesson_template.docx
```

一步生成：

```powershell
python -m teacher_agent.cli generate `
  --template templates/sample_lesson_template.docx `
  --subject 物联网 `
  --grade 24级物联网班 `
  --title PCB板设计 `
  --class-hour 32课时 `
  --material-file examples/sample_material.md `
  --output outputs/PCB板设计教案.docx `
  --no-strict-ai
```

诊断真实模板：

```powershell
python -m teacher_agent.cli diagnose-template `
  --template tests/fixtures/教案模板.docx `
  --subject 物联网 `
  --grade 24级物联网班 `
  --title 传感器基础 `
  --material-file examples/sample_material.md `
  --output-dir outputs/diagnose_real_template `
  --no-strict-ai
```

## DeepSeek 配置

复制 `.env.example` 为 `.env`，填写：

```text
DEEPSEEK_API_KEY=你的 Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

`strict_ai=true` 时，模型不可用会直接报错；`strict_ai=false` 时，会使用本地 fallback 初稿并明确标记 `generation_backend=local_fallback`。

## 验证

```powershell
node --check web/static/app.js
python -m compileall teacher_agent
pytest
```

GitHub Actions 会在每次推送到 `main` 或创建 Pull Request 时自动执行：

- Ubuntu：Python 3.10、3.11、3.12、3.13；
- Windows：Python 3.11；
- Python 编译、前端 JavaScript 语法检查、模板扫描 smoke test、完整 pytest。

## 格式保持边界

系统不会让 AI 直接决定 Word 格式；格式来自 Word 模板。`python-docx` 能尽量保留字体、段落、表格边框、列宽、页眉页脚和原布局。但极端复杂的嵌套表格、文本框、浮动对象或扫描版 PDF 教材仍可能需要人工复核。
