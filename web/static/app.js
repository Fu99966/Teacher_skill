const lessonForm = document.querySelector("#lesson-form");
const agentRequest = document.querySelector("#agent-request");
const supplementFields = document.querySelector("#supplement-fields");
const useSchoolTemplate = document.querySelector("#use-school-template");
const templateUploadWrap = document.querySelector("#template-upload-wrap");
const templateInput = document.querySelector("#template-input");
const generateButton = document.querySelector("#generate-button");
const previewCard = document.querySelector("#preview-card");
const previewGroupsRoot = document.querySelector("#preview-groups");
const statusLine = document.querySelector("#status-line");
const scopeHint = document.querySelector("#scope-hint");
const methodWarning = document.querySelector("#method-warning");
const deriveMethodButton = document.querySelector("#derive-method-button");
const exportButton = document.querySelector("#export-button");
const regenerateButton = document.querySelector("#regenerate-button");
const deliveryCard = document.querySelector("#delivery-card");
const deliveryChecklist = document.querySelector("#delivery-checklist");
const qualityJudgment = document.querySelector("#quality-judgment");
const qualityScore = document.querySelector("#quality-score");
const qualityRisk = document.querySelector("#quality-risk");
const qualitySuggestion = document.querySelector("#quality-suggestion");
const downloadLink = document.querySelector("#download-link");
const backEditButton = document.querySelector("#back-edit-button");
const restartButton = document.querySelector("#restart-button");
const aiStatus = document.querySelector("#ai-status");
const aiStatusText = document.querySelector("#ai-status-text");
const checkAiButton = document.querySelector("#check-ai-button");
const historyList = document.querySelector("#history-list");
const refreshHistoryButton = document.querySelector("#refresh-history-button");
const diagnosticsOutput = document.querySelector("#diagnostics-output");
const toast = document.querySelector("#toast");

const examplePrompts = {
  training: "帮我生成一份 24物联网1班《PCB板设计》的实训课教案，适合项目式教学，课时 2 课时。",
  open: "帮我生成一份《传感器基础》的公开课教案，要求有情境导入、学生互动和评价反馈。",
  regular: "帮我生成一份《物联网通信基础》的常规课教案，内容简洁，适合日常备课。"
};

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
  reflection: "课后小记"
};

const previewGroups = [
  { title: "基本信息", keys: ["teaching_date", "class_name", "lesson_title", "subject", "grade", "class_type", "class_hour"] },
  { title: "教学准备", keys: ["teaching_environment", "teaching_aids"] },
  { title: "教学目标与重难点", keys: ["teaching_goals", "teaching_key_difficult"] },
  { title: "教学过程与方法", keys: ["teaching_process", "teaching_method"] },
  { title: "作业与反思", keys: ["homework", "reflection"] }
];

const ChineseFieldAliases = {
  teaching_date: ["授课日期", "日期"],
  class_name: ["授课班级", "班级"],
  lesson_title: ["课题", "课题名称", "教学课题"],
  subject: ["学科"],
  grade: ["年级", "班级/年级"],
  class_type: ["授课类型", "课型"],
  class_hour: ["课时数", "课时"],
  teaching_environment: ["对教学环境的要求", "教学环境", "教学环境要求"],
  teaching_goals: ["教学目的", "教学目标", "教学目的与要求"],
  teaching_key_difficult: ["重点难点", "教学重难点"],
  teaching_aids: ["教具挂图", "教具", "教学用具"],
  teaching_process: ["主要教学内容", "教学过程", "教学流程"],
  teaching_method: ["教学方法的运用", "教学方法", "教法"],
  homework: ["作业", "作业设计"],
  reflection: ["课后小记", "课后小结", "教学反思"]
};

const requiredDeliveryKeys = [
  "lesson_title",
  "teaching_goals",
  "teaching_key_difficult",
  "teaching_process",
  "teaching_method",
  "homework",
  "reflection"
];

let currentFields = {};
let currentTemplateId = "";
let currentRequestContext = {};
let currentGenerationBackend = "";
let currentReviewReport = null;
let currentWorkflowTrace = [];
let currentTemplateAnalysis = null;
let currentFillReport = null;
let currentEvaluationReport = null;

function apiFetch(path, options = {}) {
  return fetch(path, options);
}

async function readApiJson(response) {
  const text = await response.text();
  if (!text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("接口返回了网页而不是 JSON。请确认本地 Teacher Skill 后端正在运行，并刷新页面后重试。");
  }
}

function showToast(message, type = "info") {
  toast.textContent = message;
  toast.dataset.type = type;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
  }, 4200);
}

