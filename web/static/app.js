const form = document.querySelector("#lesson-form");
const generateButton = document.querySelector("#generate-button");
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

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function setBusy(isBusy) {
  generateButton.disabled = isBusy;
  exportButton.disabled = isBusy || !currentFields;
  generateButton.querySelector("span:last-child").textContent = isBusy ? "生成中" : "生成内容";
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

function refreshResultTitle(fields) {
  if (!fields) return;
  resultTitle.textContent = `${fields.grade || ""}${fields.subject || ""}：${fields.lesson_title || ""}`;
}

function renderPreview(fields) {
  previewList.innerHTML = "";
  previewOrder.forEach((key) => {
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
  exportButton.disabled = true;
  setDownloadStale("未导出");
  renderTemplateAnalysis(null);

  try {
    const formData = new FormData(form);
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
    refreshResultTitle(data.fields);
    fieldCount.textContent = String(data.template_fields.length);
    renderTemplateAnalysis(data.template_analysis);
    renderPreview(data.fields);
    exportButton.disabled = false;
    setStatus(`内容已生成（${backendLabels[data.generation_backend] || "生成器"}）`);
  } catch (error) {
    setStatus(error.message || "生成失败", true);
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
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "导出失败");
    }

    currentFields = editedFields;
    currentTemplateAnalysis = data.template_analysis || currentTemplateAnalysis;
    refreshResultTitle(currentFields);
    renderTemplateAnalysis(currentTemplateAnalysis);
    setDownloadReady(data.download_url, data.output_name);
    setPreviewReady(data.preview_url);
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
