const $ = (id) => document.getElementById(id);

const i18n = window.NotesSnapshotI18n;
if (!i18n) {
  throw new Error("NotesSnapshotI18n is required before app.js");
}

const endpoints = {
  status: "/api/status",
  doctor: "/api/doctor",
  metrics: "/api/metrics?tail=120",
  recentRuns: "/api/recent-runs?tail=20",
  access: "/api/access",
};

const tokenParam = new URLSearchParams(window.location.search).get("token");
const tokenStorageKey = "notes_snapshot_web_token";
const storedToken = window.localStorage.getItem(tokenStorageKey);
let authToken = tokenParam || storedToken || "";
if (tokenParam) {
  window.localStorage.setItem(tokenStorageKey, tokenParam);
  authToken = tokenParam;
  const cleanUrl = `${window.location.pathname}${window.location.hash || ""}`;
  window.history.replaceState({}, "", cleanUrl);
}

const refreshButton = $("refresh");
const lastUpdated = $("last-updated");
const banner = $("system-banner");
const connection = $("connection-status");
const outputPane = $("action-output");
const actionAnnouncer = $("action-announcer");
const outputPill = $("output-pill");
const actionsPill = $("actions-pill");
const accessPill = $("access-pill");
const metricsFilterInput = $("metrics-run-id");
const localeSwitcher = $("locale-switcher");

const uiState = {
  connected: false,
  lastUpdatedAt: null,
  status: null,
  logHealth: null,
  doctor: null,
  metrics: [],
  recentRuns: null,
  access: null,
  bannerKey: "",
  renderedLocale: null,
};

function authHeaders() {
  if (!authToken) return {};
  return { Authorization: `Bearer ${authToken}` };
}

function formatAge(ageSec) {
  if (ageSec === null || ageSec === undefined || ageSec === "") return "--";
  const value = Number(ageSec);
  if (!Number.isFinite(value)) return String(ageSec);
  if (value < 60) return i18n.t("common.durationSeconds", { count: value });
  const minutes = Math.floor(value / 60);
  const rem = value % 60;
  if (minutes < 60) {
    return i18n.t("common.durationMinuteSecond", { minutes, seconds: rem });
  }
  const hours = Math.floor(minutes / 60);
  const min = minutes % 60;
  return i18n.t("common.durationHourMinute", { hours, minutes: min });
}

function formatMinutes(value) {
  if (value === null || value === undefined || value === "") return "--";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return i18n.t("common.durationMinutes", { count: number });
}

function formatRateLimit(max, windowSec) {
  const safeMax = Number(max || 0);
  const safeWindow = Number(windowSec || 0);
  return i18n.t("common.rateLimitFormat", { count: safeMax, window: safeWindow });
}