function setStatus(message, isError = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", isError);
  if (isError) showToast(message, "error");
}

function stepOrder(step) {
  return ["input", "generate", "preview", "export"].indexOf(step);
}

function setStep(step) {
  document.querySelectorAll(".step-bar li").forEach((item) => {
    const active = item.dataset.step === step;
    item.classList.toggle("active", active);
    item.classList.toggle("done", item.dataset.step !== step && stepOrder(item.dataset.step) < stepOrder(step));
  });
}

function setBusy(busy, label = "生成中") {
  generateButton.disabled = busy;
  if (!generateButton.dataset.originalText) {
    generateButton.dataset.originalText = generateButton.textContent;
  }
  generateButton.textContent = busy ? label : generateButton.dataset.originalText;
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

function hasOwn(fields, key) {
  return Object.prototype.hasOwnProperty.call(fields, key);
}

function firstExistingKey(fields, canonicalKey) {
  if (hasOwn(fields, canonicalKey)) return canonicalKey;
  const aliases = ChineseFieldAliases[canonicalKey] || [];
  return aliases.find((key) => hasOwn(fields, key)) || canonicalKey;
}

function fieldValue(fields, canonicalKey) {
  const key = firstExistingKey(fields, canonicalKey);
  return fields[key] ?? "";
}

function parseClassHourCount(value) {
  const text = String(value || "").replace(/[０-９]/g, (char) =>
    String.fromCharCode(char.charCodeAt(0) - 0xfee0)
  );
  const digitMatch = text.match(/(\d+)/);
  if (digitMatch) return Math.max(1, Number.parseInt(digitMatch[1], 10) || 1);

  const chineseMap = { 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
  const chineseMatch = text.match(/([一二两三四五六七八九十]+)/);
  if (!chineseMatch) return 1;
  const raw = chineseMatch[1];
  if (!raw.includes("十")) return chineseMap[raw] || 1;
  const [left, right] = raw.split("十");
  const tens = left ? chineseMap[left] || 1 : 1;
  const ones = right ? chineseMap[right] || 0 : 0;
  return Math.max(1, tens * 10 + ones);
}

function updateLessonScopeHint(fields = collectEditedFields()) {
  if (!scopeHint) return;
  const count = parseClassHourCount(fieldValue(fields, "class_hour"));
  if (count < 9) {
    scopeHint.hidden = true;
    scopeHint.classList.remove("warning");
    scopeHint.textContent = "";
    return;
  }

  const processText = String(fieldValue(fields, "teaching_process") || "");
  const hasProjectShape = /项目|阶段|课时分配/.test(processText);
  scopeHint.hidden = false;
  scopeHint.classList.toggle("warning", !hasProjectShape);
  scopeHint.textContent = hasProjectShape
    ? "已识别为长课时项目/单元教案，系统将按项目整体教学方案生成。"
    : "当前内容可能仍偏单课时，建议重新生成或手动补充课时分配。";
}

function hasTeachingMethod(fields) {
  return String(fieldValue(fields, "teaching_method") || "").trim().length > 0;
}

function hasTeachingProcess(fields) {
  return String(fieldValue(fields, "teaching_process") || "").trim().length > 0;
}

function groupedKnownKeys() {
  const known = new Set(previewGroups.flatMap((group) => group.keys));
  Object.values(ChineseFieldAliases).forEach((aliases) => aliases.forEach((alias) => known.add(alias)));
  return known;
}

function createFieldEditor(fields, canonicalKey) {
  const actualKey = firstExistingKey(fields, canonicalKey);
  if (!hasOwn(fields, actualKey)) fields[actualKey] = "";

  const item = document.createElement("label");
  item.className = `preview-field preview-field-${canonicalKey}`;

  const label = document.createElement("span");
  label.textContent = fieldLabels[canonicalKey] || actualKey;

  const textarea = document.createElement("textarea");
  textarea.dataset.field = actualKey;
  textarea.rows = canonicalKey === "teaching_process" ? 9 : 3;
  textarea.value = fields[actualKey] ?? "";
  textarea.addEventListener("input", () => {
    currentFields[actualKey] = textarea.value;
    setDownload(null);
    deliveryCard.hidden = true;
    updateTeachingMethodGuard();
    updateLessonScopeHint();
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
    group.keys.forEach((key) => grid.append(createFieldEditor(fields, key)));
    section.append(grid);
    previewGroupsRoot.append(section);
  });

  const known = groupedKnownKeys();
  const extraKeys = Object.keys(fields).filter((key) => !known.has(key));
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
  updateLessonScopeHint(fields);
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
  const blocked = !hasTeachingMethod(fields);
  methodWarning.hidden = !blocked;
  deriveMethodButton.disabled = !hasTeachingProcess(fields);
  exportButton.disabled = blocked;
  return !blocked;
}

function setSupplementVisible(visible, task = {}) {
  supplementFields.hidden = !visible;
  if (!visible) return;
  const subject = supplementFields.querySelector('[name="subject"]');
  const grade = supplementFields.querySelector('[name="grade"]');
  const title = supplementFields.querySelector('[name="title"]');
  if (!subject.value) subject.value = task.subject || "";
  if (!grade.value) grade.value = task.grade || "";
  if (!title.value) title.value = task.title || "";
}

function supplementReady() {
  const subject = supplementFields.querySelector('[name="subject"]').value.trim();
  const grade = supplementFields.querySelector('[name="grade"]').value.trim();
  const title = supplementFields.querySelector('[name="title"]').value.trim();
  return Boolean(subject && grade && title);
}

function writeSupplementToFormData(formData) {
  ["subject", "grade", "title"].forEach((key) => {
    const input = supplementFields.querySelector(`[name="${key}"]`);
    if (input?.value.trim()) formData.set(key, input.value.trim());
  });
}

function applyTaskDefaults(formData, task = {}) {
  if (task.subject && !formData.get("subject")) formData.set("subject", task.subject);
  if (task.grade && !formData.get("grade")) formData.set("grade", task.grade);
  if (task.title && !formData.get("title")) formData.set("title", task.title);
  formData.set("class_hour", task.class_hour || formData.get("class_hour") || "1课时");
  formData.set("class_type", task.class_type || formData.get("class_type") || "新授课");
  formData.set("teaching_style", task.teaching_style || "常规启发式");
  formData.set("student_level", task.student_level || "常规混合水平");
  formData.set("generation_depth", task.generation_depth || "标准");
  formData.set("strict_ai", "0");
}

async function previewRequest(formData) {
  const payload = {
    agent_request: formData.get("agent_request") || "",
    subject: formData.get("subject") || "",
    grade: formData.get("grade") || "",
    title: formData.get("title") || ""
  };
  const response = await apiFetch("/api/agent-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await readApiJson(response);
  if (!response.ok) throw new Error(data.message || data.error || "需求解析失败");
  return data;
}

function buildDiagnostics(data = {}) {
  const report = {
    template_mode: data.template_mode || (useSchoolTemplate.checked ? "upload" : "system"),
    generation_backend: data.generation_backend || currentGenerationBackend,
    template_fields: data.template_fields || currentTemplateAnalysis?.mapped_fields || [],
    template_analysis: data.template_analysis || currentTemplateAnalysis,
    fill_report: data.fill_report || currentFillReport,
    evaluation_report: data.evaluation_report || currentEvaluationReport,
    agent_trace: data.workflow_trace || currentWorkflowTrace
  };
  diagnosticsOutput.textContent = JSON.stringify(report, null, 2);
}

function applyResult(data) {
  currentFields = data.fields || {};
  currentTemplateId = data.template_id || currentTemplateId || "";
  currentTemplateAnalysis = data.template_analysis || currentTemplateAnalysis || null;
  currentFillReport = data.fill_report || currentFillReport || null;
  currentEvaluationReport = data.evaluation_report || currentEvaluationReport || null;
  currentGenerationBackend = data.generation_backend || currentGenerationBackend || "";
  currentReviewReport = data.review_report ?? currentReviewReport;
  currentWorkflowTrace = data.workflow_trace || currentWorkflowTrace || [];

  previewCard.hidden = false;
  deliveryCard.hidden = true;
  renderPreview(currentFields);
  buildDiagnostics(data);
  setDownload(data.download_url || null);
  updateTeachingMethodGuard();
  if (data.generation_backend === "local_fallback") {
    showToast("AI 未配置，已使用本地示例内容生成初稿，可继续编辑后导出。");
  }
}

async function submitLessonForm(event) {
  event.preventDefault();
  if (useSchoolTemplate.checked && !templateInput.files.length) {
    showToast("请上传学校 Word 模板，或取消“使用学校 Word 模板”。", "error");
    templateInput.focus();
    return;
  }

  setStep("generate");
  previewCard.hidden = false;
  deliveryCard.hidden = true;
  setStatus("正在理解需求...");
  setBusy(true, "生成中");
  setDownload(null);

  try {
    const initialData = new FormData(lessonForm);
    writeSupplementToFormData(initialData);
    const preview = await previewRequest(initialData);
    const task = preview.agent_task || {};
    const missing = preview.missing_fields || task.missing_fields || [];
    const stillMissing = missing.filter((name) => ["subject", "grade", "title"].includes(name));
    if (stillMissing.length && !supplementReady()) {
      setSupplementVisible(true, task);
      setStep("input");
      setStatus("还缺少学科、班级/年级或课题，请补齐后再点“生成教案”。", true);
      return;
    }

    const runData = new FormData(lessonForm);
    writeSupplementToFormData(runData);
    applyTaskDefaults(runData, task);
    runData.set("template_mode", useSchoolTemplate.checked ? "upload" : "system");
    if (useSchoolTemplate.checked) {
      runData.set("template", templateInput.files[0]);
    } else {
      runData.delete("template");
    }

    setStatus("正在生成内容并写入 Word...");
    const response = await apiFetch("/api/agent-run", { method: "POST", body: runData });
    const data = await readApiJson(response);
    if (!response.ok) {
      if (data.needs_input && data.agent_task) setSupplementVisible(true, data.agent_task);
      throw new Error(data.message || data.error || "生成教案失败");
    }

    currentRequestContext = {
      agent_request: runData.get("agent_request") || "",
      material: runData.get("material") || "",
      subject: runData.get("subject") || task.subject || "",
      grade: runData.get("grade") || task.grade || "",
      title: runData.get("title") || task.title || "",
      class_hour: runData.get("class_hour") || "1课时",
      class_type: runData.get("class_type") || "新授课"
    };
    setSupplementVisible(false);
    applyResult(data);
    setStep("preview");
    if (data.generation_backend === "local_fallback") {
      setStatus("AI 未配置，已使用本地示例内容生成初稿，可继续编辑后导出。");
    } else {
      setStatus("教案内容已生成，请预览并确认字段。");
    }
    if (data.download_url && updateTeachingMethodGuard()) {
      renderDelivery(data);
    }
    await loadHistory();
  } catch (error) {
    setStep("input");
    setStatus(error.message || "生成教案失败", true);
  } finally {
    setBusy(false);
  }
}

async function deriveTeachingMethod() {
  const fields = collectEditedFields();
  const teachingProcess = String(fieldValue(fields, "teaching_process") || "").trim();
  if (!teachingProcess) {
    setStatus("请先填写主要教学内容，再提取教学方法。", true);
    return;
  }

  deriveMethodButton.disabled = true;
  deriveMethodButton.textContent = "提取中";
  try {
    const response = await apiFetch("/api/refine-field", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        field: "teaching_method",
        value: teachingProcess,
        action: "derive_from_process",
        instruction: currentRequestContext.title || ""
      })
    });
    const data = await readApiJson(response);
    if (!response.ok) throw new Error(data.error || "提取教学方法失败");
    const methodKey = firstExistingKey(fields, "teaching_method");
    currentFields[methodKey] = data.value || data.refined || "";
    renderPreview(currentFields);
    setStatus("已从主要教学内容提取教学方法，请确认后导出。");
  } catch (error) {
    setStatus(error.message || "提取教学方法失败", true);
  } finally {
    deriveMethodButton.textContent = "从主要教学内容提取教学方法";
    deriveMethodButton.disabled = false;
    updateTeachingMethodGuard();
  }
}

