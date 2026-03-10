/* ═══════════════════════════════════════════════════════════════
   app.js — RecruitAI main application logic
   Handles: tabs, file upload/remove, analysis, certificates,
            dashboard, toasts, confetti, CSV export
   ═══════════════════════════════════════════════════════════════ */

/* ─── STATE ─── */
let selectedFiles = [];      // Array of File objects for resume upload
let lastResults   = [];      // Last batch analysis results
let allResults    = [];      // Cumulative results across all analyses
let totalResumes  = 0;
let totalCerts    = 0;

let pipelinePollers = {};    // phone -> intervalId for pipeline polling
let shortlistedCandidates = []; // Shortlisted candidate names

/* ═══════════════════════════════════════════
   TOAST SYSTEM
   ═══════════════════════════════════════════ */
function showToast(message, type = 'success') {
  const box = document.getElementById('toastBox');
  const icons = { success: 'check-circle', error: 'exclamation-circle', info: 'info-circle' };
  const id = 't_' + Date.now();
  const el = document.createElement('div');
  el.id = id;
  el.className = 'toast toast-' + type;
  el.innerHTML = `<i class="fas fa-${icons[type] || icons.info}"></i><span>${message}</span><button onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>`;
  box.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 3500);
}

/* ═══════════════════════════════════════════
   TAB NAVIGATION
   ═══════════════════════════════════════════ */
document.querySelectorAll('.nav-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('pane-' + tab.dataset.tab).classList.add('active');
    // Load dashboard data when switching to dash tab
    if (tab.dataset.tab === 'dash') loadDashboard();
    // Load shortlist when switching to shortlist tab
    if (tab.dataset.tab === 'shortlist') renderShortlist();
  });
});

/* Mobile burger */
const burger = document.getElementById('navBurger');
if (burger) {
  burger.addEventListener('click', () => {
    document.getElementById('navTabs').classList.toggle('open');
  });
}

/* ═══════════════════════════════════════════
   LOGOUT
   ═══════════════════════════════════════════ */
async function doLogout() {
  try {
    await fetch('/logout', { method: 'POST' });
  } catch (e) { /* ignore */ }
  window.location.href = '/auth';
}

/* ═══════════════════════════════════════════
   JOB DESCRIPTION
   ═══════════════════════════════════════════ */
const jdEl = document.getElementById('jobDesc');
const jdCount = document.getElementById('jdCount');
if (jdEl) {
  jdEl.addEventListener('input', () => {
    jdCount.textContent = jdEl.value.length + ' characters';
    updateAnalyzeBtn();
  });
}

function appendSkill(skill) {
  if (!jdEl) return;
  const sep = jdEl.value.trim() ? ', ' : '';
  jdEl.value += sep + skill;
  jdEl.dispatchEvent(new Event('input'));
  showToast(skill + ' added', 'info');
}

/* ═══════════════════════════════════════════
   FILE UPLOAD + REMOVE (Resume Tab)
   Uses a JS array (selectedFiles) instead of
   relying on the native FileList, enabling
   individual file removal.
   ═══════════════════════════════════════════ */
const dropZone  = document.getElementById('dropZone');
const fileInput  = document.getElementById('fileInput');
const chipsEl    = document.getElementById('fileChips');
const badgeEl    = document.getElementById('fileBadge');
const clearBtn   = document.getElementById('btnClearAll');

if (dropZone) {
  dropZone.addEventListener('click', (e) => {
    // Only trigger file picker if clicking the zone itself, not the native input
    if (e.target !== fileInput) fileInput.click();
  });
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener('change', () => { addFiles(fileInput.files); fileInput.value = ''; });
}

