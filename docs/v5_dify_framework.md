# Teacher_skill V5 Dify-inspired 框架

V5 的目标不是复制 Dify，而是吸收它的核心思想：把一个 AI 应用拆成可配置、可观测、可编排的工作流。教师看到的是一个备课工具，系统内部运行的是一条教育文档生成流水线。

## 总体架构图

```mermaid
flowchart LR
  U["教师用户"] --> UI["Web 工作台"]
  UI --> W["Workflow 编排器"]
  W --> T["Word 模板解析"]
  W --> K["RAG 上下文打包"]
  K --> A1["执教老师 Agent"]
  A1 --> A2["教研组长 Agent 审阅"]
  A2 --> A3["二次修订 Agent"]
  A3 --> D["Word 渲染器"]
  D --> H["SQLite 历史记录"]
  D --> O["下载 / 预览"]
```

## 用户使用流程图

```mermaid
sequenceDiagram
  participant Teacher as 教师
  participant Web as Web 工作台
  participant Flow as Workflow
  participant Agent as 多 Agent 教研链
  participant Doc as Word 渲染器
  participant Store as 历史记录

  Teacher->>Web: 上传 Word 模板，填写课程信息
  Web->>Flow: 提交生成请求
  Flow->>Flow: 解析模板字段与表格映射
  Flow->>Flow: 抽取教材重点片段和样例提示
  Flow->>Agent: 生成教案初稿
  Agent->>Agent: 教研审阅并二次修订
  Agent-->>Web: 返回可编辑字段、审阅报告、工作流 Trace
  Teacher->>Web: 局部修改或微调字段
  Web->>Doc: 按原模板导出 Word
  Doc->>Store: 保存历史记录
  Doc-->>Teacher: 下载 Word / 查看预览
```

## 工程分层

```mermaid
flowchart TB
  subgraph UI["表现层"]
    I["web/index.html"]
    JS["web/static/app.js"]
    CSS["web/static/app.css"]
  end

  subgraph API["接口层"]
    HTTP["teacher_agent/web_app.py"]
  end

  subgraph APP["应用编排层"]
    WF["teacher_agent/workflow.py"]
    RAG["teacher_agent/rag_context.py"]
    AG["teacher_agent/teacher_agents.py"]
  end

  subgraph MODEL["模型层"]
    DS["teacher_agent/deepseek_client.py"]
    LOCAL["本地确定性生成器"]
  end

  subgraph TOOL["文档工具层"]
    TP["template_parser.py"]
    DF["docx_filler.py"]
    PV["preview_renderer.py"]
  end

  subgraph DATA["数据层"]
    DB["SQLite history_store.py"]
    OUT["outputs/"]
  end

  UI --> API --> APP
  APP --> MODEL
  APP --> TOOL
  TOOL --> DATA
  APP --> DATA
```

## 当前已落地模块

- `workflow.py`：V5 工作流编排器，统一返回字段、审阅报告、知识上下文和 Trace。
- `rag_context.py`：轻量 RAG 骨架，先基于教材文本做重点片段抽取，后续可替换为 Chroma、FAISS 等向量库。
- `teacher_agents.py`：多 Agent 教研链，包括执教老师生成、教研组长审阅、二次修订。
- `lesson_generator.py`：支持模板字段反向驱动生成，遇到 `warm_up`、`safety_precautions` 等自定义占位符时会自动补充字段内容。
- `history_store.py`：SQLite 历史记录，保存最近导出的教案、下载链接和工作流 Trace。
- `web_app.py`：新增 `/api/workflow-schema` 和 `/api/history`，生成/导出接口接入 V5 工作流。
- Web 页面：新增框架链路、教研审阅结果和最近导出记录。

## 后续升级路线

P0：把当前 V5 骨架跑稳定，确保 Word 模板格式不被破坏。  
P1：把 `rag_context.py` 替换为真实教材库检索，支持 PDF/OCR/图片教材。  
P2：将 `web_app.py` 迁移到 FastAPI，引入 SSE 流式输出。  
P3：扩展大单元教学、PPTX 生成和班级/教师账号体系。  