async function exportEditedDocument() {
  const editedFields = collectEditedFields();
  if (!hasTeachingMethod(editedFields)) {
    updateTeachingMethodGuard();
    setStatus("教学方法的运用为空，请补充后再导出。", true);
    return;
  }
  if (!currentTemplateId) {
    setStatus("缺少模板信息，请重新生成后再导出。", true);
    return;
  }

  exportButton.disabled = true;
  setStep("export");
  setStatus("正在导出 Word...");
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
        workflow_trace: currentWorkflowTrace
      })
    });
    const data = await readApiJson(response);
    if (!response.ok) throw new Error(data.error || "导出 Word 失败");
    currentFields = editedFields;
    currentTemplateAnalysis = data.template_analysis || currentTemplateAnalysis;
    currentFillReport = data.fill_report || currentFillReport;
    currentEvaluationReport = data.evaluation_report || currentEvaluationReport;
    buildDiagnostics(data);
    setDownload(data.download_url);
    renderDelivery(data);
    setStatus("Word 已生成，可以下载。");
    await loadHistory();
  } catch (error) {
    setStep("preview");
    setStatus(error.message || "导出 Word 失败", true);
  } finally {
    exportButton.disabled = false;
    updateTeachingMethodGuard();
  }
}

function normalizeScore(data = {}) {
  const candidates = [
    data.delivery_score,
    data.evaluation_report?.delivery_score,
    data.evaluation_report?.score,
    currentEvaluationReport?.delivery_score,
    currentEvaluationReport?.score
  ];
  const value = candidates.find((item) => item !== null && item !== undefined && item !== "");
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : null;
}

