/* INFLATION LENS — API client.
   Replaces the static figures this file used to hold with live reads from
   the Flask engine (Back-end/). Every consumer — showcase.js, index.html's
   inline script, app.html's inline script — still reads a single
   `window.LENS` object of the same shape the static version had; the only
   difference visible to them is that it isn't ready synchronously.

   Await `window.LENS_READY` (a promise) before reading `window.LENS` for
   the first time. `window.LENS_API.load(geo, opts)` re-fetches and
   re-assigns `window.LENS` for the workbench's geography/window/adjustment
   rails and search; `window.LENS_API.resolve(q)` backs search.

   If the engine cannot be reached at all, `window.LENS_READY` resolves to
   `null` and `window.LENS_ERROR` carries the failure — callers render the
   product's own "unavailable" treatment rather than a blank page (the
   product's whole premise is that missing data stays visibly missing). */
(() => {
  const API_BASE = window.LENS_API_BASE || 'http://localhost:5000/api/v1';

  async function fetchJSON(path) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(`${path} -> HTTP ${res.status}: ${body.error?.message || res.statusText}`);
    }
    return res.json();
  }

  const SRC_NAME = { bls: 'BLS', bea: 'BEA', fred: 'FRED', eurostat: 'Eurostat', ecb: 'ECB', world_bank: 'World Bank' };
  // Trimmed-mean PCE is distributed through FRED but published by the
  // Dallas Fed -- the design's own convention (data.js originally) names
  // the publisher, not the distribution channel.
  const srcFor = m => (m.id === 'trim' ? 'Dallas Fed' : (SRC_NAME[m.src] || m.src || '—'));

  function formatPeriod(period) {
    // "2026-07" -> "Jul 2026"; leaves anything else (null, a year alone) as-is.
    if (!period || !/^\d{4}-\d{2}$/.test(period)) return period;
    const [y, m] = period.split('-').map(Number);
    return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
  }

  function formatAsOf(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  function assembleUs(measuresRes, categoriesRes, regionsRes) {
    const measures = measuresRes.measures.map(m => ({
      id: m.id, code: m.code, name: m.name,
      yoy: m.yoy, mom: m.mom,
      period: formatPeriod(m.period),
      src: srcFor(m),
      note: m.note || '',
      seasonallyAdjusted: m.seasonally_adjusted,
      coverage: m.coverage, isEstimated: m.is_estimated,
    }));
    // Integration point 1: spread is derived from whatever measures
    // actually came back, not a literal — Math.max/min over available yoy.
    const withValues = measures.filter(m => m.yoy != null).map(m => m.yoy);
    const spread = withValues.length ? { lo: Math.min(...withValues), hi: Math.max(...withValues) } : null;
    const cpi = measures.find(m => m.id === 'cpi');

    return {
      asOf: cpi ? cpi.period : null, // already formatted, above
      measures,
      spread,
      index: null, // not exposed by the engine's IndicatorResult contract -- see DESIGN_HANDOFF.md's flagged gaps
      context: (measuresRes.context || []).map(c => ({ k: c.k, v: `${c.v}%` })),
      categories: (categoriesRes?.categories || []).map(c => ({ name: c.name, v: c.v })),
      // MODELLED. BLS publishes no state-level CPI: every state below
      // inherits its census region's *published* regional CPI rather than
      // a per-state estimate (README.md "Backend integration", point 3).
      modelled: true,
      regions: regionsRes?.regions || {},
      stateRegion: regionsRes?.stateRegion || {},
      stateValues: regionsRes?.stateValues || {},
      stateNames: regionsRes?.stateNames || {},
      regionTails: regionsRes?.regionTails || null,
    };
  }

  function assembleWorld(worldRes) {
    return {
      headline: { v: worldRes.headline, label: 'Global headline inflation', period: null, src: null },
      median: { v: worldRes.median, label: 'Global median', period: null, src: 'World Bank' },
      g20: { v: worldRes.g20, label: 'G20', src: null },
      economies: worldRes.economies,
      // Not ingested: no continent-level aggregate is computed server-side
      // (see README.md's flagged gaps). Left empty rather than fabricated.
      regions: [],
      tails: worldRes.tails.map(t => ({ name: t.name, v: t.v })),
      byIso: worldRes.byIso,
    };
  }

  function assembleSources(sourcesRes) {
    return (sourcesRes.publishers || []).map(p => ({
      org: p.org, full: p.full, url: p.url,
      series: `${p.series} series drawn`,
      cov: p.cov,
      latest: p.latest ? formatAsOf(p.latest) : '—',
      next: p.next || 'Not published',
    }));
  }

  async function load(geo = 'USA', { window: win = '12m', adjustment = 'as_published' } = {}) {
    const qs = `?window=${win}&adjustment=${adjustment}`;
    const [measuresRes, categoriesRes, regionsRes, worldRes, sourcesRes] = await Promise.all([
      fetchJSON(`/measures/${geo}${qs}`),
      geo === 'USA' ? fetchJSON('/categories/USA') : Promise.resolve(null),
      geo === 'USA' ? fetchJSON('/regions/us') : Promise.resolve(null),
      fetchJSON('/world/cross-section'),
      fetchJSON('/meta/data-sources'),
    ]);
    const us = assembleUs(measuresRes, categoriesRes, regionsRes);
    const cpiSnapshot = measuresRes.measures.find(m => m.id === 'cpi')?.data_snapshot;
    window.LENS = {
      asOf: cpiSnapshot ? formatAsOf(cpiSnapshot.as_of) : formatAsOf(new Date().toISOString()),
      geography: geo,
      world: assembleWorld(worldRes),
      us,
      sources: assembleSources(sourcesRes),
    };
    return window.LENS;
  }

  async function resolve(q) {
    if (!q || !q.trim()) return [];
    const data = await fetchJSON(`/resolve?q=${encodeURIComponent(q.trim())}`);
    return data.matches;
  }

  window.LENS_API = { base: API_BASE, load, resolve };
  window.LENS_READY = load('USA').catch(err => {
    console.error(`data.js: could not reach the engine at ${API_BASE}`, err);
    window.LENS_ERROR = err;
    document.body.setAttribute('data-lens', 'unavailable');
    // Progressive enhancement: pages that carry a #lens-alert element (a
    // real, accessible role="alert" region -- see index.html/app.html) get
    // it populated here so a screen-reader user is told the same thing a
    // sighted one sees, not just a CSS ::before nobody's AT will announce.
    // The API base stays in the console line above, not in this copy: it's
    // meaningless to a non-technical reader and shouldn't leak internals.
    const alertEl = document.getElementById('lens-alert');
    if (alertEl) {
      alertEl.textContent = 'The engine could not be reached. Figures on this page are unavailable.';
      alertEl.hidden = false;
    }
    return null;
  });
})();
