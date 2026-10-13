/* Home page panel logic. Map interactions are handled by map-core.js (window.MetroMap). */
const originLineSelect = document.querySelector('#origin-line-select');
const destinationLineSelect = document.querySelector('#destination-line-select');
const originSelect = document.querySelector('#origin-select');
const destinationSelect = document.querySelector('#destination-select');
const results = document.querySelector('#fare-results');
const resultCount = document.querySelector('#result-count');
const resetButton = document.querySelector('#reset-button');
const swapButton = document.querySelector('#swap-button');
const searchInput = document.querySelector('#station-search');
const searchResults = document.querySelector('#search-results');
const tabTrip = document.querySelector('#tab-trip');
const tabTable = document.querySelector('#tab-table');
const quickRoutes = document.querySelector('#quick-routes');

let groupsData = [];
let searchData = [];
try {
  groupsData = JSON.parse(document.querySelector('#groups-data').textContent);
  searchData = JSON.parse(document.querySelector('#search-data').textContent);
} catch (e) { /* data missing */ }

let currentTab = 'trip';                  // 'trip' | 'table'
let tableState = { field: 'fare', dir: 1 }; // 票价表排序状态

const LS_RECENT = 'metrocount_recent';
const LS_SAVED = 'metrocount_saved';

function readLS(key) {
  try { return JSON.parse(localStorage.getItem(key)) || []; }
  catch (e) { return []; }
}
function writeLS(key, arr) {
  try { localStorage.setItem(key, JSON.stringify(arr)); } catch (e) { /* storage unavailable */ }
}
function cleanName(label) {
  return String(label || '').replace(/（.*）/g, '');
}

function chipTextColor(bg) {
  const m = /#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i.exec(bg || '');
  if (!m) return '#fff';
  const lum = 0.299 * parseInt(m[1], 16) + 0.587 * parseInt(m[2], 16) + 0.114 * parseInt(m[3], 16);
  return lum > 160 ? '#1f2328' : '#fff';
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

let currentMainSegments = null;

function renderTrip(t, alternatives) {
  const meta = [];
  if (t.distance_km != null) meta.push(`全程约 ${esc(t.distance_km)} 公里`);
  if (t.minutes != null) meta.push(`约 ${esc(t.minutes)} 分钟`);
  if (t.transfers != null) meta.push(t.transfers === 0 ? '直达' : `换乘 ${esc(t.transfers)} 次`);
  const segHtml = (segs) => (segs || []).map((seg) => {
    const bg = seg.color || '#666';
    const fg = chipTextColor(bg);
    return `
    <div class="seg">
      <span class="seg-line" style="background:${bg};color:${fg}">${esc(seg.line)}</span>
      <span class="seg-route">${esc(seg.from)} → ${esc(seg.to)}</span>
      <span class="seg-stops">${esc(seg.stopCount)} 站</span>
    </div>`;
  }).join('');
  const segmentsHtml = segHtml(t.segments);
  currentMainSegments = t.segments || null;
  const saved = isSaved(originSelect.value, destinationSelect.value);

  resultCount.textContent = '行程票价';
  results.className = 'fare-results trip-view';
  results.innerHTML = `
    <div class="trip-card">
      <div class="trip-route">
        <div class="trip-endpoint"><span class="trip-label">出发</span><strong>${esc(t.origin)}</strong></div>
        <div class="trip-arrow">→</div>
        <div class="trip-endpoint"><span class="trip-label">到达</span><strong>${esc(t.destination)}</strong></div>
      </div>
      <div class="trip-meta">${meta.join(' · ')}</div>
      <div class="trip-detail">
        <span class="trip-fare">¥${t.fare}</span>
      </div>
      ${segmentsHtml ? `<div class="trip-segments"><div class="trip-segments-title">乘坐方案</div>${segmentsHtml}</div>` : ''}
      <div class="trip-actions">
        <button type="button" class="mini-btn ${saved ? 'saved' : ''}" id="trip-save">${saved ? '★ 已收藏' : '☆ 收藏路线'}</button>
        <button type="button" class="mini-btn" id="trip-share">复制链接</button>
      </div>
    </div>`;
  if (t.segments && t.segments.length) MetroMap.showRoute(t.segments);

  (alternatives || []).forEach((alt) => {
    const fastNames = [];
    (alt.segments || []).forEach((s) => {
      if (s.line === '磁悬浮') fastNames.push('磁悬浮');
      else if (s.line === '市域机场线') fastNames.push('机场线');
    });
    const fastLabel = fastNames.length ? [...new Set(fastNames)].join(' / ') : '更快';
    results.insertAdjacentHTML('beforeend', `
      <details class="alt-plan">
        <summary>备选方案 · ${fastLabel}（约 ${alt.minutes} 分钟 · ¥${alt.fare}，更快）</summary>
        <div class="trip-segments"><div class="trip-segments-title">备选乘坐方案</div>${segHtml(alt.segments)}</div>
      </details>`);
    results.querySelector('.alt-plan:last-of-type').addEventListener('toggle', (e) => {
      MetroMap.showRoute(e.target.open ? alt.segments : currentMainSegments);
    });
  });

  const saveBtn = results.querySelector('#trip-save');
  if (saveBtn) saveBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const savedNow = toggleSave(originSelect.value, destinationSelect.value);
    saveBtn.textContent = savedNow ? '★ 已收藏' : '☆ 收藏路线';
    saveBtn.classList.toggle('saved', savedNow);
    renderQuickRoutes();
  });
  const shareBtn = results.querySelector('#trip-share');
  if (shareBtn) shareBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    copyShareLink(originSelect.value, destinationSelect.value, shareBtn);
  });
}