function addFiles(fileList) {
  for (const f of fileList) {
    if (f.type !== 'application/pdf') {
      showToast(f.name + ' is not a PDF — skipped', 'error');
      if (dropZone) { dropZone.classList.add('shake'); setTimeout(() => dropZone.classList.remove('shake'), 500); }
      continue;
    }
    if (selectedFiles.length >= 10) { showToast('Maximum 10 files allowed', 'error'); break; }
    // Prevent duplicates by name
    if (!selectedFiles.some(sf => sf.name === f.name && sf.size === f.size)) {
      selectedFiles.push(f);
    }
  }
  renderChips();
}

function removeFile(idx) {
  selectedFiles.splice(idx, 1);
  renderChips();
  showToast('File removed', 'info');
}

function clearAllFiles() {
  selectedFiles = [];
  renderChips();
  showToast('All files cleared', 'info');
}

function renderChips() {
  if (!chipsEl) return;
  if (!selectedFiles.length) {
    chipsEl.innerHTML = '';
    badgeEl.style.display = 'none';
    clearBtn.style.display = 'none';
    updateAnalyzeBtn();
    return;
  }
  let html = '';
  selectedFiles.forEach((f, i) => {
    const size = (f.size / 1024).toFixed(0);
    html += `<div class="file-chip">
      <i class="fas fa-file-pdf"></i>
      <span class="fc-name" title="${f.name}">${truncate(f.name, 28)}</span>
      <span class="fc-size">${size} KB</span>
      <button class="fc-remove" onclick="removeFile(${i})" title="Remove file"><i class="fas fa-times"></i></button>
    </div>`;
  });
  chipsEl.innerHTML = html;
  badgeEl.textContent = selectedFiles.length + ' PDF' + (selectedFiles.length > 1 ? 's' : '');
  badgeEl.style.display = 'inline-flex';
  clearBtn.style.display = selectedFiles.length >= 2 ? 'inline-flex' : 'none';
  updateAnalyzeBtn();
}

function truncate(s, n) { return s.length > n ? s.slice(0, n - 3) + '…' : s; }

function updateAnalyzeBtn() {
  const btn = document.getElementById('btnAnalyze');
  if (btn) btn.disabled = !(selectedFiles.length > 0 && jdEl && jdEl.value.trim().length > 0);
}

/* ═══════════════════════════════════════════
   ANALYZE RESUMES
   ═══════════════════════════════════════════ */
