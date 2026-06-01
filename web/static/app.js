const homeView = document.querySelector("#home-view");
const templateFlow = document.querySelector("#template-flow");
const quickFlow = document.querySelector("#quick-flow");
const resultView = document.querySelector("#result-view");
const templateForm = document.querySelector("#template-form");
const quickForm = document.querySelector("#quick-form");
const quickTemplateWrap = document.querySelector("#quick-template-wrap");
const quickMissingFields = document.querySelector("#quick-missing-fields");
const resultTitle = document.querySelector("#result-title");
const statusLine = document.querySelector("#status-line");
const previewGroupsRoot = document.querySelector("#preview-groups");
const exportButton = document.querySelector("#export-button");
const downloadLink = document.querySelector("#download-link");
const editAgainButton = document.querySelector("#edit-again-button");
const regenerateButton = document.querySelector("#regenerate-button");
const methodWarning = document.querySelector("#method-warning");
const aiStatus = document.querySelector("#ai-status");
const aiStatusText = document.querySelector("#ai-status-text");
const checkAiButton = document.querySelector("#check-ai-button");
const historyList = document.querySelector("#history-list");
const diagnosticsOutput = document.querySelector("#diagnostics-output");

const fieldLabels = {
  teaching_date: "授课日期",
  class_name: "授课班级",
  lesson_title: "课题",
  subject: "学科",
  grade: "班级/年级",
  class_type: "授课类型",
  class_hour: "课时数",
  teaching_environment: "对教学环境的要求",
  teaching_goals: "教学目的",
  teaching_key_difficult: "重点难点",
  teaching_aids: "教具挂图",
  teaching_process: "主要教学内容",
  teaching_method: "教学方法的运用",
  homework: "作业",
  reflection: "课后小记",
};

const previewGroups = [
  { title: "基本信息", keys: ["teaching_date", "class_name", "lesson_title", "subject", "grade", "class_type", "class_hour"] },
  { title: "教学准备", keys: ["teaching_environment", "teaching_aids"] },
  { title: "教学目标与重难点", keys: ["teaching_goals", "teaching_key_difficult"] },
  { title: "教学过程与方法", keys: ["teaching_process", "teaching_method"] },
  { title: "作业与反思", keys: ["homework", "reflection"] },
];

const fieldAliases = {
  teaching_date: ["teaching_date", "授课日期", "日期"],
  class_name: ["class_name", "授课班级", "班级", "grade"],
  lesson_title: ["lesson_title", "课题", "课题名称"],
  subject: ["subject", "学科"],
  grade: ["grade", "班级", "年级"],
  class_type: ["class_type", "授课类型", "课型"],
  class_hour: ["class_hour", "课时数", "课时"],
  teaching_environment: ["teaching_environment", "对教学环境的要求", "教学环境"],
  teaching_goals: ["teaching_goals", "教学目的", "教学目标"],
  teaching_key_difficult: ["teaching_key_difficult", "重点难点", "教学重难点"],
  teaching_aids: ["teaching_aids", "教具挂图", "教具"],
  teaching_process: ["teaching_process", "主要教学内容", "教学过程"],
  teaching_method: ["teaching_method", "教学方法的运用", "教学方法"],
  homework: ["homework", "作业", "作业设计"],
  reflection: ["reflection", "课后小记", "教学反思"],
};

let activeFlow = "home";
let currentFields = {};
let currentTemplateId = "";
let currentRequestContext = {};
let currentGenerationBackend = "";
let currentReviewReport = null;
let currentWorkflowTrace = [];
let currentTemplateAnalysis = null;
let currentFillReport = null;

function apiFetch(path, options = {}) {
  return fetch(path, options);
}

async function readApiJson(response) {
  const text = await response.text();
  if (!text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("接口返回的不是 JSON。请确认已通过本地 Teacher Skill 后端打开页面。");
  }
}

