// 网球时差 · 流水线看板。数据只来自同目录的 snapshot.json（tools/build_dashboard_snapshot.py）。
// 规矩（判据在 tests/test_dashboard_snapshot.py）：
// - 没有链接就渲 <div>，不写空锚点
// - 刷新失败不抹掉上一次的状态：保留、标「已过期」、给重试
// - 平台已接收 ≠ 手机送达，两句话钉死
const $ = (id) => document.getElementById(id);
const TYPE_LABELS = { reel: "赛场之上", interview: "赛后开麦", explainer: "网球有故事" };
// 和首屏「流程状态」同一套词（build_dashboard_snapshot.STAGE_FIELDS）
const STAGES = [["discovered", "发现"], ["orchestrated", "编排"], ["spec", "Spec"],
  ["rendered", "渲染"], ["qc", "质检"], ["pushed", "推送"]];
const STAGE_LABEL = Object.fromEntries(STAGES);
const HERO_CHIP = {
  failed: ["destructive", "✕ 阻塞"], running: ["info", "运行中"],
  healthy: ["success", "正常"], warning: ["warning", "状态未知"], error: ["warning", "读取失败"],
};
const RUN_TONE = { failure: "destructive", running: "info", success: "success", warning: "warning" };
const REFRESH_MS = 5 * 60 * 1000;
let snapshot = null;
let activeType = "all";
let loading = false;

const esc = (value = "") => String(value).replace(/[&<>'"]/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
const safeUrl = (url) => (typeof url === "string" && /^https?:\/\//.test(url) ? url : "");
const relative = (iso) => {
  if (!iso) return "时间未知";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "刚刚";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  return `${Math.floor(seconds / 86400)} 天前`;
};
const clock = (iso) => new Date(iso).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });

// 有链接才是 <a>；没有就是 <div>——不渲染指向本页的空锚点
function linkOrDiv(url, cls, inner, attrs = "") {
  const href = safeUrl(url);
  return href
    ? `<a class="${cls}" href="${esc(href)}" target="_blank" rel="noreferrer" ${attrs}>${inner}</a>`
    : `<div class="${cls}" ${attrs}>${inner}</div>`;
}

function chip(tone, label, withDot = false) {
  const dot = withDot ? `<span class="dot" data-status="${tone === "info" ? "running" : ""}"></span>` : "";
  return `<span class="chip chip-${tone}">${dot}${esc(label)}</span>`;
}

function renderHero(data) {
  const h = data.health;
  const hero = $("hero");
  hero.dataset.status = h.status;
  hero.removeAttribute("aria-busy");
  const [tone, label] = HERO_CHIP[h.status] || HERO_CHIP.warning;
  const blocked = h.blocked || [];
  const list = blocked.length ? `<ul class="fail-list">${blocked.map((b) => `<li>${linkOrDiv(b.url, "fail-item",
    `<span class="fail-stage">${esc((b.stages || []).join(" · ") || b.workflow)}</span>`
    + `<span class="fail-what"><span class="fail-wf">${esc(b.mode ? `${b.workflow}（${b.mode}）` : b.workflow)}</span>`
    + `<span class="fail-slug">${esc(b.slug || "run 标题里没写是哪条")}</span></span>`
    + `<span class="fail-time">${relative(b.at)}</span>`)}</li>`).join("")}</ul>` : "";
  const action = safeUrl(h.action_url)
    ? `<div class="hero-actions"><a class="btn btn-primary" href="${esc(h.action_url)}" target="_blank" rel="noreferrer">打开失败的 run ↗</a></div>`
    : "";
  hero.innerHTML = `<div class="hero-head">${chip(tone, label, h.status !== "failed")}`
    + `<span class="stamp">${relative(data.generated_at)}</span></div>`
    + `<h2>${esc(h.title)}</h2><p class="hero-msg">${esc(h.message)}</p>${list}${action}`;
}

function renderMetrics(data) {
  const s = data ? data.summary : null;
  const none = "—";
  const items = [
    ["运行中", s ? s.active : none, "当前 Actions 任务"],
    ["24h 平台接收", s ? s.accepted_24h : none, "不等于手机送达"],
    ["待处理", s ? s.pending : none, "dispatch / render 队列"],
    // 没有成片样本就是「不知道」，不是 0%
    ["10 分钟达标率", s && s.sla_rate != null ? `${s.sla_rate}%` : none,
      s && s.sla_total ? `${s.sla_met}/${s.sla_total} 条成片` : "暂无成片数据"],
  ];
  $("metrics").innerHTML = items.map(([label, value, hint]) => `<article class="metric">`
    + `<div class="metric-label">${label}</div>`
    + `<div class="metric-value${value === none ? " is-empty" : ""}">${esc(value)}</div>`
    + `<div class="metric-hint">${hint}</div></article>`).join("");
}

function renderStages(data) {
  $("stages").innerHTML = data.stages.map((s) => {
    const detail = s.slug ? `${s.detail} · ${s.slug}` : s.detail;
    const inner = `<span class="dot" data-status="${esc(s.status)}"></span>`
      + `<span class="stage-name">${esc(s.label)}</span>`
      + `<span class="stage-detail">${esc(detail)}</span>`
      + `<span class="stage-time">${s.updated_at ? relative(s.updated_at) : "—"}</span>`;
    return linkOrDiv(s.url, "stage", inner, `data-status="${esc(s.status)}"`);
  }).join("");
}

// 一颗芯片说清「走到哪一步、下一步是什么」，和首屏阶段同一套词
function progress(x) {
  if (x.failed_stage) {
    return `<span class="progress is-failed">${esc(STAGE_LABEL[x.failed_stage] || x.failed_stage)} ✕</span>`;
  }
  if (x.pushed) return "";
  let last = -1;
  STAGES.forEach(([key], i) => { if (x[key]) last = i; });
  const done = last >= 0 ? `${STAGES[last][1]} ✓ · ` : "";
  return `<span class="progress">${done}下一步 ${STAGES[last + 1][1]}</span>`;
}

function contentState(x) {
  if (x.failed_stage) return ["destructive", `${STAGE_LABEL[x.failed_stage] || x.failed_stage}失败`];
  if (x.pushed) {
    const confirmed = x.delivery_status === "confirmed" || x.delivery_status === "delivered";
    return ["success", confirmed ? "送达已确认" : "平台已接收"];
  }
  if (x.rendered) return ["warning", "待推送"];
  return ["info", "处理中"];
}

function renderContent(data) {
  const rows = data.content.filter((x) => activeType === "all" || x.type === activeType).slice(0, 16);
  if (!rows.length) { $("content-list").innerHTML = '<div class="empty">暂无可展示记录</div>'; return; }
  $("content-list").innerHTML = rows.map((x) => {
    const [tone, label] = contentState(x);
    const meta = [TYPE_LABELS[x.type] || x.type, relative(x.updated_at), x.title ? x.slug : ""]
      .filter(Boolean).map(esc).join(" · ");
    const inner = `<div class="row-main"><div class="row-title">${esc(x.title || x.slug)}</div>`
      + `<div class="row-meta">${meta}</div>${progress(x)}</div>${chip(tone, label)}`;
    return linkOrDiv(x.url, "row", inner);
  }).join("");
}

function renderWorkflows(data) {
  const rows = data.workflows.slice(0, 12);
  $("workflows").innerHTML = rows.map((w) => linkOrDiv(w.url, "row",
    `<div class="row-main"><div class="row-title">${esc(w.label)}</div>`
    + `<div class="row-meta">${esc([w.detail, relative(w.updated_at)].filter(Boolean).join(" · "))}</div></div>`
    + chip(RUN_TONE[w.status] || "neutral", w.status_label))).join("")
    || '<div class="empty">暂无任务记录</div>';
}

// ── 分段控件 ─────────────────────────────────────────────
function placeIndicator(animate = true) {
  const box = $("filters");
  const ind = box.querySelector(".segmented-indicator");
  const btn = box.querySelector('button[aria-pressed="true"]');
  if (!ind || !btn) return;
  if (!animate) ind.classList.add("no-anim");
  ind.style.width = `${btn.offsetWidth}px`;
  ind.style.transform = `translateX(${btn.offsetLeft}px)`;
  if (!animate) { void ind.offsetWidth; ind.classList.remove("no-anim"); }
}

function setupFilters() {
  const buttons = $("filters").querySelectorAll("button");
  buttons.forEach((btn) => btn.addEventListener("click", () => {
    activeType = btn.dataset.type;
    // 只改 aria-pressed，不重建按钮——键盘焦点留在刚按的那一个上
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
    placeIndicator(true);
    if (snapshot) renderContent(snapshot);
  }));
  window.addEventListener("resize", () => placeIndicator(false));
  placeIndicator(false);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => placeIndicator(false));
}

