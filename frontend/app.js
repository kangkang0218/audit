const state = {
  file: null,
  logs: [],
  progressTimer: null,
  uploadId: null,
  useChunked: false,
  uploadDone: false,
  reviewing: false,
};

const CHUNK_SIZE = 30 * 1024 * 1024;
const UPLOAD_BASE = "/api/v1/upload";

const el = {
  fileInput: document.querySelector("#fileInput"),
  dropzone: document.querySelector("#dropzone"),
  fileCard: document.querySelector("#fileCard"),
  fileName: document.querySelector("#fileName"),
  fileSize: document.querySelector("#fileSize"),
  pageCount: document.querySelector("#pageCount"),
  runButton: document.querySelector("#runButton"),
  resetButton: document.querySelector("#resetButton"),
  modePill: document.querySelector("#modePill"),
  runState: document.querySelector("#runState"),
  resultState: document.querySelector("#resultState"),
  progressLabel: document.querySelector("#progressLabel"),
  progressPercent: document.querySelector("#progressPercent"),
  progressBar: document.querySelector("#progressBar"),
  steps: document.querySelectorAll("#steps li"),
  logList: document.querySelector("#logList"),
  logCount: document.querySelector("#logCount"),
  resultName: document.querySelector("#resultName"),
  resultHint: document.querySelector("#resultHint"),
  downloadLink: document.querySelector("#downloadLink"),
  timerLine: document.querySelector("#timerLine"),
  timerElapsed: document.querySelector("#timerElapsed"),
};

const stageMap = {
  classify:     { label: "PDF 类型判别" },
  ocr:          { label: "文档解析" },
  split:        { label: "Markdown 分片" },
  llm:          { label: "LLM 并行提取" },
  consistency:  { label: "一致性校验" },
  excel:        { label: "生成 Excel" },
  done:         { label: "完成" },
};
const stageOrder = ["classify", "ocr", "split", "llm", "consistency", "excel", "done"];

const STEP_LABELS = ["类型判别","文档解析","Markdown分片","LLM提取","一致性校验","生成Excel"];

function formatBytes(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes, index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
function formatTime(sec) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}
function showTimer(elapsed) {
  el.timerLine.style.display = "block";
  el.timerElapsed.textContent = formatTime(elapsed || 0);
}
function hideTimer() {
  el.timerLine.style.display = "none";
}
function setPill(node, text, className = "neutral") {
  node.className = `status-pill ${className}`.trim();
  node.textContent = text;
}
function setProgress(progress, label) {
  el.progressBar.style.width = `${progress}%`;
  el.progressPercent.textContent = `${progress}%`;
  el.progressLabel.textContent = label;
}
function setStep(index) {
  el.steps.forEach((step, i) => {
    step.classList.toggle("done", i < index);
    step.classList.toggle("active", i === index);
  });
}
function setStepLabels(labels) {
  el.steps.forEach((step, i) => {
    if (i < labels.length) step.textContent = labels[i];
  });
}
function addLog(message, title = "阶段摘要") {
  if (state.logs.length === 0) el.logList.innerHTML = "";
  state.logs.push({ title, message });
  const item = document.createElement("div");
  item.className = "log-item";
  item.innerHTML = `<strong>${title}</strong><br>${message}`;
  el.logList.append(item);
  el.logList.scrollTop = el.logList.scrollHeight;
  el.logCount.textContent = `${state.logs.length} 条`;
}
function resetResult() {
  setPill(el.resultState, "未生成", "neutral");
  el.resultName.textContent = "等待生成审查工作簿";
  el.resultHint.textContent = "输出文件会按固定 sheet 与表头生成，并对异常、模糊、需人工复核内容做红色标注。";
  el.downloadLink.href = "#";
  el.downloadLink.classList.add("disabled");
  el.downloadLink.setAttribute("aria-disabled", "true");
  el.downloadLink.removeAttribute("download");
}
function resetRun() {
  state.logs = [];
  setProgress(0, state.file ? "准备开始审查" : "等待 PDF 文件");
  setStep(-1);
  setPill(el.runState, "待开始", "neutral");
  el.logList.innerHTML = '<p class="empty">运行后这里会显示阶段性处理摘要。</p>';
  el.logCount.textContent = "0 条";
  resetResult();
  setStepLabels(STEP_LABELS);
  hideTimer();
}

