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

const beginnerWorkflow = document.querySelector("#beginner-workflow");
const professionalWorkspace = document.querySelector("#professional-workspace");
const beginnerModeButton = document.querySelector("#beginner-mode-button");
const professionalModeButton = document.querySelector("#professional-mode-button");
const beginnerNotice = document.querySelector("#beginner-notice");
const beginnerRequestInput = document.querySelector("#beginner-agent-request");
const beginnerStartButton = document.querySelector("#beginner-start-button");
const beginnerSubject = document.querySelector("#beginner-subject");
const beginnerGrade = document.querySelector("#beginner-grade");
const beginnerTitle = document.querySelector("#beginner-title");
const beginnerClassType = document.querySelector("#beginner-class-type");
const beginnerClassHour = document.querySelector("#beginner-class-hour");
const beginnerTeachingStyle = document.querySelector("#beginner-teaching-style");
const beginnerMissingCard = document.querySelector("#beginner-missing-card");
const beginnerConfirmButton = document.querySelector("#beginner-confirm-button");
const beginnerBackToIntent = document.querySelector("#beginner-back-to-intent");
const beginnerBackToConfirm = document.querySelector("#beginner-back-to-confirm");
const beginnerGenerateButton = document.querySelector("#beginner-generate-button");
const beginnerTemplateInput = document.querySelector("#beginner-template-input");
const beginnerUploadWrap = document.querySelector("#beginner-upload-wrap");
const beginnerMaterial = document.querySelector("#beginner-material");
const beginnerGenericNote = document.querySelector("#beginner-generic-note");
const beginnerProgressList = document.querySelector("#beginner-progress-list");
const beginnerResultTitle = document.querySelector("#beginner-result-title");
const beginnerSummary = document.querySelector("#beginner-summary");
const beginnerDownloadLink = document.querySelector("#beginner-download-link");
const beginnerPreviewLink = document.querySelector("#beginner-preview-link");
const beginnerEditButton = document.querySelector("#beginner-edit-button");
const beginnerRegenerateButton = document.querySelector("#beginner-regenerate-button");
const beginnerPreviewList = document.querySelector("#beginner-preview-list");
const beginnerReviewCard = document.querySelector("#beginner-review-card");
const beginnerReviewScore = document.querySelector("#beginner-review-score");
const beginnerReviewSummary = document.querySelector("#beginner-review-summary");
const beginnerAgentTaskType = document.querySelector("#beginner-agent-task-type");
const beginnerAgentPlanList = document.querySelector("#beginner-agent-plan-list");
const beginnerEvaluationStatus = document.querySelector("#beginner-evaluation-status");
const beginnerEvaluationSummary = document.querySelector("#beginner-evaluation-summary");
const beginnerEvaluationList = document.querySelector("#beginner-evaluation-list");
const beginnerTemplateMode = document.querySelector("#beginner-template-mode");
const beginnerTemplateMap = document.querySelector("#beginner-template-map");
const beginnerWorkflowSteps = document.querySelector("#beginner-workflow-steps");
const beginnerHistoryList = document.querySelector("#beginner-history-list");

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

const previewGroups = [
  { title: "基本信息", keys: ["lesson_title", "subject", "grade", "class_hour"] },
  { title: "教学目标", keys: ["teaching_goals"] },
  { title: "重难点", keys: ["key_points", "difficult_points", "teaching_preparation"] },
  { title: "教学过程", keys: ["teaching_process", "blackboard_design"] },
  { title: "作业与反思", keys: ["homework", "reflection"] },
];

const backendLabels = {
  deepseek: "DeepSeek V4 Pro",
  local: "本地草稿",
  local_fallback: "DeepSeek 失败，已用本地草稿",
};

const missingLabels = {
  subject: "学科",
  grade: "年级",
  title: "课题",
  task_type: "任务类型",
};