async function analyzeResumes() {
  const btn   = document.getElementById('btnAnalyze');
  const label = btn.querySelector('.btn-label');
  const load  = btn.querySelector('.btn-loading');

  btn.disabled = true;
  label.style.display = 'none';
  load.style.display  = 'inline-flex';

  const fd = new FormData();
  fd.append('job_description', jdEl.value);
  selectedFiles.forEach(f => fd.append('resumes', f));

  try {
    const res  = await fetch('/upload-resume', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { showToast(data.error, 'error'); return; }

    lastResults = data.results;
    allResults = data.all_results || allResults.concat(data.results);
    totalResumes = allResults.length;
    renderResultCards(lastResults);
    document.getElementById('resultsArea').style.display = 'block';
    document.getElementById('waRequestCard').style.display = 'block';

    // Show automated WhatsApp pipeline status
    renderAutoWaStatus(data.results, data.auto_whatsapp || []);

    showToast(`Ranked ${lastResults.length} resume(s) successfully! (${allResults.length} total)`);

    // Confetti for top result
    if (lastResults.length > 0) launchConfetti();
  } catch (err) {
    showToast('Server error: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    label.style.display = 'inline-flex';
    load.style.display  = 'none';
  }
}

function reAnalyze() {
  document.getElementById('resultsArea').style.display = 'none';
  analyzeResumes();
}

/* ═══════════════════════════════════════════
   RENDER RESULT CARDS
   ═══════════════════════════════════════════ */
function renderResultCards(results) {
  const grid = document.getElementById('resultsGrid');
  grid.innerHTML = '';
  results.forEach((r, i) => {
    const pct  = r.score;
    const circumference = 2 * Math.PI * 38;
    const offset = circumference - (pct / 100) * circumference;
    const color = pct >= 70 ? '#00d4aa' : pct >= 40 ? '#f5a623' : '#ff4d4d';
    const label = pct >= 70 ? 'Excellent' : pct >= 40 ? 'Good' : pct >= 20 ? 'Average' : 'Poor';
    const labelCls = pct >= 70 ? 'lbl-green' : pct >= 40 ? 'lbl-amber' : 'lbl-red';
    const isTop = r.rank === 1;

    const card = document.createElement('div');
    card.className = 'result-card' + (isTop ? ' top-card' : '');
    card.style.animationDelay = (i * 0.08) + 's';
    card.innerHTML = `
      <div class="rc-rank">${r.rank}</div>
      <div class="rc-info">
        <h4 class="rc-name">${r.filename}</h4>
        <span class="rc-label ${labelCls}">${label} Match</span>
        ${isTop ? '<span class="rc-badge">⭐ Top Match</span>' : ''}
      </div>
      <div class="rc-ring">
        <svg viewBox="0 0 88 88">
          <circle cx="44" cy="44" r="38" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="6"/>
          <circle cx="44" cy="44" r="38" fill="none" stroke="${color}" stroke-width="6"
            stroke-dasharray="${circumference}" stroke-dashoffset="${circumference}"
            stroke-linecap="round" transform="rotate(-90 44 44)" class="ring-progress"
            style="--target:${offset}"/>
        </svg>
        <span class="rc-pct">${pct}%</span>
      </div>`;
    grid.appendChild(card);
  });
  // Trigger ring animation after render
  requestAnimationFrame(() => {
    document.querySelectorAll('.ring-progress').forEach(c => {
      c.style.strokeDashoffset = c.style.getPropertyValue('--target');
    });
  });
}

/* ═══════════════════════════════════════════
   BLOCKCHAIN STATUS (checked on load)
   ═══════════════════════════════════════════ */
async function checkBlockchain() {
  try {
    const res  = await fetch('/blockchain-status');
    const data = await res.json();
    return data.connected;
  } catch { return false; }
}
checkBlockchain();

/* ═══════════════════════════════════════════
   DASHBOARD
   ═══════════════════════════════════════════ */
async function loadDashboard() {
  try {
    const res  = await fetch('/dashboard-data');
    const data = await res.json();
    if (data.results && data.results.length) {
      allResults   = data.results;
      totalResumes = data.total_resumes || allResults.length;
      totalCerts   = data.total_certs || 0;
    }
  } catch { /* use local state */ }
  renderDashboard();
}

function renderDashboard() {
  // Stats with count-up
  animateCounter('dStatResumes', totalResumes);
  animateCounter('dStatCerts', totalCerts);
  const topScore = allResults.length ? allResults[0].score : 0;
  if (allResults.length) {
    const el = document.getElementById('dStatTop');
    el.textContent = topScore + '%';
  }
  const pending = allResults.length ? Math.max(0, allResults.length - totalCerts) : 0;
  animateCounter('dStatPending', pending);

  // Sparklines
  renderSparkline('spark1', generateSparkData(totalResumes));
  renderSparkline('spark2', generateSparkData(topScore));
  renderSparkline('spark3', generateSparkData(totalCerts));
  renderSparkline('spark4', generateSparkData(pending));

  // Table — show ALL cumulative results, not just last batch
  renderDashTable(allResults);
}

function animateCounter(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  let start = 0;
  const dur = 1200;
  const step = target / (dur / 16);
  if (target === 0) { el.textContent = '0'; return; }
  const timer = setInterval(() => {
    start += step;
    if (start >= target) { start = target; clearInterval(timer); }
    el.textContent = Math.round(start);
  }, 16);
}

function renderSparkline(id, data) {
  const el = document.getElementById(id);
  if (!el) return;
  const max = Math.max(...data, 1);
  const points = data.map((v, i) => `${(i / (data.length - 1)) * 100},${100 - (v / max) * 80}`).join(' ');
  el.innerHTML = `<svg viewBox="0 0 100 100" preserveAspectRatio="none"><polyline fill="none" stroke="rgba(0,212,170,.5)" stroke-width="2" points="${points}"/></svg>`;
}

function generateSparkData(seed) {
  const arr = [];
  for (let i = 0; i < 8; i++) arr.push(Math.max(0, seed * (0.3 + Math.random() * 0.7)));
  arr.push(seed);
  return arr;
}

let filteredResults = [];

function renderDashTable(results) {
  filteredResults = [...results];
  applyFilters();
}

function applyFilters() {
  const minScore = parseInt(document.getElementById('filterScore').value);
  document.getElementById('filterScoreVal').textContent = minScore + '%';
  const certFilter = document.getElementById('filterCert').value;

  let filtered = allResults.filter(r => r.score >= minScore);
  if (certFilter === 'verified') filtered = filtered.filter(r => r.cert_status === 'verified');
  if (certFilter === 'pending') filtered = filtered.filter(r => r.cert_status !== 'verified');

  // Sort: verified first, then descending by score, and re-rank
  filtered.sort((a, b) => {
    const aV = a.cert_status === 'verified' ? 0 : 1;
    const bV = b.cert_status === 'verified' ? 0 : 1;
    if (aV !== bV) return aV - bV;
    return b.score - a.score;
  });
  filtered.forEach((r, i) => r.rank = i + 1);

  const tbody = document.getElementById('dashBody');
  if (!filtered.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="7"><div class="empty-state"><i class="fas fa-inbox"></i><p>No matching results</p><span>Adjust your filters or analyze more resumes.</span></div></td></tr>';
    document.getElementById('selectAllCandidates').checked = false;
    updateShortlistBar();
    return;
  }
  let html = '';
  filtered.forEach((r, i) => {
    const pct = r.score;
    const color = pct >= 70 ? '#00d4aa' : pct >= 40 ? '#f5a623' : '#ff4d4d';
    const barW = Math.max(pct, 4);
    const trust = r.trust_score;
    let trustHtml;
    if (trust != null) {
      const tc = trust >= 70 ? 'trust-high' : trust >= 40 ? 'trust-med' : 'trust-low';
      trustHtml = `<span class="trust-badge ${tc}">${trust}%</span>`;
    } else {
      trustHtml = '<span class="trust-badge trust-na">N/A</span>';
    }
    const isShortlisted = shortlistedCandidates.includes(r.filename);
    const realName = r.candidate_name || r.filename;
    html += `<tr style="animation-delay:${i * 0.04}s">
      <td style="text-align:center"><input type="checkbox" class="candidate-cb" data-name="${r.filename}" data-realname="${realName}" data-phone="${r.phone || ''}" data-score="${pct}" onchange="updateShortlistBar()"${isShortlisted ? ' checked disabled title="Already shortlisted"' : ''}/></td>
      <td><span class="rank-num">#${r.rank}</span></td>
      <td class="td-name">${r.filename}${isShortlisted ? ' <i class="fas fa-star" style="color:var(--amber);font-size:.7rem" title="Shortlisted"></i>' : ''}</td>
      <td>${pct}%</td>
      <td><div class="score-bar-bg"><div class="score-bar-fill" style="width:${barW}%;background:${color}"></div></div></td>
      <td>${r.cert_status === 'verified'
        ? '<span class="pill-badge pill-verified"><i class="fas fa-check-circle"></i> Verified</span>'
        : '<span class="pill-badge pill-pending"><i class="fas fa-hourglass-half"></i> Pending</span>'
      }</td>
      <td>${trustHtml}</td>
    </tr>`;
  });
  tbody.innerHTML = html;
  document.getElementById('selectAllCandidates').checked = false;
  updateShortlistBar();
}

/* ═══════════════════════════════════════════
   CSV EXPORT
   ═══════════════════════════════════════════ */
function exportCSV() {
  const data = allResults.length ? allResults : lastResults;
  if (!data.length) { showToast('No data to export', 'info'); return; }
  let csv = 'Rank,Candidate,Match Score (%),Certificate Status,Trust Score\n';
  data.forEach(r => csv += `${r.rank},"${r.filename}",${r.score},${r.cert_status || 'pending'},${r.trust_score != null ? r.trust_score : 'N/A'}\n`);
  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'recruitai_results.csv'; a.click();
  URL.revokeObjectURL(url);
  showToast('CSV downloaded!');
}

/* ═══════════════════════════════════════════
   WHATSAPP — AUTOMATED PIPELINE
   ═══════════════════════════════════════════ */

/**
 * After analysis, show which candidates were auto-contacted
 * and which need manual phone entry.
 */
function renderAutoWaStatus(results, autoWa) {
  const autoList    = document.getElementById('waAutoList');
  const manualSec   = document.getElementById('waManualSection');
  const manualList  = document.getElementById('waManualList');
  const summaryEl   = document.getElementById('waPipelineSummary');

  const contacted = results.filter(r => r.wa_status === 'sent');
  const noPhone   = results.filter(r => r.wa_status === 'no_phone');
  const failed    = results.filter(r => r.wa_status === 'failed');

  // Render auto-contacted candidates
  if (contacted.length) {
    autoList.innerHTML = contacted.map(r =>
      `<div class="file-chip" style="border-color:var(--accent)">
        <i class="fab fa-whatsapp" style="color:#25d366"></i>
        <span class="fc-name">${r.filename}</span>
        <span class="fc-size">${r.phone}</span>
      </div>`
    ).join('');
    // Start polling for all contacted candidates
    contacted.forEach(r => startPipelinePolling(r.phone, r.filename));
  } else {
    autoList.innerHTML = '<span style="color:var(--text2)">No candidates had phone numbers in their resume</span>';
  }

  // Show manual section for candidates without phone
  if (noPhone.length || failed.length) {
    manualSec.style.display = 'block';
    const all = [...noPhone, ...failed];
    manualList.innerHTML = all.map(r =>
      `<div class="file-chip" style="border-color:var(--amber)">
        <i class="fas fa-phone-slash" style="color:var(--amber)"></i>
        <span class="fc-name">${r.filename}</span>
        <span class="fc-size">${r.wa_status === 'failed' ? 'Send failed' : 'No phone found'}</span>
      </div>`
    ).join('');
    // Populate manual dropdown with only no-phone candidates
    const sel = document.getElementById('waCandidateSelect');
    if (sel) {
      sel.innerHTML = '<option value="">— Select —</option>';
      all.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.filename;
        opt.textContent = `${r.filename} (${r.score}%)`;
        sel.appendChild(opt);
      });
    }
  }

  // Summary
  summaryEl.innerHTML = `<i class="fas fa-paper-plane" style="color:var(--accent)"></i> ${contacted.length} contacted automatically` +
    (noPhone.length ? ` &middot; <span style="color:var(--amber)">${noPhone.length} need manual phone entry</span>` : '') +
    (failed.length ? ` &middot; <span style="color:var(--danger)">${failed.length} failed to send</span>` : '');
}

