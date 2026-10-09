// FaceID Dashboard - Frontend Application Logic

let currentToken = localStorage.getItem("access_token") || "";
let activePersonId = null;
let currentPersonsList = [];

// --- Toast Notifications ---
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// --- API Client ---
async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (currentToken) {
    headers["Authorization"] = `Bearer ${currentToken}`;
  }
  if (!headers["Content-Type"] && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  try {
    const res = await fetch(endpoint, { ...options, headers });
    if (res.status === 401) {
      // Prompt login if unauthorized
      document.getElementById("btn-header-auth").textContent = "Admin Login";
      localStorage.removeItem("access_token");
      currentToken = "";
    }
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Request failed (${res.status})`);
    }
    return data;
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    throw err;
  }
}

// --- Navigation Tabs ---
function switchTab(tabId) {
  document.querySelectorAll(".nav-tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-pane").forEach(pane => {
    pane.classList.toggle("active", pane.id === tabId);
  });

  if (tabId === "tab-overview") loadStats();
  if (tabId === "tab-review") loadUnrecognized();
  if (tabId === "tab-persons") loadPersons();
  if (tabId === "tab-settings") loadSettings();
  if (tabId === "tab-rtsp") {
    loadRtspStatus();
    startRtspPolling();
  } else {
    stopRtspPolling();
  }
}

// --- Modals ---
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add("active");
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove("active");
}

// Helper: Convert File to Base64
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result);
    reader.onerror = error => reject(error);
  });
}

// --- 1. Overview & Stats ---
async function loadStats() {
  try {
    const stats = await apiFetch("/api/v1/stats");
    document.getElementById("stat-total-persons").textContent = stats.total_persons;
    document.getElementById("stat-total-samples").textContent = stats.total_samples;
    document.getElementById("stat-unrecognized-count").textContent = stats.unrecognized_count;
    document.getElementById("stat-accuracy-rate").textContent = `${stats.accuracy_rate}%`;

    // Update unknown badge in navigation
    const badge = document.getElementById("badge-unknown-count");
    if (badge) {
      if (stats.unrecognized_count > 0) {
        badge.textContent = stats.unrecognized_count;
        badge.style.display = "inline-block";
      } else {
        badge.style.display = "none";
      }
    }

    // Render Recent Activity Stream
    const activityContainer = document.getElementById("activity-list-container");
    if (activityContainer && stats.recent_activity) {
      if (stats.recent_activity.length === 0) {
        activityContainer.innerHTML = `<div style="text-align: center; color: var(--text-dim); padding: 2rem;">No recent detections logged yet.</div>`;
      } else {
        activityContainer.innerHTML = stats.recent_activity.map(act => `
          <div class="activity-item">
            <div class="activity-user">
              <img src="${act.thumbnail_url}" class="activity-avatar" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>👤</text></svg>'">
              <div class="activity-details">
                <h4>${act.matched_name || 'Unknown Face'}</h4>
                <span>${act.camera_id ? 'Camera: ' + act.camera_id + ' • ' : ''}${new Date(act.timestamp).toLocaleTimeString()}</span>
              </div>
            </div>
            <div>
              <span class="chip-tag ${act.status}">
                ${act.status === 'matched' ? '✓ ' + Math.round(act.similarity * 100) + '%' : act.status}
              </span>
            </div>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    showToast("Failed to refresh statistics: " + err.message, "error");
  }
}

// --- 2. Unknown Faces Review Queue ---
async function loadUnrecognized() {
  const container = document.getElementById("unrecognized-faces-grid");
  if (!container) return;
  container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-muted);">Fetching unknown detections...</div>`;

  try {
    const data = await apiFetch("/api/v1/detections/unrecognized");
    const count = data.count || 0;

    // Update badge
    const badge = document.getElementById("badge-unknown-count");
    if (badge) {
      badge.textContent = count;
      badge.style.display = count > 0 ? "inline-block" : "none";
    }

    if (count === 0) {
      container.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 4rem; color: var(--text-muted);" class="glass-panel">
          <div style="font-size: 3rem; margin-bottom: 0.5rem;">🎉</div>
          <h3>Inbox Zero!</h3>
          <p style="margin-top: 0.25rem;">No unclassified face detections pending review.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = data.detections.map(det => `
      <div class="glass-panel face-card" id="card-det-${det.id}">
        <div class="face-card-preview">
          <img src="${det.thumbnail_url}" alt="Unknown face" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>👤</text></svg>'">
          <span class="face-card-time">${new Date(det.created_at).toLocaleString()}</span>
        </div>
        <div class="face-card-content">
          <h4 style="font-size: 1rem; margin-bottom: 0.25rem;">Unrecognized Face</h4>
          <span class="text-muted" style="font-size: 0.8rem;">Camera: ${det.camera_id || 'Unknown source'}</span>
        </div>
        <div class="face-card-actions">
          <button class="btn btn-primary btn-sm" style="flex: 1;" onclick="openAssignModal('${det.id}')">👤 Assign</button>
          <button class="btn btn-danger btn-sm" onclick="dismissDetection('${det.id}')">Dismiss</button>
        </div>
      </div>
    `).join("");
  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: var(--accent-rose); text-align: center; padding: 2rem;">Error: ${err.message}</div>`;
  }
}

