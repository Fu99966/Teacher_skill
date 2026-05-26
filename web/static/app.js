const form = document.querySelector("#lesson-form");
const generateButton = document.querySelector("#generate-button");
const agentRunButton = document.querySelector("#agent-run-button");
const agentRequestInput = document.querySelector("#agent-request");
const templateInput = document.querySelector("#template-input");
const statusBox = document.querySelector("#status");
const resultTitle = document.querySelector("#result-title");
const downloadLink = document.querySelector("#download-link");
const exportButton = document.querySelector("#export-button");
const fieldCount = document.querySelector("#field-count");
const fileName = document.querySelector("#file-name");
const previewList = document.querySelector("#preview-list");
const templateMode = document.querySelector("#template-mode");
const templateMap = document.querySelector("#template-map");
const previewLink = document.querySelector("#preview-link");
const workflowVersion = document.querySelector("#workflow-version");
const workflowSteps = document.querySelector("#workflow-steps");
const reviewPanel = document.querySelector("#review-panel");
const reviewScore = document.querySelector("#review-score");
const reviewSummary = document.querySelector("#review-summary");
const reviewIssues = document.querySelector("#review-issues");
const reviewImprovements = document.querySelector("#review-improvements");
const historyList = document.querySelector("#history-list");
const agentResultPanel = document.querySelector("#agent-result-panel");
const agentTaskType = document.querySelector("#agent-task-type");
const agentPlanList = document.querySelector("#agent-plan-list");
const evaluationPanel = document.querySelector("#evaluation-panel");
const evaluationStatus = document.querySelector("#evaluation-status");
const evaluationSummary = document.querySelector("#evaluation-summary");
const evaluationList = document.querySelector("#evaluation-list");

const fieldLabels = {
  lesson_title: "课题",
  subject: "学科",
  grade: "年级",
  class_hour: "课时",
  teaching_goals: "教学目标",
  key_points: "教学重点",
  difficult_points: "教学难点",
  teaching_preparation: "教学准备",
  teaching_process: "教学过程",
  blackboard_design: "板书设计",
  homework: "作业设计",
  reflection: "教学反思",
  safety_precautions: "安全注意事项",
  warm_up: "热身环节",
  core_training: "核心训练",
  assessment: "学习评价",
  resources: "教学资源",
  unit_plan: "单元规划",
};

const previewOrder = [
  "lesson_title",
  "subject",
  "grade",
  "class_hour",
  "teaching_goals",
  "key_points",
  "difficult_points",
  "teaching_preparation",
  "teaching_process",
  "blackboard_design",
  "homework",
  "reflection",
];

const backendLabels = {
  deepseek: "DeepSeek V4 Pro",
  local: "本地草稿",
  local_fallback: "DeepSeek 失败，已用本地草稿",
};

let currentFields = null;
let currentTemplateId = null;
let currentDownloadUrl = "#";
let currentPreviewUrl = "#";
let currentTemplateAnalysis = null;
let currentRequestContext = null;
let currentReviewReport = null;
let currentWorkflowTrace = [];
let currentGenerationBackend = null;
let workflowSchema = null;
let currentAgentPlan = null;
let currentEvaluationReport = null;

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function focusStatus() {
  statusBox.scrollIntoView({ behavior: "smooth", block: "center" });
}

function validateAgentInputs() {
  if (!agentRequestInput.value.trim()) {
    setStatus("请先输入 Agent 指令", true);
    agentRequestInput.focus();
    return false;
  }
  if (!templateInput.files || templateInput.files.length === 0) {
    setStatus("请先上传学校 Word 模板，然后再点击 Agent 执行", true);
    templateInput.focus();
    return false;
  }
  return true;
}

function setBusy(isBusy) {
  generateButton.disabled = isBusy;
  agentRunButton.disabled = isBusy;
  exportButton.disabled = isBusy || !currentFields;
  generateButton.querySelector("span:last-child").textContent = isBusy ? "生成中" : "生成内容";
  agentRunButton.querySelector("span:last-child").textContent = isBusy ? "执行中" : "Agent 执行";
}

function setDownloadReady(url, outputName) {
  currentDownloadUrl = url;
  fileName.textContent = outputName;
  downloadLink.href = url;
  downloadLink.classList.remove("is-disabled");
  downloadLink.setAttribute("aria-disabled", "false");
}