/**
 * Manual WhatsApp send for candidates without phone
 */
async function sendManualWhatsApp() {
  const candidate = document.getElementById('waCandidateSelect')?.value;
  const countryCode = document.getElementById('waCountryCode')?.value || '+91';
  const phone = document.getElementById('waPhoneInput')?.value?.trim();
  if (!candidate) { showToast('Select a candidate first', 'error'); return; }
  if (!phone || phone.length < 7) { showToast('Enter a valid phone number', 'error'); return; }
  const fullPhone = countryCode + phone;
  const btn = document.getElementById('btnSendWA');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';
  try {
    const res = await fetch('/send-whatsapp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_name: candidate, phone: fullPhone })
    });
    const data = await res.json();
    if (data.error) { showToast(data.error, 'error'); return; }
    showToast('WhatsApp message sent to ' + fullPhone);
    startPipelinePolling(fullPhone, candidate);
    // Update the manual chip to show "sent"
    const chips = document.querySelectorAll('#waManualList .file-chip');
    chips.forEach(c => {
      if (c.querySelector('.fc-name')?.textContent === candidate) {
        c.style.borderColor = 'var(--accent)';
        c.querySelector('i').className = 'fab fa-whatsapp';
        c.querySelector('i').style.color = '#25d366';
        c.querySelector('.fc-size').textContent = fullPhone;
      }
    });
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fab fa-whatsapp"></i> Send WhatsApp Request';
  }
}