function openAssignModal(detectionId) {
  document.getElementById("assign-detection-id").value = detectionId;
  const select = document.getElementById("assign-person-select");
  select.innerHTML = `<option value="">-- Choose Member --</option>` + 
    currentPersonsList.map(p => `<option value="${p.id}">${p.name} (${p.sample_count} samples)</option>`).join("");
  document.getElementById("assign-new-name").value = "";
  openModal("modal-assign");
}

async function dismissDetection(detectionId) {
  try {
    await apiFetch(`/api/v1/detections/${detectionId}/dismiss`, { method: "DELETE" });
    const card = document.getElementById(`card-det-${detectionId}`);
    if (card) {
      card.style.opacity = "0";
      card.style.transform = "scale(0.9)";
      card.style.transition = "all 0.25s ease";
      setTimeout(() => card.remove(), 250);
    }
    showToast("Detection dismissed", "info");
    loadStats();
  } catch (err) {
    showToast("Dismiss failed: " + err.message, "error");
  }
}

// --- 3. Known Members Directory ---
async function loadPersons() {
  const container = document.getElementById("persons-grid");
  if (!container) return;
  container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-muted);">Loading household directory...</div>`;

  try {
    const data = await apiFetch("/api/v1/persons");
    currentPersonsList = data.persons || [];

    if (currentPersonsList.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 4rem; color: var(--text-muted);" class="glass-panel">
          <div style="font-size: 3rem; margin-bottom: 0.5rem;">👥</div>
          <h3>No Members Registered</h3>
          <p style="margin-top: 0.25rem;">Register your first household member to start recognizing faces.</p>
          <button class="btn btn-primary" style="margin-top: 1rem;" onclick="openModal('modal-add-person')">+ Add First Member</button>
        </div>
      `;
      return;
    }

    container.innerHTML = currentPersonsList.map(p => `
      <div class="glass-panel person-card" onclick="openPersonDetails('${p.id}')">
        <img src="${p.primary_thumbnail || 'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>👤</text></svg>'}" 
             class="person-card-avatar" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>👤</text></svg>'">
        <div class="person-card-name">${p.name}</div>
        <div class="person-card-meta">${p.notes || 'Household Member'}</div>
        <div class="person-card-samples">
          <span>🧠</span> <span>${p.sample_count} Samples</span>
        </div>
      </div>
    `).join("");
  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: var(--accent-rose); text-align: center; padding: 2rem;">Error: ${err.message}</div>`;
  }
}

async function openPersonDetails(personId) {
  activePersonId = personId;
  try {
    const person = await apiFetch(`/api/v1/persons/${personId}`);
    document.getElementById("detail-person-name").textContent = person.name;
    document.getElementById("detail-sample-count").textContent = `${person.sample_count} learned face samples`;

    const gallery = document.getElementById("person-samples-gallery");
    if (!person.samples || person.samples.length === 0) {
      gallery.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-dim); padding: 2rem;">No sample photos stored yet.</div>`;
    } else {
      gallery.innerHTML = person.samples.map(s => `
        <div class="sample-thumbnail" id="sample-item-${s.id}">
          <img src="${s.thumbnail_url}" alt="Sample face">
          <button class="btn-del-sample" onclick="deleteSample('${person.id}', '${s.id}', event)">✕</button>
        </div>
      `).join("");
    }

    openModal("modal-person-detail");
  } catch (err) {
    showToast("Failed to load details: " + err.message, "error");
  }
}

async function deleteSample(personId, sampleId, evt) {
  evt.stopPropagation();
  if (!confirm("Remove this face sample from training?")) return;
  try {
    await apiFetch(`/api/v1/persons/${personId}/samples/${sampleId}`, { method: "DELETE" });
    const item = document.getElementById(`sample-item-${sampleId}`);
    if (item) item.remove();
    showToast("Sample deleted and model updated", "info");
    loadPersons();
    loadStats();
  } catch (err) {
    showToast("Failed to delete sample: " + err.message, "error");
  }
}

// --- 4. Interactive Test Sandbox ---
function setupSandbox() {
  const dropzone = document.getElementById("sandbox-dropzone");
  const fileInput = document.getElementById("sandbox-file-input");
  const previewImg = document.getElementById("sandbox-preview-img");
  const canvasWrapper = document.getElementById("sandbox-canvas-wrapper");
  const resultWrapper = document.getElementById("sandbox-result-wrapper");
  const detailsPanel = document.getElementById("sandbox-details");
  const emptyState = document.getElementById("sandbox-empty-state");
  const btnClear = document.getElementById("btn-clear-sandbox");

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleSandboxFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleSandboxFile(e.target.files[0]);
    }
  });

  if (btnClear) {
    btnClear.addEventListener("click", () => {
      fileInput.value = "";
      resultWrapper.style.display = "none";
      dropzone.style.display = "block";
      detailsPanel.style.display = "none";
      emptyState.style.display = "block";
      // Clear overlay boxes
      document.querySelectorAll(".face-bbox").forEach(b => b.remove());
    });
  }

  async function handleSandboxFile(file) {
    showToast("Analyzing image with FaceID model...", "info");
    try {
      const base64Data = await fileToBase64(file);
      previewImg.src = base64Data;
      dropzone.style.display = "none";
      resultWrapper.style.display = "block";

      // Clear previous boxes
      document.querySelectorAll(".face-bbox").forEach(b => b.remove());

      // Send to recognition endpoint
      const result = await apiFetch("/api/v1/recognize", {
        method: "POST",
        body: JSON.stringify({
          image: base64Data,
          min_confidence: 0.40,
          save_unrecognized: true
        })
      });

      emptyState.style.display = "none";
      detailsPanel.style.display = "block";
      document.getElementById("sandbox-face-count").textContent = result.count;
      document.getElementById("sandbox-latency").textContent = `${result.latency_ms} ms`;

      // Render side list of detected faces
      const facesList = document.getElementById("sandbox-faces-list");
      if (result.count === 0) {
        facesList.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 1rem;">No faces detected in this image.</div>`;
      } else {
        facesList.innerHTML = result.faces.map(f => `
          <div class="activity-item" style="padding: 0.5rem 0.75rem;">
            <div class="activity-user">
              <img src="${f.thumbnail_url}" class="activity-avatar" style="width: 38px; height: 38px;">
              <div class="activity-details">
                <h4 style="font-size: 0.875rem;">${f.name}</h4>
                <span style="font-size: 0.75rem;">Score: ${Math.round(f.similarity * 100)}% • Conf: ${Math.round(f.detection_confidence * 100)}%</span>
              </div>
            </div>
            <span class="chip-tag ${f.match ? 'matched' : 'unrecognized'}">
              ${f.match ? 'Matched' : 'Unknown'}
            </span>
          </div>
        `).join("");
      }

      // Draw bounding boxes once image is rendered
      previewImg.onload = () => {
        renderBoundingBoxes(previewImg, canvasWrapper, result.faces);
      };
      if (previewImg.complete) {
        renderBoundingBoxes(previewImg, canvasWrapper, result.faces);
      }

      showToast(`Detected ${result.count} face(s) in ${result.latency_ms}ms`, "success");
      loadStats();
    } catch (err) {
      showToast("Detection failed: " + err.message, "error");
    }
  }

  function renderBoundingBoxes(img, container, faces) {
    document.querySelectorAll(".face-bbox").forEach(b => b.remove());
    const naturalWidth = img.naturalWidth || img.width;
    const naturalHeight = img.naturalHeight || img.height;
    const renderedWidth = img.clientWidth || img.width;
    const renderedHeight = img.clientHeight || img.height;

    const scaleX = renderedWidth / naturalWidth;
    const scaleY = renderedHeight / naturalHeight;

    faces.forEach(face => {
      const box = document.createElement("div");
      box.className = `face-bbox ${face.match ? '' : 'unknown'}`;
      
      const left = face.bbox.x1 * scaleX;
      const top = face.bbox.y1 * scaleY;
      const width = face.bbox.width * scaleX;
      const height = face.bbox.height * scaleY;

      box.style.left = `${left}px`;
      box.style.top = `${top}px`;
      box.style.width = `${width}px`;
      box.style.height = `${height}px`;

      const label = document.createElement("div");
      label.className = `bbox-label ${face.match ? '' : 'unknown'}`;
      label.textContent = `${face.name} (${Math.round(face.similarity * 100)}%)`;
      box.appendChild(label);

      container.appendChild(box);
    });
  }
}

// --- DOM Event Listeners & Initialization ---
document.addEventListener("DOMContentLoaded", () => {
  // Navigation tabs
  document.querySelectorAll(".nav-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Header login button
  const btnAuth = document.getElementById("btn-header-auth");
  if (btnAuth) {
    btnAuth.addEventListener("click", () => openModal("modal-login"));
  }

  // Refresh buttons
  const btnRefreshStats = document.getElementById("btn-refresh-stats");
  if (btnRefreshStats) btnRefreshStats.addEventListener("click", loadStats);

  const btnRefreshReview = document.getElementById("btn-refresh-review");
  if (btnRefreshReview) btnRefreshReview.addEventListener("click", loadUnrecognized);

  // Add Member button
  const btnAddPerson = document.getElementById("btn-add-person");
  if (btnAddPerson) btnAddPerson.addEventListener("click", () => openModal("modal-add-person"));

  // Delete Member button
  const btnDelPerson = document.getElementById("btn-delete-person");
  if (btnDelPerson) {
    btnDelPerson.addEventListener("click", async () => {
      if (!activePersonId) return;
      if (!confirm("Are you sure you want to permanently delete this member and all learned vectors?")) return;
      try {
        await apiFetch(`/api/v1/persons/${activePersonId}`, { method: "DELETE" });
        closeModal("modal-person-detail");
        showToast("Member deleted", "info");
        loadPersons();
        loadStats();
      } catch (err) {
        showToast("Delete failed: " + err.message, "error");
      }
    });
  }

  // Upload Extra Sample Input
  const inputExtraSample = document.getElementById("input-upload-extra-sample");
  if (inputExtraSample) {
    inputExtraSample.addEventListener("change", async (e) => {
      if (!activePersonId || !e.target.files[0]) return;
      try {
        const b64 = await fileToBase64(e.target.files[0]);
        await apiFetch(`/api/v1/persons/${activePersonId}/samples`, {
          method: "POST",
          body: JSON.stringify({ image: b64 })
        });
        showToast("Face sample successfully added to model!", "success");
        openPersonDetails(activePersonId);
        loadPersons();
        loadStats();
      } catch (err) {
        showToast("Upload failed: " + err.message, "error");
      }
    });
  }

  // Form: Login
  const formLogin = document.getElementById("form-login");
  if (formLogin) {
    formLogin.addEventListener("submit", async (e) => {
      e.preventDefault();
      const username = document.getElementById("login-username").value;
      const password = document.getElementById("login-password").value;
      try {
        const data = await apiFetch("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ username, password })
        });
        currentToken = data.access_token;
        localStorage.setItem("access_token", currentToken);
        btnAuth.textContent = `User: ${data.username}`;
        closeModal("modal-login");
        showToast(`Welcome back, ${data.username}!`, "success");
      } catch (err) {
        showToast("Login failed: " + err.message, "error");
      }
    });
  }

  // Form: Add Person
  const formAddPerson = document.getElementById("form-add-person");
  if (formAddPerson) {
    formAddPerson.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("add-person-name").value.trim();
      const notes = document.getElementById("add-person-notes").value.trim();
      const photoFile = document.getElementById("add-person-photo").files[0];

      let initialImage = null;
      if (photoFile) {
        initialImage = await fileToBase64(photoFile);
      }

      try {
        await apiFetch("/api/v1/persons", {
          method: "POST",
          body: JSON.stringify({ name, notes, initial_image: initialImage })
        });
        formAddPerson.reset();
        closeModal("modal-add-person");
        showToast(`Registered member '${name}'`, "success");
        loadPersons();
        loadStats();
      } catch (err) {
        showToast("Registration failed: " + err.message, "error");
      }
    });
  }

  // Form: Assign Unknown Detection
  const formAssign = document.getElementById("form-assign");
  if (formAssign) {
    formAssign.addEventListener("submit", async (e) => {
      e.preventDefault();
      const detectionId = document.getElementById("assign-detection-id").value;
      const personId = document.getElementById("assign-person-select").value;
      const newName = document.getElementById("assign-new-name").value.trim();

      if (!personId && !newName) {
        showToast("Please choose an existing member or type a new name", "error");
        return;
      }

      try {
        await apiFetch(`/api/v1/detections/${detectionId}/assign`, {
          method: "POST",
          body: JSON.stringify({
            person_id: personId || null,
            new_person_name: newName || null
          })
        });
        closeModal("modal-assign");
        showToast("Face assigned and model updated!", "success");
        loadUnrecognized();
        loadPersons();
        loadStats();
      } catch (err) {
        showToast("Assignment failed: " + err.message, "error");
      }
    });
  }

  // RTSP Start & Stop Buttons
  const btnRtspStart = document.getElementById("btn-rtsp-start");
  if (btnRtspStart) {
    btnRtspStart.addEventListener("click", async () => {
      try {
        await apiFetch("/api/v1/rtsp/start", { method: "POST" });
        showToast("Starting RTSP stream worker...", "success");
        setTimeout(loadRtspStatus, 1000);
      } catch (err) {
        showToast("Failed to start stream: " + err.message, "error");
      }
    });
  }

  const btnRtspStop = document.getElementById("btn-rtsp-stop");
  if (btnRtspStop) {
    btnRtspStop.addEventListener("click", async () => {
      try {
        await apiFetch("/api/v1/rtsp/stop", { method: "POST" });
        showToast("RTSP stream worker stopped", "info");
        setTimeout(loadRtspStatus, 500);
      } catch (err) {
        showToast("Failed to stop stream: " + err.message, "error");
      }
    });
  }

  // RTSP Config Form
  const formRtspConfig = document.getElementById("form-rtsp-config");
  if (formRtspConfig) {
    formRtspConfig.addEventListener("submit", async (e) => {
      e.preventDefault();
      const url = document.getElementById("cfg-rtsp-url").value.trim();
      const camera_name = document.getElementById("cfg-rtsp-name").value.trim();
      const fps = parseFloat(document.getElementById("cfg-rtsp-fps").value) || 3.0;
      const cooldown_seconds = parseInt(document.getElementById("cfg-rtsp-cooldown").value) || 30;
      const webhook_url = document.getElementById("cfg-rtsp-webhook").value.trim();
      const webhook_only_known_faces = document.getElementById("cfg-webhook-only-known") ? document.getElementById("cfg-webhook-only-known").checked : false;
      const mqtt_enabled = document.getElementById("cfg-mqtt-enabled").checked;
      const mqtt_host = document.getElementById("cfg-mqtt-host").value.trim();
      const mqtt_port = parseInt(document.getElementById("cfg-mqtt-port").value) || 1883;
      const mqtt_topic = document.getElementById("cfg-mqtt-topic").value.trim();
      const mqtt_user = document.getElementById("cfg-mqtt-user") ? document.getElementById("cfg-mqtt-user").value.trim() : "";
      const mqtt_password = document.getElementById("cfg-mqtt-pass") ? document.getElementById("cfg-mqtt-pass").value : "";

      try {
        await apiFetch("/api/v1/rtsp/config", {
          method: "POST",
          body: JSON.stringify({
            url, camera_name, fps, cooldown_seconds, webhook_url, webhook_only_known_faces,
            mqtt_enabled, mqtt_host, mqtt_port, mqtt_topic, mqtt_user, mqtt_password
          })
        });
        showToast("Stream and MQTT settings updated!", "success");
        loadRtspStatus();
      } catch (err) {
        showToast("Config update failed: " + err.message, "error");
      }
    });
  }

  // Initialize Sandbox & Settings
  setupSandbox();
  setupSettingsForm();

  // Initial Data Load
  loadStats();
  loadSettings();
});

// --- RTSP Helper Functions ---
let rtspPollTimer = null;

function startRtspPolling() {
  if (rtspPollTimer) clearInterval(rtspPollTimer);
  rtspPollTimer = setInterval(loadRtspStatus, 2500);
}

function stopRtspPolling() {
  if (rtspPollTimer) {
    clearInterval(rtspPollTimer);
    rtspPollTimer = null;
  }
}

async function loadRtspStatus() {
  try {
    const data = await apiFetch("/api/v1/rtsp/status");
    const badge = document.getElementById("rtsp-status-badge");
    const previewImg = document.getElementById("rtsp-live-preview");
    const placeholder = document.getElementById("rtsp-offline-placeholder");
    const indicator = document.getElementById("rtsp-live-indicator");

    if (badge) {
      if (data.is_running) {
        badge.textContent = data.is_connected ? "● Connected" : "Connecting...";
        badge.className = `chip-tag ${data.is_connected ? 'matched' : 'unrecognized'}`;
        if (previewImg && data.is_connected) {
          previewImg.style.display = "block";
          if (placeholder) placeholder.style.display = "none";
          if (indicator) indicator.style.display = "block";
          previewImg.src = `/api/v1/rtsp/preview?t=${Date.now()}`;
        }
      } else {
        badge.textContent = "Stopped";
        badge.className = "chip-tag unrecognized";
        if (previewImg) previewImg.style.display = "none";
        if (placeholder) placeholder.style.display = "block";
        if (indicator) indicator.style.display = "none";
      }
    }

    const actualFpsElem = document.getElementById("rtsp-actual-fps");
    if (actualFpsElem) actualFpsElem.textContent = data.actual_fps ? data.actual_fps.toFixed(1) : "0.0";

    const lastPersonElem = document.getElementById("rtsp-last-person");
    if (lastPersonElem) {
      lastPersonElem.textContent = data.last_detection ? `${data.last_detection.person_name} (${Math.round(data.last_detection.similarity * 100)}%)` : "None";
    }

    const cooldownsElem = document.getElementById("rtsp-active-cooldowns-count");
    if (cooldownsElem) {
      cooldownsElem.textContent = data.active_cooldowns ? Object.keys(data.active_cooldowns).length : 0;
    }

    // Populate inputs if user is not actively typing
    const activeEl = document.activeElement;
    if (!activeEl || activeEl.tagName !== "INPUT") {
      if (data.url && document.getElementById("cfg-rtsp-url")) document.getElementById("cfg-rtsp-url").value = data.url;
      if (data.camera_name && document.getElementById("cfg-rtsp-name")) document.getElementById("cfg-rtsp-name").value = data.camera_name;
      if (data.target_fps && document.getElementById("cfg-rtsp-fps")) document.getElementById("cfg-rtsp-fps").value = data.target_fps;
      if (data.cooldown_seconds && document.getElementById("cfg-rtsp-cooldown")) document.getElementById("cfg-rtsp-cooldown").value = data.cooldown_seconds;
      if (data.webhook_url && document.getElementById("cfg-rtsp-webhook")) document.getElementById("cfg-rtsp-webhook").value = data.webhook_url;
      if (document.getElementById("cfg-webhook-only-known") && data.webhook_only_known_faces !== undefined) {
        document.getElementById("cfg-webhook-only-known").checked = !!data.webhook_only_known_faces;
      }
      if (data.mqtt) {
        if (document.getElementById("cfg-mqtt-enabled")) document.getElementById("cfg-mqtt-enabled").checked = !!data.mqtt.enabled;
        if (data.mqtt.host && document.getElementById("cfg-mqtt-host")) document.getElementById("cfg-mqtt-host").value = data.mqtt.host;
        if (data.mqtt.port && document.getElementById("cfg-mqtt-port")) document.getElementById("cfg-mqtt-port").value = data.mqtt.port;
        if (data.mqtt.topic && document.getElementById("cfg-mqtt-topic")) document.getElementById("cfg-mqtt-topic").value = data.mqtt.topic;
        if (document.getElementById("cfg-mqtt-user") && data.mqtt.user !== undefined) document.getElementById("cfg-mqtt-user").value = data.mqtt.user;
      }
    }

    // Update MQTT Status Badge
    const mqttBadge = document.getElementById("mqtt-status-badge");
    if (mqttBadge && data.mqtt) {
      if (!data.mqtt.enabled) {
        mqttBadge.style.display = "none";
      } else {
        mqttBadge.style.display = "inline-block";
        if (data.mqtt.connected) {
          mqttBadge.className = "chip-tag matched";
          mqttBadge.textContent = "MQTT Connected";
          mqttBadge.title = `Connected to ${data.mqtt.host}:${data.mqtt.port}`;
        } else if (data.mqtt.last_error) {
          mqttBadge.className = "chip-tag unrecognized";
          mqttBadge.textContent = "MQTT Auth Error";
          mqttBadge.title = data.mqtt.last_error;
        } else {
          mqttBadge.className = "chip-tag";
          mqttBadge.textContent = "MQTT Disconnected";
          mqttBadge.title = "Connecting or offline";
        }
      }
    }
  } catch (err) {
    console.error("Failed to load RTSP status:", err);
  }
}

// --- System Settings Functions ---
async function loadSettings() {
  try {
    const data = await apiFetch("/api/v1/settings");
    if (!data) return;

    // Detection & Recognition
    const detConfInput = document.getElementById("set-detection-confidence");
    if (detConfInput && data.detection_confidence !== undefined) {
      detConfInput.value = data.detection_confidence;
      const lbl = document.getElementById("val-detection-confidence");
      if (lbl) lbl.textContent = parseFloat(data.detection_confidence).toFixed(2);
    }

    const simThreshInput = document.getElementById("set-similarity-threshold");
    if (simThreshInput && data.similarity_threshold !== undefined) {
      simThreshInput.value = data.similarity_threshold;
      const lbl = document.getElementById("val-similarity-threshold");
      if (lbl) lbl.textContent = parseFloat(data.similarity_threshold).toFixed(2);
    }

    const detSizeSelect = document.getElementById("set-det-size");
    if (detSizeSelect && data.det_size !== undefined) {
      detSizeSelect.value = String(data.det_size);
    }

    const maxSamplesInput = document.getElementById("set-max-samples");
    if (maxSamplesInput && data.max_samples_per_person !== undefined) {
      maxSamplesInput.value = data.max_samples_per_person;
    }

    // Notification Thresholds
    const notifThreshInput = document.getElementById("set-notification-threshold");
    if (notifThreshInput && data.notification_threshold !== undefined) {
      notifThreshInput.value = data.notification_threshold;
      const lbl = document.getElementById("val-notification-threshold");
      if (lbl) lbl.textContent = parseFloat(data.notification_threshold).toFixed(2);
    }

    const notifyUnknownCheck = document.getElementById("set-notify-unknown");
    if (notifyUnknownCheck && data.notify_on_unknown !== undefined) {
      notifyUnknownCheck.checked = !!data.notify_on_unknown;
    }

    const unknownMinConfInput = document.getElementById("set-unknown-min-conf");
    if (unknownMinConfInput && data.unknown_min_confidence !== undefined) {
      unknownMinConfInput.value = data.unknown_min_confidence;
      const lbl = document.getElementById("val-unknown-min-conf");
      if (lbl) lbl.textContent = parseFloat(data.unknown_min_confidence).toFixed(2);
    }

    const cooldownInput = document.getElementById("set-cooldown-seconds");
    if (cooldownInput && data.rtsp_cooldown_seconds !== undefined) {
      cooldownInput.value = data.rtsp_cooldown_seconds;
    }

    // RTSP Video Stream
    const rtspEnabledCheck = document.getElementById("set-rtsp-enabled");
    if (rtspEnabledCheck && data.rtsp_enabled !== undefined) {
      rtspEnabledCheck.checked = !!data.rtsp_enabled;
    }

    const rtspUrlInput = document.getElementById("set-rtsp-url");
    if (rtspUrlInput && data.rtsp_url !== undefined) {
      rtspUrlInput.value = data.rtsp_url;
    }

    const cameraNameInput = document.getElementById("set-camera-name");
    if (cameraNameInput && data.rtsp_camera_name !== undefined) {
      cameraNameInput.value = data.rtsp_camera_name;
    }

    const rtspFpsInput = document.getElementById("set-rtsp-fps");
    if (rtspFpsInput && data.rtsp_fps !== undefined) {
      rtspFpsInput.value = data.rtsp_fps;
    }

    const webhookUrlInput = document.getElementById("set-webhook-url");
    if (webhookUrlInput && data.rtsp_webhook_url !== undefined) {
      webhookUrlInput.value = data.rtsp_webhook_url;
    }

    const webhookOnlyKnownCheck = document.getElementById("set-webhook-only-known");
    if (webhookOnlyKnownCheck && data.webhook_only_known_faces !== undefined) {
      webhookOnlyKnownCheck.checked = !!data.webhook_only_known_faces;
    }

    // MQTT Broker Integration
    const mqttEnabledCheck = document.getElementById("set-mqtt-enabled");
    if (mqttEnabledCheck && data.mqtt_enabled !== undefined) {
      mqttEnabledCheck.checked = !!data.mqtt_enabled;
    }

    const mqttHostInput = document.getElementById("set-mqtt-host");
    if (mqttHostInput && data.mqtt_host !== undefined) {
      mqttHostInput.value = data.mqtt_host;
    }

    const mqttPortInput = document.getElementById("set-mqtt-port");
    if (mqttPortInput && data.mqtt_port !== undefined) {
      mqttPortInput.value = data.mqtt_port;
    }

    const mqttTopicInput = document.getElementById("set-mqtt-topic");
    if (mqttTopicInput && data.mqtt_topic !== undefined) {
      mqttTopicInput.value = data.mqtt_topic;
    }

    const mqttUserInput = document.getElementById("set-mqtt-user");
    if (mqttUserInput && data.mqtt_user !== undefined) {
      mqttUserInput.value = data.mqtt_user;
    }

    const mqttPassInput = document.getElementById("set-mqtt-pass");
    if (mqttPassInput && data.mqtt_password !== undefined) {
      mqttPassInput.value = data.mqtt_password;
    }

    // Load migration versioning status
    await loadMigrationStatus();

  } catch (err) {
    console.error("Failed to load system settings:", err);
  }
}

async function loadMigrationStatus() {
  try {
    const data = await apiFetch("/api/v1/settings/migrations");
    if (!data) return;

    const versionBadge = document.getElementById("db-version-badge");
    if (versionBadge) versionBadge.textContent = `v${data.database_version || data.current_app_version}`;

    const syncBadge = document.getElementById("db-sync-badge");
    if (syncBadge) {
      const isSynced = data.database_version === data.current_app_version;
      syncBadge.textContent = isSynced ? "Synchronized" : "Pending Sync";
      syncBadge.className = `chip-tag ${isSynced ? 'matched' : 'unrecognized'}`;
    }

    const listEl = document.getElementById("migration-history-list");
    if (listEl) {
      if (!data.applied_migrations || data.applied_migrations.length === 0) {
        listEl.innerHTML = `<span style="color: var(--text-dim);">No migrations recorded yet.</span>`;
      } else {
        listEl.innerHTML = data.applied_migrations.map(m => `
          <div style="padding: 3px 0; border-bottom: 1px dashed rgba(255,255,255,0.06);">
            <strong style="color: var(--accent-emerald);">✓ [v${m.app_version}]</strong> #${m.migration_id}: ${m.name}
            <span style="color: var(--text-dim); float: right;">${m.applied_at || ''}</span>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Failed to load migration status:", err);
  }
}

function setupSettingsForm() {
  // Bind range sliders to live text badges
  const sliderMappings = [
    { inputId: "set-detection-confidence", badgeId: "val-detection-confidence", decimals: 2 },
    { inputId: "set-similarity-threshold", badgeId: "val-similarity-threshold", decimals: 2 },
    { inputId: "set-notification-threshold", badgeId: "val-notification-threshold", decimals: 2 },
    { inputId: "set-unknown-min-conf", badgeId: "val-unknown-min-conf", decimals: 2 }
  ];

  sliderMappings.forEach(({ inputId, badgeId, decimals }) => {
    const inputEl = document.getElementById(inputId);
    const badgeEl = document.getElementById(badgeId);
    if (inputEl && badgeEl) {
      inputEl.addEventListener("input", () => {
        badgeEl.textContent = parseFloat(inputEl.value).toFixed(decimals);
      });
    }
  });

  // Top save button helper
  const btnSaveTop = document.getElementById("btn-save-settings-top");
  if (btnSaveTop) {
    btnSaveTop.addEventListener("click", () => {
      const form = document.getElementById("form-system-settings");
      if (form) form.requestSubmit();
    });
  }

  // Reload settings button
  const btnReload = document.getElementById("btn-reload-settings");
  if (btnReload) {
    btnReload.addEventListener("click", async () => {
      await loadSettings();
      showToast("Settings reloaded from database.", "info");
    });
  }

  // Migration rollback button
  const btnRollback = document.getElementById("btn-schema-rollback-1-0");
  if (btnRollback) {
    btnRollback.addEventListener("click", async () => {
      if (!confirm("Are you sure you want to rollback the database schema to v1.0.0?\n\nAn atomic backup will be created automatically, and your household entities & face embeddings will be safely preserved.")) {
        return;
      }
      try {
        await apiFetch("/api/v1/settings/migrations/rollback", {
          method: "POST",
          body: JSON.stringify({ target_version: "1.0.0" })
        });
        showToast("Database safely rolled back to v1.0.0! Backup created.", "info");
        await loadSettings();
      } catch (err) {
        showToast("Rollback failed: " + err.message, "error");
      }
    });
  }

  // Migration forward button
  const btnForward = document.getElementById("btn-schema-forward-latest");
  if (btnForward) {
    btnForward.addEventListener("click", async () => {
      try {
        await apiFetch("/api/v1/settings/migrations/forward", {
          method: "POST",
          body: JSON.stringify({ target_version: "1.1.0" })
        });
        showToast("Database schema reconciled to v1.1.0!", "success");
        await loadSettings();
      } catch (err) {
        showToast("Migration forward failed: " + err.message, "error");
      }
    });
  }

  // Handle form submission
  const formSettings = document.getElementById("form-system-settings");
  if (formSettings) {
    formSettings.addEventListener("submit", async (e) => {
      e.preventDefault();

      const payload = {
        detection_confidence: parseFloat(document.getElementById("set-detection-confidence").value),
        similarity_threshold: parseFloat(document.getElementById("set-similarity-threshold").value),
        notification_threshold: parseFloat(document.getElementById("set-notification-threshold").value),
        notify_on_unknown: document.getElementById("set-notify-unknown").checked,
        unknown_min_confidence: parseFloat(document.getElementById("set-unknown-min-conf").value),
        det_size: parseInt(document.getElementById("set-det-size").value) || 320,
        max_samples_per_person: parseInt(document.getElementById("set-max-samples").value) || 50,
        rtsp_enabled: document.getElementById("set-rtsp-enabled").checked,
        rtsp_url: document.getElementById("set-rtsp-url").value.trim(),
        rtsp_camera_name: document.getElementById("set-camera-name").value.trim(),
        rtsp_fps: parseFloat(document.getElementById("set-rtsp-fps").value) || 3.0,
        rtsp_cooldown_seconds: parseInt(document.getElementById("set-cooldown-seconds").value) || 30,
        rtsp_webhook_url: document.getElementById("set-webhook-url").value.trim(),
        webhook_only_known_faces: document.getElementById("set-webhook-only-known").checked,
        mqtt_enabled: document.getElementById("set-mqtt-enabled").checked,
        mqtt_host: document.getElementById("set-mqtt-host").value.trim(),
        mqtt_port: parseInt(document.getElementById("set-mqtt-port").value) || 1883,
        mqtt_topic: document.getElementById("set-mqtt-topic").value.trim(),
        mqtt_user: document.getElementById("set-mqtt-user").value.trim(),
        mqtt_password: document.getElementById("set-mqtt-pass").value
      };

      try {
        await apiFetch("/api/v1/settings", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        showToast("Settings saved to SQLite and active in memory!", "success");
        loadRtspStatus();
      } catch (err) {
        showToast("Failed to save settings: " + err.message, "error");
      }
    });
  }
}
