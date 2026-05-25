const form = document.querySelector("#lesson-form");
const materialInput = document.querySelector("#material");
const sampleButton = document.querySelector("#sample-button");
const generateButton = document.querySelector("#generate-button");
const statusBox = document.querySelector("#status");
const resultTitle = document.querySelector("#result-title");
const downloadLink = document.querySelector("#download-link");
const exportButton = document.querySelector("#export-button");
const fieldCount = document.querySelector("#field-count");
const fileName = document.querySelector("#file-name");
const previewList = document.querySelector("#preview-list");

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

let currentFields = null;
let currentTemplateId = null;

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function setBusy(isBusy) {
  generateButton.disabled = isBusy;
  sampleButton.disabled = isBusy;
  exportButton.disabled = isBusy || !currentFields;
  generateButton.querySelector("span:last-child").textContent = isBusy ? "生成中" : "生成内容";
}

function renderPreview(fields) {
  previewList.innerHTML = "";
  previewOrder.forEach((key) => {
    if (!fields[key]) return;
    const item = document.createElement("article");
    item.className = "preview-item";

    const title = document.createElement("h3");
    title.textContent = fieldLabels[key] || key;

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

    item.append(title, body);
    previewList.appendChild(item);
  });
}

function collectEditedFields() {
  const fields = { ...(currentFields || {}) };
  document.querySelectorAll("[data-field]").forEach((node) => {
    fields[node.dataset.field] = node.value;
  });
  return fields;
}

async function loadSampleMaterial() {
  setStatus("正在载入示例材料");
  const response = await fetch("/api/sample-material");
  if (!response.ok) {
    setStatus("示例材料载入失败", true);
    return;
  }
  const data = await response.json();
  materialInput.value = data.material;
  setStatus("示例材料已填入");
}

sampleButton.addEventListener("click", () => {
  loadSampleMaterial().catch(() => setStatus("示例材料载入失败", true));
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  setStatus("正在生成教案内容");

  currentFields = null;
  currentTemplateId = null;
  exportButton.disabled = true;
  downloadLink.classList.add("is-disabled");
  downloadLink.setAttribute("aria-disabled", "true");
  downloadLink.href = "#";
  fileName.textContent = "未导出";

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
    resultTitle.textContent = `${data.fields.grade}${data.fields.subject}：${data.fields.lesson_title}`;
    fieldCount.textContent = String(data.template_fields.length);
    renderPreview(data.fields);
    exportButton.disabled = false;
    setStatus("内容已生成");
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
  setStatus("正在导出 Word");

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
    fileName.textContent = data.output_name;
    downloadLink.href = data.download_url;
    downloadLink.classList.remove("is-disabled");
    downloadLink.setAttribute("aria-disabled", "false");
    setStatus("Word 已导出");
  } catch (error) {
    setStatus(error.message || "导出失败", true);
  } finally {
    exportButton.disabled = false;
  }
});

loadSampleMaterial().catch(() => {});