/* ═══════════════════════════════════════════
   PIPELINE STATUS POLLING
   ═══════════════════════════════════════════ */
function startPipelinePolling(phone, candidateName) {
  if (pipelinePollers[phone]) clearInterval(pipelinePollers[phone]);
  pipelinePollers[phone] = setInterval(async () => {
    try {
      const res  = await fetch('/check-cert-status?phone=' + encodeURIComponent(phone));
      const data = await res.json();
      if (data.stage === 'complete' || data.stage === 'error') {
        clearInterval(pipelinePollers[phone]);
        delete pipelinePollers[phone];
        if (data.stage === 'complete') {
          showToast(`Certificate verified for ${candidateName || phone}!`);
          // Auto-refresh dashboard to reflect new ranking
          loadDashboard();
          updatePipelineSummary();
        } else {
          showToast('Pipeline issue for ' + (candidateName || phone) + ': ' + (data.message || ''), 'error');
        }
      }
    } catch { /* retry on next interval */ }
  }, 8000);
}

function updatePipelineSummary() {
  const summaryEl = document.getElementById('waPipelineSummary');
  if (!summaryEl) return;
  const activeCount = Object.keys(pipelinePollers).length;
  if (activeCount > 0) {
    summaryEl.innerHTML = `<i class="fas fa-spinner fa-spin" style="color:var(--accent)"></i> ${activeCount} candidate(s) still being processed...`;
  } else {
    summaryEl.innerHTML = `<i class="fas fa-check-circle" style="color:var(--accent)"></i> All pipelines complete! Check the Dashboard for updated rankings.`;
  }
}