const defaultWorkflowNodes = [
  { id: "app_input", label: "接收课程需求", layer: "应用层" },
  { id: "template_analyzer", label: "分析 Word 模板", layer: "编排层" },
  { id: "knowledge_context", label: "提取教材重点", layer: "知识层" },
  { id: "lesson_writer", label: "生成教案初稿", layer: "Agent 层" },
  { id: "teaching_reviewer", label: "教研审阅", layer: "Agent 层" },
  { id: "lesson_reviser", label: "修订优化", layer: "Agent 层" },
  { id: "doc_renderer", label: "写入 Word", layer: "工具层" },
  { id: "history_store", label: "保存历史", layer: "数据层" },
];

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
let activeMode = localStorage.getItem("teacherSkillMode") || "beginner";
let beginnerTask = null;
let beginnerStep = "intent";
let beginnerDownloadIsFresh = false;

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function showBeginnerNotice(message, isError = false) {
  beginnerNotice.hidden = !message;
  beginnerNotice.textContent = message || "";
  beginnerNotice.classList.toggle("error", isError);
}

function focusStatus() {
  statusBox.scrollIntoView({ behavior: "smooth", block: "center" });
}

function setMode(mode) {
  activeMode = mode === "professional" ? "professional" : "beginner";
  localStorage.setItem("teacherSkillMode", activeMode);
  beginnerWorkflow.hidden = activeMode !== "beginner";
  professionalWorkspace.hidden = activeMode !== "professional";
  beginnerModeButton.classList.toggle("is-active", activeMode === "beginner");
  professionalModeButton.classList.toggle("is-active", activeMode === "professional");
  beginnerModeButton.setAttribute("aria-selected", activeMode === "beginner" ? "true" : "false");
  professionalModeButton.setAttribute("aria-selected", activeMode === "professional" ? "true" : "false");
}

function setBeginnerStep(step) {
  beginnerStep = step;
  document.querySelectorAll(".beginner-step").forEach((panel) => {
    panel.hidden = panel.dataset.step !== step;
  });
  document.querySelectorAll("[data-beginner-nav]").forEach((button) => {
    const target = button.dataset.beginnerNav;
    const order = ["intent", "confirm", "prepare", "done"];
    const activeIndex = step === "generating" ? 3 : order.indexOf(step);
    const buttonIndex = order.indexOf(target);
    button.classList.toggle("is-active", target === step || (step === "generating" && target === "done"));
    button.classList.toggle("is-complete", buttonIndex >= 0 && buttonIndex < activeIndex);
  });
  showBeginnerNotice("");
}

function validateAgentInputs() {
  if (!agentRequestInput.value.trim()) {
    setStatus("请先输入一句话指令", true);
    agentRequestInput.focus();
    return false;
  }
  if (!templateInput.files || templateInput.files.length === 0) {
    setStatus("专业模式需要上传学校 Word 模板；新手模式可以直接使用系统标准模板。", true);
    templateInput.focus();
    return false;
  }
  return true;
}

function setBusy(isBusy) {
  generateButton.disabled = isBusy;
  agentRunButton.disabled = isBusy;
  beginnerStartButton.disabled = isBusy;
  beginnerGenerateButton.disabled = isBusy;
  exportButton.disabled = isBusy || !currentFields;
  generateButton.querySelector("span:last-child").textContent = isBusy ? "生成中" : "生成教案";
  agentRunButton.querySelector("span:last-child").textContent = isBusy ? "备课中" : "开始备课";
  beginnerStartButton.querySelector("span:last-child").textContent = isBusy ? "理解中" : "开始备课";
  beginnerGenerateButton.textContent = isBusy ? "正在生成" : "生成教案";
}

function setDownloadReady(url, outputName) {
  currentDownloadUrl = url || "#";
  fileName.textContent = outputName || "已生成";
  downloadLink.href = currentDownloadUrl;
  downloadLink.classList.toggle("is-disabled", !url);
  downloadLink.setAttribute("aria-disabled", url ? "false" : "true");

  beginnerDownloadLink.href = currentDownloadUrl;
  beginnerDownloadLink.classList.toggle("is-disabled", !url);
  beginnerDownloadLink.setAttribute("aria-disabled", url ? "false" : "true");
  beginnerDownloadIsFresh = Boolean(url);
}

function setPreviewReady(url) {
  currentPreviewUrl = url || "#";
  previewLink.href = currentPreviewUrl;
  previewLink.classList.toggle("is-disabled", !url);
  previewLink.setAttribute("aria-disabled", url ? "false" : "true");

  beginnerPreviewLink.href = currentPreviewUrl;
  beginnerPreviewLink.classList.toggle("is-disabled", !url);
  beginnerPreviewLink.setAttribute("aria-disabled", url ? "false" : "true");
}