function renderFares(data) {
  if (data.trip) {
    renderTrip(data.trip, data.alternatives || []);
    return;
  }
  MetroMap.clearRoute();
  resultCount.textContent = `从 ${data.origin.name} 出发 · ${data.fares.length} 个可达站点`;
  if (!data.fares.length) {
    results.className = 'fare-results empty-state';
    results.textContent = '当前组合暂无可用线路数据。';
    return;
  }
  results.className = 'fare-results fare-grid';
  results.innerHTML = data.fares.map((item) => `
    <div class="fare-card">
      <span class="fare-price">¥${esc(item.fare)}</span>
      <strong>${esc(item.name)}</strong>
      <span>${esc(item.line)} · ${esc(item.distance_km)} km</span>
    </div>`).join('');
}

/* ---- 票价表 Tab ---- */
function findLineOf(id) {
  for (const g of groupsData) {
    for (const s of g.stations) {
      if (String(s.id) === String(id)) return g.line;
    }
  }
  return null;
}

function switchTab(tab) {
  currentTab = tab;
  tabTrip.classList.toggle('active', tab === 'trip');
  tabTable.classList.toggle('active', tab === 'table');
  if (tab === 'table') loadFareTable();
  else loadFares();
}

function loadFareTable() {
  const origin = originSelect.value;
  if (!origin) {
    resultCount.textContent = '票价表：请先选择起点';
    results.className = 'fare-results empty-state';
    results.textContent = '选择起点后，展示从该站到全网各站的票价。';
    return;
  }
  results.className = 'fare-results empty-state';
  results.textContent = '正在加载票价表…';
  const seq = ++fareReqSeq;
  fetch(`/api/stations/${origin}/fares/`)
    .then((response) => response.json())
    .then((data) => {
      if (seq !== fareReqSeq) return;
      renderFareTable(data);
    })
    .catch(() => {
      if (seq !== fareReqSeq) return;
      resultCount.textContent = '加载失败';
      results.textContent = '无法加载票价，请确认 Django 服务正在运行。';
    });
}

function tableArrow(f) {
  return tableState.field === f ? (tableState.dir > 0 ? '↑' : '↓') : '';
}

/* 线路排序键：拆出线路号数字，如 "14号线、8号线" -> [14, 8]；非数字线路（浦江线/磁悬浮/机场线）排最后 */
function lineSortKey(s) {
  return String(s || '').split(/[、,，]/).map((x) => {
    const n = parseInt(x, 10);
    return Number.isNaN(n) ? 999 : n;
  });
}