function setView(view) {
  activeFlow = view;
  homeView.hidden = view !== "home";
  templateFlow.hidden = view !== "template";
  quickFlow.hidden = view !== "quick";
  resultView.hidden = view === "home";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setStatus(message, isError = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", isError);
}

function setBusy(form, busy, textWhenBusy) {
  const buttons = form ? [...form.querySelectorAll("button")] : [];
  buttons.forEach((button) => {
    button.disabled = busy;
    if (button.type === "submit") {
      if (!button.dataset.originalText) button.dataset.originalText = button.textContent;
      button.textContent = busy ? textWhenBusy : button.dataset.originalText;
    }
  });
}

function normalizeDownloadUrl(url) {
  if (!url || url === "#") return "#";
  try {
    return new URL(url, window.location.origin).href;
  } catch {
    return url;
  }
}

function setDownload(url) {
  const href = normalizeDownloadUrl(url);
  const ready = href !== "#";
  downloadLink.href = href;
  downloadLink.classList.toggle("disabled", !ready);
  downloadLink.setAttribute("aria-disabled", ready ? "false" : "true");
}

function firstExistingKey(fields, canonicalKey) {
  const candidates = fieldAliases[canonicalKey] || [canonicalKey];
  return candidates.find((key) => Object.prototype.hasOwnProperty.call(fields, key)) || canonicalKey;
}

function fieldValue(fields, canonicalKey) {
  const key = firstExistingKey(fields, canonicalKey);
  return fields[key] ?? "";
}

function hasNonEmptyTeachingMethod(fields) {
  return String(fieldValue(fields, "teaching_method") || "").trim().length > 0;
}

function knownPreviewKeys() {
  return new Set(previewGroups.flatMap((group) => group.keys.flatMap((key) => fieldAliases[key] || [key])));
}

function createFieldEditor(fields, canonicalKey) {
  const actualKey = firstExistingKey(fields, canonicalKey);
  const item = document.createElement("label");
  item.className = "preview-field";

  const label = document.createElement("span");
  label.textContent = fieldLabels[canonicalKey] || fieldLabels[actualKey] || actualKey;

  const textarea = document.createElement("textarea");
  textarea.dataset.field = actualKey;
  textarea.rows = canonicalKey === "teaching_process" ? 8 : 3;
  textarea.value = fields[actualKey] ?? "";
  textarea.addEventListener("input", () => {
    currentFields[actualKey] = textarea.value;
    updateTeachingMethodGuard();
    setDownload(null);
  });

  item.append(label, textarea);
  return item;
}

function renderPreview(fields) {
  previewGroupsRoot.innerHTML = "";
  previewGroups.forEach((group) => {
    const section = document.createElement("details");
    section.className = "preview-section";
    section.open = true;

    const summary = document.createElement("summary");
    summary.textContent = group.title;
    section.append(summary);

    const grid = document.createElement("div");
    grid.className = "preview-grid";
    group.keys.forEach((key) => {
      grid.append(createFieldEditor(fields, key));
    });
    section.append(grid);
    previewGroupsRoot.append(section);
  });

  const used = knownPreviewKeys();
  const extraKeys = Object.keys(fields).filter((key) => !used.has(key));
  if (extraKeys.length) {
    const section = document.createElement("details");
    section.className = "preview-section";
    const summary = document.createElement("summary");
    summary.textContent = "模板其他字段";
    section.append(summary);
    const grid = document.createElement("div");
    grid.className = "preview-grid";
    extraKeys.forEach((key) => grid.append(createFieldEditor(fields, key)));
    section.append(grid);
    previewGroupsRoot.append(section);
  }

  updateTeachingMethodGuard();
}

function collectEditedFields() {
  const fields = { ...currentFields };
  previewGroupsRoot.querySelectorAll("[data-field]").forEach((textarea) => {
    fields[textarea.dataset.field] = textarea.value;
  });
  return fields;
}

function updateTeachingMethodGuard() {
  const fields = collectEditedFields();
  const blocked = !hasNonEmptyTeachingMethod(fields);
  methodWarning.hidden = !blocked;
  exportButton.disabled = blocked;
}

function readRequestContextFromForm(form) {
  const data = new FormData(form);
  return {
    subject: data.get("subject") || "",
    grade: data.get("grade") || "",
    title: data.get("title") || "",
    class_hour: data.get("class_hour") || "1课时",
    class_type: data.get("class_type") || "",
    teaching_style: data.get("teaching_style") || "",
    generation_depth: data.get("generation_depth") || "",
  };
}

function buildDiagnostics(payload = {}) {
  const useful = {
    template_fields: payload.template_fields || currentTemplateAnalysis?.mapped_fields || [],
    template_analysis: payload.template_analysis || currentTemplateAnalysis,
    fill_report: payload.fill_report || currentFillReport,
    evaluation_report: payload.evaluation_report || null,
  };
  diagnosticsOutput.textContent = JSON.stringify(useful, null, 2);
}

function applyResult(data, options = {}) {
  currentFields = data.fields || {};
  currentTemplateId = data.template_id || currentTemplateId || "";
  currentTemplateAnalysis = data.template_analysis || currentTemplateAnalysis || null;
  currentReviewReport = data.review_report || data.review_report === null ? data.review_report : currentReviewReport;
  currentWorkflowTrace = data.workflow_trace || currentWorkflowTrace || [];
  currentGenerationBackend = data.generation_backend || currentGenerationBackend || "";
  currentFillReport = data.fill_report || currentFillReport || null;

  resultTitle.textContent = options.title || "字段预览 / 可编辑";
  renderPreview(currentFields);
  buildDiagnostics(data);
  setDownload(data.download_url || null);
}

async function loadAiStatus(probe = false) {
  checkAiButton.disabled = true;
  aiStatusText.textContent = probe ? "诊断中" : "检查中";
  try {
    const response = await apiFetch(`/api/llm-health${probe ? "?probe=1" : ""}`);
    const data = await readApiJson(response);
    const llm = data.llm || {};
    const state = llm.status || (llm.ok ? "ok" : "not_configured");
    const labels = {
      ok: "正常",
      configured: "已配置",
      not_configured: "未配置",
      error: "异常",
    };
    aiStatus.dataset.status = state;
    aiStatusText.textContent = labels[state] || state;
    aiStatus.title = llm.message || "";
  } catch {
    aiStatus.dataset.status = "error";
    aiStatusText.textContent = "异常";
  } finally {
    checkAiButton.disabled = false;
  }
}

async function loadHistory() {
  try {
    const response = await apiFetch("/api/history");
    const data = await readApiJson(response);
    const items = data.items || [];
    historyList.innerHTML = "";
    if (!items.length) {
      historyList.textContent = "暂无导出记录";
      return;
    }
    items.slice(0, 5).forEach((item) => {
      const link = document.createElement("a");
      link.className = "history-item";
      link.href = normalizeDownloadUrl(item.download_url);
      link.textContent = `${item.title || item.output_name || "教案"} · ${item.grade || ""}`;
      historyList.append(link);
    });
  } catch {
    historyList.textContent = "无法读取最近导出";
  }
}

async function submitTemplateFlow(event) {
  event.preventDefault();
  const templateFile = document.querySelector("#template-file");
  if (!templateFile.files.length) {
    setStatus("请先上传学校 Word 模板。", true);
    templateFile.focus();
    return;
  }

  setView("template");
  resultView.hidden = false;
  setStatus("正在识别模板字段并生成教案内容...");
  setBusy(templateForm, true, "生成中");
  setDownload(null);

  try {
    const formData = new FormData(templateForm);
    currentRequestContext = readRequestContextFromForm(templateForm);
    const response = await apiFetch("/api/draft", { method: "POST", body: formData });
    const data = await readApiJson(response);
    if (!response.ok) throw new Error(data.error || "生成失败");
    applyResult(data, { title: "老师确认 / 编辑字段" });
    setStatus("字段内容已生成。请确认后点击“写入 Word”。");
  } catch (error) {
    setStatus(error.message || "生成失败", true);
  } finally {
    setBusy(templateForm, false, "生成并填写模板");
  }
}

async function previewQuickRequest(formData) {
  const payload = {
    agent_request: formData.get("agent_request") || "",
    subject: formData.get("subject") || "",
    grade: formData.get("grade") || "",
    title: formData.get("title") || "",
  };
  const response = await apiFetch("/api/agent-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await readApiJson(response);
  if (!response.ok) throw new Error(data.error || "需求解析失败");
  return data;
}

function fillQuickMissingFields(task = {}) {
  quickMissingFields.hidden = false;
  const subject = quickMissingFields.querySelector('[name="subject"]');
  const grade = quickMissingFields.querySelector('[name="grade"]');
  const title = quickMissingFields.querySelector('[name="title"]');
  if (!subject.value) subject.value = task.subject || "";
  if (!grade.value) grade.value = task.grade || "";
  if (!title.value) title.value = task.title || "";
}

function quickRequiredFieldsAreReady() {
  const subject = quickMissingFields.querySelector('[name="subject"]').value.trim();
  const grade = quickMissingFields.querySelector('[name="grade"]').value.trim();
  const title = quickMissingFields.querySelector('[name="title"]').value.trim();
  return subject && grade && title;
}

async function submitQuickFlow(event) {
  event.preventDefault();
  setView("quick");
  resultView.hidden = false;
  setStatus("正在理解一句话需求...");
  setBusy(quickForm, true, "生成中");
  setDownload(null);

  try {
    const formData = new FormData(quickForm);
    const preview = await previewQuickRequest(formData);
    const task = preview.agent_task || {};
    const missing = preview.missing_fields || task.missing_fields || [];
    if (missing.length && !quickRequiredFieldsAreReady()) {
      fillQuickMissingFields(task);
      setStatus("还缺少学科、班级或课题，请补齐后再次点击“生成教案”。", true);
      return;
    }

    const requestData = new FormData(quickForm);
    const supplement = new FormData(quickMissingFields.closest("form"));
    ["subject", "grade", "title"].forEach((key) => {
      const value = supplement.get(key);
      if (value && !requestData.get(key)) requestData.set(key, value);
    });
    requestData.set("class_hour", task.class_hour || "1课时");
    requestData.set("class_type", task.class_type || "新授课");
    requestData.set("teaching_style", task.teaching_style || "常规启发式");
    requestData.set("student_level", task.student_level || "常规混合水平");
    requestData.set("generation_depth", task.generation_depth || "标准");
    requestData.set("strict_ai", "1");

    if (requestData.get("template_mode") === "upload") {
      const file = document.querySelector("#quick-template-file");
      if (!file.files.length) {
        setStatus("请选择学校 Word 模板，或改用系统标准模板。", true);
        file.focus();
        return;
      }
      requestData.set("template", file.files[0]);
    }

    setStatus("正在生成标准教案并写入 Word...");
    const response = await apiFetch("/api/agent-run", { method: "POST", body: requestData });
    const data = await readApiJson(response);
    if (!response.ok) {
      if (data.needs_input && data.agent_task) fillQuickMissingFields(data.agent_task);
      throw new Error(data.message || data.error || "生成失败");
    }
    currentRequestContext = {
      subject: requestData.get("subject") || task.subject || "",
      grade: requestData.get("grade") || task.grade || "",
      title: requestData.get("title") || task.title || "",
      class_hour: requestData.get("class_hour") || "1课时",
    };
    applyResult(data, { title: "标准教案预览 / 可编辑" });
    setStatus("教案已生成。可以直接下载，也可以编辑后重新写入 Word。");
    loadHistory();
  } catch (error) {
    setStatus(error.message || "生成失败", true);
  } finally {
    setBusy(quickForm, false, "生成教案");
  }
}

async function exportEditedDocument() {
  const editedFields = collectEditedFields();
  if (!hasNonEmptyTeachingMethod(editedFields)) {
    updateTeachingMethodGuard();
    setStatus("教学方法的运用为空，请补充后再导出。", true);
    return;
  }
  if (!currentTemplateId) {
    setStatus("缺少模板信息，请重新生成。", true);
    return;
  }

  exportButton.disabled = true;
  setStatus("正在写入 Word...");
  try {
    const response = await apiFetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template_id: currentTemplateId,
        fields: editedFields,
        request_context: currentRequestContext,
        generation_backend: currentGenerationBackend,
        review_report: currentReviewReport,
        workflow_trace: currentWorkflowTrace,
      }),
    });
    const data = await readApiJson(response);
    if (!response.ok) throw new Error(data.error || "写入 Word 失败");
    currentFields = editedFields;
    currentTemplateAnalysis = data.template_analysis || currentTemplateAnalysis;
    currentFillReport = data.fill_report || currentFillReport;
    currentWorkflowTrace = data.workflow_trace || currentWorkflowTrace;
    buildDiagnostics(data);
    setDownload(data.download_url);
    setStatus("Word 已写入完成，可以下载。");
    loadHistory();
  } catch (error) {
    setStatus(error.message || "写入 Word 失败", true);
  } finally {
    exportButton.disabled = false;
    updateTeachingMethodGuard();
  }
}