function setDownloadStale(message = "未导出") {
  currentDownloadUrl = "#";
  currentPreviewUrl = "#";
  fileName.textContent = message;
  downloadLink.href = "#";
  downloadLink.classList.add("is-disabled");
  downloadLink.setAttribute("aria-disabled", "true");
  beginnerDownloadLink.href = "#";
  beginnerDownloadLink.classList.add("is-disabled");
  beginnerDownloadLink.setAttribute("aria-disabled", "true");
  beginnerDownloadIsFresh = false;
  setPreviewReady(null);
}

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

function renderWorkflowTrace(trace = [], target = workflowSteps) {
  const nodes = workflowSchema?.nodes?.length ? workflowSchema.nodes : defaultWorkflowNodes;
  const traceByNode = new Map((trace || []).map((item) => [item.node, item]));
  target.innerHTML = "";
  nodes.forEach((node) => {
    const event = traceByNode.get(node.id);
    const item = document.createElement("div");
    item.className = `workflow-step ${event?.status || ""}`.trim();

    const title = document.createElement("strong");
    title.textContent = node.label;

    const detail = document.createElement("span");
    detail.textContent = event ? event.detail : node.layer;

    item.append(title, detail);
    target.appendChild(item);
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
    beginnerReviewCard.hidden = true;
    return;
  }

  reviewPanel.hidden = false;
  reviewScore.textContent = `${report.score || 0}分`;
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

  beginnerReviewCard.hidden = false;
  beginnerReviewScore.textContent = `${report.score || 0}分`;
  beginnerReviewSummary.textContent = report.summary || (report.improvements || [])[0] || "结构完整，可结合班级情况微调。";
}

function renderAgentPlan(task, plan = [], target = agentPlanList, labelTarget = agentTaskType) {
  currentAgentPlan = plan || null;
  if (!task && !plan.length) {
    agentResultPanel.hidden = true;
    labelTarget.textContent = "等待任务";
    target.innerHTML = "";
    return;
  }

  if (target === agentPlanList) {
    agentResultPanel.hidden = false;
  }
  labelTarget.textContent = task ? `${task.task_type || "unknown"} · ${Math.round((task.confidence || 0) * 100)}%` : "执行计划";
  target.innerHTML = "";
  plan.forEach((step) => {
    const item = document.createElement("div");
    item.className = `agent-plan-step ${step.status || ""}`.trim();
    const status = document.createElement("strong");
    status.textContent = step.status || "pending";
    const detail = document.createElement("span");
    detail.textContent = `${step.label || step.tool}${step.detail ? `：${step.detail}` : ""}`;
    item.append(status, detail);
    target.appendChild(item);
  });
}

function renderEvaluation(report, targets = {}) {
  currentEvaluationReport = report || null;
  const panel = targets.panel || evaluationPanel;
  const statusTarget = targets.status || evaluationStatus;
  const summaryTarget = targets.summary || evaluationSummary;
  const listTarget = targets.list || evaluationList;

  if (!report) {
    if (panel) panel.hidden = true;
    statusTarget.textContent = "待检查";
    summaryTarget.textContent = "";
    listTarget.innerHTML = "";
    return;
  }

  if (panel) panel.hidden = false;
  statusTarget.textContent = report.passed ? "通过" : "需复核";
  summaryTarget.textContent = report.summary || "";
  listTarget.innerHTML = "";
  (report.checks || []).forEach((check) => {
    const item = document.createElement("div");
    item.className = `evaluation-check ${check.passed ? "passed" : "failed"}`;
    const status = document.createElement("strong");
    status.textContent = check.passed ? "通过" : "未通过";
    const detail = document.createElement("span");
    detail.textContent = check.detail || check.name;
    item.append(status, detail);
    listTarget.appendChild(item);
  });
}

function renderHistory(items = []) {
  historyList.innerHTML = "";
  beginnerHistoryList.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = "暂无导出记录";
    historyList.appendChild(empty);
    beginnerHistoryList.textContent = "暂无";
    return;
  }

  items.slice(0, 6).forEach((item) => {
    const link = document.createElement("a");
    link.className = "history-item";
    link.href = item.download_url;

    const text = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = `${item.grade || ""}${item.subject || ""}《${item.title || "教案"}》`;
    const meta = document.createElement("span");
    meta.textContent = `${item.created_at || ""} · ${backendLabels[item.backend] || item.backend || "生成器"}`;
    text.append(title, meta);

    const action = document.createElement("span");
    action.textContent = "下载";
    link.append(text, action);
    historyList.appendChild(link);
  });

  items.slice(0, 2).forEach((item) => {
    const link = document.createElement("a");
    link.href = item.download_url;
    link.textContent = `${item.grade || ""}${item.subject || ""}《${item.title || "教案"}》`;
    beginnerHistoryList.appendChild(link);
  });
}

