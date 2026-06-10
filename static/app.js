// Foco no Estudo — frontend do aplicativo (vanilla JS, sem dependências).

const state = {
  data: null,
  selectedSubjectId: null,
  period: "week",
  report: null,
  lastTodaySeconds: null,
  goalCelebrated: false,
  audioContext: null,
};

const $ = (selector) => document.querySelector(selector);

// --- API ---

const clientTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || "";

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Client-Time-Zone": clientTimeZone(),
      "X-Client-Timezone-Offset": String(new Date().getTimezoneOffset()),
      ...(options.headers || {}),
    },
  });
  if (response.status === 401) {
    window.location.href = "/";
    throw new Error("Sessão expirada. Faça login novamente.");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Erro inesperado");
  return data;
};

// Executa uma ação que devolve o estado completo e re-renderiza tudo.
async function applyAction(path, body = {}) {
  state.data = await api(path, { method: "POST", body: JSON.stringify(body) });
  renderState();
  await loadReport(state.period);
}

async function loadState() {
  state.data = await api("/api/state");
  renderState();
  await loadReport(state.period);
}

async function loadReport(period) {
  state.period = period;
  state.report = await api(`/api/reports?period=${period}`);
  document.querySelectorAll(".segmented button").forEach((button) => {
    button.classList.toggle("active", button.dataset.period === period);
  });
  renderReport();
}

// --- Formatação ---

const formatDuration = (seconds, compact = false) => {
  const safe = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  if (hours > 0) {
    return compact ? `${hours}h${String(minutes).padStart(2, "0")}` : `${hours}h ${minutes}min`;
  }
  if (minutes > 0) return `${minutes}min`;
  return `${safe % 60}s`;
};