document.querySelector("#open-template-flow").addEventListener("click", () => setView("template"));
document.querySelector("#open-quick-flow").addEventListener("click", () => setView("quick"));
document.querySelectorAll("[data-back-home]").forEach((button) => {
  button.addEventListener("click", () => setView("home"));
});

templateForm.addEventListener("submit", submitTemplateFlow);
quickForm.addEventListener("submit", submitQuickFlow);
exportButton.addEventListener("click", exportEditedDocument);
checkAiButton.addEventListener("click", () => loadAiStatus(true));
document.querySelector("#refresh-history-button").addEventListener("click", loadHistory);

editAgainButton.addEventListener("click", () => {
  const first = previewGroupsRoot.querySelector("textarea");
  first?.focus();
  first?.scrollIntoView({ behavior: "smooth", block: "center" });
});

regenerateButton.addEventListener("click", () => {
  setDownload(null);
  if (activeFlow === "quick") {
    quickForm.requestSubmit();
  } else if (activeFlow === "template") {
    templateForm.requestSubmit();
  }
});

downloadLink.addEventListener("click", (event) => {
  if (downloadLink.classList.contains("disabled")) {
    event.preventDefault();
    setStatus("请先生成并写入 Word。", true);
  }
});

quickForm.querySelectorAll('input[name="template_mode"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    quickTemplateWrap.hidden = quickForm.template_mode.value !== "upload";
  });
});

setView("home");
setDownload(null);
loadAiStatus(false);
loadHistory();