async function loadWorkflowSchema() {
  try {
    const response = await fetch("/api/workflow-schema");
    workflowSchema = await response.json();
    workflowVersion.textContent = workflowSchema.version || "Teacher_skill V7";
  } catch {
    workflowSchema = null;
  }
  renderWorkflowTrace(currentWorkflowTrace, workflowSteps);
  renderWorkflowTrace(currentWorkflowTrace, beginnerWorkflowSteps);
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
  const text = `${fields.grade || ""}${fields.subject || ""}《${fields.lesson_title || ""}》`;
  resultTitle.textContent = text;
  beginnerResultTitle.textContent = text ? `${text}教案已完成` : "教案已完成";
}

function orderedFieldKeys(fields) {
  return [...previewOrder, ...Object.keys(fields || {}).filter((key) => !previewOrder.includes(key))].filter((key, index, array) => {
    return fields?.[key] && array.indexOf(key) === index;
  });
}

function createFieldEditor(key, value, editable = true) {
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
    ["more_vivid", "更像公开课"],
    ["simplify", "更适合基础班"],
    ["more_interaction", "增加课堂互动"],
    ["shorten", "压缩到40分钟"],
    ["blackboard_clean", "板书更简洁"],
  ].forEach(([optionValue, label]) => {
    const option = document.createElement("option");
    option.value = optionValue;
    option.textContent = label;
    refineMode.appendChild(option);
  });

  const refineButton = document.createElement("button");
  refineButton.type = "button";
  refineButton.className = "icon-button refine-button";
  refineButton.dataset.refineField = key;
  refineButton.title = "局部优化";
  refineButton.setAttribute("aria-label", `${fieldLabels[key] || key} 局部优化`);
  refineButton.textContent = "AI";

  controls.append(refineMode, refineButton);
  itemHead.append(title, controls);

  const body = document.createElement("textarea");
  body.className = "field-editor";
  body.dataset.field = key;
  body.value = value;
  body.readOnly = !editable;
  if (["lesson_title", "subject", "grade", "class_hour"].includes(key)) {
    body.classList.add("compact");
    body.rows = 1;
  } else {
    body.rows = Math.min(10, Math.max(3, String(value).split("\n").length + 1));
  }

  item.append(itemHead, body);
  return item;
}

function renderPreview(fields, target = previewList) {
  target.innerHTML = "";
  orderedFieldKeys(fields).forEach((key) => {
    target.appendChild(createFieldEditor(key, fields[key], true));
  });
}

