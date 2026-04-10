const API = "";  // same origin

// ── State ─────────────────────────────────────────────────────────────────────
let docLoaded = false;
let providerReady = false;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const dropZone       = document.getElementById("drop-zone");
const fileInput      = document.getElementById("file-input");
const browseBtn      = document.getElementById("browse-btn");
const docStatus      = document.getElementById("doc-status");
const docName        = document.getElementById("doc-name");
const docChunks      = document.getElementById("doc-chunks");
const uploadProgress = document.getElementById("upload-progress");
const progressFill   = document.getElementById("progress-fill");
const progressLabel  = document.getElementById("progress-label");

const providerSelect = document.getElementById("provider-select");
const modelField     = document.getElementById("model-field");
const modelSelect    = document.getElementById("model-select");
const providerBadge  = document.getElementById("provider-badge");
const badgeText      = document.getElementById("badge-text");

const messages       = document.getElementById("messages");
const emptyState     = document.getElementById("empty-state");
const questionInput  = document.getElementById("question-input");
const sendBtn        = document.getElementById("send-btn");
const chatSubtitle   = document.getElementById("chat-subtitle");
const inputHint      = document.getElementById("input-hint");

// ── Providers ─────────────────────────────────────────────────────────────────
async function loadProviders() {
  try {
    const res = await fetch(`${API}/providers`);
    const data = await res.json();

    providerSelect.innerHTML = "";
    data.providers.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name;
      providerSelect.appendChild(opt);
    });

    // Store provider data for later use
    providerSelect._providers = data.providers;
    updateProviderUI();
  } catch (err) {
    providerSelect.innerHTML = '<option value="">Failed to load</option>';
    showToast("Could not connect to backend. Is the server running?");
  }
}

function updateProviderUI() {
  const providers = providerSelect._providers || [];
  const selected = providers.find(p => p.id === providerSelect.value);
  if (!selected) return;

  if (selected.requires_model_selection) {
    // Ollama - show model dropdown
    modelField.style.display = "block";
    providerBadge.style.display = "none";
    modelSelect.innerHTML = "";

    if (selected.models.length === 0) {
      modelSelect.innerHTML = '<option value="">No models found — run: ollama pull &lt;model&gt;</option>';
      providerReady = false;
    } else {
      selected.models.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        modelSelect.appendChild(opt);
      });
      providerReady = true;
    }
  } else {
    // Gemini - show fixed badge
    modelField.style.display = "none";
    providerBadge.style.display = "flex";
    badgeText.textContent = selected.models[0] || "gemini-2.0-flash";
    providerReady = true;
  }

  refreshInputState();
}

providerSelect.addEventListener("change", updateProviderUI);
modelSelect.addEventListener("change", refreshInputState);

// ── File Upload ───────────────────────────────────────────────────────────────
browseBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

dropZone.addEventListener("click", (e) => {
  if (e.target !== browseBtn) fileInput.click();
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragging");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragging"));

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragging");
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

async function handleFile(file) {
  const ext = file.name.split(".").pop().toLowerCase();
  if (!["pdf", "txt"].includes(ext)) {
    showToast("Only PDF and TXT files are supported.");
    return;
  }

  // Show progress
  uploadProgress.style.display = "block";
  docStatus.style.display = "none";
  progressFill.style.width = "30%";
  progressLabel.textContent = "Uploading…";

  const formData = new FormData();
  formData.append("file", file);

  try {
    progressFill.style.width = "60%";
    progressLabel.textContent = "Processing & embedding…";

    const res = await fetch(`${API}/upload`, { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Upload failed");
    }

    progressFill.style.width = "100%";
    progressLabel.textContent = "Done!";

    setTimeout(() => {
      uploadProgress.style.display = "none";
      docStatus.style.display = "flex";
      docName.textContent = data.filename;
      docChunks.textContent = `${data.chunks} chunks`;
      docLoaded = true;
      refreshInputState();
    }, 600);

  } catch (err) {
    uploadProgress.style.display = "none";
    showToast(err.message);
  }
}

// ── Input State ───────────────────────────────────────────────────────────────
function refreshInputState() {
  const ready = docLoaded && providerReady;
  questionInput.disabled = !ready;
  sendBtn.disabled = !ready;

  if (!docLoaded) {
    inputHint.textContent = "Upload a document to start chatting";
    chatSubtitle.textContent = "Upload a document and select a provider to begin";
  } else if (!providerReady) {
    inputHint.textContent = "Select a provider and model";
    chatSubtitle.textContent = "Select an LLM provider to start asking questions";
  } else {
    inputHint.textContent = "Press Enter to send, Shift+Enter for new line";
    chatSubtitle.textContent = `Chatting with ${docName.textContent}`;
  }
}

// ── Chat ──────────────────────────────────────────────────────────────────────
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendMessage();
  }
});

