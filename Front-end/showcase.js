/* INFLATION LENS — the scroll showcase.
   Two acts on one pinned stage: a line-drawn world, then a zoom into the
   United States at state resolution. Geometry is real (Natural Earth via
   world-atlas / us-atlas), projected with d3-geo and drawn stroke-only —
   the map is a technical drawing, not an illustration.
   Mobile and prefers-reduced-motion drop the pin and read as two blocks.

   Waits on window.LENS_READY (data.js) before touching window.LENS -- the
   figures below are live API reads, not literals. */
(async () => {
  const L = await window.LENS_READY;
  const q = (s, r) => (r || document).querySelector(s);
  if (!L) {
    // data.js already flagged data-lens="unavailable" on <body>; nothing
    // in this file has anything to draw against, so stop here rather
    // than throw on the first `L.us` access.
    q('#m-rows').innerHTML = '<li class="m-row"><span class="m-note">The engine could not be reached. Figures are unavailable.</span></li>';
    return;
  }
  const fmt = (v, d) => (v == null ? '—' : (v > 0 && d ? '+' : '') + v.toFixed(1) + '%');
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const span = (p, a, b) => clamp((p - a) / (b - a), 0, 1);
  const ease = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  const RAMP = ['#eef6ff', '#d6ebff', '#b5d9fd', '#94bce3', '#749dc4', '#597ea3', '#416180', '#2c455d', '#1d2d3d'];

  const track = q('#showcase'), stage = q('#stage');
  const act1 = q('#act1'), act2 = q('#act2');
  const railFill = q('#rail-fill');
  const acts = [...document.querySelectorAll('[data-act-dot]')];

  const flat = () => matchMedia('(max-width:880px)').matches ||
    matchMedia('(prefers-reduced-motion:reduce)').matches;

  /* ── content: the engine's measures, the category ladder, the world figures ── */
  const rows = L.us.measures.map((m, i) => {
    const frac = m.yoy == null ? 0 : clamp(m.yoy / 5, 0, 1);
    return `
    <li class="m-row" style="--i:${i}">
      <span class="m-code">${m.code}</span>
      <span class="m-val">${fmt(m.yoy)}</span>
      <span class="m-bar"><i style="--w:${(frac * 100).toFixed(1)}%;--c:${RAMP[Math.min(8, Math.round(frac * 8) + 1)]}"></i></span>
      <span class="m-note">${m.note}</span>
      <span class="m-src">${m.src} · ${m.period || 'unavailable'}</span>
    </li>`;
  }).join('');
  q('#m-rows').innerHTML = rows;

  // Integration point 4: normalise against the tallest bar actually
  // returned, not a hardcoded 40 -- the category set is whatever the
  // engine's essential-cost basket carries this period.
  const maxCat = Math.max(1, ...L.us.categories.map(c => c.v));
  q('#cat-bars').innerHTML = L.us.categories.map(c => `
    <li class="cat">
      <span class="cat-n">${c.name}</span>
      <span class="cat-b"><i style="--w:${(c.v / maxCat * 100).toFixed(1)}%"></i></span>
      <span class="cat-v">${fmt(c.v, 1)}</span>
    </li>`).join('');

  q('#w-tails').innerHTML = L.world.tails.map(t =>
    `<li><span>${t.name}</span><b>${fmt(t.v)}</b></li>`).join('');
  q('#w-regions').innerHTML = L.world.regions.filter(r => r.v).map(r =>
    `<li><span>${r.name}</span><b>${fmt(r.v)}</b></li>`).join('');
  // No per-state tail list is computed (every state in a region shares
  // that region's published rate, so a "top 3 states" would just be an
  // arbitrary slice of ties) -- the highest/lowest *region* stands in.
  q('#us-hi').innerHTML = L.us.regionTails ? `<li><span>${L.us.regionTails.hi.region}</span><b>${fmt(L.us.regionTails.hi.v)}</b></li>` : '<li><span>Unavailable</span></li>';
  q('#us-lo').innerHTML = L.us.regionTails ? `<li><span>${L.us.regionTails.lo.region}</span><b>${fmt(L.us.regionTails.lo.v)}</b></li>` : '<li><span>Unavailable</span></li>';

  /* ── geometry ── */
  const W = [1000, 520], U = [1000, 600];
  let usPoint = [500, 200], drawn = false, wLand = null;

  const scaleFor = v => RAMP[clamp(Math.round((v - 1) / 6 * 8), 0, 8)];

  Promise.all([
    d3.json('./static/geo/countries-110m.json'),
    d3.json('./static/geo/states-10m.json')
  ]).then(([wt, ut]) => {
    /* world */
    const countries = topojson.feature(wt, wt.objects.countries);
    const proj = d3.geoNaturalEarth1().fitExtent([[10, 12], [W[0] - 10, W[1] - 12]], countries);
    const path = d3.geoPath(proj);

    q('#w-grat').setAttribute('d', path(d3.geoGraticule10()));
    q('#w-sphere').setAttribute('d', path({ type: 'Sphere' }));

    const land = q('#w-land');
    land.innerHTML = countries.features.map(f => {
      // Integration point 2: join on ISO 3166-1 numeric, which is what
      // world-atlas keys its feature ids on -- L.world.byIso comes
      // straight from /world/cross-section keyed the same way.
      const v = L.world.byIso[+f.id];
      const d = path(f);
      if (!d) return '';
      return `<path d="${d}" fill="${v == null ? 'none' : scaleFor(v)}" fill-opacity="${v == null ? 0 : 0.5}"/>`;
    }).join('');
    wLand = q('#w-lines');
    wLand.innerHTML = countries.features.map(f => {
      const d = path(f); return d ? `<path d="${d}"/>` : '';
    }).join('');

    const usa = countries.features.find(f => +f.id === 840);
    if (usa) q('#w-usa').setAttribute('d', path(usa));
    usPoint = proj([-98.5, 39.5]);

    /* united states, by state */
    const states = topojson.feature(ut, ut.objects.states);
    const projU = d3.geoAlbersUsa().fitExtent([[14, 14], [U[0] - 14, U[1] - 14]], states);
    const pathU = d3.geoPath(projU);
    q('#u-fill').innerHTML = states.features.map(f => {
      // Integration point 3: stateVal() is gone. This is a plain lookup
      // into { FIPS -> region's published CPI } from GET /regions/us --
      // no per-state jitter is invented.
      const region = L.us.stateRegion[f.id];
      const v = L.us.stateValues[f.id];
      const d = pathU(f);
      if (!d || v == null) return '';
      const name = L.us.stateNames?.[f.id] || f.properties.name;
      return `<path d="${d}" fill="${scaleFor(v)}" fill-opacity="0.62"><title>${name} — ${v.toFixed(1)}% (modelled: ${region} region CPI)</title></path>`;
    }).join('');
    q('#u-lines').innerHTML = states.features.map(f => {
      const d = pathU(f); return d ? `<path d="${d}"/>` : '';
    }).join('');
    q('#u-outline').setAttribute('d', pathU(topojson.merge(ut, ut.objects.states.geometries)));

    document.body.setAttribute('data-maps', 'ready');
    frame();
  }).catch(e => {
    console.error('showcase: map geometry failed to load', e);
    document.body.setAttribute('data-maps', 'failed');
  });

  /* ── the line draw-in: the world is inked once, on arrival ── */
  function draw() {
    if (drawn || !wLand) return; drawn = true;
    [...wLand.children].forEach((p, i) => {
      const len = p.getTotalLength() || 1;
      p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
      p.style.transition = `stroke-dashoffset 900ms cubic-bezier(.4,0,.2,1) ${Math.min(900, i * 5)}ms`;
      requestAnimationFrame(() => { p.style.strokeDashoffset = 0; });
    });
  }

  /* ── the scroll ── */
  let p = 0, raf = 0;
  function measure() {
    if (flat()) { p = 1; return; }
    const r = track.getBoundingClientRect();
    const run = track.offsetHeight - innerHeight;
    p = clamp(-r.top / (run || 1), 0, 1);
  }
  function apply() {
    if (flat()) {
      document.body.setAttribute('data-flat', '');
      setVars(1, 0, 1, 1, 1, 1, 1);
      draw();
      return;
    }
    document.body.removeAttribute('data-flat');
    if (p > 0.005 || track.getBoundingClientRect().top < innerHeight * 0.8) draw();
    const k = 1 + ease(span(p, 0.20, 0.52)) * 6.2;
    setVars(
      1 - span(p, 0.30, 0.44),               // act 1 copy
      k,                                      // world zoom
      1 - span(p, 0.32, 0.47),                // world opacity
      span(p, 0.34, 0.50),                    // us opacity
      0.80 + span(p, 0.28, 0.56) * 0.20,      // us scale
      span(p, 0.46, 0.56),                    // act 2 copy
      span(p, 0.56, 0.92)                     // act 2 reveal / bar growth
    );
    railFill.style.transform = `scaleY(${p})`;
    const active = p < 0.42 ? 0 : 1;
    acts.forEach((d, i) => d.toggleAttribute('data-on', i === active));
  }
  function setVars(a1, k, wo, uo, us, a2, rev) {
    const s = stage.style;
    s.setProperty('--a1', a1); s.setProperty('--wo', wo);
    s.setProperty('--uo', uo); s.setProperty('--us', us);
    s.setProperty('--a2', a2); s.setProperty('--rev', rev);
    q('#w-zoom').setAttribute('transform',
      `translate(${usPoint[0]} ${usPoint[1]}) scale(${k}) translate(${-usPoint[0]} ${-usPoint[1]})`);
  }
  function frame() { measure(); apply(); }
  function onScroll() { if (raf) return; raf = requestAnimationFrame(() => { raf = 0; frame(); }); }

  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', onScroll);
  frame();
})();