function renderFareTable(data) {
  MetroMap.clearRoute();
  resultCount.textContent = `从 ${data.origin.name} 出发 · ${data.fares.length} 个可达站点`;
  const rows = data.fares.map((r) => Object.assign({}, r));
  const sortRows = () => {
    const f = tableState.field;
    const dir = tableState.dir;
    rows.sort((a, b) => {
      if (f === 'name') return dir * String(a.name).localeCompare(String(b.name), 'zh-Hans-CN');
      if (f === 'line') {
        const ka = lineSortKey(a.line);
        const kb = lineSortKey(b.line);
        const len = Math.max(ka.length, kb.length);
        for (let i = 0; i < len; i++) {
          const va = ka[i] || 0;
          const vb = kb[i] || 0;
          if (va !== vb) return dir * (va - vb);
        }
        return 0;
      }
      const va = (f === 'fare' ? a.fare : a.distance_km) || 0;
      const vb = (f === 'fare' ? b.fare : b.distance_km) || 0;
      return dir * (va - vb);
    });
  };
  sortRows();
  results.className = 'fare-results fare-table-view';
  results.innerHTML = `
    <div class="fare-table-wrap">
      <table class="fare-table">
        <thead>
          <tr>
            <th class="sortable" data-field="name">站名 ${tableArrow('name')}</th>
            <th class="sortable" data-field="fare">票价 ¥ ${tableArrow('fare')}</th>
            <th class="sortable" data-field="distance_km">里程 km ${tableArrow('distance_km')}</th>
            <th class="sortable" data-field="line">线路 ${tableArrow('line')}</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r) => `
            <tr data-id="${r.id}">
              <td class="ft-name">${esc(r.name)}</td>
              <td>¥${r.fare}</td>
              <td>${r.distance_km == null ? '—' : r.distance_km}</td>
              <td class="ft-line">${esc(r.line)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
  results.querySelectorAll('th.sortable').forEach((th) => th.addEventListener('click', () => {
    const f = th.dataset.field;
    if (tableState.field === f) tableState.dir *= -1;
    else { tableState.field = f; tableState.dir = 1; }
    renderFareTable(data);
  }));
  results.querySelectorAll('tbody tr').forEach((tr) => tr.addEventListener('click', () => {
    const line = findLineOf(tr.dataset.id);
    if (!line) return;
    switchTab('trip');
    setStation('destination', line, tr.dataset.id);
  }));
}

/* ---- 常用路线 / 最近查询（localStorage） ---- */
function isSaved(oid, did) {
  return readLS(LS_SAVED).some((x) => String(x.oid) === String(oid) && String(x.did) === String(did));
}

function selectedLabel(sel) {
  const opt = sel && sel.options[sel.selectedIndex];
  return opt ? opt.textContent : '';
}

function toggleSave(oid, did) {
  let arr = readLS(LS_SAVED);
  if (isSaved(oid, did)) {
    arr = arr.filter((x) => !(String(x.oid) === String(oid) && String(x.did) === String(did)));
  } else {
    const oName = selectedLabel(originSelect);
    const dName = selectedLabel(destinationSelect);
    if (!oName || !dName) return isSaved(oid, did);
    arr.unshift({
      oid: String(oid), oline: originLineSelect.value, oname: oName,
      did: String(did), dline: destinationLineSelect.value, dname: dName,
      ts: Date.now(),
    });
    arr = arr.slice(0, 10);
  }
  writeLS(LS_SAVED, arr);
  renderQuickRoutes();
  return isSaved(oid, did);
}

function recordRecent(oid, did) {
  const oName = selectedLabel(originSelect);
  const dName = selectedLabel(destinationSelect);
  if (!oName || !dName) return;
  const arr = readLS(LS_RECENT)
    .filter((x) => !(String(x.oid) === String(oid) && String(x.did) === String(did)));
  arr.unshift({
    oid: String(oid), oline: originLineSelect.value, oname: oName,
    did: String(did), dline: destinationLineSelect.value, dname: dName,
    ts: Date.now(),
  });
  writeLS(LS_RECENT, arr.slice(0, 6));
  renderQuickRoutes();
}

function applyQuick(item) {
  setStation('origin', item.oline, item.oid);
  setStation('destination', item.dline, item.did);
}

function renderQuickRoutes() {
  if (!quickRoutes) return;
  const saved = readLS(LS_SAVED);
  const recent = readLS(LS_RECENT);
  if (!saved.length && !recent.length) {
    quickRoutes.hidden = true;
    quickRoutes.innerHTML = '';
    return;
  }
  const chip = (item, kind) => `
    <span class="qr-chip">
      <button type="button" class="qr-main" data-oline="${esc(item.oline)}" data-oid="${esc(item.oid)}" data-dline="${esc(item.dline)}" data-did="${esc(item.did)}" title="${esc(cleanName(item.oname))} → ${esc(cleanName(item.dname))}">${esc(cleanName(item.oname))} → ${esc(cleanName(item.dname))}</button>
      ${kind === 'saved' ? `<button type="button" class="qr-del" data-oid="${esc(item.oid)}" data-did="${esc(item.did)}" title="取消收藏">×</button>` : ''}
    </span>`;
  quickRoutes.hidden = false;
  quickRoutes.innerHTML =
    (saved.length ? `<span class="qr-label">常用</span>${saved.map((x) => chip(x, 'saved')).join('')}` : '') +
    (recent.length ? `<span class="qr-label">最近</span>${recent.map((x) => chip(x, 'recent')).join('')}` : '');
}

/* ---- 起终点互换 ---- */
function updateSwapState() {
  swapButton.disabled = !(originSelect.value && destinationSelect.value);
}

/* ---- 复制分享链接 ---- */
function copyShareLink(oid, did, btn) {
  const url = `${location.origin}/map/?origin=${oid}&destination=${did}`;
  const done = () => {
    if (btn) {
      const old = btn.textContent;
      btn.textContent = '已复制 ✓';
      setTimeout(() => { btn.textContent = old; }, 1600);
    }
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(done).catch(() => fallbackCopy(url, done));
  } else {
    fallbackCopy(url, done);
  }
}

function fallbackCopy(text, done) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); done(); }
  catch (e) { window.prompt('请手动复制分享链接：', text); }
  document.body.removeChild(ta);
}