function setPreviewReady(url) {
  currentPreviewUrl = url || "#";
  previewLink.href = currentPreviewUrl;
  previewLink.classList.toggle("is-disabled", !url);
  previewLink.setAttribute("aria-disabled", url ? "false" : "true");
}

function setDownloadStale(message = "未导出") {
  currentDownloadUrl = "#";
  currentPreviewUrl = "#";
  fileName.textContent = message;
  downloadLink.href = "#";
  downloadLink.classList.add("is-disabled");
  downloadLink.setAttribute("aria-disabled", "true");
  setPreviewReady(null);
}

const defaultWorkflowNodes = [
  { id: "app_input", label: "应用输入", layer: "应用层" },
  { id: "template_analyzer", label: "模板解析", layer: "编排层" },
  { id: "knowledge_context", label: "RAG 上下文", layer: "知识层" },
  { id: "lesson_writer", label: "执教老师 Agent", layer: "Agent 层" },
  { id: "teaching_reviewer", label: "教研组长 Agent", layer: "Agent 层" },
  { id: "lesson_reviser", label: "二次修订 Agent", layer: "Agent 层" },
  { id: "doc_renderer", label: "Word 渲染器", layer: "工具层" },
  { id: "history_store", label: "历史记录", layer: "数据层" },
];

function readRequestContext(formData) {
  return {
    subject: formData.get("subject") || "",
    grade: formData.get("grade") || "",
    title: formData.get("title") || "",
    class_hour: formData.get("class_hour") || "",
    class_type: formData.get("class_type") || "",
    teaching_style: formData.get("teaching_style") || "",
    student_level: formData.get("student_level") || "",
    generation_depth: formData.get("generation_depth") || "",
  };
}

function renderWorkflowTrace(trace = []) {
  const nodes = workflowSchema?.nodes?.length ? workflowSchema.nodes : defaultWorkflowNodes;
  const traceByNode = new Map((trace || []).map((item) => [item.node, item]));
  workflowSteps.innerHTML = "";
  nodes.forEach((node) => {
    const event = traceByNode.get(node.id);
    const item = document.createElement("div");
    item.className = `workflow-step ${event?.status || ""}`.trim();

    const title = document.createElement("strong");
    title.textContent = node.label;

    const detail = document.createElement("span");
    detail.textContent = event ? event.detail : node.layer;

    item.append(title, detail);
    workflowSteps.appendChild(item);
  });
}

function renderReviewReport(report) {
  currentReviewReport = report || null;
  if (!report) {
    reviewPanel.hidden = true;
    reviewScore.textContent = "0";
    reviewSummary.textContent = "";
    reviewIssues.innerHTML = "";
    reviewImprovements.innerHTML = "";
    return;
  }

  reviewPanel.hidden = false;
  reviewScore.textContent = `${report.score || 0} 分`;
  reviewSummary.textContent = report.summary || "已完成教研审阅。";

  reviewIssues.innerHTML = "";
  (report.issues || []).forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    reviewIssues.appendChild(item);
  });

  reviewImprovements.innerHTML = "";
  (report.improvements || []).forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    reviewImprovements.appendChild(item);
  });
}

function renderAgentPlan(task, plan = []) {
  currentAgentPlan = plan || null;
  if (!task && !plan.length) {
    agentResultPanel.hidden = true;
    agentTaskType.textContent = "等待任务";
    agentPlanList.innerHTML = "";
    return;
  }

  agentResultPanel.hidden = false;
  agentTaskType.textContent = task ? `${task.task_type || "unknown"} · ${Math.round((task.confidence || 0) * 100)}%` : "执行计划";
  agentPlanList.innerHTML = "";
  plan.forEach((step) => {
    const item = document.createElement("div");
    item.className = `agent-plan-step ${step.status || ""}`.trim();
    const status = document.createElement("strong");
    status.textContent = step.status || "pending";
    const detail = document.createElement("span");
    detail.textContent = `${step.label || step.tool}${step.detail ? `：${step.detail}` : ""}`;
    item.append(status, detail);
    agentPlanList.appendChild(item);
  });
}