function updateFile(file) {
  state.file = file;
  state.uploadDone = false;
  state.useChunked = file.size > CHUNK_SIZE;
  el.fileCard.hidden = false;
  el.fileName.textContent = file.name;
  el.fileSize.textContent = formatBytes(file.size);

  setPill(el.modePill, state.useChunked ? "等待上传" : "就绪", state.useChunked ? "neutral" : "done");
  resetRun();
  addLog(`文件 ${file.name} 已载入，大小 ${formatBytes(file.size)}。`, "输入确认");

  if (state.useChunked) {
    el.pageCount.textContent = "等待上传完成...";
    el.runButton.disabled = true;
    el.runButton.textContent = "上传完成后可审查";
    setProgress(0, "切片上传等待中...");
    setStepLabels(["上传切片","文档解析","Markdown分片","LLM提取","一致性校验","生成Excel"]);
    startChunkedUpload(file);
  } else {
    el.pageCount.textContent = "读取中...";
    el.runButton.disabled = false;
    el.runButton.textContent = "开始审查";
    const infoBody = new FormData();
    infoBody.append("pdf", file);
    fetch("/api/v1/pdf-info", { method: "POST", body: infoBody })
      .then(async (r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then((p) => { if (state.file && state.file.name === file.name && p.pageCount) el.pageCount.textContent = `${p.pageCount} 页`; })
      .catch(() => { if (state.file && state.file.name === file.name) el.pageCount.textContent = "无法读取"; });
  }
}

function handleFiles(files) {
  const file = files && files[0];
  if (!file) return;
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    addLog("请选择 PDF 文件。", "文件类型不支持");
    return;
  }
  updateFile(file);
}

function makeOutputName(inputName) {
  const base = inputName.replace(/\.pdf$/i, "").replace(/\(\d+\)$/u, "");
  return `${base}投标文件三项审查_提取与判断建议.xlsx`;
}

function enableDownload(result) {
  el.resultName.textContent = result.name;
  el.resultHint.textContent = "审查完成，已收到后端生成的 Excel 工作簿。";
  el.downloadLink.href = result.url;
  el.downloadLink.download = result.name;
  el.downloadLink.classList.remove("disabled");
  el.downloadLink.setAttribute("aria-disabled", "false");
  setPill(el.resultState, "已生成", "done");
}

function summarizeError(message) {
  const text = String(message || "");
  if (text.includes("Failed to fetch")) return "未连接到本地审查服务，请确认后端已启动。";
  return `处理过程中遇到问题：${text}`;
}

async function startChunkedUpload(file) {
  const chunkCount = Math.ceil(file.size / CHUNK_SIZE);
  addLog(`初始化切片上传: ${chunkCount} 片, 每片 ${formatBytes(CHUNK_SIZE)}`, "切片上传");

  let uploadId;
  try {
    const initRes = await fetch(`${UPLOAD_BASE}/init`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fileName: file.name, fileSize: file.size, chunkSize: CHUNK_SIZE, contentType: file.type || "application/pdf" }),
    });
    if (!initRes.ok) throw new Error("切片上传初始化失败");
    ({ uploadId } = await initRes.json());
    state.uploadId = uploadId;
  } catch (e) {
    addLog(summarizeError(e.message), "上传失败");
    setPill(el.modePill, "上传失败", "warn");
    return;
  }

  let completed = 0;
  const MAX_RETRY = 3;
  for (let i = 0; i < chunkCount; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, file.size);
    const blob = file.slice(start, end);
    const form = new FormData();
    form.append("chunk", blob, `${i}.part`);

    let retry = 0, ok = false;
    while (retry < MAX_RETRY) {
      try {
        const res = await fetch(`${UPLOAD_BASE}/${uploadId}/chunks/${i}`, { method: "POST", body: form });
        if (res.ok) { ok = true; break; }
        const err = await res.json().catch(() => ({}));
        if (err.detail === "UPLOAD_CONFLICT") { ok = true; break; }
        retry++;
      } catch (e) {
        retry++;
      }
      if (retry < MAX_RETRY) {
        addLog(`分片 ${i + 1}/${chunkCount} 重试 ${retry}/${MAX_RETRY}...`, "切片上传");
        await new Promise(r => setTimeout(r, 2000));
      }
    }
    if (!ok) {
      addLog(`分片 ${i + 1}/${chunkCount} 重试${MAX_RETRY}次均失败`, "上传中断");
      setPill(el.modePill, "上传失败", "warn");
      return;
    }
    completed++;
    const pct = Math.round((completed / chunkCount) * 100);
    setProgress(pct, `切片上传 ${completed}/${chunkCount} (${pct}%)`);
    addLog(`分片 ${i + 1}/${chunkCount} 完成 (${formatBytes(blob.size)})`, `切片上传 ${pct}%`);
  }

  try {
    addLog("合并分片...", "切片上传");
    const completeRes = await fetch(`${UPLOAD_BASE}/${uploadId}/complete`, { method: "POST" });
    if (!completeRes.ok) throw new Error("文件合并失败");
    const completeData = await completeRes.json();
    state.uploadDone = true;
    el.pageCount.textContent = `${formatBytes(completeData.fileSize)} (上传完成)`;
    el.runButton.disabled = false;
    el.runButton.textContent = "开始审查";
    setPill(el.modePill, "就绪", "done");
    setProgress(100, "切片上传完成");
    addLog(`上传完成, MD5: ${completeData.checksum.slice(0,12)}...`, "切片上传 100%");
  } catch (e) {
    addLog(summarizeError(e.message), "合并失败");
    setPill(el.modePill, "上传失败", "warn");
  }
}