function renderGroupedPreview(fields, target = beginnerPreviewList) {
  target.innerHTML = "";
  const rendered = new Set();
  previewGroups.forEach((group, index) => {
    const keys = group.keys.filter((key) => fields?.[key]);
    if (!keys.length) return;

    const details = document.createElement("details");
    details.className = "field-section";
    details.open = index < 2;
    const summary = document.createElement("summary");
    summary.textContent = group.title;
    details.appendChild(summary);

    keys.forEach((key) => {
      rendered.add(key);
      details.appendChild(createFieldEditor(key, fields[key], true));
    });
    target.appendChild(details);
  });

  orderedFieldKeys(fields)
    .filter((key) => !rendered.has(key))
    .forEach((key) => {
      const details = target.querySelector(".field-section.other") || document.createElement("details");
      if (!details.classList.contains("other")) {
        details.className = "field-section other";
        details.open = true;
        const summary = document.createElement("summary");
        summary.textContent = "其他字段";
        details.appendChild(summary);
        target.appendChild(details);
      }
      details.appendChild(createFieldEditor(key, fields[key], true));
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

function activeEditorRoot() {
  return activeMode === "beginner" ? beginnerPreviewList : previewList;
}

function renderTemplateAnalysis(analysis, targets = {}) {
  currentTemplateAnalysis = analysis || null;
  const modeTarget = targets.mode || templateMode;
  const mapTarget = targets.map || templateMap;
  if (!analysis) {
    modeTarget.textContent = "待识别";
    mapTarget.hidden = true;
    mapTarget.innerHTML = "";
    return;
  }

  const placeholderCount = analysis.placeholders?.length || 0;
  const mappingEntries = Object.entries(analysis.table_mappings || {});
  modeTarget.textContent = placeholderCount > 0 ? "占位符填充" : "表格映射填充";
  mapTarget.hidden = false;
  mapTarget.innerHTML = "";

  const title = document.createElement("div");
  title.className = "template-map-title";
  title.textContent =
    placeholderCount > 0
      ? `已读取 ${placeholderCount} 个 Word 占位符，生成时保持原模板格式。`
      : `未发现占位符，已按表格标签自动匹配 ${mappingEntries.length} 个字段。`;
  mapTarget.appendChild(title);

  const list = document.createElement("div");
  list.className = "template-map-list";
  const fields = placeholderCount > 0 ? analysis.placeholders : mappingEntries.map(([field]) => field);
  fields.forEach((field) => {
    const chip = document.createElement("span");
    chip.textContent = fieldLabels[field] || field;
    list.appendChild(chip);
  });
  mapTarget.appendChild(list);
}

function collectEditedFields(root = activeEditorRoot()) {
  const fields = { ...(currentFields || {}) };
  root.querySelectorAll("[data-field]").forEach((node) => {
    fields[node.dataset.field] = node.value;
  });
  return fields;
}

function markEditedContent(root = activeEditorRoot()) {
  if (!currentFields) return;
  const hadDownload = currentDownloadUrl !== "#";
  currentFields = collectEditedFields(root);
  refreshResultTitle(currentFields);
  setDownloadStale(hadDownload ? "内容已修改，需重新导出" : "未导出");
  exportButton.disabled = false;
  if (activeMode === "beginner") {
    beginnerSummary.textContent = "内容已修改。下载前请重新生成 Word，以保证文件和页面内容一致。";
  } else if (hadDownload) {
    setStatus("内容已修改，请重新生成 Word");
  }
}

function applyGenerationResult(data, formData = null) {
  currentFields = data.fields;
  currentTemplateId = data.template_id;
  currentTemplateAnalysis = data.template_analysis;
  currentReviewReport = data.review_report || null;
  currentWorkflowTrace = data.workflow_trace || [];
  currentGenerationBackend = data.generation_backend || null;
  currentRequestContext = formData
    ? readRequestContext(formData)
    : {
        ...(data.agent_task || {}),
        material: beginnerMaterial.value || "",
      };

  if (data.workflow_schema) {
    workflowSchema = data.workflow_schema;
    workflowVersion.textContent = workflowSchema.version || "Teacher_skill V7";
  }

  refreshResultTitle(data.fields);
  fieldCount.textContent = String((data.template_fields || []).length);
  renderTemplateAnalysis(data.template_analysis);
  renderTemplateAnalysis(data.template_analysis, { mode: beginnerTemplateMode, map: beginnerTemplateMap });
  renderAgentPlan(data.agent_task, data.agent_plan || [], agentPlanList, agentTaskType);
  renderAgentPlan(data.agent_task, data.agent_plan || [], beginnerAgentPlanList, beginnerAgentTaskType);
  renderEvaluation(data.evaluation_report);
  renderEvaluation(data.evaluation_report, {
    panel: null,
    status: beginnerEvaluationStatus,
    summary: beginnerEvaluationSummary,
    list: beginnerEvaluationList,
  });
  renderReviewReport(currentReviewReport);
  renderWorkflowTrace(currentWorkflowTrace, workflowSteps);
  renderWorkflowTrace(currentWorkflowTrace, beginnerWorkflowSteps);
  renderPreview(data.fields);
  renderGroupedPreview(data.fields);
  if (data.download_url) {
    setDownloadReady(data.download_url, data.output_name);
    setPreviewReady(data.preview_url);
  } else {
    setDownloadStale("未导出");
  }
}

async function exportCurrentDocument() {
  if (!currentFields || !currentTemplateId) {
    throw new Error("请先生成教案");
  }

  const editedFields = collectEditedFields(activeEditorRoot());
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
  renderTemplateAnalysis(currentTemplateAnalysis, { mode: beginnerTemplateMode, map: beginnerTemplateMap });
  renderWorkflowTrace(currentWorkflowTrace, workflowSteps);
  renderWorkflowTrace(currentWorkflowTrace, beginnerWorkflowSteps);
  setDownloadReady(data.download_url, data.output_name);
  setPreviewReady(data.preview_url);
  loadHistory();
  return data;
}

function fillBeginnerTask(task) {
  beginnerTask = task;
  beginnerSubject.value = task.subject || "";
  beginnerGrade.value = task.grade || "";
  beginnerTitle.value = task.title || "";
  beginnerClassType.value = task.class_type || "新授课";
  beginnerClassHour.value = task.class_hour || "1课时";
  beginnerTeachingStyle.value = task.teaching_style || "常规启发式";

  if (task.missing_fields?.length) {
    const labels = task.missing_fields.map((key) => missingLabels[key] || key).join("、");
    beginnerMissingCard.hidden = false;
    beginnerMissingCard.textContent = `还差一步：请补齐 ${labels}。可以直接在上面的卡片里填写。`;
  } else {
    beginnerMissingCard.hidden = true;
    beginnerMissingCard.textContent = "";
  }
}

function validateBeginnerConfirm() {
  const missing = [];
  if (!beginnerSubject.value.trim()) missing.push("学科");
  if (!beginnerGrade.value.trim()) missing.push("年级");
  if (!beginnerTitle.value.trim()) missing.push("课题");
  if (missing.length) {
    beginnerMissingCard.hidden = false;
    beginnerMissingCard.textContent = `我还不知道这节课的${missing.join("、")}是什么，请补充后继续。`;
    return false;
  }
  return true;
}

function getBeginnerTemplateMode() {
  return document.querySelector('input[name="beginner_template_mode"]:checked')?.value || "system";
}

function syncBeginnerTemplateMode() {
  const mode = getBeginnerTemplateMode();
  beginnerUploadWrap.hidden = mode !== "upload";
  beginnerGenericNote.textContent =
    mode === "system"
      ? "默认使用系统标准模板。没有教材也可以生成通用版。"
      : "上传学校模板后，系统会尽量保持原 Word 格式。";
}

function resetBeginnerProgress() {
  beginnerProgressList.querySelectorAll("[data-progress-step]").forEach((item) => {
    item.classList.remove("done", "active");
  });
}

function beginFakeProgress() {
  const items = [...beginnerProgressList.querySelectorAll("[data-progress-step]")];
  let index = 0;
  resetBeginnerProgress();
  items[0]?.classList.add("active");
  return window.setInterval(() => {
    if (index < items.length - 1) {
      items[index].classList.remove("active");
      items[index].classList.add("done");
      index += 1;
      items[index].classList.add("active");
    }
  }, 850);
}

function finishBeginnerProgress() {
  beginnerProgressList.querySelectorAll("[data-progress-step]").forEach((item) => {
    item.classList.remove("active");
    item.classList.add("done");
  });
}

async function previewBeginnerIntent() {
  const agentRequest = beginnerRequestInput.value.trim();
  if (!agentRequest) {
    showBeginnerNotice("我还不知道你要备哪节课。请先输入一句话需求，例如：帮我生成一份四年级语文《观潮》的探究课教案。", true);
    beginnerRequestInput.focus();
    return;
  }

  setBusy(true);
  showBeginnerNotice("正在理解你的备课需求...");
  try {
    const response = await fetch("/api/agent-preview", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ agent_request: agentRequest }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "需求识别失败");
    }
    fillBeginnerTask(data.agent_task);
    renderAgentPlan(data.agent_task, data.agent_plan || [], beginnerAgentPlanList, beginnerAgentTaskType);
    setBeginnerStep("confirm");
  } catch (error) {
    showBeginnerNotice(error.message || "需求识别失败，请换一种说法。", true);
  } finally {
    setBusy(false);
  }
}

async function runBeginnerAgent() {
  if (!validateBeginnerConfirm()) {
    setBeginnerStep("confirm");
    return;
  }

  const templateModeValue = getBeginnerTemplateMode();
  if (templateModeValue === "upload" && (!beginnerTemplateInput.files || beginnerTemplateInput.files.length === 0)) {
    showBeginnerNotice("还差一步：请选择学校 Word 模板，或改用系统标准模板。", true);
    beginnerTemplateInput.focus();
    return;
  }

  const formData = new FormData();
  formData.append("agent_request", beginnerRequestInput.value.trim());
  formData.append("subject", beginnerSubject.value.trim());
  formData.append("grade", beginnerGrade.value.trim());
  formData.append("title", beginnerTitle.value.trim());
  formData.append("class_type", beginnerClassType.value);
  formData.append("class_hour", beginnerClassHour.value.trim() || "1课时");
  formData.append("teaching_style", beginnerTeachingStyle.value);
  formData.append("student_level", "常规混合水平");
  formData.append("generation_depth", beginnerRequestInput.value.includes("公开课") ? "深度" : "标准");
  formData.append("template_mode", templateModeValue);
  formData.append("material", beginnerMaterial.value.trim());
  if (templateModeValue === "upload" && beginnerTemplateInput.files[0]) {
    formData.append("template", beginnerTemplateInput.files[0]);
  }

  setBusy(true);
  setBeginnerStep("generating");
  const timer = beginFakeProgress();

  try {
    const response = await fetch("/api/agent-run", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      if (data.agent_task) {
        fillBeginnerTask(data.agent_task);
        renderAgentPlan(data.agent_task, data.agent_plan || [], beginnerAgentPlanList, beginnerAgentTaskType);
        setBeginnerStep("confirm");
      }
      throw new Error(data.message || data.error || "生成失败");
    }

    finishBeginnerProgress();
    applyGenerationResult(data);
    beginnerSummary.textContent = data.beginner_summary || "已完成教研审阅，自动检查通过，可下载 Word。";
    if (data.is_generic_material) {
      beginnerSummary.textContent += " 本次未填写教材内容，已按通用版生成。";
    }
    loadHistory();
    setBeginnerStep("done");
  } catch (error) {
    showBeginnerNotice(error.message || "生成失败，请检查信息后重试。", true);
  } finally {
    window.clearInterval(timer);
    setBusy(false);
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
  renderWorkflowTrace([], workflowSteps);

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

    applyGenerationResult(data, formData);
    exportButton.disabled = false;
    setStatus(`教案已生成并完成教研审阅：${backendLabels[data.generation_backend] || "生成器"}`);
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
  setStatus("正在理解任务并执行备课流程");

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
  renderWorkflowTrace([], workflowSteps);

  try {
    const formData = new FormData(form);
    formData.append("template_mode", "upload");
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

    applyGenerationResult(data, formData);
    exportButton.disabled = false;
    loadHistory();
    setStatus(data.evaluation_report?.passed ? "已完成备课并通过自动检查" : "已完成备课，建议复核自动检查提示");
  } catch (error) {
    setStatus(error.message || "Agent 执行失败", true);
    focusStatus();
  } finally {
    setBusy(false);
  }
});

exportButton.addEventListener("click", async () => {
  exportButton.disabled = true;
  setStatus("正在生成 Word");

  try {
    activeMode = "professional";
    const data = await exportCurrentDocument();
    setStatus(data.preview_url ? "最新 Word 已生成，可预览或下载。" : "最新 Word 已生成；本机未检测到 PDF 预览工具。");
  } catch (error) {
    setStatus(error.message || "导出失败", true);
  } finally {
    exportButton.disabled = false;
  }
});

function handlePreviewInput(event) {
  if (event.target?.dataset?.field) {
    resizeFieldEditor(event.target);
    markEditedContent(event.currentTarget);
  }
}

async function handleRefineClick(event) {
  const button = event.target.closest(".refine-button");
  if (!button || !currentFields) return;

  const root = event.currentTarget;
  const field = button.dataset.refineField;
  const editor = root.querySelector(`[data-field="${field}"]`);
  const mode = root.querySelector(`[data-refine-field="${field}"].refine-mode`);
  if (!editor) return;

  button.disabled = true;
  const oldText = button.textContent;
  button.textContent = "...";
  if (activeMode === "beginner") {
    showBeginnerNotice(`正在优化：${fieldLabels[field] || field}`);
  } else {
    setStatus(`正在局部优化：${fieldLabels[field] || field}`);
  }

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
    markEditedContent(root);
    if (activeMode === "beginner") {
      showBeginnerNotice(`${fieldLabels[field] || field} 已优化，下载前请重新生成 Word。`);
    } else {
      setStatus(`${fieldLabels[field] || field} 已优化，请重新生成 Word`);
    }
  } catch (error) {
    if (activeMode === "beginner") {
      showBeginnerNotice(error.message || "局部优化失败", true);
    } else {
      setStatus(error.message || "局部优化失败", true);
    }
  } finally {
    button.disabled = false;
    button.textContent = oldText;
  }
}

