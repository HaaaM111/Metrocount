/* MetroMap core: shared map logic for both home and fullscreen pages.
   Depends on: groups/search data injected via #groups-data / #search-data,
   and an SVG inside .map-wrap. Exposes window.MetroMap. */
(function () {
  const svg = document.querySelector('.map-wrap svg');
  if (!svg) return;

  let groupsData = [];
  try { groupsData = JSON.parse(document.querySelector('#groups-data').textContent); } catch (e) {}

  function normalize(name) {
    return String(name || '').replace(/[（(].*?[)）]/g, '').trim();
  }

  /* ---- station index: normalized name -> {cx, cy, els} ---- */
  const stationIndex = (() => {
    const idx = new Map();
    svg.querySelectorAll('[data-name]').forEach((el) => {
      const n = normalize(el.getAttribute('data-name'));
      if (!idx.has(n)) idx.set(n, { cx: null, cy: null, els: [] });
      const rec = idx.get(n);
      rec.els.push(el);
      if ((el.tagName === 'circle' || el.tagName === 'ellipse') && rec.cx === null) {
        rec.cx = parseFloat(el.getAttribute('cx'));
        rec.cy = parseFloat(el.getAttribute('cy'));
      }
    });
    return idx;
  })();

  const lineColor = {};
  groupsData.forEach((g) => { if (g.color) lineColor[g.line] = g.color; });

  /* ---- route highlight ---- */
  function clearRoute() {
    const hl = svg.querySelector('g[data-role="route-highlight"]');
    if (hl) hl.remove();
    svg.querySelectorAll('path, ellipse, circle, text').forEach((el) => { el.style.opacity = ''; });
  }

  function nearestLenOnPath(path, coord) {
    const total = path.getTotalLength();
    let bestLen = 0, bestDist = Infinity;
    const steps = Math.max(120, Math.floor(total / 4));
    for (let i = 0; i <= steps; i++) {
      const d = total * i / steps;
      const pt = path.getPointAtLength(d);
      const dist = Math.hypot(pt.x - coord[0], pt.y - coord[1]);
      if (dist < bestDist) { bestDist = dist; bestLen = d; }
    }
    return bestDist < 25 ? bestLen : null;
  }

  function showRoute(segments) {
    if (!segments || !segments.length) { clearRoute(); return; }
    clearRoute();
    const NS = 'http://www.w3.org/2000/svg';

    svg.querySelectorAll('path').forEach((p) => { p.style.opacity = '0.10'; });
    svg.querySelectorAll('ellipse').forEach((e) => { e.style.opacity = '0.22'; });
    svg.querySelectorAll('circle[data-name], .line-badge circle').forEach((c) => { c.style.opacity = '0.22'; });
    svg.querySelectorAll('text').forEach((t) => { t.style.opacity = '0.30'; });

    const g = document.createElementNS(NS, 'g');
    g.setAttribute('data-role', 'route-highlight');
    g.style.pointerEvents = 'none';
    svg.appendChild(g);

    const coordOf = (name) => {
      const rec = stationIndex.get(normalize(name));
      return rec && rec.cx !== null ? [rec.cx, rec.cy] : null;
    };
    const restoreStation = (name) => {
      const rec = stationIndex.get(normalize(name));
      if (rec) rec.els.forEach((el) => { el.style.opacity = '1'; });
    };

    segments.forEach((seg) => {
      (seg.stations || []).forEach((n) => restoreStation(n));
    });

    segments.forEach((seg, si) => {
      const col = lineColor[seg.line];
      const startC = coordOf(seg.stations[0]);
      const endC = coordOf(seg.stations[seg.stations.length - 1]);
      if (!startC || !endC || !col) return;

      svg.querySelectorAll('path.metro-line').forEach((p) => {
        if ((p.getAttribute('stroke') || '').toUpperCase() !== String(col).toUpperCase()) return;
        const total = p.getTotalLength();
        const sLen = nearestLenOnPath(p, startC);
        const eLen = nearestLenOnPath(p, endC);
        if (sLen == null || eLen == null) return;
        let a = sLen < eLen ? sLen : eLen;
        let b = sLen < eLen ? eLen : sLen;
        const forward = b - a;
        const backward = total - forward;
        const p0 = p.getPointAtLength(0);
        const p1 = p.getPointAtLength(total);
        const isLoop = Math.hypot(p0.x - p1.x, p0.y - p1.y) < 20;
        const clone = p.cloneNode(false);
        clone.style.opacity = '1';
        clone.setAttribute('stroke-width', '12');
        if (isLoop && backward < forward) {
          clone.style.strokeDasharray = `${backward} ${forward}`;
          clone.style.strokeDashoffset = `${-b}`;
        } else {
          clone.style.strokeDasharray = `${forward} ${backward}`;
          clone.style.strokeDashoffset = `${-a}`;
        }
        g.appendChild(clone);
      });

      if (si < segments.length - 1) {
        const tName = seg.stations[seg.stations.length - 1];
        const tCoord = coordOf(tName);
        if (tCoord) {
          restoreStation(tName);
          const ring = document.createElementNS(NS, 'circle');
          ring.setAttribute('cx', tCoord[0]); ring.setAttribute('cy', tCoord[1]);
          ring.setAttribute('r', '16'); ring.setAttribute('fill', '#ffffff');
          ring.setAttribute('stroke', '#1f2328'); ring.setAttribute('stroke-width', '3');
          g.appendChild(ring);
          const dot = document.createElementNS(NS, 'circle');
          dot.setAttribute('cx', tCoord[0]); dot.setAttribute('cy', tCoord[1]);
          dot.setAttribute('r', '7'); dot.setAttribute('fill', col);
          g.appendChild(dot);
        }
      }
    });
  }

  /* ---- pick markers (orange origin / blue destination) ---- */
  const NS = 'http://www.w3.org/2000/svg';
  let originMark = null, destMark = null;
  const picks = { origin: null, destination: null };

  function removeMark(mark) { if (mark) { mark.ring.remove(); mark.dot.remove(); } }

  function placeMarker(side, el) {
    removeMark(side === 'origin' ? originMark : destMark);
    let cx = null, cy = null;
    const tag = el.tagName;
    if (tag === 'ellipse' || tag === 'circle') {
      cx = parseFloat(el.getAttribute('cx'));
      cy = parseFloat(el.getAttribute('cy'));
    } else {
      const name = el.getAttribute('data-name');
      const marker = svg.querySelector('circle[data-name="' + name + '"], ellipse[data-name="' + name + '"]');
      if (marker) {
        cx = parseFloat(marker.getAttribute('cx'));
        cy = parseFloat(marker.getAttribute('cy'));
      } else {
        cx = parseFloat(el.getAttribute('x'));
        cy = parseFloat(el.getAttribute('y')) - 8;
      }
    }
    if (cx == null || cy == null) return;
    const color = side === 'origin' ? '#FF6B00' : '#00A8FF';
    const ring = document.createElementNS(NS, 'circle');
    ring.setAttribute('cx', cx); ring.setAttribute('cy', cy);
    ring.setAttribute('r', '20'); ring.setAttribute('fill', 'none');
    ring.setAttribute('stroke', color); ring.setAttribute('stroke-width', '5');
    ring.style.pointerEvents = 'none';
    const dot = document.createElementNS(NS, 'circle');
    dot.setAttribute('cx', cx); dot.setAttribute('cy', cy);
    dot.setAttribute('r', '6'); dot.setAttribute('fill', color);
    dot.style.pointerEvents = 'none';
    svg.appendChild(ring); svg.appendChild(dot);
    const mark = { ring, dot };
    if (side === 'origin') originMark = mark; else destMark = mark;
  }

  function setPick(side, lineName, stationId) {
    const g = groupsData.find((x) => x.line === lineName);
    const st = g && g.stations.find((s) => String(s.id) === String(stationId));
    if (!st) return;
    const norm = normalize(st.label);
    let el = svg.querySelector('text[data-name="' + st.label + '"], circle[data-name="' + st.label + '"], ellipse[data-name="' + st.label + '"]');
    if (!el) {
      svg.querySelectorAll('ellipse, circle, text').forEach((n) => {
        if (!el && n.getAttribute('data-name') && normalize(n.getAttribute('data-name')) === norm) el = n;
      });
    }
    if (!el) return;
    placeMarker(side, el);
    picks[side] = { line: lineName, id: stationId, name: st.label };
  }

  function clearPicks() {
    removeMark(originMark); originMark = null;
    removeMark(destMark); destMark = null;
    picks.origin = null; picks.destination = null;
  }

  /* ---- find station by svg element ---- */
  const colorToLine = {};
  groupsData.forEach((g) => { if (g.color) colorToLine[g.color] = g.line; });

  function findStation(name, color) {
    const norm = normalize(name);
    const lineName = colorToLine[color];
    if (lineName) {
      const g = groupsData.find((x) => x.line === lineName);
      if (g) {
        const st = g.stations.find((s) => normalize(s.label) === norm);
        if (st) return { line: lineName, id: st.id };
      }
    }
    let hits = [];
    groupsData.forEach((g) => g.stations.forEach((s) => {
      if (normalize(s.label) === norm) hits.push({ line: g.line, id: s.id });
    }));
    if (hits.length === 1) return hits[0];
    return null;
  }

  /* ---- fixed-size pan (no zoom): drag to move, wheel scrolls natively ---- */
  let dragMoved = false;
  (function setupPan() {
    const wrap = document.querySelector('.map-wrap');
    if (!wrap) return;
    svg.style.willChange = 'auto';
    const vb = svg.viewBox.baseVal;
    const vbW = vb.width || 4405;
    const vbX = vb.x || 118, vbY = vb.y || 42;
    const CITY = [2475.6, 2543.6];
    const FONT = 22;

    function render() {
      svg.style.width = '100%';
      svg.style.height = 'auto';
      svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      const s = svg.clientWidth / vbW;
      const f = FONT * s;
      svg.dataset.density = 'high';
      svg.style.setProperty('--lbl-scale', Math.max(1, 10 / f).toFixed(3));
      svg.style.setProperty('--badge-scale', (9 / (20 * s)).toFixed(3));
      svg.style.setProperty('--dot-scale', '1');
      const px = (CITY[0] - vbX) * s;
      const py = (CITY[1] - vbY) * s;
      wrap.scrollLeft = Math.max(0, px - wrap.clientWidth / 2);
      wrap.scrollTop = Math.max(0, py - wrap.clientHeight / 2);
    }

    wrap.style.cursor = 'grab';
    wrap.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      dragMoved = false;
      const startX = e.pageX, startY = e.pageY;
      const startSL = wrap.scrollLeft, startST = wrap.scrollTop;
      wrap.style.cursor = 'grabbing';
      function onMove(ev) {
        const dx = ev.pageX - startX, dy = ev.pageY - startY;
        if (Math.abs(dx) > 4 || Math.abs(dy) > 4) dragMoved = true;
        if (dragMoved) {
          wrap.scrollLeft = startSL - dx;
          wrap.scrollTop = startST - dy;
        }
      }
      function onUp() {
        wrap.style.cursor = 'grab';
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
      }
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });

    const zf = document.getElementById('map-fit');
    if (zf) zf.addEventListener('click', render);
    window.addEventListener('resize', render);
    render();
  })();

  /* ---- init: wire up station clicks if interactive ---- */
  function init(opts) {
    opts = opts || {};
    if (!opts.interactive) return;

    let clickCount = 0;
    svg.querySelectorAll('ellipse, circle, text').forEach((el) => {
      const name = el.getAttribute('data-name');
      if (!name) return;
      el.style.cursor = 'pointer';
      el.addEventListener('click', (e) => {
        if (dragMoved) return;
        e.stopPropagation();
        const hit = findStation(name, el.getAttribute('data-color'));
        if (!hit) return;
        clickCount += 1;
        if (clickCount === 1) {
          if (opts.onPick) opts.onPick('origin', hit);
        } else if (clickCount === 2) {
          if (opts.onPick) opts.onPick('destination', hit);
        } else {
          clickCount = 1;
          clearPicks();
          if (opts.onReset) opts.onReset();
          if (opts.onPick) opts.onPick('origin', hit);
        }
      });
    });

    svg.addEventListener('click', (e) => {
      if (dragMoved) return;
      const t = e.target;
      if (t === svg || t.tagName === 'path' || t.tagName === 'rect') {
        clickCount = 0;
        clearPicks();
        if (opts.onReset) opts.onReset();
      }
    });
  }

  window.MetroMap = {
    init: init,
    setPick: setPick,
    clearPicks: clearPicks,
    showRoute: showRoute,
    clearRoute: clearRoute,
    getPicks: () => ({ origin: picks.origin, destination: picks.destination }),
    _stationIndex: stationIndex,
  };
})();