const formatDayLabel = (date) =>
  new Date(`${date}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const sessionSeconds = (session) => {
  if (!session) return 0;
  const started = new Date(session.logical_started_at || session.started_at).getTime();
  if (Number.isNaN(started)) return 0;
  return Math.max(0, Math.floor((Date.now() - started) / 1000));
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

// --- Gráficos (canvas) ---

function roundRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function drawGauge(percent) {
  const canvas = $("#gaugeCanvas");
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  const centerX = width / 2;
  const centerY = height * 0.82;
  const radius = Math.min(width * 0.39, height * 0.68);
  const start = Math.PI;
  const clamped = Math.min(percent, 100) / 100;

  ctx.clearRect(0, 0, width, height);
  ctx.lineCap = "round";

  ctx.beginPath();
  ctx.arc(centerX, centerY, radius, start, Math.PI * 2);
  ctx.strokeStyle = css("--panel-soft");
  ctx.lineWidth = 28;
  ctx.stroke();

  const gradient = ctx.createLinearGradient(42, 0, width - 42, 0);
  gradient.addColorStop(0, "#d6453d");
  gradient.addColorStop(0.5, "#d9993f");
  gradient.addColorStop(1, "#1f9d63");

  ctx.beginPath();
  ctx.arc(centerX, centerY, radius, start, start + Math.PI * clamped);
  ctx.strokeStyle = gradient;
  ctx.lineWidth = 28;
  ctx.stroke();

  for (let i = 0; i <= 10; i += 1) {
    const angle = start + Math.PI * (i / 10);
    ctx.beginPath();
    ctx.moveTo(centerX + Math.cos(angle) * (radius - 24), centerY + Math.sin(angle) * (radius - 24));
    ctx.lineTo(centerX + Math.cos(angle) * (radius - 8), centerY + Math.sin(angle) * (radius - 8));
    ctx.strokeStyle = "rgba(23, 32, 29, 0.26)";
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

function drawBarChart(items) {
  const canvas = $("#barChart");
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  const pad = 42;
  const chartHeight = height - pad * 1.55;
  const max = Math.max(...items.map((item) => item.seconds), 3600);

  ctx.clearRect(0, 0, width, height);
  ctx.font = "13px system-ui";

  const gap = 10;
  const barWidth = Math.max(10, (width - pad * 2 - gap * (items.length - 1)) / Math.max(items.length, 1));

  items.forEach((item, index) => {
    const barHeight = Math.max(item.seconds ? 4 : 0, (item.seconds / max) * chartHeight);
    const x = pad + index * (barWidth + gap);

    ctx.fillStyle = "rgba(23, 107, 91, 0.14)";
    ctx.fillRect(x, pad, barWidth, chartHeight);
    ctx.fillStyle = css("--primary");
    roundRect(ctx, x, pad + chartHeight - barHeight, barWidth, barHeight, 5);
    ctx.fill();

    ctx.save();
    ctx.translate(x + barWidth / 2, height - 16);
    ctx.rotate(items.length > 14 ? -0.65 : 0);
    ctx.fillStyle = css("--muted");
    ctx.textAlign = items.length > 14 ? "right" : "center";
    ctx.fillText(formatDayLabel(item.date), 0, 0);
    ctx.restore();
  });

  ctx.strokeStyle = css("--line");
  ctx.beginPath();
  ctx.moveTo(pad, pad + chartHeight);
  ctx.lineTo(width - pad, pad + chartHeight);
  ctx.stroke();
}

function drawDonutChart(items) {
  const canvas = $("#donutChart");
  const ctx = canvas.getContext("2d");
  const { width, height } = canvas;
  const centerX = width * 0.38;
  const centerY = height * 0.5;
  const radius = Math.min(width, height) * 0.28;
  const total = items.reduce((sum, item) => sum + item.seconds, 0);

  ctx.clearRect(0, 0, width, height);
  if (!total) {
    ctx.fillStyle = css("--muted");
    ctx.font = "16px system-ui";
    ctx.textAlign = "center";
    ctx.fillText("Sem dados no período", width / 2, height / 2);
    return;
  }

  let start = -Math.PI / 2;
  items.forEach((item) => {
    const angle = (item.seconds / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.arc(centerX, centerY, radius, start, start + angle);
    ctx.closePath();
    ctx.fillStyle = item.color;
    ctx.fill();
    start += angle;
  });

  ctx.beginPath();
  ctx.arc(centerX, centerY, radius * 0.58, 0, Math.PI * 2);
  ctx.fillStyle = "#fff";
  ctx.fill();

  ctx.fillStyle = css("--text");
  ctx.font = "700 20px system-ui";
  ctx.textAlign = "center";
  ctx.fillText(formatDuration(total, true), centerX, centerY + 7);

  ctx.textAlign = "left";
  ctx.font = "13px system-ui";
  items.slice(0, 6).forEach((item, index) => {
    const x = width * 0.68;
    const y = 68 + index * 30;
    ctx.fillStyle = item.color;
    roundRect(ctx, x, y - 10, 12, 12, 3);
    ctx.fill();
    ctx.fillStyle = css("--text");
    ctx.fillText(item.name.slice(0, 22), x + 20, y);
  });
}

// --- Celebração da meta diária ---

function unlockAudio() {
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) return;
  if (!state.audioContext) state.audioContext = new AudioContext();
  if (state.audioContext.state === "suspended") state.audioContext.resume();
}

function playGoalSound() {
  unlockAudio();
  const audio = state.audioContext;
  if (!audio) return;

  const now = audio.currentTime;
  const notes = [
    { frequency: 523.25, start: 0, duration: 0.16 },
    { frequency: 659.25, start: 0.13, duration: 0.18 },
    { frequency: 783.99, start: 0.3, duration: 0.32 },
  ];
  notes.forEach((note) => {
    const oscillator = audio.createOscillator();
    const gain = audio.createGain();
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(note.frequency, now + note.start);
    gain.gain.setValueAtTime(0.0001, now + note.start);
    gain.gain.exponentialRampToValueAtTime(0.16, now + note.start + 0.025);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + note.start + note.duration);
    oscillator.connect(gain).connect(audio.destination);
    oscillator.start(now + note.start);
    oscillator.stop(now + note.start + note.duration + 0.03);
  });
}

function triggerGoalCelebration() {
  playGoalSound();
  const panel = $(".focus-panel");
  const burst = $("#goalCelebration");
  panel.classList.remove("goal-celebration");
  burst.innerHTML = "";

  for (let index = 0; index < 24; index += 1) {
    const piece = document.createElement("span");
    piece.style.setProperty("--x", `${Math.random() * 220 - 110}px`);
    piece.style.setProperty("--y", `${Math.random() * -120 - 44}px`);
    piece.style.setProperty("--r", `${Math.random() * 240 - 120}deg`);
    piece.style.setProperty("--delay", `${Math.random() * 0.16}s`);
    piece.style.setProperty("--color", ["#176b5b", "#d9993f", "#2f80ed", "#1f9d63"][index % 4]);
    burst.appendChild(piece);
  }

  requestAnimationFrame(() => panel.classList.add("goal-celebration"));
  $("#statusLine").textContent = "Meta diária atingida. Bom trabalho!";
  window.setTimeout(() => {
    panel.classList.remove("goal-celebration");
    burst.innerHTML = "";
  }, 1700);
}

function maybeCelebrateDailyGoal(todaySeconds, goalSeconds) {
  const previous = state.lastTodaySeconds;
  state.lastTodaySeconds = todaySeconds;

  if (!goalSeconds || previous === null) return;
  if (todaySeconds < goalSeconds) {
    state.goalCelebrated = false;
    return;
  }
  if (!state.goalCelebrated && previous < goalSeconds) {
    state.goalCelebrated = true;
    triggerGoalCelebration();
  }
}

// Ao trocar de projeto, zera o controle da celebração e a disciplina escolhida.
function resetProjectView() {
  state.selectedSubjectId = null;
  state.lastTodaySeconds = null;
  state.goalCelebrated = false;
}

// --- Renderização ---

function renderState() {
  const data = state.data;
  const project = data.project;
  const todaySeconds = data.today.total_seconds;
  const dailyGoalSeconds = project.daily_goal_minutes * 60;
  const dailyPercent = dailyGoalSeconds ? Math.floor((todaySeconds / dailyGoalSeconds) * 100) : 0;
  const totalSeconds = data.total.total_seconds;
  const totalGoalSeconds = project.total_goal_minutes * 60;
  const totalPercent = totalGoalSeconds ? Math.floor((totalSeconds / totalGoalSeconds) * 100) : 0;
  const running = data.running_session;
  const remainingSeconds = Math.max(0, dailyGoalSeconds - todaySeconds);

  $("#projectName").textContent = project.name;
  $("#dailyPercent").textContent = `${dailyPercent}%`;
  $("#dailyTime").textContent = `${formatDuration(todaySeconds)} de ${formatDuration(dailyGoalSeconds)}`;
  $("#sessionElapsed").textContent = formatDuration(sessionSeconds(running));
  $("#remainingTime").textContent = remainingSeconds ? formatDuration(remainingSeconds) : "Meta batida";
  $("#currentSubjectBadge").textContent = running ? `Agora: ${running.subject_name}` : "Timer pausado";
  $("#currentSubjectBadge").classList.toggle("is-running", Boolean(running));
  $(".focus-panel").classList.toggle("is-running", Boolean(running));
  $("#totalProgressText").textContent = `${formatDuration(totalSeconds)} de ${formatDuration(totalGoalSeconds)}`;
  $("#totalPercent").textContent = `${totalPercent}%`;
  $("#totalProgressBar").style.width = `${Math.min(totalPercent, 100)}%`;
  $("#timerButton").textContent = running ? "Pausar" : "Iniciar";
  $("#statusLine").textContent = running
    ? `Estudando ${running.subject_name} desde ${new Date(running.logical_started_at || running.started_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}.`
    : "Timer pausado. Selecione uma disciplina e inicie quando estiver pronto.";

  renderProjectSelect();
  renderSubjectSelect();
  renderTodaySubjects();
  drawGauge(dailyPercent);
  maybeCelebrateDailyGoal(todaySeconds, dailyGoalSeconds);
}

function renderProjectSelect() {
  const select = $("#projectSelect");
  const projects = state.data.projects || [];
  select.innerHTML =
    projects
      .map((project) => `<option value="${project.id}">${escapeHtml(project.name)}</option>`)
      .join("") + `<option value="__new__">+ Novo projeto…</option>`;
  select.value = String(state.data.project.id);
}

function renderSubjectSelect() {
  const select = $("#subjectSelect");
  const activeSubjects = state.data.subjects.filter((subject) => subject.active);
  const running = state.data.running_session;
  const chosen = running?.subject_id || state.selectedSubjectId || activeSubjects[0]?.id || "";

  select.innerHTML = activeSubjects
    .map((subject) => `<option value="${subject.id}">${escapeHtml(subject.name)}</option>`)
    .join("");
  select.value = String(chosen);
  state.selectedSubjectId = Number(select.value || 0);
}

function renderTodaySubjects() {
  const container = $("#todaySubjects");
  const items = state.data.today.by_subject;
  const total = Math.max(state.data.today.total_seconds, 1);
  if (!items.length) {
    container.innerHTML = `<p class="status-line">Nenhuma sessão registrada hoje.</p>`;
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <div class="subject-item">
          <span class="swatch" style="background:${item.color}"></span>
          <div class="subject-main">
            <strong>${escapeHtml(item.name)}</strong>
            <div class="subject-bar" aria-hidden="true">
              <span style="width:${Math.round((item.seconds / total) * 100)}%;background:${item.color}"></span>
            </div>
          </div>
          <span>${formatDuration(item.seconds, true)}</span>
        </div>
      `,
    )
    .join("");
}

