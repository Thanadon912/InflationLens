import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, loadLensData, resolveEntity } from "../api/lensClient";
import type {
  AdjustmentCode,
  BasketWeights,
  GeographyCode,
  LensData,
  MeasureItem,
  WindowCode,
} from "../types/lens";
import {
  GEO_LABELS,
  WINDOW_LABELS,
  axisPosition,
  buildAxisScale,
  formatMoM,
  formatPercent,
  layoutAxisDots,
} from "../utils/format";

const GEO_OPTIONS: GeographyCode[] = ["USA", "EA"];
const WINDOW_OPTIONS: Array<{ id: WindowCode; label: string }> = [
  { id: "12m", label: "12-month" },
  { id: "1m", label: "1-month" },
  { id: "6m", label: "6-month annualised" },
];
const ADJUSTMENT_OPTIONS: Array<{ id: AdjustmentCode; label: string }> = [
  { id: "as_published", label: "As published" },
  { id: "sa", label: "Seasonally adjusted" },
  { id: "nsa", label: "Not seasonally adjusted" },
];

interface WorkbenchPageProps {
  initialGeo: GeographyCode;
  initialQuery: string;
  initialLens: LensData | null;
  initialStale: boolean;
  initialAlertMessage: string | null;
  initialUnsupportedQuery?: string | null;
}

export function WorkbenchPage({
  initialGeo,
  initialQuery,
  initialLens,
  initialStale,
  initialAlertMessage,
  initialUnsupportedQuery = null,
}: WorkbenchPageProps) {
  const [geo, setGeo] = useState<GeographyCode>(initialGeo);
  const [unsupportedQuery, setUnsupportedQuery] = useState<string | null>(
    initialUnsupportedQuery
  );
  const [windowCode, setWindowCode] = useState<WindowCode>("12m");
  const [adjustment, setAdjustment] = useState<AdjustmentCode>("as_published");
  const [searchQuery, setSearchQuery] = useState<string>(initialQuery);
  const [weights, setWeights] = useState<BasketWeights>({
    housing: 34,
    food: 13,
    energy: 7,
  });

  const [lens, setLens] = useState<LensData | null>(initialLens);
  const [stale, setStale] = useState<boolean>(initialStale);
  const [alertMessage, setAlertMessage] = useState<string | null>(
    initialAlertMessage
  );
  const [isNarrow, setIsNarrow] = useState<boolean>(() =>
    typeof window !== "undefined" ? window.innerWidth < 640 : false
  );

  useEffect(() => {
    const handleResize = () => setIsNarrow(window.innerWidth < 640);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);
  const requestSeqRef = useRef(0);

  const fetchScope = useCallback(
    async (
      targetGeo: GeographyCode,
      targetWin: WindowCode,
      targetAdj: AdjustmentCode
    ) => {
      const seq = ++requestSeqRef.current;
      try {
        const data = await loadLensData(targetGeo, {
          window: targetWin,
          adjustment: targetAdj,
        });
        if (seq !== requestSeqRef.current) return;
        document.body.removeAttribute("data-lens");
        setAlertMessage(null);
        setStale(false);
        setLens(data);
      } catch (err) {
        if (seq !== requestSeqRef.current) return;
        console.error(
          `WorkbenchPage: could not reach the engine at ${API_BASE}`,
          err
        );
        document.body.setAttribute("data-lens", "unavailable");
        setAlertMessage(
          "The engine could not be reached. Figures on this screen may be stale or empty."
        );
        setStale(true);
      }
    },
    []
  );

  const handleGeoChange = (nextGeo: GeographyCode) => {
    setUnsupportedQuery(null);
    setSearchQuery("");
    setGeo(nextGeo);
    void fetchScope(nextGeo, windowCode, adjustment);
  };

  const handleWindowChange = (nextWindow: WindowCode) => {
    setWindowCode(nextWindow);
    void fetchScope(geo, nextWindow, adjustment);
  };

  const handleAdjustmentChange = (nextAdj: AdjustmentCode) => {
    setAdjustment(nextAdj);
    void fetchScope(geo, windowCode, nextAdj);
  };

  const handleSearchInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchQuery(val);
    const trimmed = val.trim().toLowerCase();
    if (!trimmed) {
      if (unsupportedQuery) {
        setUnsupportedQuery(null);
        void fetchScope(geo, windowCode, adjustment);
      }
      return;
    }
    try {
      const matches = await resolveEntity(trimmed);
      if (matches.length > 0 && matches[0].id !== geo) {
        const nextGeo = matches[0].id;
        setUnsupportedQuery(null);
        setGeo(nextGeo);
        void fetchScope(nextGeo, windowCode, adjustment);
      }
    } catch {
      // Ignore transient search errors while typing
    }
  };

  const handleSearchKeyDown = async (
    e: React.KeyboardEvent<HTMLInputElement>
  ) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const trimmed = searchQuery.trim();
    if (!trimmed) return;
    try {
      const matches = await resolveEntity(trimmed.toLowerCase());
      if (matches.length > 0) {
        const nextGeo = matches[0].id;
        setUnsupportedQuery(null);
        setGeo(nextGeo);
        void fetchScope(nextGeo, windowCode, adjustment);
      } else {
        // Query specified a country that the multi-measure engine cannot compute
        setUnsupportedQuery(trimmed);
        setLens(null);
        setStale(true);
        setAlertMessage(
          `“${trimmed}” is not currently supported by the calculation engine. The engine currently computes multi-dimensional inflation only for the United States (USA) and Euro area (EA).`
        );
        document.body.setAttribute("data-lens", "unavailable");
      }
    } catch {
      // Ignore transient search errors
    }
  };

  // Every input is a 12-month category rate from /categories, so the
  // estimate stays on one time basis whatever Window/Adjustment is
  // selected. The unassigned weight is priced at the mean of the other
  // published categories -- never at a headline rate from another window.
  const basketEstimate = useMemo(() => {
    if (!lens || stale) return null;
    const cats = Object.fromEntries(
      lens.us.categories.map((c) => [c.name, c.v])
    );
    const shelter = cats.Housing;
    const food = cats.Food;
    const energy = cats.Energy;
    const others = lens.us.categories
      .filter((c) => !["Housing", "Food", "Energy"].includes(c.name))
      .map((c) => c.v);
    const rest = others.length
      ? others.reduce((a, b) => a + b, 0) / others.length
      : null;
    if (shelter == null || food == null || energy == null || rest == null) {
      return null;
    }
    const restWeight = Math.max(
      0,
      100 - weights.housing - weights.food - weights.energy
    );
    const v =
      (weights.housing * shelter +
        weights.food * food +
        weights.energy * energy +
        restWeight * rest) /
      100;
    return `${v.toFixed(1)}%`;
  }, [lens, stale, weights]);

  const measures = lens?.us.measures ?? [];
  const withValues = useMemo(
    () =>
      measures.filter((m): m is MeasureItem & { yoy: number } => m.yoy != null),
    [measures]
  );

  const label = unsupportedQuery
    ? unsupportedQuery.length <= 3
      ? unsupportedQuery.toUpperCase()
      : unsupportedQuery.charAt(0).toUpperCase() + unsupportedQuery.slice(1)
    : GEO_LABELS[geo] || geo;
  const cpi = measures.find((m) => m.id === "cpi") || measures[0];
  const spreadTxt = lens?.us.spread
    ? `${(lens.us.spread.hi - lens.us.spread.lo).toFixed(1)} pp`
    : "—";

  // The axis is scaled to the values actually on screen: a fixed 1.8–5%
  // range crowded every 12-month dot into one corner and threw every
  // 1-month dot off the left edge.
  const axisScale = useMemo(
    () => buildAxisScale(withValues.map((m) => m.yoy)),
    [withValues]
  );
  const axisLayout = useMemo(
    () =>
      layoutAxisDots(
        withValues.map((m) => ({ id: m.id, code: m.code, v: m.yoy })),
        axisScale,
        isNarrow ? 18 : 12
      ),
    [withValues, axisScale, isNarrow]
  );
  // A 2% target is an annual-rate concept; drawing it against
  // month-on-month changes would invite a false comparison.
  const showTarget =
    windowCode !== "1m" && 2 >= axisScale.lo && 2 <= axisScale.hi;

  const visibleSources = useMemo(
    () =>
      (lens?.sources ?? []).filter((s) =>
        s.cov
          .split(",")
          .map((c) => c.trim().toUpperCase())
          .includes(geo)
      ),
    [lens, geo]
  );

  const categories = lens?.us.categories ?? [];
  const maxCategoryValue = Math.max(1, ...categories.map((c) => c.v));

  const stateRows = useMemo(() => {
    if (!lens || geo !== "USA") return [];
    return Object.entries(lens.us.stateRegion)
      .map(([id, region]) => ({
        id,
        name: lens.us.stateNames[id] || id,
        region,
        v: lens.us.stateValues[id],
      }))
      .filter((s): s is typeof s & { v: number } => s.v != null)
      .sort((a, b) => b.v - a.v);
  }, [lens, geo]);

  const normalizedFilter = searchQuery.trim().toLowerCase();
  const isEntitySearch =
    normalizedFilter !== "" &&
    [
      "usa",
      "us",
      "united states",
      "america",
      "ea",
      "euro area",
      "eurozone",
      "europe",
      "euro",
    ].some((alias) => alias.includes(normalizedFilter));
  const tableFilter = isEntitySearch ? "" : normalizedFilter;
  const filterMatches =
    tableFilter === ""
      ? null
      : categories.filter((c) => c.name.toLowerCase().includes(tableFilter))
          .length +
        stateRows.filter((s) =>
          `${s.name} ${s.region}`.toLowerCase().includes(tableFilter)
        ).length;

  const handleExportCsv = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    if (!lens) return;
    const lines = [
      "code,name,period,yoy_percent,mom_percent,publisher,coverage",
      ...lens.us.measures.map(
        (m) =>
          `"${m.code}","${m.name}","${m.period || ""}",${m.yoy ?? ""},${
            m.mom ?? ""
          },"${m.src}","${m.coverage}"`
      ),
    ];
    const blob = new Blob([lines.join("\n")], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `inflation-lens-${geo.toLowerCase()}-${windowCode}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div id="lens-alert" role="alert" hidden={!alertMessage}>
        {alertMessage || ""}
      </div>

      <header className="top">
        <div className="bar">
          <a className="brand" href="index.html">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="M11 7v8M7 11h8" />
              <path d="M16.2 16.2 21 21" />
            </svg>
            Inflation Lens
          </a>
          <div className="sbox">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="M16.2 16.2 21 21" />
            </svg>
            <input
              id="q"
              type="search"
              value={searchQuery}
              onChange={handleSearchInput}
              onKeyDown={handleSearchKeyDown}
              placeholder="Search United States or Euro area, or filter this screen"
              aria-label="Search a geography, or filter this screen"
            />
          </div>
          <span className="who" id="who">
            {label}
          </span>
        </div>
      </header>

      <div className="work">
        <aside className="pane left">
          <div className="grp">
            <h6>Geography</h6>
            <div
              className="opts"
              role="group"
              aria-label="Geography"
              id="geo-rail"
            >
              {GEO_OPTIONS.map((g) => (
                <button
                  key={g}
                  type="button"
                  data-geo={g}
                  aria-pressed={!unsupportedQuery && geo === g}
                  onClick={() => handleGeoChange(g)}
                >
                  {GEO_LABELS[g]}
                </button>
              ))}
            </div>
          </div>

          <div className="grp">
            <h6>Window</h6>
            <div
              className="opts"
              role="group"
              aria-label="Window"
              id="window-rail"
            >
              {WINDOW_OPTIONS.map((w) => (
                <button
                  key={w.id}
                  type="button"
                  data-window={w.id}
                  aria-pressed={windowCode === w.id}
                  onClick={() => handleWindowChange(w.id)}
                >
                  {w.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grp">
            <h6>Adjustment</h6>
            <div
              className="opts"
              role="group"
              aria-label="Adjustment"
              id="adjustment-rail"
            >
              {ADJUSTMENT_OPTIONS.map((adj) => (
                <button
                  key={adj.id}
                  type="button"
                  data-adjustment={adj.id}
                  aria-pressed={adjustment === adj.id}
                  onClick={() => handleAdjustmentChange(adj.id)}
                >
                  {adj.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grp">
            <h6>Your basket</h6>
            <div className="wt">
              <label>
                Housing <b id="w1v">{weights.housing}%</b>
                <input
                  id="w1"
                  type="range"
                  min={0}
                  max={60}
                  value={weights.housing}
                  onChange={(e) =>
                    setWeights((prev) => ({
                      ...prev,
                      housing: Number(e.target.value),
                    }))
                  }
                  onInput={(e) =>
                    setWeights((prev) => ({
                      ...prev,
                      housing: Number((e.target as HTMLInputElement).value),
                    }))
                  }
                />
              </label>
              <label>
                Food <b id="w2v">{weights.food}%</b>
                <input
                  id="w2"
                  type="range"
                  min={0}
                  max={40}
                  value={weights.food}
                  onChange={(e) =>
                    setWeights((prev) => ({
                      ...prev,
                      food: Number(e.target.value),
                    }))
                  }
                  onInput={(e) =>
                    setWeights((prev) => ({
                      ...prev,
                      food: Number((e.target as HTMLInputElement).value),
                    }))
                  }
                />
              </label>
              <label>
                Energy <b id="w3v">{weights.energy}%</b>
                <input
                  id="w3"
                  type="range"
                  min={0}
                  max={30}
                  value={weights.energy}
                  onChange={(e) =>
                    setWeights((prev) => ({
                      ...prev,
                      energy: Number(e.target.value),
                    }))
                  }
                  onInput={(e) =>
                    setWeights((prev) => ({
                      ...prev,
                      energy: Number((e.target as HTMLInputElement).value),
                    }))
                  }
                />
              </label>
            </div>
            <p className="mini-note" style={{ marginTop: "10px" }}>
              Reweighting recomputes a 12-month rate from published category
              changes; the remaining weight is priced at the average of the
              other categories. The result is yours, not the statistical
              agency&apos;s, and the engine labels it that way.
            </p>
            <p
              style={{ margin: "10px 0 0" }}
              id="ownIdxRow"
              hidden={basketEstimate === null}
            >
              <b className="num" style={{ fontSize: "26px" }} id="ownIdx">
                {basketEstimate ?? "—"}
              </b>{" "}
              <span
                style={{
                  fontSize: "11px",
                  letterSpacing: ".1em",
                  textTransform: "uppercase",
                  color: "color-mix(in srgb,var(--ink) 55%,transparent)",
                }}
              >
                your basket <span className="est">est</span>
              </span>
            </p>
          </div>
        </aside>

        <main
          className="pane"
          id="results"
          data-stale={stale ? "true" : undefined}
        >
          <div className="head">
            <span className="kick" id="head-kick">
              {unsupportedQuery
                ? "Calculation unavailable for this geography"
                : stale
                ? "Live refresh failed — figures below are stale or empty"
                : `Result · resolved from “${label}”`}
            </span>
            <span
              className="est"
              id="stale-tag"
              hidden={!stale && !unsupportedQuery}
            >
              {unsupportedQuery ? "unsupported" : "stale"}
            </span>
            <h1 id="head-name">{label}</h1>
            <div className="meta" id="head-meta">
              {!unsupportedQuery && lens && (
                <>
                  <span>
                    Reference <b>{cpi?.period || "—"}</b>
                  </span>
                  <span>
                    Measures{" "}
                    <b>
                      {withValues.length} of {measures.length}
                    </b>
                  </span>
                  <span>
                    Spread <b>{spreadTxt}</b>
                  </span>
                </>
              )}
            </div>
          </div>

          {unsupportedQuery ? (
            <div
              className="calc-unavailable-card"
              id="calc-unavailable"
              role="region"
              aria-live="polite"
            >
              <div className="unavail-badge">NO CALCULATION PERFORMED</div>
              <h3>Calculation engine cannot resolve “{unsupportedQuery}”</h3>
              <p>
                Inflation Lens strictly adheres to multi-series data integrity.
                We do not substitute invented rates, proxies, or fallback estimates
                for unindexed economies.
              </p>
              <p>
                Official multi-source inflation models (harmonised consumer
                indexes, essential baskets, monetary metrics, and regional
                breakdowns) are currently available for:
              </p>
              <div className="unavail-actions">
                <button
                  type="button"
                  className="btn-switch"
                  onClick={() => handleGeoChange("USA")}
                >
                  Switch to United States (USA)
                </button>
                <button
                  type="button"
                  className="btn-switch"
                  onClick={() => handleGeoChange("EA")}
                >
                  Switch to Euro area (EA)
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="spread">
            <div className="cap">
              <h2 id="spread-h2">
                {lens
                  ? `${measures.length} measure${
                      measures.length === 1 ? "" : "s"
                    }, one axis`
                  : "Seven measures, one axis"}
              </h2>
              <em id="spread-sub">
                {`${
                  WINDOW_LABELS[windowCode] || windowCode
                } percent change · latest published period each`}
              </em>
            </div>
            <div
              className="axis"
              id="axis"
              style={{ height: `${axisLayout.rows * 50 + 34}px` }}
            >
              {lens && (
                <>
                  {axisScale.ticks.map((t) => (
                    <span
                      key={t}
                      className="tick"
                      style={{ left: `${axisPosition(t, axisScale).toFixed(2)}%` }}
                    >
                      <s>{formatPercent(t, false)}</s>
                    </span>
                  ))}
                  {showTarget && (
                    <span
                      className="tick target"
                      style={{ left: `${axisPosition(2, axisScale).toFixed(2)}%` }}
                      title="2% inflation target"
                    >
                      <s>target</s>
                    </span>
                  )}
                  {axisLayout.dots.map((dot) => (
                    <span
                      key={dot.id}
                      className="dot"
                      style={{ left: `${dot.left.toFixed(2)}%`, top: `${dot.row * 50}px` }}
                    >
                      <i />
                      <b>{formatPercent(dot.v)}</b>
                      <span>{dot.code}</span>
                    </span>
                  ))}
                </>
              )}
            </div>
          </div>

          <div className="mgrid" id="mgrid">
            {measures.map((m) => (
              <div key={m.id} className="mcard">
                <span className="c">{m.code}</span>
                {m.mom != null && (
                  <span className="mm">{formatMoM(m.mom)}</span>
                )}
                <span className="v">{formatPercent(m.yoy)}</span>
                <span className="n">
                  {m.name}
                  {m.note
                    ? `. ${m.note}.`
                    : m.coverage === "unavailable"
                      ? " — unavailable this period."
                      : "."}
                </span>
                <span className="s">
                  {m.src} · {m.period || "unavailable"}
                </span>
              </div>
            ))}
          </div>

          {lens && measures.length === 0 && (
            <p className="empty" id="mgrid-empty">
              No {GEO_LABELS[geo] || geo} measure is published with this
              adjustment. Switch Adjustment to &ldquo;As published&rdquo; to see
              every series.
            </p>
          )}

          {filterMatches !== null && (
            <p className="filter-status" id="filter-status" role="status">
              {filterMatches === 0
                ? `No category or state matches “${searchQuery.trim()}”.`
                : `Filtering tables by “${searchQuery.trim()}” — ${filterMatches} row${
                    filterMatches === 1 ? "" : "s"
                  } match.`}
            </p>
          )}

          <div className="two" id="geo-scoped-tables">
            <div className="blk">
              <h2>By category</h2>
              <p className="sub" id="cats-sub">
                {`Essential-cost basket components, 12-month percent change${
                  cpi?.period ? ` · ${cpi.period}` : ""
                }`}
              </p>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Component</th>
                    <th />
                    <th>12-mo</th>
                  </tr>
                </thead>
                <tbody id="cats">
                  {categories.map((c) => {
                    const key = c.name.toLowerCase();
                    const isHidden =
                      tableFilter !== "" && !key.includes(tableFilter);
                    return (
                      <tr key={c.name} data-k={key} hidden={isHidden}>
                        <td>{c.name}</td>
                        <td>
                          <span className="track">
                            <i
                              style={{
                                width: `${(
                                  (c.v / maxCategoryValue) *
                                  100
                                ).toFixed(1)}%`,
                              }}
                            />
                          </span>
                        </td>
                        <td className="v">{formatPercent(c.v)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div
              className="blk"
              id="states-block"
              hidden={geo !== "USA" || stateRows.length === 0}
            >
              <h2>
                By state <span className="est">modelled</span>
              </h2>
              <p className="sub">
                Every state&apos;s figure is its census region&apos;s published
                CPI — BLS publishes no state-level series
              </p>
              <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>State</th>
                    <th>Region</th>
                    <th>12-mo</th>
                  </tr>
                </thead>
                <tbody id="states">
                  {stateRows.map((s) => {
                    const key = `${s.name.toLowerCase()} ${s.region.toLowerCase()}`;
                    const isHidden =
                      tableFilter !== "" && !key.includes(tableFilter);
                    return (
                      <tr key={s.id} data-k={key} hidden={isHidden}>
                        <td>{s.name}</td>
                        <td className="region">{s.region}</td>
                        <td className="v">{formatPercent(s.v)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              </div>
            </div>
          </div>
            </>
          )}
        </main>

        <aside className="pane right">
          <h6>Sources on this screen</h6>
          <ul className="prov" id="prov">
            {visibleSources.map((s) => (
              <li key={s.org}>
                <b>
                  <a href={s.url} target="_blank" rel="noopener noreferrer">
                    {s.org}
                  </a>
                </b>
                <span>{s.series}</span>
                <em>
                  Released {s.latest} · next {s.next}
                </em>
              </li>
            ))}
          </ul>
          <a className="btn-out" href="index.html#sources">
            Full source ledger
          </a>
          <a className="btn-out" href="#export" onClick={handleExportCsv}>
            Export this view (CSV)
          </a>
          <p className="mini-note">
            Every figure above carries its publisher and reference period.
            Modelled values are marked. Prior vintages are retained — nothing is
            silently restated.
          </p>
        </aside>
      </div>
    </>
  );
}
