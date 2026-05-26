# Agent Core V6 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first true Agent Core so a teacher can type a natural-language request and the system can identify a lesson-plan task, prepare a plan, call the existing V5 workflow, evaluate the result, and return a structured response.

**Architecture:** Keep V5 as the stable document workflow. Add a thin `teacher_agent/agent_core/` layer above it with task routing, planning, tool execution, evaluation, and memory. The first version supports only `lesson_plan` to avoid overbuilding.

**Tech Stack:** Python stdlib, existing `http.server` web app, existing V5 workflow modules, browser-side HTML/CSS/JS.

---

### Task 1: Agent Core Models And Router

**Files:**
- Create: `teacher_agent/agent_core/__init__.py`
- Create: `teacher_agent/agent_core/task_router.py`

**Steps:**
1. Define `AgentTask` dataclass with task type, extracted lesson fields, missing fields, and confidence.
2. Implement a deterministic Chinese parser for grade, subject, lesson title, class type, teaching style, student level, and generation depth.
3. Verify with a Python one-liner that “帮我生成四年级语文《观潮》的探究课教案” maps to `lesson_plan`.

### Task 2: Planner, Tool Registry, Executor

**Files:**
- Create: `teacher_agent/agent_core/planner.py`
- Create: `teacher_agent/agent_core/tool_registry.py`
- Create: `teacher_agent/agent_core/executor.py`

**Steps:**
1. Define a small plan format: step id, tool name, label, status.
2. Register tools that wrap the existing V5 workflow: `draft_lesson`, `export_word`, `save_memory`.
3. Implement executor that runs a plan sequentially and records trace events.

### Task 3: Evaluator And Memory

**Files:**
- Create: `teacher_agent/agent_core/evaluator.py`
- Create: `teacher_agent/agent_core/memory.py`

**Steps:**
1. Add checks for fields, Word output, download URL, placeholder remnants, and lesson structure.
2. Store simple teacher preferences and last template id in SQLite-compatible JSON rows using the existing output directory.
3. Keep memory optional: failure to save memory must not break generation.

### Task 4: Web API And UI

**Files:**
- Modify: `teacher_agent/web_app.py`
- Modify: `web/index.html`
- Modify: `web/static/app.js`
- Modify: `web/static/app.css`

**Steps:**
1. Add `/api/agent-run` endpoint that accepts multipart form data with `agent_request` and template file.
2. Add a natural-language input above the existing form.
3. Let the Agent auto-fill fields and call the existing V5 workflow.
4. Render Agent plan, evaluator report, and final status on the page.

### Task 5: Verification

**Commands:**
- `python -m compileall teacher_agent`
- `node --check web\static\app.js`
- `curl` multipart request to `/api/agent-run`
- Export generated Word and verify no `{{` or `}}` remains.

**Acceptance Criteria:**
- Natural-language request creates a `lesson_plan` task.
- Missing fields are reported clearly.
- Successful run returns fields, review report, workflow trace, agent plan, evaluation report, download URL, and history item.
- Existing `/api/draft` and `/api/export` continue to work.
