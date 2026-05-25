const form = document.querySelector("#lesson-form");
const materialInput = document.querySelector("#material");
const sampleButton = document.querySelector("#sample-button");
const generateButton = document.querySelector("#generate-button");
const statusBox = document.querySelector("#status");
const resultTitle = document.querySelector("#result-title");
const downloadLink = document.querySelector("#download-link");
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
  "teaching_goals",
  "key_points",
  "difficult_points",
  "teaching_process",
  "blackboard_design",
  "homework",
  "reflection",
];

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function setBusy(isBusy) {
  generateButton.disabled = isBusy;
  sampleButton.disabled = isBusy;
  generateButton.textContent = isBusy ? "生成中" : "生成教案";
}

function renderPreview(fields) {
  previewList.innerHTML = "";
  previewOrder.forEach((key) => {
    if (!fields[key]) return;
    const item = document.createElement("article");
    item.className = "preview-item";

    const title = document.createElement("h3");
    title.textContent = fieldLabels[key] || key;

    const body = document.createElement("pre");
    body.textContent = fields[key];

    item.append(title, body);
    previewList.appendChild(item);
  });
}

async function loadSampleMaterial() {
  setStatus("正在载入示例材料。");
  const response = await fetch("/api/sample-material");
  if (!response.ok) {
    setStatus("示例材料载入失败。", true);
    return;
  }
  const data = await response.json();
  materialInput.value = data.material;
  setStatus("示例材料已填入。");
}

sampleButton.addEventListener("click", () => {
  loadSampleMaterial().catch(() => setStatus("示例材料载入失败。", true));
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  setStatus("正在生成教案并填充 Word 模板。");

  downloadLink.classList.add("is-disabled");
  downloadLink.setAttribute("aria-disabled", "true");
  downloadLink.href = "#";

  try {
    const formData = new FormData(form);
    const response = await fetch("/api/generate", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "生成失败");
    }

    resultTitle.textContent = `${data.fields.grade}${data.fields.subject}：${data.fields.lesson_title}`;
    fieldCount.textContent = String(data.template_fields.length);
    fileName.textContent = data.output_name;
    downloadLink.href = data.download_url;
    downloadLink.classList.remove("is-disabled");
    downloadLink.setAttribute("aria-disabled", "false");
    renderPreview(data.fields);
    setStatus("已生成 Word 教案。");
  } catch (error) {
    setStatus(error.message || "生成失败。", true);
  } finally {
    setBusy(false);
  }
});

loadSampleMaterial().catch(() => {});