function renderReport() {
  const report = state.report;
  const total = report.total_seconds || 1;
  const daysWithData = report.by_day.filter((item) => item.seconds > 0);
  const averageBase = report.period === "total" ? Math.max(daysWithData.length, 1) : Math.max(report.by_day.length, 1);
  const bestDay = report.by_day.reduce((best, item) => (item.seconds > best.seconds ? item : best), {
    date: null,
    seconds: 0,
  });
  const topSubject = report.by_subject[0];

  $("#reportTotal").textContent = formatDuration(report.total_seconds);
  $("#reportAverage").textContent = formatDuration(Math.round(report.total_seconds / averageBase));
  $("#reportBestDay").textContent = bestDay.date ? `${formatDayLabel(bestDay.date)} - ${formatDuration(bestDay.seconds, true)}` : "-";
  $("#reportTopSubject").textContent = topSubject ? topSubject.name : "-";

  drawBarChart(report.by_day);
  drawDonutChart(report.by_subject);
  $("#subjectsTable").innerHTML = report.by_subject.length
    ? report.by_subject
        .map((item) => {
          const percent = Math.round((item.seconds / total) * 100);
          return `
            <tr>
              <td><span class="swatch" style="display:inline-block;background:${item.color};vertical-align:middle;margin-right:10px"></span>${escapeHtml(item.name)}</td>
              <td>${formatDuration(item.seconds)}</td>
              <td>${percent}%</td>
            </tr>
          `;
        })
        .join("")
    : `<tr><td colspan="3">Sem dados no período.</td></tr>`;
}