questionInput.addEventListener("input", () => {
  questionInput.style.height = "auto";
  questionInput.style.height = Math.min(questionInput.scrollHeight, 160) + "px";
});

sendBtn.addEventListener("click", sendMessage);

async function sendMessage() {
  const question = questionInput.value.trim();
  if (!question) return;

  // Determine provider config
  const provider = providerSelect.value;
  const model = provider === "ollama" ? modelSelect.value : null;

  // Clear input
  questionInput.value = "";
  questionInput.style.height = "auto";

  // Remove empty state
  if (emptyState) emptyState.remove();

  // Add user message
  appendMessage("user", question);

  // Show thinking indicator
  const thinkingEl = appendThinking();

  // Lock input
  questionInput.disabled = true;
  sendBtn.disabled = true;

  try {
    const res = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, provider, model }),
    });

    const data = await res.json();

    thinkingEl.remove();

    if (!res.ok) {
      throw new Error(data.detail || "Failed to get answer");
    }

    appendMessage("assistant", data.answer, data.citations);

  } catch (err) {
    thinkingEl.remove();
    appendMessage("assistant", `⚠ Error: ${err.message}`);
  } finally {
    questionInput.disabled = false;
    sendBtn.disabled = false;
    questionInput.focus();
    scrollToBottom();
  }
}

function appendMessage(role, text, citations = []) {
  const msg = document.createElement("div");
  msg.className = `message ${role}`;

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "You" : "Assistant";

  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = text;

  msg.appendChild(roleLabel);
  msg.appendChild(body);

  // Citations
  if (citations && citations.length > 0) {
    const citBlock = document.createElement("div");
    citBlock.className = "citations";

    const label = document.createElement("div");
    label.className = "citations-label";
    label.textContent = `Sources (${citations.length} chunks)`;
    citBlock.appendChild(label);

    citations.forEach((c, i) => {
      const card = document.createElement("div");
      card.className = "citation-card";

      const meta = document.createElement("div");
      meta.className = "citation-meta";
      meta.textContent = `${c.filename} · Chunk ${c.chunk_index + 1}`;

      const excerpt = document.createElement("div");
      excerpt.className = "citation-text";
      excerpt.textContent = c.text;

      card.appendChild(meta);
      card.appendChild(excerpt);

      // Toggle expand on click
      card.addEventListener("click", () => card.classList.toggle("expanded"));

      citBlock.appendChild(card);
    });

    msg.appendChild(citBlock);
  }

  messages.appendChild(msg);
  scrollToBottom();
  return msg;
}

function appendThinking() {
  const wrapper = document.createElement("div");
  wrapper.className = "message assistant";

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = "Assistant";

  const thinking = document.createElement("div");
  thinking.className = "thinking";
  [1, 2, 3].forEach(() => {
    const dot = document.createElement("div");
    dot.className = "thinking-dot";
    thinking.appendChild(dot);
  });

  wrapper.appendChild(roleLabel);
  wrapper.appendChild(thinking);
  messages.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => toast.remove(), 4000);
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadProviders();