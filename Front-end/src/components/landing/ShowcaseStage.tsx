import { useEffect, useRef, useState } from "react";
import {
  geoAlbersUsa,
  geoGraticule10,
  geoNaturalEarth1,
  geoPath,
} from "d3-geo";
import { feature, merge } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import type { FeatureCollection, Geometry } from "geojson";
import type { LensData } from "../../types/lens";
import {
  STEEL_RAMP,
  clamp,
  easeInOutQuad,
  formatPercent,
  scaleForRate,
  span,
} from "../../utils/format";

interface ShowcaseStageProps {
  lens: LensData | null;
  unavailable: boolean;
}

interface WorldCountryPath {
  key: string;
  id: number;
  d: string;
}

interface UsStatePath {
  id: string;
  name: string;
  d: string;
}

interface GeometryState {
  sphereD: string;
  gratD: string;
  usaHighlightD: string;
  usCenterPoint: [number, number];
  usTargetPoint: [number, number];
  worldCountries: WorldCountryPath[];
  usStates: UsStatePath[];
  usOutlineD: string;
}

const WORLD_SIZE: [number, number] = [1000, 520];
const US_SIZE: [number, number] = [1000, 600];

export function ShowcaseStage({ lens, unavailable }: ShowcaseStageProps) {
  const trackRef = useRef<HTMLElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const wZoomRef = useRef<SVGGElement | null>(null);
  const wLinesRef = useRef<SVGGElement | null>(null);
  const railFillRef = useRef<HTMLSpanElement | null>(null);
  const dot0Ref = useRef<HTMLElement | null>(null);
  const dot1Ref = useRef<HTMLElement | null>(null);
  const drawnRef = useRef(false);

  const [geo, setGeo] = useState<GeometryState | null>(null);

  useEffect(() => {
    if (!lens) return;
    let cancelled = false;

    Promise.all([
      fetch("./static/geo/countries-110m.json").then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Topology>;
      }),
      fetch("./static/geo/states-10m.json").then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Topology>;
      }),
    ])
      .then(([wt, ut]) => {
        if (cancelled) return;
        const countriesObj = wt.objects.countries as GeometryCollection;
        const countries = feature(
          wt,
          countriesObj
        ) as FeatureCollection<Geometry>;
        const proj = geoNaturalEarth1().fitExtent(
          [
            [10, 12],
            [WORLD_SIZE[0] - 10, WORLD_SIZE[1] - 12],
          ],
          countries
        );
        const path = geoPath(proj);

        const sphereD = path({ type: "Sphere" }) || "";
        const gratD = path(geoGraticule10()) || "";

        const worldCountries: WorldCountryPath[] = [];
        countries.features.forEach((f, idx) => {
          const d = path(f);
          if (d) {
            worldCountries.push({
              key: `${f.id ?? idx}-${idx}`,
              id: Number(f.id),
              d,
            });
          }
        });

        const usaFeature = countries.features.find((f) => Number(f.id) === 840);
        const usaHighlightD = usaFeature ? path(usaFeature) || "" : "";
        const projectedCenter = proj([-98.5, 39.5]) || [500, 200];

        const statesObj = ut.objects.states as GeometryCollection<{
          name?: string;
        }>;
        const states = feature(
          ut,
          statesObj
        ) as FeatureCollection<Geometry, { name?: string }>;
        const projU = geoAlbersUsa().fitExtent(
          [
            [14, 14],
            [US_SIZE[0] - 14, US_SIZE[1] - 14],
          ],
          states
        );
        const pathU = geoPath(projU);

        const usStates: UsStatePath[] = [];
        states.features.forEach((f, idx) => {
          const d = pathU(f);
          if (d) {
            usStates.push({
              id: String(f.id ?? idx),
              name: f.properties?.name || String(f.id ?? idx),
              d,
            });
          }
        });

        const mergedStates = merge(ut, statesObj.geometries as never);
        const usOutlineD = pathU(mergedStates) || "";

        setGeo({
          sphereD,
          gratD,
          usaHighlightD,
          usCenterPoint: [projectedCenter[0], projectedCenter[1]],
          usTargetPoint: [505, 237],
          worldCountries,
          usStates,
          usOutlineD,
        });
        document.body.setAttribute("data-maps", "ready");
      })
      .catch((err: unknown) => {
        console.error("ShowcaseStage: map geometry failed to load", err);
        document.body.setAttribute("data-maps", "failed");
      });

    return () => {
      cancelled = true;
    };
  }, [lens]);

  useEffect(() => {
    if (!lens || !geo) return;

    const track = trackRef.current;
    const stage = stageRef.current;
    const wZoom = wZoomRef.current;
    const wLines = wLinesRef.current;
    const railFill = railFillRef.current;
    if (!track || !stage || !wZoom || !railFill) return;

    const isFlat = () =>
      window.matchMedia("(max-width:880px)").matches ||
      window.matchMedia("(prefers-reduced-motion:reduce)").matches;

    const drawLines = () => {
      if (drawnRef.current || !wLines) return;
      drawnRef.current = true;
      Array.from(wLines.children).forEach((child, i) => {
        const pathEl = child as SVGPathElement;
        const len =
          typeof pathEl.getTotalLength === "function"
            ? pathEl.getTotalLength() || 1
            : 1;
        pathEl.style.strokeDasharray = `${len}`;
        pathEl.style.strokeDashoffset = `${len}`;
        pathEl.style.transition = `stroke-dashoffset 900ms cubic-bezier(.4,0,.2,1) ${Math.min(
          900,
          i * 5
        )}ms`;
        requestAnimationFrame(() => {
          pathEl.style.strokeDashoffset = "0";
        });
      });
    };

    const setVars = (
      a1: number,
      k: number,
      wo: number,
      uo: number,
      us: number,
      a2: number,
      rev: number,
      gratOp = 1,
      tailOp = 1,
      camProgress = 0
    ) => {
      const s = stage.style;
      s.setProperty("--a1", String(a1));
      s.setProperty("--wo", String(wo));
      s.setProperty("--uo", String(uo));
      s.setProperty("--us", String(us));
      s.setProperty("--a2", String(a2));
      s.setProperty("--rev", String(rev));
      s.setProperty("--grat-op", String(gratOp));
      s.setProperty("--tail-op", String(tailOp));

      const [cx, cy] = geo.usCenterPoint;
      const [tx, ty] = geo.usTargetPoint;
      const curX = cx + (tx - cx) * camProgress;
      const curY = cy + (ty - cy) * camProgress;
      wZoom.setAttribute(
        "transform",
        `translate(${curX} ${curY}) scale(${k}) translate(${-cx} ${-cy})`
      );
    };

    let p = 0;
    let raf = 0;

    const frame = () => {
      if (isFlat()) {
        p = 1;
        document.body.setAttribute("data-flat", "");
        setVars(1, 1, 1, 1, 1, 1, 1, 1, 1, 0);
        drawLines();
        return;
      }
      const r = track.getBoundingClientRect();
      const run = track.offsetHeight - window.innerHeight;
      p = clamp(-r.top / (run || 1), 0, 1);

      document.body.removeAttribute("data-flat");
      if (p > 0.005 || r.top < window.innerHeight * 0.8) {
        drawLines();
      }

      // Camera smoothly zooms and tracks into USA position
      const camT = easeInOutQuad(span(p, 0.18, 0.44));
      const k = 1 + camT * 2.77;

      // Declutter macro elements as zoom approaches USA
      const gratOp = 1 - span(p, 0.14, 0.26);
      const tailOp = 1 - span(p, 0.16, 0.28);

      // Act 1 text glides out before Act 2 enters
      const a1 = 1 - span(p, 0.28, 0.38);

      // Clean cross-dissolve between world map and state-level US map
      const wo = 1 - span(p, 0.37, 0.46);
      const uo = span(p, 0.40, 0.48);

      // US map settles cleanly into view
      const us = 0.95 + span(p, 0.40, 0.52) * 0.05;

      // Act 2 arrives with full clarity
      const a2 = span(p, 0.43, 0.52);
      const rev = span(p, 0.44, 0.54);

      setVars(a1, k, wo, uo, us, a2, rev, gratOp, tailOp, camT);
      railFill.style.transform = `scaleY(${p})`;
      const active = p < 0.40 ? 0 : 1;
      dot0Ref.current?.toggleAttribute("data-on", active === 0);
      dot1Ref.current?.toggleAttribute("data-on", active === 1);
    };

    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        frame();
      });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    frame();

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [lens, geo]);

  const headlineUnavailable = !lens || lens.world.headline.v == null;
  const maxCat = lens
    ? Math.max(1, ...lens.us.categories.map((c) => c.v))
    : 1;

  return (
    <section
      id="showcase"
      ref={trackRef}
      aria-label="How the engine sees the world, then the United States"
    >
      <div id="stage" ref={stageRef}>
        <div className="mapw m-a" aria-hidden="true">
          <svg
            id="map-world"
            viewBox="0 0 1000 520"
            preserveAspectRatio="xMidYMid meet"
          >
            <g id="w-zoom" ref={wZoomRef}>
              <path id="w-sphere" d={geo?.sphereD || ""} />
              <path id="w-grat" d={geo?.gratD || ""} />
              <g id="w-land">
                {geo &&
                  lens &&
                  geo.worldCountries.map((f) => {
                    const v = lens.world.byIso[String(f.id)];
                    return (
                      <path
                        key={f.key}
                        d={f.d}
                        fill={v == null ? "none" : scaleForRate(v)}
                        fillOpacity={v == null ? 0 : 0.5}
                      />
                    );
                  })}
              </g>
              <g id="w-lines" ref={wLinesRef}>
                {geo?.worldCountries.map((f) => (
                  <path key={f.key} d={f.d} />
                ))}
              </g>
              <path id="w-usa" d={geo?.usaHighlightD || ""} />
            </g>
          </svg>
        </div>

        <div className="mapw m-b" aria-hidden="true">
          <svg
            id="map-us"
            viewBox="0 0 1000 600"
            preserveAspectRatio="xMidYMid meet"
          >
            <g id="u-fill">
              {geo &&
                lens &&
                geo.usStates.map((st) => {
                  const v = lens.us.stateValues[st.id];
                  if (v == null) return null;
                  const region = lens.us.stateRegion[st.id];
                  const stateName = lens.us.stateNames[st.id] || st.name;
                  return (
                    <path
                      key={st.id}
                      d={st.d}
                      fill={scaleForRate(v)}
                      fillOpacity={0.62}
                    >
                      <title>{`${stateName} — ${v.toFixed(
                        1
                      )}% (modelled: ${region} region CPI)`}</title>
                    </path>
                  );
                })}
            </g>
            <g id="u-lines">
              {geo?.usStates.map((st) => (
                <path key={st.id} d={st.d} />
              ))}
            </g>
            <path id="u-outline" d={geo?.usOutlineD || ""} />
          </svg>
        </div>

        <span className="scrim" aria-hidden="true" />

        <div className="rail" aria-hidden="true">
          <span className="line" />
          <span className="fill" id="rail-fill" ref={railFillRef} />
          <b ref={dot0Ref} data-act-dot data-on="" title="01 · World">
            01<em>World</em>
          </b>
          <b ref={dot1Ref} data-act-dot title="02 · United States">
            02<em>United States</em>
          </b>
        </div>

        <div className="act" id="act1">
          <span className="kick">01 · The world, as one line drawing</span>
          <hr className="rule" />
          <h2>Prices are rising everywhere. Not by the same amount.</h2>
          <div
            className="big"
            id="w-headline-big"
            data-state={
              lens
                ? headlineUnavailable
                  ? "unavailable"
                  : "ready"
                : undefined
            }
          >
            <b id="w-headline-v">
              {lens ? formatPercent(lens.world.headline.v) : "—"}
            </b>
            <span id="w-headline-label">
              {lens
                ? headlineUnavailable
                  ? "Global headline · unavailable"
                  : lens.world.headline.label
                : "Global headline inflation"}
            </span>
          </div>
          <p className="say" id="act1-say">
            A single global figure would be a GDP-weighted average of every
            national basket. It moves slowly, hides its own tails, and describes
            almost nobody&apos;s grocery bill. Look closer.
            {lens && headlineUnavailable
              ? " This engine leaves it blank rather than publish one: it doesn’t yet ingest the population and GDP-PPP weights a weighted global figure needs to be honest, and an unweighted stand-in would be worse than none."
              : ""}
          </p>
          <div className="minis">
            <div>
              <h6>Major economies · latest</h6>
              <ul id="w-regions">
                {lens?.world.regions
                  .filter((r) => r.v != null)
                  .map((r) => (
                    <li key={r.name}>
                      <span>{r.name}</span>
                      <b>{formatPercent(r.v)}</b>
                    </li>
                  ))}
              </ul>
            </div>
            <div>
              <h6>Highest inflation · latest</h6>
              <ul id="w-tails">
                {lens?.world.tails.map((t) => (
                  <li key={t.name}>
                    <span>{t.name}</span>
                    <b>{formatPercent(t.v)}</b>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        <div className="act" id="act2">
          <div className="a2-grid">
            <div>
              <span className="kick">02 · One country, every measure</span>
              <hr className="rule" />
              <h2>The United States, seven ways at once.</h2>
              <p className="say">
                Same country, same month. Seven official measures,{" "}
                {lens?.us.spread
                  ? `${(lens.us.spread.hi - lens.us.spread.lo).toFixed(1)} percentage points`
                  : "2.5 percentage points"}{" "}
                apart. The engine computes all of them side by side — and
                colours all 50 states, because a national rate is an average
                too.
              </p>
              <div className="ledger">
                <ul id="m-rows">
                  {unavailable && (
                    <li className="m-row">
                      <span className="m-note">
                        The engine could not be reached. Figures are
                        unavailable.
                      </span>
                    </li>
                  )}
                  {lens?.us.measures.map((m, i) => {
                    const frac = m.yoy == null ? 0 : clamp(m.yoy / 5, 0, 1);
                    const barColor =
                      STEEL_RAMP[Math.min(8, Math.round(frac * 8) + 1)];
                    return (
                      <li
                        key={m.id}
                        className="m-row"
                        style={{ "--i": i } as React.CSSProperties}
                      >
                        <span className="m-code">{m.code}</span>
                        <span className="m-val">{formatPercent(m.yoy)}</span>
                        <span className="m-bar">
                          <i
                            style={
                              {
                                "--w": `${(frac * 100).toFixed(1)}%`,
                                "--c": barColor,
                              } as React.CSSProperties
                            }
                          />
                        </span>
                        <span className="m-note">{m.note}</span>
                        <span className="m-src">
                          {m.src} · {m.period || "unavailable"}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>
            <div className="cats">
              <h6
                style={{
                  margin: "0 0 8px",
                  fontSize: "10px",
                  letterSpacing: ".14em",
                  color: "color-mix(in srgb,var(--paper) 52%,transparent)",
                }}
              >
                {`By category · 12-month, ${lens?.us.asOf || "Jul 2026"}`}
              </h6>
              <ul id="cat-bars">
                {lens?.us.categories.map((c) => (
                  <li key={c.name} className="cat">
                    <span className="cat-n">{c.name}</span>
                    <span className="cat-b">
                      <i
                        style={
                          {
                            "--w": `${((c.v / maxCat) * 100).toFixed(1)}%`,
                          } as React.CSSProperties
                        }
                      />
                    </span>
                    <span className="cat-v">{formatPercent(c.v, true)}</span>
                  </li>
                ))}
              </ul>
              <div className="minis" style={{ gap: "var(--lead)" }}>
                <div>
                  <h6>Highest estimates</h6>
                  <ul id="us-hi">
                    {lens ? (
                      lens.us.regionTails ? (
                        <li>
                          <span>{lens.us.regionTails.hi.region}</span>
                          <b>{formatPercent(lens.us.regionTails.hi.v)}</b>
                        </li>
                      ) : (
                        <li>
                          <span>Unavailable</span>
                        </li>
                      )
                    ) : null}
                  </ul>
                </div>
                <div>
                  <h6>Lowest estimates</h6>
                  <ul id="us-lo">
                    {lens ? (
                      lens.us.regionTails ? (
                        <li>
                          <span>{lens.us.regionTails.lo.region}</span>
                          <b>{formatPercent(lens.us.regionTails.lo.v)}</b>
                        </li>
                      ) : (
                        <li>
                          <span>Unavailable</span>
                        </li>
                      )
                    ) : null}
                  </ul>
                </div>
              </div>
              <p className="flag">
                State shading is{" "}
                <strong
                  style={{
                    font: "inherit",
                    textTransform: "uppercase",
                    letterSpacing: ".1em",
                  }}
                >
                  modelled
                </strong>{" "}
                — BLS publishes no state-level CPI. Every state&apos;s figure is
                its census region&apos;s own published CPI, and the engine
                labels every modelled figure as one. Hover a state to see its
                region.
              </p>
            </div>
          </div>
        </div>

        <span className="hintscroll">Scroll</span>
      </div>
    </section>
  );
}