function renderSettings() {
  const project = state.data.project;
  $("#projectInput").value = project.name;
  $("#dailyGoalInput").value = project.daily_goal_minutes / 60;
  $("#totalGoalInput").value = project.total_goal_minutes / 60;
  $("#subjectEditorList").innerHTML = state.data.subjects
    .map(
      (subject) => `
        <div class="editor-item" data-id="${subject.id}">
          <input type="color" value="${subject.color}" aria-label="Cor da disciplina">
          <input type="text" value="${escapeAttr(subject.name)}" aria-label="Nome da disciplina">
          <button class="ghost-button danger" type="button" title="Ativar ou desativar">${subject.active ? "✓" : "×"}</button>
          <button class="ghost-button danger delete-subject" type="button" title="Excluir disciplina">−</button>
        </div>
      `,
    )
    .join("");
}

// --- Eventos: projeto e conta ---

$("#projectSelect").addEventListener("change", async (event) => {
  const value = event.target.value;
  try {
    if (value === "__new__") {
      const name = prompt("Nome do novo projeto (ex.: Concurso Receita Federal):");
      if (!name || !name.trim()) {
        renderProjectSelect();
        return;
      }
      resetProjectView();
      await applyAction("/api/projects", { name: name.trim() });
    } else {
      resetProjectView();
      await applyAction(`/api/projects/${value}/activate`);
    }
  } catch (error) {
    alert(error.message);
    renderProjectSelect();
  }
});

$("#logoutButton").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST", body: "{}" });
  } finally {
    window.location.href = "/";
  }
});

// --- Eventos: timer ---

$("#subjectSelect").addEventListener("change", async (event) => {
  const subjectId = Number(event.target.value);
  state.selectedSubjectId = subjectId;
  if (state.data.running_session) {
    await applyAction("/api/timer/switch", { subject_id: subjectId });
  }
});