previewList.addEventListener("input", handlePreviewInput);
previewList.addEventListener("click", handleRefineClick);
beginnerPreviewList.addEventListener("input", handlePreviewInput);
beginnerPreviewList.addEventListener("click", handleRefineClick);

downloadLink.addEventListener("click", (event) => {
  if (downloadLink.classList.contains("is-disabled")) {
    event.preventDefault();
    setStatus(currentFields ? "请先生成最新 Word" : "请先生成教案", true);
  }
});

previewLink.addEventListener("click", (event) => {
  if (previewLink.classList.contains("is-disabled")) {
    event.preventDefault();
    setStatus(currentFields ? "当前环境未生成预览，请下载 Word 查看。" : "请先生成教案", true);
  }
});

beginnerDownloadLink.addEventListener("click", async (event) => {
  if (beginnerDownloadLink.classList.contains("is-disabled") || !beginnerDownloadIsFresh) {
    event.preventDefault();
    if (!currentFields) {
      showBeginnerNotice("请先生成教案。", true);
      return;
    }
    try {
      activeMode = "beginner";
      showBeginnerNotice("正在把修改后的内容重新写入 Word...");
      await exportCurrentDocument();
      showBeginnerNotice("最新 Word 已生成，请再次点击下载。");
    } catch (error) {
      showBeginnerNotice(error.message || "导出失败", true);
    }
  }
});