function formatClockTime(dateLike) {
  const date = dateLike instanceof Date ? dateLike : new Date(dateLike);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return new Intl.DateTimeFormat(i18n.getLocale(), {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function formatTimestamp(value) {
  if (value === null || value === undefined || value === "") return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat(i18n.getLocale(), {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function localizeCanonicalText(text) {
  if (!text) return text;
  const translators = [
    (value) => i18n.translateHealthSummary(value),
    (value) => i18n.translateStateLayerSummary(value),
    (value) => i18n.translateOperatorSummary(value),
    (value) => i18n.translateChangeSummary(value),
    (value) => i18n.translateWorkflowHint(value),
    (value) => i18n.translateWarning(value),
  ];
  for (const translate of translators) {
    const translated = translate(text);
    if (translated !== text) {
      return translated;
    }
  }
  return text;
}

function localizeActionName(action) {
  const keyMap = {
    setup: "ui.perfectSetup",
    run: "ui.runSnapshot",
    verify: "ui.verify",
    fix: "ui.fastFix",
    "self-heal": "ui.selfHeal",
    permissions: "ui.permissions",
    install: "ui.install",
    ensure: "ui.ensure",
    unload: "ui.unload",
    "update-vendor": "ui.updateVendor",
    logs: "ui.fetchLogs",
    "rotate-logs": "ui.rotateLogs",
  };
  return keyMap[action] ? i18n.t(keyMap[action]) : action;
}

function localizeTriggerSource(source) {
  const text = String(source || "");
  if (!text) return "--";
  if (text === "manual") {
    return i18n.t("common.manual");
  }
  if (text.startsWith("web:")) {
    const action = text.slice(4);
    const translated = localizeActionName(action);
    return i18n.t("message.webActionSource", { action: translated });
  }
  return text;
}

function localizeDependencyLabel(label) {
  const keyMap = {
    python_bin: "ui.pythonBin",
    osascript: "ui.osascript",
    launchctl: "ui.launchctl",
    plutil: "ui.plutil",
    timeout_bin: "ui.timeoutBin",
  };
  return keyMap[label] ? i18n.t(keyMap[label]) : label;
}

function localizeMetricEventName(event) {
  const text = String(event || "");
  if (!text) return i18n.t("common.metricEventFallback");
  return i18n.translateDisplay("metricEvent", text) || text;
}

function localizeActionList(actions) {
  if (!Array.isArray(actions) || actions.length === 0) {
    return [];
  }
  return actions.map((action) => localizeActionName(String(action)));
}

function formatCurrentStreak(streak) {
  const count = Number(streak?.count || 0);
  if (!count) return "--";
  const status = i18n.translateStatus(streak?.status || "unknown");
  return i18n.t("common.streakFormat", { status, count });
}

function formatStatusWindow(statusWindow) {
  const entries = Object.entries(statusWindow || {});
  if (!entries.length) {
    return i18n.t("common.none");
  }
  return entries
    .map(([status, count]) => {
      const trendLabel = i18n.translateChangeTrend(status);
      const label = trendLabel && trendLabel !== status ? trendLabel : i18n.translateStatus(status) || status;
      return `${label}: ${count}`;
    })
    .join(", ");
}

function formatCooldowns(cooldowns) {
  const entries = Object.entries(cooldowns || {});
  if (!entries.length) {
    return "{}";
  }
  return entries
    .map(
      ([action, seconds]) =>
        `${localizeActionName(action)}=${i18n.t("common.durationSeconds", { count: Number(seconds || 0) })}`
    )
    .join(", ");
}

function setText(id, value) {
  const el = $(id);
  if (!el) return;
  el.textContent = value === undefined || value === null || value === "" ? "--" : String(value);
}

function setTextWithTitle(id, value, titleValue) {
  const el = $(id);
  if (!el) return;
  el.textContent = value === undefined || value === null || value === "" ? "--" : String(value);
  if (titleValue) {
    el.setAttribute("title", String(titleValue));
  } else {
    el.removeAttribute("title");
  }
}

function setPill(el, level) {
  if (!el) return;
  const normalized = String(level || "").toLowerCase();
  el.classList.remove("pill--warn", "pill--fail");
  if (normalized === "warn" || normalized === "degraded" || normalized === "onboarding") {
    el.classList.add("pill--warn");
  } else if (normalized === "fail") {
    el.classList.add("pill--fail");
  }
  el.textContent = i18n.translateDisplay("healthLevel", level || "unknown") || level || "--";
}

function setSubPill(el, text, tone) {
  if (!el) return;
  el.classList.remove("pill--warn", "pill--fail");
  if (tone === "warn") {
    el.classList.add("pill--warn");
  } else if (tone === "fail") {
    el.classList.add("pill--fail");
  }
  el.textContent = text || "--";
}

function announceStatus(message) {
  if (!actionAnnouncer) return;
  actionAnnouncer.textContent = message || "";
}

function setBanner(message) {
  if (!banner) return;
  if (!message) {
    banner.classList.add("banner--hidden");
    banner.textContent = "";
    return;
  }
  banner.classList.remove("banner--hidden");
  banner.textContent = message;
}

function setConnection(ok) {
  uiState.connected = !!ok;
  if (!connection) return;
  connection.classList.toggle("connection--ok", uiState.connected);
  connection.textContent = i18n.translateBoolean(uiState.connected ? "online" : "offline");
}

async function fetchJson(url, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal, cache: "no-store", headers: authHeaders() });
    const data = await res.json();
    if (!res.ok) {
      return { ok: false, error: data || { status: res.status } };
    }
    return data;
  } catch (err) {
    return { ok: false, error: { message: err.message || String(err) } };
  } finally {
    clearTimeout(timer);
  }
}

async function postJson(url, payload, timeoutMs = 120000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = { "Content-Type": "application/json", ...authHeaders() };
    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload || {}),
      signal: controller.signal,
    });
    const data = await res.json();
    if (!res.ok) {
      return { ok: false, error: data || { status: res.status } };
    }
    return data;
  } catch (err) {
    return { ok: false, error: { message: err.message || String(err) } };
  } finally {
    clearTimeout(timer);
  }
}

