import { useCallback, useMemo, useRef, useState } from "react";
import { API_BASE, loadLensData, resolveEntity } from "../api/lensClient";
import type {
  AdjustmentCode,
  BasketWeights,
  GeographyCode,
  LensData,
  MeasureItem,
  WindowCode,
} from "../types/lens";
import { GEO_LABELS, WINDOW_LABELS, formatPercent } from "../utils/format";

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
}

export function WorkbenchPage({
  initialGeo,
  initialQuery,
  initialLens,
  initialStale,
  initialAlertMessage,
}: WorkbenchPageProps) {
  const [geo, setGeo] = useState<GeographyCode>(initialGeo);
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
    if (!trimmed) return;
    try {
      const matches = await resolveEntity(trimmed);
      if (matches.length > 0 && matches[0].id !== geo) {
        const nextGeo = matches[0].id;
        setGeo(nextGeo);
        void fetchScope(nextGeo, windowCode, adjustment);
      }
    } catch {
      // Ignore transient search errors while typing
    }
  };

  const basketEstimate = useMemo(() => {
    if (!lens || stale) return null;
    const cats = Object.fromEntries(
      lens.us.categories.map((c) => [c.name, c.v])
    );
    const cpi = lens.us.measures.find((m) => m.id === "cpi");
    const shelter = cats.Housing;
    const food = cats.Food;
    const energy = cats.Energy;
    const rest = cpi?.yoy;
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

  const label = GEO_LABELS[geo] || geo;
  const cpi = measures.find((m) => m.id === "cpi") || measures[0];
  const spreadTxt = lens?.us.spread
    ? `${(lens.us.spread.hi - lens.us.spread.lo).toFixed(1)} pp`
    : "—";

  const axisDots = useMemo(() => {
    const lo = 1.8;
    const hi = 5.0;
    const rowEnd: number[] = [];
    return withValues
      .slice()
      .sort((a, b) => a.yoy - b.yoy)
      .map((m) => {
        const pos = ((m.yoy - lo) / (hi - lo)) * 100;
        let row = 0;
        while (rowEnd[row] != null && pos - rowEnd[row] < 9) row++;
        rowEnd[row] = pos;
        return {
          id: m.id,
          code: m.code,
          yoy: m.yoy,
          left: `${pos.toFixed(2)}%`,
          top: `${row * 32}px`,
        };
      });
  }, [withValues]);

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
                  aria-pressed={geo === g}
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
              Reweighting recomputes the index from published component changes.
              The result is yours, not BLS&apos;s, and the engine labels it that
              way.
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
              {stale
                ? "Live refresh failed — figures below are stale or empty"
                : `Result · resolved from “${label}”`}
            </span>
            <span className="est" id="stale-tag" hidden={!stale}>
              stale
            </span>
            <h1 id="head-name">{label}</h1>
            <div className="meta" id="head-meta">
              {lens && (
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
            <div className="axis" id="axis">
              {lens && (
                <>
                  {[2, 3, 4, 5].map((t) => (
                    <span
                      key={t}
                      className={`tick${t === 2 ? " target" : ""}`}
                      style={{
                        left: `${(((t - 1.8) / (5.0 - 1.8)) * 100).toFixed(
                          2
                        )}%`,
                      }}
                    >
                      <s>{t}%</s>
                    </span>
                  ))}
                  {axisDots.map((dot) => (
                    <span
                      key={dot.id}
                      className="dot"
                      style={{ left: dot.left, top: dot.top }}
                    >
                      <i />
                      <b>{formatPercent(dot.yoy)}</b>
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
                  <span className="mm">
                    {`${m.mom > 0 ? "+" : ""}${m.mom.toFixed(1)} mo`}
                  </span>
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
                        <td>
                          {s.name}
                          <span className="est">modelled</span>
                        </td>
                        <td
                          style={{
                            color:
                              "color-mix(in srgb,var(--ink) 65%,transparent)",
                            fontSize: "12px",
                          }}
                        >
                          {s.region}
                        </td>
                        <td className="v">{formatPercent(s.v)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </main>

        <aside className="pane right">
          <h6>Sources on this screen</h6>
          <ul className="prov" id="prov">
            {lens?.sources.slice(0, 4).map((s) => (
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