async function runReview() {
  if (!state.file || state.reviewing) return;
  if (state.useChunked && !state.uploadDone) return;

  state.reviewing = true;
  el.runButton.disabled = true;
  el.runButton.textContent = "审查中...";
  setPill(el.runState, "正在启动...", "running");
  setPill(el.modePill, "处理中", "running");
  setProgress(2, "正在启动审查...");

  let runId;
  try {
    const startRes = await fetch("/api/v1/upload-review/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uploadId: state.uploadId, mode: "bid_review_three_items" }),
    });
    if (!startRes.ok) throw new Error("启动审查失败: " + startRes.status);
    ({ runId } = await startRes.json());
  } catch (e) {
    addLog(summarizeError(e.message), "处理失败");
    setPill(el.modePill, "处理失败", "warn");
    setPill(el.runState, "处理失败", "warn");
    state.reviewing = false;
    el.runButton.disabled = false;
    el.runButton.textContent = "开始审查";
    return;
  }

  let stageIdx = -1, lastStageName = "", seenStages = new Set();

  while (true) {
    await new Promise(r => setTimeout(r, 500));
    try {
      const statusRes = await fetch(`/api/v1/upload-review/${runId}/status`);
      if (!statusRes.ok) { addLog(`状态查询失败: ${statusRes.status}`); continue; }
      const s = await statusRes.json();

      if (s.status === "error") {
        addLog(s.error || "未知错误", "处理失败");
        setPill(el.modePill, "处理失败", "warn");
        setPill(el.runState, "处理失败", "warn");
        hideTimer();
        break;
      }

      const elapsed = s.elapsed || 0;
      showTimer(elapsed);
      const stage = s.stage;
      const label = s.label || stage;
      setProgress(s.progress || 0, `${label} (${formatTime(elapsed)})`);

      if (s.llm_errors && s.llm_errors.length > 0) {
        addLog(`LLM 提取错误: ${s.llm_errors.join("; ")}`, "LLM 错误");
      }

      if (stage !== "starting" && !seenStages.has(stage)) {
        seenStages.add(stage);
        const meta = [];
        if (elapsed) meta.push(`${formatTime(elapsed)}`);
        addLog(`${label}`, label);
        stageIdx = stageOrder.indexOf(stage);
        if (stageIdx >= 0 && stageIdx <= el.steps.length) setStep(stageIdx);
        setPill(el.runState, label + "...", "running");
        lastStageName = label;
      }

      if (s.status === "done") {
        showTimer(elapsed);
        addLog(`总耗时 ${formatTime(elapsed)}`, "完成");
        setPill(el.modePill, "已完成", "done");
        setPill(el.runState, "已完成", "done");
        setProgress(100, `完成 (${formatTime(elapsed)})`);
        setStep(stageOrder.length);

        try {
          const resultRes = await fetch(`/api/v1/upload-review/${runId}/result`);
          if (!resultRes.ok) throw new Error("获取结果失败");
          const blob = await resultRes.blob();
          const name = makeOutputName(state.file.name);
          enableDownload({ url: URL.createObjectURL(blob), name, source: "api" });
        } catch (e) {
          addLog("结果下载失败: " + e.message, "错误");
        }
        break;
      }
    } catch (e) {
      addLog("轮询失败: " + e.message);
    }
  }

  state.reviewing = false;
  el.runButton.disabled = !state.useChunked || state.uploadDone ? false : true;
  el.runButton.textContent = el.runButton.disabled ? "上传完成后可审查" : "开始审查";
}

el.fileInput.addEventListener("change", (event) => handleFiles(event.target.files));
el.dropzone.addEventListener("dragover", (e) => { e.preventDefault(); el.dropzone.classList.add("dragging"); });
el.dropzone.addEventListener("dragleave", () => el.dropzone.classList.remove("dragging"));
el.dropzone.addEventListener("drop", (e) => { e.preventDefault(); el.dropzone.classList.remove("dragging"); handleFiles(e.dataTransfer.files); });
el.runButton.addEventListener("click", runReview);
el.resetButton.addEventListener("click", () => {
  el.fileInput.value = "";
  state.file = null;
  state.uploadDone = false;
  state.useChunked = false;
  state.uploadId = null;
  el.fileCard.hidden = true;
  el.runButton.disabled = true;
  el.runButton.textContent = "开始审查";
  setPill(el.modePill, "等待文件", "neutral");
  resetRun();
  setStepLabels(STEP_LABELS);
});
setStepLabels(STEP_LABELS);
resetRun();