function renderPhases(phasesBar) {
  const container = $("phases-bars");
  if (!container) return;
  container.innerHTML = "";
  if (!Array.isArray(phasesBar) || phasesBar.length === 0) {
    return;
  }
  phasesBar.slice(0, 6).forEach((item) => {
    const wrapper = document.createElement("div");
    wrapper.className = "phase-bar";

    const label = document.createElement("span");
    const phaseName = item.name || i18n.t("common.phaseFallback");
    label.textContent = i18n.t("common.phaseDuration", {
      name: phaseName,
      duration: i18n.t("common.durationSeconds", { count: item.duration_sec || 0 }),
    });

    const bar = document.createElement("div");
    bar.className = "bar";

    const fill = document.createElement("i");
    const width = Math.min(Math.max(Number(item.percent) || 0, 2), 100);
    fill.style.width = `${width}%`;

    bar.appendChild(fill);
    wrapper.appendChild(label);
    wrapper.appendChild(bar);
    container.appendChild(wrapper);
  });
}

function renderMetricsTable(entries) {
  const table = $("metrics-table");
  if (!table) return;
  table.innerHTML = "";
  let rows = Array.isArray(entries) ? entries : [];
  const filter = (metricsFilterInput?.value || "").trim();
  if (filter) {
    rows = rows.filter((row) => String(row.run_id || "").includes(filter));
  }
  if (rows.length === 0) {
    table.textContent = i18n.t("emptyState.metrics");
    return;
  }
  rows.slice(0, 10).forEach((row) => {
    const line = document.createElement("div");
    line.className = "table-row";

    const event = document.createElement("strong");
    event.textContent = localizeMetricEventName(row.event || "");

    const detail = document.createElement("div");
    const detailText = row.message || row.run_id || row.root_dir || row.pipeline_exit_reason || "--";
    detail.textContent = detailText;

    const time = document.createElement("div");
    const rawTime = row.end_iso || row.start_iso || "--";
    time.textContent = formatTimestamp(rawTime);
    if (rawTime && rawTime !== "--") {
      time.setAttribute("title", String(rawTime));
    }

    line.appendChild(event);
    line.appendChild(detail);
    line.appendChild(time);
    table.appendChild(line);
  });
}

function renderStateLayers(layers) {
  const list = $("state-layers");
  if (!list) return;
  list.innerHTML = "";

  const order = ["config", "launchd", "ledger"];
  order.forEach((key) => {
    const layer = layers?.[key];
    const li = document.createElement("li");
    const label = i18n.translateDisplay("stateLayerLabel", key) || key;
    if (!layer) {
      li.textContent = `${label}: --`;
      list.appendChild(li);
      return;
    }
    const parts = [
      label,
      i18n.translateStateLayerStatus(layer.status || "unknown"),
    ];
    if (layer.summary) {
      parts.push(localizeCanonicalText(layer.summary));
    }
    li.textContent = parts.join(" - ");
    list.appendChild(li);
  });
}