function evaluateQuality(fields, data = {}) {
  const missing = requiredDeliveryKeys.filter((key) => !String(fieldValue(fields, key) || "").trim());
  const score = normalizeScore(data);
  const riskFromReport = data.evaluation_report?.risks || data.evaluation_report?.warnings || currentEvaluationReport?.risks || [];
  const risks = Array.isArray(riskFromReport) ? riskFromReport.filter(Boolean) : [riskFromReport].filter(Boolean);

  if (missing.includes("teaching_method")) {
    return {
      judgment: "不可提交",
      score,
      risk: "教学方法为空",
      suggestion: "请先补充“教学方法的运用”，或点击“从主要教学内容提取教学方法”。"
    };
  }

  if (missing.length) {
    return {
      judgment: "建议修改",
      score,
      risk: `${missing.map((key) => fieldLabels[key]).join("、")}未填写`,
      suggestion: "建议返回编辑页补齐缺失字段后再提交或下载。"
    };
  }

  if (risks.length) {
    return {
      judgment: "建议修改",
      score,
      risk: risks.slice(0, 2).join("；"),
      suggestion: data.evaluation_report?.suggestion || "建议根据风险提示微调后再下载。"
    };
  }

  return {
    judgment: score !== null && score < 70 ? "建议修改" : "可提交",
    score,
    risk: "无",
    suggestion: data.evaluation_report?.suggestion || "核心字段已填写，可下载 Word 教案。"
  };
}