/* ---- two-level selectors ---- */
function populateStations(lineSelect, stationSelect) {
  const line = lineSelect.value;
  stationSelect.innerHTML = '<option value="">' + (stationSelect === originSelect ? '请选择站点' : '请选择终点') + '</option>';
  if (!line) return;
  const group = groupsData.find((g) => g.line === line);
  if (!group) return;
  group.stations.forEach((s) => {
    const opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = s.label;
    stationSelect.appendChild(opt);
  });
}

function setStation(side, lineName, stationId) {
  const lineSel = side === 'origin' ? originLineSelect : destinationLineSelect;
  const stSel = side === 'origin' ? originSelect : destinationSelect;
  lineSel.value = lineName;
  populateStations(lineSel, stSel);
  stSel.value = String(stationId);
  if (MetroMap.setPick) MetroMap.setPick(side, lineName, stationId);
  if (currentTab === 'table') loadFareTable();
  else loadFares();
}

let fareReqSeq = 0;

function loadFares() {
  const origin = originSelect.value;
  const destination = destinationSelect.value;
  updateSwapState();
  if (!origin) {
    resultCount.textContent = '请选择起点和终点';
    results.className = 'fare-results empty-state';
    results.textContent = '选择起点和终点后，显示参考票价与乘坐方案。';
    return;
  }
  if (!destination) {
    resultCount.textContent = '请选择终点';
    results.className = 'fare-results empty-state';
    results.textContent = '选择终点后，显示参考票价与乘坐方案。';
    return;
  }
  results.className = 'fare-results empty-state';
  results.textContent = '正在计算参考票价…';
  const seq = ++fareReqSeq;
  fetch(`/api/stations/${origin}/fares/?destination=${destination}`)
    .then((response) => response.json())
    .then((data) => {
      if (seq !== fareReqSeq) return;
      renderFares(data);
      if (data.trip) recordRecent(origin, destination);
    })
    .catch(() => {
      if (seq !== fareReqSeq) return;
      resultCount.textContent = '加载失败';
      results.textContent = '无法加载票价，请确认 Django 服务正在运行。';
    });
}

function resetAll() {
  originLineSelect.value = '';
  destinationLineSelect.value = '';
  populateStations(originLineSelect, originSelect);
  populateStations(destinationLineSelect, destinationSelect);
  searchInput.value = '';
  closeSearch();
  MetroMap.clearPicks();
  MetroMap.clearRoute();
  if (currentTab === 'table') loadFareTable();
  else loadFares();
}

/* ---- search ---- */
function closeSearch() {
  searchResults.hidden = true;
  searchResults.innerHTML = '';
}

function renderSearch(keyword) {
  const kw = keyword.trim();
  if (!kw) { closeSearch(); return; }
  const hits = searchData.filter((s) => s.name.includes(kw)).slice(0, 15);
  if (!hits.length) {
    searchResults.hidden = false;
    searchResults.innerHTML = '<div class="search-empty">未找到匹配站点</div>';
    return;
  }
  searchResults.hidden = false;
  searchResults.innerHTML = hits.map((s) => {
    const firstId = s.ids[s.lines[0]];
    const chips = s.lines.map((l) =>
      `<span class="si-line" data-line="${esc(l)}" data-id="${esc(s.ids[l])}">${esc(l)}</span>`).join('');
    return `
      <div class="search-item">
        <div class="si-top">
          <span class="si-name">${esc(s.name)}</span>
          <span class="si-chips">${chips}</span>
        </div>
        <div class="si-actions">
          <button type="button" class="si-btn si-origin" data-line="${esc(s.lines[0])}" data-id="${esc(firstId)}">设为起点</button>
          <button type="button" class="si-btn si-dest" data-line="${esc(s.lines[0])}" data-id="${esc(firstId)}">设为终点</button>
        </div>
      </div>`;
  }).join('');

  searchResults.querySelectorAll('.si-origin').forEach((b) =>
    b.addEventListener('click', () => { setStation('origin', b.dataset.line, b.dataset.id); closeSearch(); }));
  searchResults.querySelectorAll('.si-dest').forEach((b) =>
    b.addEventListener('click', () => { setStation('destination', b.dataset.line, b.dataset.id); closeSearch(); }));
  searchResults.querySelectorAll('.si-line').forEach((c) =>
    c.addEventListener('click', () => { setStation('origin', c.dataset.line, c.dataset.id); closeSearch(); }));
}