/* ═══════════════════════════════════════════
   SHORTLIST FUNCTIONS
   ═══════════════════════════════════════════ */
function toggleSelectAll(masterCb) {
  const checkboxes = document.querySelectorAll('.candidate-cb:not(:disabled)');
  checkboxes.forEach(cb => cb.checked = masterCb.checked);
  updateShortlistBar();
}

function updateShortlistBar() {
  const checked = document.querySelectorAll('.candidate-cb:checked:not(:disabled)');
  const bar = document.getElementById('shortlistBar');
  const countEl = document.getElementById('shortlistCount');
  if (checked.length > 0) {
    bar.style.display = 'flex';
    countEl.textContent = checked.length + ' selected';
  } else {
    bar.style.display = 'none';
  }
}

async function shortlistSelected() {
  const checked = document.querySelectorAll('.candidate-cb:checked:not(:disabled)');
  if (!checked.length) { showToast('No candidates selected', 'info'); return; }
  const candidates = Array.from(checked).map(cb => ({
    filename: cb.dataset.name,
    realname: cb.dataset.realname || cb.dataset.name,
    phone: cb.dataset.phone || '',
    score: cb.dataset.score || ''
  }));
  const btn = document.querySelector('#shortlistBar .btn-primary');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Notifying...';
  try {
    const res = await fetch('/shortlist-notify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidates })
    });
    const data = await res.json();
    if (data.error) { showToast(data.error, 'error'); return; }
    // Add to shortlisted list
    candidates.forEach(c => {
      if (!shortlistedCandidates.includes(c.filename)) {
        shortlistedCandidates.push(c.filename);
      }
    });
    showToast(`${data.notified} candidate(s) shortlisted & notified!`);
    applyFilters(); // Re-render to show shortlisted state
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-paper-plane"></i> Shortlist & Notify via WhatsApp';
  }
}