function renderEvaluation(report) {
  currentEvaluationReport = report || null;
  if (!report) {
    evaluationPanel.hidden = true;
    evaluationStatus.textContent = "待检查";
    evaluationSummary.textContent = "";
    evaluationList.innerHTML = "";
    return;
  }

  evaluationPanel.hidden = false;
  evaluationStatus.textContent = report.passed ? "通过" : "需处理";
  evaluationSummary.textContent = report.summary || "";
  evaluationList.innerHTML = "";
  (report.checks || []).forEach((check) => {
    const item = document.createElement("div");
    item.className = `evaluation-check ${check.passed ? "passed" : "failed"}`;
    const status = document.createElement("strong");
    status.textContent = check.passed ? "通过" : "未通过";
    const detail = document.createElement("span");
    detail.textContent = check.detail || check.name;
    item.append(status, detail);
    evaluationList.appendChild(item);
  });
}

function renderHistory(items = []) {
  historyList.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = "暂无导出记录";
    historyList.appendChild(empty);
    return;
  }

  items.slice(0, 6).forEach((item) => {
    const link = document.createElement("a");
    link.className = "history-item";
    link.href = item.download_url;

    const text = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = `${item.grade || ""}${item.subject || ""}：${item.title || "教案"}`;
    const meta = document.createElement("span");
    meta.textContent = `${item.created_at || ""} · ${backendLabels[item.backend] || item.backend || "生成器"}`;
    text.append(title, meta);

    const action = document.createElement("span");
    action.textContent = "下载";
    link.append(text, action);
    historyList.appendChild(link);
  });
}

async function loadWorkflowSchema() {
  try {
    const response = await fetch("/api/workflow-schema");
    workflowSchema = await response.json();
    workflowVersion.textContent = workflowSchema.version || "V5";
  } catch {
    workflowSchema = null;
  }
  renderWorkflowTrace(currentWorkflowTrace);
}

async function loadHistory() {
  try {
    const response = await fetch("/api/history");
    const data = await response.json();
    renderHistory(data.items || []);
  } catch {
    renderHistory([]);
  }
}

function refreshResultTitle(fields) {
  if (!fields) return;
  resultTitle.textContent = `${fields.grade || ""}${fields.subject || ""}：${fields.lesson_title || ""}`;
}

function renderPreview(fields) {
  previewList.innerHTML = "";
  const keys = [...previewOrder, ...Object.keys(fields || {}).filter((key) => !previewOrder.includes(key))];
  keys.forEach((key) => {
    if (!fields[key]) return;
    const item = document.createElement("article");
    item.className = "preview-item";

    const itemHead = document.createElement("div");
    itemHead.className = "preview-item-head";

    const title = document.createElement("h3");
    title.textContent = fieldLabels[key] || key;

    const controls = document.createElement("div");
    controls.className = "field-ai-tools";

    const refineMode = document.createElement("select");
    refineMode.className = "refine-mode";
    refineMode.dataset.refineField = key;
    [
      ["more_vivid", "更生动"],
      ["deepen_inquiry", "深化探究"],
      ["simplify", "降低难度"],
      ["more_interaction", "增加互动"],
      ["shorten", "精简"],
    ].forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      refineMode.appendChild(option);
    });

    const refineButton = document.createElement("button");
    refineButton.type = "button";
    refineButton.className = "icon-button refine-button";
    refineButton.dataset.refineField = key;
    refineButton.title = "局部 AI 微调";
    refineButton.setAttribute("aria-label", `${fieldLabels[key] || key} 局部 AI 微调`);
    refineButton.textContent = "✦";

    controls.append(refineMode, refineButton);
    itemHead.append(title, controls);

    const body = document.createElement("textarea");
    body.className = "field-editor";
    body.dataset.field = key;
    body.value = fields[key];
    if (["lesson_title", "subject", "grade", "class_hour"].includes(key)) {
      body.classList.add("compact");
      body.rows = 1;
    } else {
      body.rows = Math.min(10, Math.max(3, String(fields[key]).split("\n").length + 1));
    }

    item.append(itemHead, body);
    previewList.appendChild(item);
  });
}

function resizeFieldEditor(editor) {
  if (!editor) return;
  if (editor.classList.contains("compact")) {
    editor.rows = 1;
    return;
  }
  editor.rows = Math.min(12, Math.max(3, String(editor.value).split("\n").length + 1));
}