searchInput.addEventListener('input', () => renderSearch(searchInput.value));
searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const first = searchResults.querySelector('.si-origin');
    if (first) { first.click(); e.preventDefault(); }
  }
  if (e.key === 'Escape') { searchInput.value = ''; closeSearch(); }
});
document.addEventListener('click', (e) => {
  if (!e.target.closest('.search-box')) closeSearch();
});

originLineSelect.addEventListener('change', () => {
  populateStations(originLineSelect, originSelect);
  MetroMap.setPick('origin', '', '');
});
destinationLineSelect.addEventListener('change', () => {
  populateStations(destinationLineSelect, destinationSelect);
  MetroMap.setPick('destination', '', '');
});
originSelect.addEventListener('change', () => {
  MetroMap.setPick('origin', originLineSelect.value, originSelect.value);
  if (currentTab === 'table') loadFareTable();
  else loadFares();
  updateSwapState();
});
destinationSelect.addEventListener('change', () => {
  MetroMap.setPick('destination', destinationLineSelect.value, destinationSelect.value);
  if (currentTab === 'table') loadFareTable();
  else loadFares();
  updateSwapState();
});

/* ---- Tab 切换 ---- */
tabTrip.addEventListener('click', () => switchTab('trip'));
tabTable.addEventListener('click', () => switchTab('table'));

/* ---- 互换 ---- */
swapButton.addEventListener('click', () => {
  if (!originSelect.value || !destinationSelect.value) return;
  const oLine = originLineSelect.value;
  const dLine = destinationLineSelect.value;
  const oSt = originSelect.value;
  const dSt = destinationSelect.value;
  originLineSelect.value = dLine;
  destinationLineSelect.value = oLine;
  populateStations(originLineSelect, originSelect);
  populateStations(destinationLineSelect, destinationSelect);
  originSelect.value = dSt;
  destinationSelect.value = oSt;
  MetroMap.setPick('origin', dLine, dSt);
  MetroMap.setPick('destination', oLine, oSt);
  if (currentTab === 'table') switchTab('trip');
  loadFares();
});

/* ---- 常用/最近 chips ---- */
quickRoutes.addEventListener('click', (e) => {
  const main = e.target.closest('.qr-main');
  if (main) {
    applyQuick({
      oline: main.dataset.oline, oid: main.dataset.oid,
      dline: main.dataset.dline, did: main.dataset.did,
    });
    return;
  }
  const del = e.target.closest('.qr-del');
  if (del) {
    const arr = readLS(LS_SAVED)
      .filter((x) => !(String(x.oid) === del.dataset.oid && String(x.did) === del.dataset.did));
    writeLS(LS_SAVED, arr);
    renderQuickRoutes();
  }
});

resetButton.addEventListener('click', resetAll);

/* ---- init MetroMap (home: display-only, no station picking) ---- */
MetroMap.init({ interactive: false });
renderQuickRoutes();
updateSwapState();

/* ---- URL params: ?origin=<id>&destination=<id> auto-fill ---- */
(function initFromURL() {
  const params = new URLSearchParams(location.search);
  const oid = params.get('origin');
  const did = params.get('destination');
  if (!oid || !did) return;
  // find station meta by id across groups
  let oLine = null, dLine = null;
  for (const g of groupsData) {
    if (g.stations.some((s) => String(s.id) === String(oid))) oLine = g.line;
    if (g.stations.some((s) => String(s.id) === String(did))) dLine = g.line;
  }
  if (oLine) setStation('origin', oLine, oid);
  if (dLine) setStation('destination', dLine, did);
})();

/* ---- 顶部实时时钟 ---- */
(function initClock() {
  const dateEl = document.getElementById('clock-date');
  const timeEl = document.getElementById('clock-time');
  if (!dateEl || !timeEl) return;
  const pad = (n) => String(n).padStart(2, '0');
  const fmtDate = (d) => {
    const wk = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()];
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 周${wk}`;
  };
  const tick = () => {
    const d = new Date();
    dateEl.textContent = fmtDate(d);
    timeEl.textContent = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };
  tick();
  setInterval(tick, 1000);
})();