function renderShortlist() {
  const listEl = document.getElementById('shortlistedList');
  const emptyEl = document.getElementById('shortlistEmpty');
  if (!shortlistedCandidates.length) {
    listEl.innerHTML = '';
    listEl.appendChild(emptyEl);
    emptyEl.style.display = '';
    return;
  }
  if (emptyEl) emptyEl.style.display = 'none';
  let html = '<div class="shortlist-grid">';
  shortlistedCandidates.forEach((name, i) => {
    const match = allResults.find(r => r.filename === name);
    const score = match ? match.score + '%' : '—';
    const cert = match && match.cert_status === 'verified'
      ? '<span class="pill-badge pill-verified" style="font-size:.7rem"><i class="fas fa-check-circle"></i> Verified</span>'
      : '<span class="pill-badge pill-pending" style="font-size:.7rem"><i class="fas fa-hourglass-half"></i> Pending</span>';
    const phone = match && match.phone ? match.phone : 'No phone';
    html += `<div class="shortlist-card anim-fade" style="--d:${i}">
      <div class="sl-card-top">
        <div class="sl-avatar">${name.charAt(0).toUpperCase()}</div>
        <div class="sl-info">
          <div class="sl-name">${name}</div>
          <div class="sl-meta"><i class="fas fa-phone-alt"></i> ${phone}</div>
        </div>
      </div>
      <div class="sl-card-bottom">
        <span class="sl-score"><i class="fas fa-chart-bar"></i> ${score}</span>
        ${cert}
        <span class="sl-notified"><i class="fab fa-whatsapp" style="color:#25d366"></i> Notified</span>
      </div>
    </div>`;
  });
  html += '</div>';
  listEl.innerHTML = html;
}

function exportShortlistCSV() {
  if (!shortlistedCandidates.length) { showToast('No shortlisted candidates to export', 'info'); return; }
  let csv = 'Candidate,Match Score (%),Certificate Status,Phone\n';
  shortlistedCandidates.forEach(name => {
    const match = allResults.find(r => r.filename === name);
    csv += `"${name}",${match ? match.score : ''},${match ? (match.cert_status || 'pending') : ''},${match && match.phone ? match.phone : ''}\n`;
  });
  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'shortlisted_candidates.csv'; a.click();
  URL.revokeObjectURL(url);
  showToast('Shortlist CSV downloaded!');
}

/* ═══════════════════════════════════════════
   CONFETTI
   ═══════════════════════════════════════════ */
function launchConfetti() {
  const canvas = document.getElementById('confettiCanvas');
  if (!canvas) return;
  canvas.style.display = 'block';
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const pieces = [];
  const colors = ['#00d4aa', '#7c3aed', '#f5a623', '#ff4d4d', '#00b4d8', '#fff'];
  for (let i = 0; i < 120; i++) {
    pieces.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height - canvas.height,
      w: Math.random() * 8 + 4,
      h: Math.random() * 4 + 2,
      color: colors[Math.floor(Math.random() * colors.length)],
      vx: (Math.random() - 0.5) * 4,
      vy: Math.random() * 4 + 2,
      rot: Math.random() * 360,
      rv: (Math.random() - 0.5) * 8
    });
  }
  let frames = 0;
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    pieces.forEach(p => {
      p.x += p.vx; p.y += p.vy; p.rot += p.rv;
      p.vy += 0.05; // gravity
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot * Math.PI / 180);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    });
    frames++;
    if (frames < 150) requestAnimationFrame(draw);
    else { ctx.clearRect(0, 0, canvas.width, canvas.height); canvas.style.display = 'none'; }
  }
  draw();
}

/* ═══════════════════════════════════════════
   INIT
   ═══════════════════════════════════════════ */
loadDashboard();