$("#timerButton").addEventListener("click", async () => {
  unlockAudio();
  const running = state.data.running_session;
  try {
    if (running) {
      await applyAction("/api/timer/pause");
    } else {
      await applyAction("/api/timer/start", { subject_id: state.selectedSubjectId });
    }
  } catch (error) {
    $("#statusLine").textContent = error.message;
  }
});

document.querySelectorAll(".segmented button").forEach((button) => {
  button.addEventListener("click", () => loadReport(button.dataset.period));
});

// --- Eventos: configurações ---

$("#settingsButton").addEventListener("click", () => {
  renderSettings();
  $("#settingsDialog").showModal();
});

$("#addSubjectButton").addEventListener("click", () => {
  const item = document.createElement("div");
  item.className = "editor-item";
  item.dataset.id = "new";
  item.innerHTML = `
    <input type="color" value="#2f80ed" aria-label="Cor da disciplina">
    <input type="text" value="" placeholder="Nova disciplina" aria-label="Nome da disciplina">
    <button class="ghost-button danger" type="button" title="Ativar ou desativar">✓</button>
    <button class="ghost-button danger delete-subject" type="button" title="Excluir disciplina">−</button>
  `;
  $("#subjectEditorList").appendChild(item);
});

$("#subjectEditorList").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  const item = button.closest(".editor-item");
  if (button.classList.contains("delete-subject")) {
    if (item.dataset.id === "new") {
      item.remove();
      return;
    }
    const name = item.querySelector('input[type="text"]').value.trim() || "esta disciplina";
    if (!confirm(`Excluir ${name}? As sessões dessa disciplina também serão removidas.`)) return;
    api(`/api/subjects/${item.dataset.id}`, { method: "DELETE" })
      .then(async (data) => {
        state.data = data;
        renderSettings();
        renderState();
        await loadReport(state.period);
      })
      .catch((error) => alert(error.message));
    return;
  }
  const inactive = button.textContent.trim() === "×";
  button.textContent = inactive ? "✓" : "×";
});

$("#resetButton").addEventListener("click", async () => {
  const message = "Zerar as sessões deste projeto? Todo o histórico de estudo será apagado. Disciplinas e metas são mantidas.";
  if (!confirm(message)) return;
  try {
    await applyAction("/api/reset");
    $("#settingsDialog").close();
  } catch (error) {
    alert(error.message);
  }
});

$("#deleteProjectButton").addEventListener("click", async () => {
  const project = state.data.project;
  const message = `Excluir o projeto "${project.name}"? Disciplinas e todo o histórico de sessões serão apagados. Essa ação não pode ser desfeita.`;
  if (!confirm(message)) return;
  try {
    state.data = await api(`/api/projects/${project.id}`, { method: "DELETE" });
    $("#settingsDialog").close();
    resetProjectView();
    renderState();
    await loadReport(state.period);
  } catch (error) {
    alert(error.message);
  }
});

$("#saveSettingsButton").addEventListener("click", async () => {
  const projectPayload = {
    name: $("#projectInput").value.trim(),
    daily_goal_minutes: Math.round(Number($("#dailyGoalInput").value) * 60),
    total_goal_minutes: Math.round(Number($("#totalGoalInput").value) * 60),
  };

  try {
    state.data = await api("/api/project", { method: "POST", body: JSON.stringify(projectPayload) });
    for (const item of document.querySelectorAll("#subjectEditorList .editor-item")) {
      const [colorInput, nameInput] = item.querySelectorAll("input");
      const name = nameInput.value.trim();
      if (!name) continue;
      const payload = {
        name,
        color: colorInput.value,
        active: item.querySelector("button").textContent.trim() === "✓",
      };
      const isNew = item.dataset.id === "new";
      await api(isNew ? "/api/subjects" : `/api/subjects/${item.dataset.id}`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    }
    $("#settingsDialog").close();
    await loadState();
  } catch (error) {
    alert(error.message);
  }
});

// --- Inicialização ---

setInterval(async () => {
  if (!state.data?.running_session) return;
  state.data = await api("/api/state");
  renderState();
  if (state.period === "today") await loadReport("today");
}, 1000);

loadState().catch((error) => {
  document.body.innerHTML = `<main class="app-shell"><p>${escapeHtml(error.message)}</p></main>`;
});