function renderHealthSummary(summary) {
  const list = $("health-summary");
  if (!list) return;
  list.innerHTML = "";

  const lines = Array.isArray(summary)
    ? summary
    : String(summary || "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
  if (lines.length === 0) {
    const li = document.createElement("li");
    li.textContent = i18n.t("emptyState.healthSummary");
    list.appendChild(li);
    return;
  }
  lines.forEach((line) => {
    const li = document.createElement("li");
    li.textContent = localizeCanonicalText(line);
    list.appendChild(li);
  });
}

function renderOnboarding(data) {
  const card = $("onboarding-card");
  const pill = $("onboarding-pill");
  const summary = $("onboarding-summary");
  const steps = $("onboarding-steps");
  const hint = $("onboarding-hint");
  if (!card || !pill || !summary || !steps || !hint) return;

  const ledgerStatus = data?.state_layers?.ledger?.status || "";
  const needsFirstRun = ledgerStatus === "needs_first_run";
  card.hidden = !needsFirstRun;
  if (!needsFirstRun) {
    return;
  }

  setPill(pill, "ONBOARDING");
  summary.textContent = i18n.t("message.firstRunExplanation");
  steps.innerHTML = "";
  ["onboarding.stepRun", "onboarding.stepVerify", "onboarding.stepDoctor"].forEach((key) => {
    const li = document.createElement("li");
    li.textContent = i18n.t(key);
    steps.appendChild(li);
  });
  hint.innerHTML = i18n.t("message.firstRunHintHtml");
}

function renderDoctor(data) {
  setPill($("doctor-pill"), data?.warnings && data.warnings.length > 0 ? "WARN" : "OK");
  setText("doctor-summary", data?.operator_summary ? localizeCanonicalText(data.operator_summary) : i18n.t("emptyState.doctorSummary"));

  const deps = $("doctor-deps");
  if (deps) {
    deps.innerHTML = "";
    const depList = data?.dependencies || {};
    const depPairs = [
      [localizeDependencyLabel("python_bin"), depList.python_bin || ""],
      [localizeDependencyLabel("osascript"), depList.osascript ? i18n.t("common.ok") : i18n.t("common.missing")],
      [localizeDependencyLabel("launchctl"), depList.launchctl ? i18n.t("common.ok") : i18n.t("common.missing")],
      [localizeDependencyLabel("plutil"), depList.plutil ? i18n.t("common.ok") : i18n.t("common.missing")],
      [localizeDependencyLabel("timeout_bin"), depList.timeout_bin || ""],
    ];
    depPairs.forEach(([label, value]) => {
      const li = document.createElement("li");
      li.textContent = `${label}: ${value || `(${i18n.t("common.missing")})`}`;
      deps.appendChild(li);
    });
  }

  const warnings = $("doctor-warnings");
  if (warnings) {
    warnings.innerHTML = "";
    const list = data?.warnings || [];
    if (!list.length) {
      const li = document.createElement("li");
      li.textContent = i18n.t("emptyState.noWarnings");
      warnings.appendChild(li);
    } else {
      list.slice(0, 6).forEach((warn) => {
        const li = document.createElement("li");
        li.textContent = localizeCanonicalText(warn);
        warnings.appendChild(li);
      });
    }
  }

  setText("doctor-repo", data?.repo_root || "--");
  setText("doctor-vendor", data?.vendor_dir || "--");
  setText("doctor-state", data?.state_dir || "--");
}

function renderRecentRuns(payload) {
  const summary = payload?.summary || {};
  const recentRunCount = Number(summary.recent_run_count || 0);
  const successCount = Number(summary.success_count || 0);
  const failedCount = Number(summary.failed_count || 0);
  const changeSummary = summary.change_summary || {};
  const currentStreak = summary.current_streak || {};
  const failureClusters = Array.isArray(summary.failure_clusters) ? summary.failure_clusters : [];

  setText("recent-runs-count", recentRunCount);
  setText("recent-runs-success", successCount);
  setText("recent-runs-failed", failedCount);
  setText("recent-runs-latest-status", i18n.translateStatus(summary.latest_status || "unknown"));
  setText(
    "recent-runs-top-failure",
    summary.top_failure_reason ? localizeCanonicalText(summary.top_failure_reason) : i18n.t("common.none")
  );
  setText("recent-runs-trend", i18n.translateChangeTrend(changeSummary.trend || "unknown"));
  setText("recent-runs-streak", formatCurrentStreak(currentStreak));

  const pill = $("recent-runs-pill");
  if (failedCount > 0) {
    setPill(pill, "WARN");
  } else if (recentRunCount > 0) {
    setPill(pill, "OK");
  } else {
    setPill(pill, "ONBOARDING");
  }

  const summaryList = $("recent-runs-change-summary");
  if (summaryList) {
    summaryList.innerHTML = "";
    const entries = [];
    if (changeSummary.summary) {
      entries.push(localizeCanonicalText(changeSummary.summary));
    }
    if (summary.workflow_hint) {
      entries.push(localizeCanonicalText(summary.workflow_hint));
    }
    if (summary.recoverability) {
      entries.push(
        i18n.t("common.recoverabilityFormat", {
          state: i18n.translateRecoverability(summary.recoverability),
        })
      );
    }
    if (summary.status_window && Object.keys(summary.status_window).length) {
      entries.push(
        i18n.t("common.statusWindowFormat", {
          window: formatStatusWindow(summary.status_window),
        })
      );
    }
    if (!entries.length) {
      const li = document.createElement("li");
      li.textContent = i18n.t("emptyState.noChangeSummary");
      summaryList.appendChild(li);
    } else {
      entries.forEach((entry) => {
        const li = document.createElement("li");
        li.textContent = entry;
        summaryList.appendChild(li);
      });
    }
  }

  const list = $("recent-runs-trigger-sources");
  if (!list) return;
  list.innerHTML = "";
  const entries = Object.entries(summary.trigger_sources || {});
  if (entries.length === 0) {
    const li = document.createElement("li");
    li.textContent = i18n.t("emptyState.noRecordedRuns");
    list.appendChild(li);
    return;
  }
  entries.forEach(([source, count]) => {
    const li = document.createElement("li");
    li.textContent = `${localizeTriggerSource(source)}: ${count}`;
    list.appendChild(li);
  });

  const clusterList = $("recent-runs-failure-clusters");
  if (clusterList) {
    clusterList.innerHTML = "";
    if (!failureClusters.length) {
      const li = document.createElement("li");
      li.textContent = i18n.t("emptyState.noFailureClusters");
      clusterList.appendChild(li);
    } else {
      failureClusters.slice(0, 3).forEach((cluster) => {
        const li = document.createElement("li");
        li.textContent = `${localizeCanonicalText(cluster.reason || i18n.t("common.unknown"))} x${cluster.count || 0}`;
        clusterList.appendChild(li);
      });
    }
  }
}

function renderAccess(data) {
  if (!data) return;
  setText("access-require-token", i18n.translateBoolean(data.require_token ? "yes" : "no"));
  setText("access-require-static", i18n.translateBoolean(data.require_token_for_static ? "yes" : "no"));
  setText("access-readonly", i18n.translateBoolean(data.readonly ? "yes" : "no"));

  const scopes = Array.isArray(data.token_scopes) ? data.token_scopes.join(", ") : "--";
  const allow = Array.isArray(data.actions_allowlist) ? localizeActionList(data.actions_allowlist).join(", ") : "--";
  setText("access-scopes", scopes || "--");
  setText("access-actions-allow", allow || "--");
  setText("access-rate-limit", formatRateLimit(data.rate_limit_max, data.rate_limit_window_sec));
  setText("access-cooldowns", formatCooldowns(data.action_cooldowns));

  if (data.readonly) {
    setPill(accessPill, "READONLY");
  } else if (Array.isArray(data.actions_effective) && data.actions_effective.length > 0) {
    setPill(accessPill, "ACTIVE");
  } else {
    setPill(accessPill, "LOCKED");
  }

  const list = $("access-actions");
  if (!list) return;
  list.innerHTML = "";
  const items = Array.isArray(data.actions_effective) ? data.actions_effective : [];
  if (!items.length) {
    const li = document.createElement("li");
    li.textContent = i18n.t("emptyState.noActions");
    list.appendChild(li);
    return;
  }
  items.slice(0, 10).forEach((action) => {
    const li = document.createElement("li");
    li.textContent = localizeActionName(action);
    list.appendChild(li);
  });
}

function updateLastUpdated() {
  if (!lastUpdated) return;
  lastUpdated.textContent = uiState.lastUpdatedAt ? formatClockTime(uiState.lastUpdatedAt) : "--";
}

function syncOutputForLocale() {
  if (!outputPane || !outputPill) return;
  if (outputPill.classList.contains("pill--warn") || outputPill.classList.contains("pill--fail")) {
    return;
  }

  const getCatalogValue = (locale, key) => {
    const catalog = i18n.getMessages(locale);
    if (!catalog || typeof catalog !== "object") return "";
    return key.split(".").reduce((current, segment) => {
      if (!current || typeof current !== "object") return undefined;
      return current[segment];
    }, catalog);
  };

  const isKnownLocalizedEmptyValue = (text) => {
    if (!text) return false;
    const normalized = text.trim();
    return ["emptyState.noActionsYet", "common.noOutputYet"].some((key) =>
      i18n.SUPPORTED_LOCALES.some((locale) => getCatalogValue(locale, key) === normalized)
    );
  };

  const current = outputPane.textContent.trim();
  if (!current || isKnownLocalizedEmptyValue(current)) {
    setOutput(i18n.t("emptyState.noActionsYet"), "idle", { announce: false });
  } else {
    outputPill.textContent = i18n.translateDisplay("healthLevel", "idle");
  }
}

function computeBannerMessage(status, recentRuns, access) {
  if (!status) {
    return i18n.t("message.apiUnavailable");
  }

  const summary = recentRuns?.summary || {};
  if (access?.readonly) {
    return i18n.t("message.bannerReadonly");
  }
  if (summary.attention_state === "failure_cluster" && summary.top_failure_reason) {
    return i18n.t("message.bannerFailureCluster", {
      reason: localizeCanonicalText(summary.top_failure_reason),
    });
  }
  if (summary.attention_state === "recovery_watch") {
    return i18n.t("message.bannerRecoveryWatch");
  }
  if (status?.state_layers?.ledger?.status === "stale") {
    return i18n.t("message.bannerStale");
  }
  return "";
}

function syncToolPills() {
  const schedulePill = $("schedule-pill");
  const launchdState = uiState.status?.state_layers?.launchd?.status || uiState.status?.launchd || "";
  if (schedulePill) {
    const tone = launchdState === "not_loaded" ? "warn" : launchdState === "failed" ? "fail" : "";
    setSubPill(schedulePill, i18n.translateStateLayerStatus(launchdState || "unknown"), tone);
  }

  const vendorPill = $("vendor-pill");
  if (vendorPill) {
    const commitRequested = $("vendor-commit")?.checked;
    setSubPill(
      vendorPill,
      commitRequested ? i18n.translateDisplay("healthLevel", "ACTIVE") : i18n.t("pill.safe"),
      commitRequested ? "warn" : ""
    );
  }

  const logsPill = $("logs-pill");
  if (logsPill) {
    const logType = $("log-type")?.value || "stdout";
    setSubPill(logsPill, `${i18n.t("pill.tail")} · ${i18n.t(`options.logType.${logType}`)}`, "");
  }
}

function rerenderLocalizedView() {
  const activeLocale = i18n.getLocale() || "en";
  document.documentElement.lang = activeLocale;
  if (uiState.renderedLocale !== activeLocale) {
    i18n.applyTranslations(document);
    uiState.renderedLocale = activeLocale;
  }
  if (localeSwitcher) {
    localeSwitcher.value = activeLocale;
  }
  setConnection(uiState.connected);
  updateLastUpdated();

  if (uiState.status) {
    const data = uiState.status;
    setText("status-value", i18n.translateStatus(data.status || "unknown"));
    setText("exit-code", data.exit_code);
    setTextWithTitle("last-success", formatTimestamp(data.last_success_iso), data.last_success_iso);
    setTextWithTitle("last-run", formatTimestamp(data.last_run_iso), data.last_run_iso);
    setText("trigger-source", localizeTriggerSource(data.trigger_source));
    setText("run-id", data.run_id);
    setText("age-sec", formatAge(data.age_sec));
    setText("launchd-state", i18n.translateStateLayerStatus(data.launchd || "unknown"));
    setText("failure-reason", data.failure_reason ? localizeCanonicalText(data.failure_reason) : "--");
    setPill($("health-pill"), data.health_level || "--");
    renderHealthSummary(data.health_summary || "");
    renderStateLayers(data.state_layers || {});
    renderPhases(data.phases_bar || []);
    setText("health-score", data.health_score);
    setText("schema-version", `${data.schema_version || "--"} / ${data.schema_version_expected || "--"}`);
    setText("interval-min", data.interval_min ? formatMinutes(data.interval_min) : "--");
    renderOnboarding(data);

    const warning = $("schema-warning");
    if (warning) {
      if (data.schema_warning) {
        warning.textContent = localizeCanonicalText(data.schema_warning);
        warning.style.display = "block";
      } else {
        warning.style.display = "none";
      }
    }

    const reasons = $("health-reasons");
    if (reasons) {
      reasons.innerHTML = "";
      const items = Array.isArray(data.health_reasons) ? data.health_reasons : [];
      if (items.length === 0) {
        const li = document.createElement("li");
        li.textContent = i18n.t("emptyState.noIssues");
        reasons.appendChild(li);
      } else {
        items.slice(0, 6).forEach((reason) => {
          const li = document.createElement("li");
          li.textContent = i18n.translateHealthReason(reason) || reason;
          reasons.appendChild(li);
        });
      }
    }
  } else {
    setPill($("health-pill"), "WARN");
    renderHealthSummary("");
    const card = $("onboarding-card");
    if (card) card.hidden = true;
  }

  if (uiState.logHealth) {
    const data = uiState.logHealth;
    setPill($("log-health-pill"), data.health || "--");
    setText("log-errors-total", data.errors_total);
    setText("log-errors-stdout", data.errors_stdout);
    setText("log-errors-stderr", data.errors_stderr);
    setText("log-errors-launchd", data.errors_launchd_err);
    setText("log-pattern", data.pattern);
    setText("log-tail-lines", data.tail_lines);
    setText(
      "log-health-hint",
      data.last_status ? i18n.t("message.logHealthLastStatus", { status: i18n.translateStatus(data.last_status) }) : ""
    );
  } else {
    setPill($("log-health-pill"), "WARN");
  }

  if (uiState.doctor) {
    renderDoctor(uiState.doctor);
  } else {
    setPill($("doctor-pill"), "WARN");
  }

  const metricsPill = $("metrics-pill");
  if (metricsPill) {
    metricsPill.textContent = i18n.t("common.valueTail", { count: 120 });
  }
  renderMetricsTable(uiState.metrics);

  if (uiState.recentRuns) {
    renderRecentRuns(uiState.recentRuns);
  } else {
    renderRecentRuns({ summary: {} });
    setPill($("recent-runs-pill"), "WARN");
  }

  if (uiState.access) {
    renderAccess(uiState.access);
  } else {
    setPill(accessPill, "WARN");
  }

  syncOutputForLocale();
  syncToolPills();
  setBanner(computeBannerMessage(uiState.status, uiState.recentRuns, uiState.access));
}

function setOutput(message, level, options = {}) {
  if (outputPane) {
    outputPane.textContent = message || i18n.t("common.noOutputYet");
  }
  if (options.announce !== false) {
    announceStatus(message || "");
  }
  if (outputPill) {
    outputPill.classList.remove("pill--warn", "pill--fail");
    if (level === "warn") {
      outputPill.classList.add("pill--warn");
      outputPill.textContent = i18n.translateDisplay("healthLevel", "WARN");
    } else if (level === "fail") {
      outputPill.classList.add("pill--fail");
      outputPill.textContent = i18n.translateDisplay("healthLevel", "FAIL");
    } else if (level === "ok") {
      outputPill.textContent = i18n.translateDisplay("healthLevel", "OK");
    } else {
      outputPill.textContent = i18n.translateDisplay("healthLevel", "idle");
    }
  }
}

function setBusy(isBusy) {
  document.querySelectorAll("button").forEach((btn) => {
    if (btn.id === "refresh") return;
    btn.disabled = isBusy;
  });
  setPill(actionsPill, isBusy ? "running" : "ready");
}

async function runAction(action, payload) {
  setBusy(true);
  setOutput(i18n.t("message.runningAction", { action: localizeActionName(action) }), "warn");
  const result = await postJson(`/api/${action}`, payload, 180000);
  if (result.ok) {
    const lines = [];
    if (result.message) lines.push(result.message);
    if (result.stdout) lines.push(result.stdout);
    if (result.stderr) lines.push(result.stderr);
    if (result.data) lines.push(JSON.stringify(result.data, null, 2));
    if (result.lines) lines.push(result.lines.join("\n"));
    if (result.file) lines.push(i18n.t("message.actionFileLabel", { path: result.file }));
    setOutput(lines.filter(Boolean).join("\n\n") || i18n.t("message.outputOk"), "ok");
  } else {
    const detail = result.error ? JSON.stringify(result.error, null, 2) : i18n.t("message.unknownError");
    setOutput(i18n.t("message.actionFailed", { detail }), "fail");
  }
  setBusy(false);
  refreshAll();
}

function bindActions() {
  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.getAttribute("data-action");
      if (!action) return;

      if (action === "install") {
        const minutes = Number($("install-minutes").value || 0);
        const interval = Number($("install-interval").value || 0);
        const load = $("install-load").checked;
        const web = $("install-web").checked;
        runAction("install", { minutes, interval_sec: interval, load, web });
        return;
      }
      if (action === "ensure") {
        runAction("ensure", {});
        return;
      }
      if (action === "unload") {
        runAction("install", { unload: true, web: $("install-web").checked });
        return;
      }
      if (action === "update-vendor") {
        const ref = $("vendor-ref").value.trim();
        const dryRun = $("vendor-dry-run").checked;
        const commit = $("vendor-commit").checked;
        runAction("update-vendor", { ref, dry_run: dryRun, commit });
        return;
      }
      if (action === "rotate-logs") {
        const scope = $("rotate-scope")?.value || "all";
        runAction("rotate-logs", { scope });
        return;
      }
      if (action === "permissions") {
        runAction("permissions", {});
        return;
      }
      if (action === "setup") {
        runAction("setup", {});
        return;
      }
      if (action === "logs") {
        const logType = $("log-type").value;
        const tail = Number($("log-tail").value || 200);
        const since = Number($("log-since").value || 0);
        runAction("logs", { type: logType, tail, since_min: since });
        return;
      }

      runAction(action, {});
    });
  });
}