beginnerPreviewLink.addEventListener("click", (event) => {
  if (beginnerPreviewLink.classList.contains("is-disabled")) {
    event.preventDefault();
    showBeginnerNotice(currentFields ? "当前环境未生成预览，请下载 Word 查看。" : "请先生成教案。", true);
  }
});

beginnerModeButton.addEventListener("click", () => setMode("beginner"));
professionalModeButton.addEventListener("click", () => setMode("professional"));
beginnerStartButton.addEventListener("click", previewBeginnerIntent);
beginnerConfirmButton.addEventListener("click", () => {
  if (validateBeginnerConfirm()) {
    setBeginnerStep("prepare");
  }
});
beginnerBackToIntent.addEventListener("click", () => setBeginnerStep("intent"));
beginnerBackToConfirm.addEventListener("click", () => setBeginnerStep("confirm"));
beginnerGenerateButton.addEventListener("click", runBeginnerAgent);
beginnerEditButton.addEventListener("click", () => {
  const firstEditor = beginnerPreviewList.querySelector("[data-field]");
  firstEditor?.focus();
  firstEditor?.scrollIntoView({ behavior: "smooth", block: "center" });
});
beginnerRegenerateButton.addEventListener("click", () => setBeginnerStep("prepare"));

document.querySelectorAll(".quick-prompts [data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    beginnerRequestInput.value = button.dataset.prompt || "";
    beginnerRequestInput.focus();
  });
});

document.querySelectorAll('input[name="beginner_template_mode"]').forEach((radio) => {
  radio.addEventListener("change", syncBeginnerTemplateMode);
});

beginnerMaterial.addEventListener("input", () => {
  beginnerGenericNote.textContent = beginnerMaterial.value.trim()
    ? "已收到教材内容，生成时会优先贴合这些材料。"
    : "不填写教材内容也能生成，但贴入教材后会更贴合课文。";
});

renderReviewReport(null);
renderAgentPlan(null, []);
renderAgentPlan(null, [], beginnerAgentPlanList, beginnerAgentTaskType);
renderEvaluation(null);
renderEvaluation(null, {
  panel: null,
  status: beginnerEvaluationStatus,
  summary: beginnerEvaluationSummary,
  list: beginnerEvaluationList,
});
renderWorkflowTrace([], workflowSteps);
renderWorkflowTrace([], beginnerWorkflowSteps);
syncBeginnerTemplateMode();
setBeginnerStep("intent");
setMode(activeMode);
loadWorkflowSchema();
loadHistory();