// ── 读取、过期、失败 ─────────────────────────────────────
function render(data) {
  renderHero(data); renderMetrics(data); renderStages(data); renderContent(data); renderWorkflows(data);
}

function markFresh(data) {
  $("stale").hidden = true;
  const f = $("freshness");
  f.classList.remove("is-stale");
  f.textContent = `数据更新于 ${clock(data.generated_at)}`;
}

// 刷新失败：上一次的状态（尤其是「阻塞」）原样留着，只标过期。
// ⚠️ 要按缓存的快照重渲一遍：「刚刚」「3 分钟前」是渲染那一刻算的，不重渲就冻在那儿，
// 和顶上「已过期 · 快照 08:43」互相矛盾（复核截图 refreshfail_m390）。
function markStale(error) {
  render(snapshot);
  $("stale-text").textContent = `刷新失败（${error.message}），下面是 ${clock(snapshot.generated_at)} 的快照，可能已过期`;
  $("stale").hidden = false;
  const f = $("freshness");
  f.classList.add("is-stale");
  f.textContent = `已过期 · 快照 ${clock(snapshot.generated_at)}`;
}

function renderError(error) {
  const hero = $("hero");
  hero.dataset.status = "error";
  hero.removeAttribute("aria-busy");
  const [tone, label] = HERO_CHIP.error;
  hero.innerHTML = `<div class="hero-head">${chip(tone, label)}</div><h2>状态快照暂时不可用</h2>`
    + `<p class="hero-msg">${esc(error.message)}。Pages 可能正在部署，稍后再试。</p>`
    + '<div class="hero-actions"><button class="btn btn-secondary" type="button" data-retry>重试</button></div>';
  renderMetrics(null);
  $("stages").innerHTML = '<div class="empty">暂无数据</div>';
  $("content-list").innerHTML = '<div class="empty">暂无数据</div>';
  $("workflows").innerHTML = "";
  const f = $("freshness");
  f.classList.add("is-stale");
  f.textContent = "未取到快照";
}

async function load() {
  if (loading) return;
  loading = true;
  const btn = $("refresh");
  btn.classList.add("is-loading");
  btn.setAttribute("aria-busy", "true");
  try {
    const response = await fetch(`./snapshot.json?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    snapshot = data;
    render(data);
    markFresh(data);
  } catch (error) {
    if (snapshot) markStale(error); else renderError(error);
  } finally {
    loading = false;
    btn.classList.remove("is-loading");
    btn.removeAttribute("aria-busy");
  }
}

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-retry]")) load();
});
$("refresh").addEventListener("click", load);
setupFilters();
load();
setInterval(load, REFRESH_MS);
