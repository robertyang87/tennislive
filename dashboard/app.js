const $ = (id) => document.getElementById(id);
const TYPE_LABELS = { reel: "赛场之上", interview: "赛后开麦", explainer: "网球有故事" };
const STAGE_LABELS = { discovered:"发现", orchestrated:"编排", spec:"Spec", rendered:"渲染", qc:"质检", pushed:"平台接收" };
let snapshot = null;
let activeType = "all";

const escapeHtml = (value="") => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const relative = (iso) => {
  if (!iso) return "时间未知";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "刚刚";
  if (seconds < 3600) return `${Math.floor(seconds/60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds/3600)} 小时前`;
  return `${Math.floor(seconds/86400)} 天前`;
};

function renderHero(data) {
  const h = data.health;
  $("hero").classList.remove("skeleton");
  $("hero").innerHTML = `<div class="hero-row"><div><div class="status-orb ${h.status}"></div><h2>${escapeHtml(h.title)}</h2><p>${escapeHtml(h.message)}</p></div><span class="stamp">${relative(data.generated_at)}</span></div>`;
  $("freshness").textContent = `数据更新于 ${new Date(data.generated_at).toLocaleTimeString("zh-CN",{hour:"2-digit",minute:"2-digit"})}`;
}

function renderMetrics(data) {
  const items = [
    ["运行中", data.summary.active, "当前 Actions 任务"],
    ["24h 平台接收", data.summary.accepted_24h, "不等于手机送达"],
    ["待处理", data.summary.pending, "dispatch / render 队列"],
    ["10 分钟达标率", `${data.summary.sla_rate}%`, `${data.summary.sla_met}/${data.summary.sla_total} 条成片`]
  ];
  $("metrics").innerHTML = items.map(([label,value,hint]) => `<article class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-hint">${hint}</div></article>`).join("");
}

function renderStages(data) {
  $("stages").innerHTML = data.stages.map(s => `<a class="stage" href="${escapeHtml(s.url || '#')}" ${s.url?'target="_blank" rel="noreferrer"':''}><div class="stage-top"><span class="stage-name">${escapeHtml(s.label)}</span><span class="dot ${s.status}"></span></div><div class="stage-meta">${escapeHtml(s.detail)}<br>${relative(s.updated_at)}</div></a>`).join("");
}

function renderFilters(data) {
  const choices = [["all","全部"],["reel","赛场之上"],["interview","赛后开麦"],["explainer","网球有故事"]];
  $("filters").innerHTML = choices.map(([key,label]) => `<button class="filter ${activeType===key?'active':''}" data-type="${key}">${label}</button>`).join("");
  $("filters").querySelectorAll("button").forEach(btn => btn.addEventListener("click", () => { activeType=btn.dataset.type; renderFilters(data); renderContent(data); }));
}

function renderContent(data) {
  const rows = data.content.filter(x => activeType === "all" || x.type === activeType).slice(0, 16);
  if (!rows.length) { $("content-list").innerHTML = '<div class="empty">暂无可展示记录</div>'; return; }
  const order = ["discovered","orchestrated","spec","rendered","qc","pushed"];
  $("content-list").innerHTML = rows.map(x => {
    const state = x.failed_stage ? "failure" : x.pushed ? "sent" : x.rendered ? "rendered" : "running";
    const label = x.failed_stage ? `${STAGE_LABELS[x.failed_stage]||x.failed_stage}失败` : x.pushed ? (x.delivery_status === "confirmed" || x.delivery_status === "delivered" ? "送达已确认" : "平台已接收") : x.rendered ? "待推送" : "处理中";
    const bars = order.map(k => `<span class="${x.failed_stage===k?'fail':x[k]?'done':''}" title="${STAGE_LABELS[k]}"></span>`).join("");
    return `<a class="content-card" href="${escapeHtml(x.url||'#')}" ${x.url?'target="_blank" rel="noreferrer"':''}><div><div class="content-title">${escapeHtml(x.slug)}</div><div class="content-meta">${TYPE_LABELS[x.type]||x.type} · ${relative(x.updated_at)}</div><div class="pipeline-mini">${bars}</div></div><span class="badge ${state}">${label}</span></a>`;
  }).join("");
}

function renderWorkflows(data) {
  const rows = data.workflows.slice(0, 12);
  $("workflows").innerHTML = rows.map(w => `<a class="workflow" href="${escapeHtml(w.url)}" target="_blank" rel="noreferrer"><div><div class="workflow-title">${escapeHtml(w.label)}</div><div class="workflow-meta">${escapeHtml(w.detail)} · ${relative(w.updated_at)}</div></div><span class="badge ${w.status}">${w.status_label}</span></a>`).join("") || '<div class="empty">暂无任务记录</div>';
}

async function load() {
  $("refresh").disabled = true; $("refresh").textContent = "刷新中";
  try {
    const response = await fetch(`./snapshot.json?t=${Date.now()}`, {cache:"no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    snapshot = await response.json();
    renderHero(snapshot); renderMetrics(snapshot); renderStages(snapshot); renderFilters(snapshot); renderContent(snapshot); renderWorkflows(snapshot);
  } catch (error) {
    $("hero").innerHTML = `<div class="error-box">状态快照暂时不可用：${escapeHtml(error.message)}。请稍后刷新。</div>`;
  } finally { $("refresh").disabled = false; $("refresh").textContent = "刷新"; }
}

$("refresh").addEventListener("click", load);
load();
setInterval(load, 5 * 60 * 1000);