function renderTemplateAnalysis(analysis) {
  currentTemplateAnalysis = analysis || null;
  if (!analysis) {
    templateMode.textContent = "待识别";
    templateMap.hidden = true;
    templateMap.innerHTML = "";
    return;
  }

  const placeholderCount = analysis.placeholders?.length || 0;
  const mappingEntries = Object.entries(analysis.table_mappings || {});
  templateMode.textContent = placeholderCount > 0 ? "占位符填充" : "表格映射填充";
  templateMap.hidden = false;
  templateMap.innerHTML = "";

  const title = document.createElement("div");
  title.className = "template-map-title";
  title.textContent =
    placeholderCount > 0
      ? `已读取 ${placeholderCount} 个 Word 占位符，生成时保持原模板格式。`
      : `未发现占位符，已按表格标签自动匹配 ${mappingEntries.length} 个字段。`;
  templateMap.appendChild(title);

  const list = document.createElement("div");
  list.className = "template-map-list";
  const fields = placeholderCount > 0 ? analysis.placeholders : mappingEntries.map(([field]) => field);
  fields.forEach((field) => {
    const chip = document.createElement("span");
    chip.textContent = fieldLabels[field] || field;
    list.appendChild(chip);
  });
  templateMap.appendChild(list);
}

function collectEditedFields() {
  const fields = { ...(currentFields || {}) };
  document.querySelectorAll("[data-field]").forEach((node) => {
    fields[node.dataset.field] = node.value;
  });
  return fields;
}

function markEditedContent() {
  if (!currentFields) return;
  const hadDownload = currentDownloadUrl !== "#";
  currentFields = collectEditedFields();
  refreshResultTitle(currentFields);
  setDownloadStale(hadDownload ? "内容已修改，需重新导出" : "未导出");
  exportButton.disabled = false;
  if (hadDownload) {
    setStatus("内容已修改，请重新导出 Word");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  setStatus("正在生成教案内容");

  currentFields = null;
  currentTemplateId = null;
  currentTemplateAnalysis = null;
  currentReviewReport = null;
  currentWorkflowTrace = [];
  currentGenerationBackend = null;
  exportButton.disabled = true;
  setDownloadStale("未导出");
  renderTemplateAnalysis(null);
  renderReviewReport(null);
  renderWorkflowTrace([]);

  try {
    const formData = new FormData(form);
    currentRequestContext = readRequestContext(formData);
    const response = await fetch("/api/draft", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "生成失败");
    }

    currentFields = data.fields;
    currentTemplateId = data.template_id;
    currentTemplateAnalysis = data.template_analysis;
    currentReviewReport = data.review_report || null;
    currentWorkflowTrace = data.workflow_trace || [];
    currentGenerationBackend = data.generation_backend || null;
    if (data.workflow_schema) {
      workflowSchema = data.workflow_schema;
      workflowVersion.textContent = workflowSchema.version || "V5";
    }
    refreshResultTitle(data.fields);
    fieldCount.textContent = String(data.template_fields.length);
    renderTemplateAnalysis(data.template_analysis);
    renderReviewReport(currentReviewReport);
    renderWorkflowTrace(currentWorkflowTrace);
    renderPreview(data.fields);
    exportButton.disabled = false;
    setStatus(`内容已生成并完成教研审阅（${backendLabels[data.generation_backend] || "生成器"}）`);
  } catch (error) {
    setStatus(error.message || "生成失败", true);
  } finally {
    setBusy(false);
  }
});