async function refreshAll() {
  refreshButton.disabled = true;
  const logTail = Number($("log-health-tail")?.value || 200);
  const logHealthUrl = `/api/log-health?tail=${Number.isFinite(logTail) ? logTail : 200}`;
  const [statusPayload, logPayload, doctorPayload, metricsPayload, recentRunsPayload, accessPayload] = await Promise.all([
    fetchJson(endpoints.status),
    fetchJson(logHealthUrl),
    fetchJson(endpoints.doctor),
    fetchJson(endpoints.metrics),
    fetchJson(endpoints.recentRuns),
    fetchJson(endpoints.access),
  ]);

  uiState.status = statusPayload?.ok && statusPayload.data ? statusPayload.data : null;
  uiState.logHealth = logPayload?.ok && logPayload.data ? logPayload.data : null;
  uiState.doctor = doctorPayload?.ok && doctorPayload.data ? doctorPayload.data : null;
  uiState.metrics = metricsPayload?.ok ? metricsPayload.entries || [] : [];
  uiState.recentRuns = recentRunsPayload?.ok && recentRunsPayload.data ? recentRunsPayload.data : null;
  uiState.access = accessPayload?.ok ? accessPayload : null;

  const hasAny = !!uiState.status;
  setConnection(hasAny);
  uiState.bannerKey = "";

  uiState.lastUpdatedAt = new Date();
  rerenderLocalizedView();
  refreshButton.disabled = false;
}

i18n.subscribe(() => {
  uiState.renderedLocale = null;
  rerenderLocalizedView();
});

if (localeSwitcher) {
  localeSwitcher.value = i18n.getLocale();
  localeSwitcher.addEventListener("change", (event) => {
    i18n.setLocale(event.target.value);
  });
}

refreshButton?.addEventListener("click", refreshAll);
metricsFilterInput?.addEventListener("input", () => {
  renderMetricsTable(uiState.metrics);
});
$("vendor-commit")?.addEventListener("change", syncToolPills);
$("log-type")?.addEventListener("change", syncToolPills);

bindActions();
document.documentElement.lang = i18n.getLocale() || "en";
i18n.applyTranslations(document);
setBusy(false);
setOutput(i18n.t("emptyState.noActionsYet"), "idle", { announce: false });
syncToolPills();
refreshAll();
setInterval(refreshAll, 30000);