function renderDelivery(data = {}) {
  deliveryCard.hidden = false;
  const fields = collectEditedFields();
  const quality = evaluateQuality(fields, data);

  qualityJudgment.textContent = quality.judgment;
  qualityJudgment.dataset.level = quality.judgment;
  qualityScore.textContent = quality.score === null ? "--/100" : `${quality.score}/100`;
  qualityRisk.textContent = quality.risk;
  qualitySuggestion.textContent = quality.suggestion;

  deliveryChecklist.innerHTML = "";
  requiredDeliveryKeys.forEach((key) => {
    const item = document.createElement("li");
    const done = String(fieldValue(fields, key) || "").trim().length > 0;
    item.textContent = `${done ? "✓" : "○"} ${fieldLabels[key]}已填写`;
    item.classList.toggle("missing", !done);
    deliveryChecklist.append(item);
  });
}

async function loadAiStatus(probe = false) {
  checkAiButton.disabled = true;
  aiStatusText.textContent = probe ? "诊断中" : "检查中";
  try {
    const response = await apiFetch(`/api/model/health${probe ? "?probe=1" : ""}`);
    const data = await readApiJson(response);
    const state = data.status || (data.configured ? "configured" : "not_configured");
    const labels = {
      ok: "正常",
      configured: "已配置",
      not_configured: "未配置",
      error: "异常",
      auth_failed: "异常"
    };
    aiStatus.dataset.status = state;
    aiStatusText.textContent = labels[state] || state;
    aiStatus.title = data.message || "";
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

document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    agentRequest.value = examplePrompts[button.dataset.example] || "";
    agentRequest.focus();
    showToast("示例已填入，可以继续修改后再生成。");
  });
});

lessonForm.addEventListener("submit", submitLessonForm);
useSchoolTemplate.addEventListener("change", () => {
  templateUploadWrap.hidden = !useSchoolTemplate.checked;
});
deriveMethodButton.addEventListener("click", deriveTeachingMethod);
exportButton.addEventListener("click", exportEditedDocument);
regenerateButton.addEventListener("click", () => lessonForm.requestSubmit());
backEditButton.addEventListener("click", () => {
  deliveryCard.hidden = true;
  previewCard.scrollIntoView({ behavior: "smooth", block: "start" });
});
restartButton.addEventListener("click", () => {
  setStep("input");
  deliveryCard.hidden = true;
  previewCard.hidden = true;
  setDownload(null);
  agentRequest.focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
});
downloadLink.addEventListener("click", (event) => {
  if (downloadLink.classList.contains("disabled")) {
    event.preventDefault();
    setStatus("请先生成并导出 Word。", true);
  }
});
checkAiButton.addEventListener("click", () => loadAiStatus(true));
refreshHistoryButton.addEventListener("click", loadHistory);

setStep("input");
setDownload(null);
loadAiStatus(false);
loadHistory();