agentRunButton.addEventListener("click", async () => {
  if (!validateAgentInputs()) {
    return;
  }

  setBusy(true);
  setStatus("Agent 正在理解任务并制定执行计划");

  currentFields = null;
  currentTemplateId = null;
  currentTemplateAnalysis = null;
  currentReviewReport = null;
  currentWorkflowTrace = [];
  currentGenerationBackend = null;
  exportButton.disabled = true;
  setDownloadStale("未导出");
  renderTemplateAnalysis(null);
  renderReviewReport(null);
  renderAgentPlan(null, []);
  renderEvaluation(null);
  renderWorkflowTrace([]);

  try {
    const formData = new FormData(form);
    currentRequestContext = readRequestContext(formData);
    const response = await fetch("/api/agent-run", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      renderAgentPlan(data.agent_task, data.agent_plan || []);
      throw new Error(data.message || data.error || "Agent 执行失败");
    }

    currentFields = data.fields;
    currentTemplateId = data.template_id;
    currentTemplateAnalysis = data.template_analysis;
    currentReviewReport = data.review_report || null;
    currentWorkflowTrace = data.workflow_trace || [];
    currentGenerationBackend = data.generation_backend || null;
    currentRequestContext = {
      ...(data.agent_task || {}),
      material: formData.get("material") || "",
    };

    if (data.workflow_schema) {
      workflowSchema = data.workflow_schema;
      workflowVersion.textContent = workflowSchema.version || "V5";
    }

    refreshResultTitle(data.fields);
    fieldCount.textContent = String((data.template_fields || []).length);
    renderTemplateAnalysis(data.template_analysis);
    renderAgentPlan(data.agent_task, data.agent_plan || []);
    renderEvaluation(data.evaluation_report);
    renderReviewReport(currentReviewReport);
    renderWorkflowTrace(currentWorkflowTrace);
    renderPreview(data.fields);
    setDownloadReady(data.download_url, data.output_name);
    setPreviewReady(data.preview_url);
    exportButton.disabled = false;
    loadHistory();
    setStatus(data.evaluation_report?.passed ? "Agent 已完成任务并通过自动检查" : "Agent 已完成任务，但自动检查提示需要复核");
  } catch (error) {
    setStatus(error.message || "Agent 执行失败", true);
    focusStatus();
  } finally {
    setBusy(false);
  }
});

exportButton.addEventListener("click", async () => {
  if (!currentFields || !currentTemplateId) {
    setStatus("请先生成内容", true);
    return;
  }

  exportButton.disabled = true;
  setStatus("正在生成 Word");

  try {
    const editedFields = collectEditedFields();
    const response = await fetch("/api/export", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        template_id: currentTemplateId,
        fields: editedFields,
        request_context: currentRequestContext,
        generation_backend: currentGenerationBackend,
        review_report: currentReviewReport,
        workflow_trace: currentWorkflowTrace,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "导出失败");
    }

    currentFields = editedFields;
    currentTemplateAnalysis = data.template_analysis || currentTemplateAnalysis;
    currentWorkflowTrace = data.workflow_trace || currentWorkflowTrace;
    refreshResultTitle(currentFields);
    renderTemplateAnalysis(currentTemplateAnalysis);
    renderWorkflowTrace(currentWorkflowTrace);
    setDownloadReady(data.download_url, data.output_name);
    setPreviewReady(data.preview_url);
    loadHistory();
    setStatus(data.preview_url ? "最新 Word 已生成，可查看真实预览" : "最新 Word 已生成；本机未检测到 PDF 预览工具");
  } catch (error) {
    setStatus(error.message || "导出失败", true);
  } finally {
    exportButton.disabled = false;
  }
});

previewList.addEventListener("input", (event) => {
  if (event.target?.dataset?.field) {
    resizeFieldEditor(event.target);
    markEditedContent();
  }
});

previewList.addEventListener("click", async (event) => {
  const button = event.target.closest(".refine-button");
  if (!button || !currentFields) return;

  const field = button.dataset.refineField;
  const editor = previewList.querySelector(`[data-field="${field}"]`);
  const mode = previewList.querySelector(`[data-refine-field="${field}"].refine-mode`);
  if (!editor) return;

  button.disabled = true;
  const oldText = button.textContent;
  button.textContent = "…";
  setStatus(`正在局部优化：${fieldLabels[field] || field}`);

  try {
    const response = await fetch("/api/refine-field", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        field,
        value: editor.value,
        action: mode?.value || "more_vivid",
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "局部优化失败");
    }
    editor.value = data.value;
    resizeFieldEditor(editor);
    markEditedContent();
    setStatus(`${fieldLabels[field] || field} 已局部优化，请重新生成 Word`);
  } catch (error) {
    setStatus(error.message || "局部优化失败", true);
  } finally {
    button.disabled = false;
    button.textContent = oldText;
  }
});

downloadLink.addEventListener("click", (event) => {
  if (downloadLink.classList.contains("is-disabled")) {
    event.preventDefault();
    setStatus(currentFields ? "请先导出最新 Word" : "请先生成内容", true);
  }
});

previewLink.addEventListener("click", (event) => {
  if (previewLink.classList.contains("is-disabled")) {
    event.preventDefault();
    setStatus(currentFields ? "当前环境未生成预览，请下载 Word 查看" : "请先生成内容", true);
  }
});

renderReviewReport(null);
renderAgentPlan(null, []);
renderEvaluation(null);
renderWorkflowTrace([]);
loadWorkflowSchema();
loadHistory();
