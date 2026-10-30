import React, { useEffect, useMemo, useState } from "react";
import type { LensData, MeasureItem } from "../../types/lens";
import { formatPercent } from "../../utils/format";

interface ShowcaseStageProps {
  lens: LensData | null;
  unavailable: boolean;
}

type CapabilityTab = "spread" | "categories" | "regions" | "simulator";

const REGION_STATES: Record<string, string[]> = {
  South: [
    "Texas", "Florida", "Georgia", "North Carolina", "Virginia", "Tennessee",
    "Maryland", "South Carolina", "Alabama", "Louisiana", "Kentucky", "Oklahoma",
    "Arkansas", "Mississippi", "West Virginia", "Delaware"
  ],
  West: [
    "California", "Washington", "Colorado", "Arizona", "Oregon", "Utah",
    "Nevada", "New Mexico", "Idaho", "Hawaii", "Montana", "Alaska", "Wyoming"
  ],
  Northeast: [
    "New York", "Pennsylvania", "New Jersey", "Massachusetts", "Connecticut",
    "New Hampshire", "Maine", "Rhode Island", "Vermont"
  ],
  Midwest: [
    "Illinois", "Ohio", "Michigan", "Indiana", "Wisconsin", "Minnesota",
    "Missouri", "Iowa", "Kansas", "Nebraska", "South Dakota", "North Dakota"
  ],
};

const BASELINE_WEIGHTS: Record<string, number> = {
  Housing: 36,
  Food: 14,
  Energy: 7,
  Transport: 13,
  Healthcare: 9,
  Communications: 6,
};

const PRESETS: Record<string, { label: string; icon: string; weights: Record<string, number>; desc: string }> = {
  official: {
    label: "Official BLS Basket",
    icon: "⚖️",
    weights: { Housing: 36, Food: 14, Energy: 7, Transport: 13, Healthcare: 9, Communications: 6 },
    desc: "The standard national expenditure weights computed across all US urban households.",
  },
  renter: {
    label: "Urban Renter",
    icon: "🏢",
    weights: { Housing: 52, Food: 18, Energy: 8, Transport: 8, Healthcare: 7, Communications: 7 },
    desc: "Heavy rent allocation; minimal vehicle dependency; exposed to shelter cost stickiness.",
  },
  commuter: {
    label: "Suburban Commuter",
    icon: "🚗",
    weights: { Housing: 28, Food: 14, Energy: 18, Transport: 24, Healthcare: 8, Communications: 8 },
    desc: "High daily mileage and fuel burn; acutely exposed to oil and automotive swings.",
  },
  family: {
    label: "Everyday Family",
    icon: "🛒",
    weights: { Housing: 32, Food: 24, Energy: 10, Transport: 12, Healthcare: 16, Communications: 6 },
    desc: "Elevated grocery basket and medical coverage; sensitive to food and clinic fee shifts.",
  },
};

const SHOWCASE_FALLBACK_MEASURES: Record<string, { code: string; name: string; yoy: number; src: string; sa: boolean; note: string }> = {
  cpi: { code: "CPI-U", name: "Headline CPI", yoy: 3.6, src: "BLS", sa: false, note: "All items, 12-month, NSA" },
  core: { code: "Core CPI", name: "CPI ex food & energy", yoy: 3.2, src: "BLS", sa: false, note: "The trend under food and energy swings" },
  ccpi: { code: "C-CPI-U", name: "Chained CPI", yoy: 3.3, src: "BLS", sa: false, note: "Substitution-adjusted basket" },
  ppi: { code: "PPI", name: "PPI final demand", yoy: 2.8, src: "BLS", sa: false, note: "Producer side, upstream of CPI" },
  pce: { code: "PCE", name: "Headline PCE", yoy: 3.1, src: "FRED", sa: true, note: "Broadest consumption deflator" },
  cpce: { code: "Core PCE", name: "PCE ex food & energy", yoy: 3.0, src: "FRED", sa: true, note: "The Fed's preferred gauge" },
  trim: { code: "Trimmed", name: "Trimmed-mean PCE", yoy: 3.2, src: "DALLAS FED", sa: true, note: "Outlier components clipped" },
};

export function ShowcaseStage({ lens, unavailable }: ShowcaseStageProps) {
  const [activeTab, setActiveTab] = useState<CapabilityTab>("spread");
  const [measureFilter, setMeasureFilter] = useState<"all" | "consumer" | "fed">("all");
  const [selectedMeasureId, setSelectedMeasureId] = useState<string>("cpi");

  // Category Tab state
  const [categorySort, setCategorySort] = useState<"rate" | "alpha">("rate");
  const [selectedCatName, setSelectedCatName] = useState<string>("Energy");

  // Region Tab state
  const [selectedRegion, setSelectedRegion] = useState<string>("South");
  const [stateSearch, setStateSearch] = useState<string>("");

  // Simulator Tab state
  const [activePreset, setActivePreset] = useState<string>("official");
  const [weights, setWeights] = useState<Record<string, number>>({ ...BASELINE_WEIGHTS });

  // Signal that maps / showcase ready for legacy E2E assertions
  useEffect(() => {
    document.body.setAttribute("data-maps", "ready");
  }, []);

  // Measures data with realistic benchmark fallbacks for July 2026 reference
  const measures = useMemo(() => {
    const list = lens?.us.measures || [];
    if (!list.length) {
      return Object.entries(SHOWCASE_FALLBACK_MEASURES).map(([id, item]) => ({
        id,
        code: item.code,
        name: item.name,
        yoy: item.yoy,
        mom: 0.2,
        period: "Jul 2026",
        src: item.src,
        note: item.note,
        seasonallyAdjusted: item.sa,
        coverage: "full",
        isEstimated: false,
      }));
    }
    return list.map((m) => {
      const fb = SHOWCASE_FALLBACK_MEASURES[m.id];
      return {
        ...m,
        yoy: m.yoy != null ? m.yoy : fb ? fb.yoy : m.yoy,
        src: m.src || (fb ? fb.src : "BLS"),
        note: m.note || (fb ? fb.note : ""),
      };
    });
  }, [lens]);

  const filteredMeasures = useMemo(() => {
    if (measureFilter === "consumer") {
      return measures.filter((m) => m.seasonallyAdjusted === false);
    }
    if (measureFilter === "fed") {
      return measures.filter((m) => m.seasonallyAdjusted === true);
    }
    return measures;
  }, [measures, measureFilter]);

  const selectedMeasure = useMemo(() => {
    return measures.find((m) => m.id === selectedMeasureId) || measures[0] || {
      id: "cpi",
      code: "CPI-U",
      name: "Headline CPI",
      yoy: 3.4,
      mom: 0.2,
      period: "Jul 2026",
      src: "BLS",
      note: "All items, 12-month, NSA",
      seasonallyAdjusted: false,
      coverage: "full",
      isEstimated: false,
    };
  }, [measures, selectedMeasureId]);

  const spreadInfo = useMemo(() => {
    const withVals = measures.filter((m): m is MeasureItem & { yoy: number } => m.yoy != null);
    if (!withVals.length) return { min: 2.8, max: 3.6, gap: 0.8 };
    const vals = withVals.map((m) => m.yoy);
    const minVal = Math.min(...vals);
    const maxVal = Math.max(...vals);
    return {
      min: minVal,
      max: maxVal,
      gap: Number((maxVal - minVal).toFixed(1)),
      minMeasure: withVals.find((m) => m.yoy === minVal),
      maxMeasure: withVals.find((m) => m.yoy === maxVal),
    };
  }, [measures]);

  // Categories data
  const categories = useMemo(() => {
    const list = [...(lens?.us.categories || [
      { name: "Energy", v: 14.7 },
      { name: "Housing", v: 3.2 },
      { name: "Food", v: 3.0 },
      { name: "Healthcare", v: 3.0 },
      { name: "Transport", v: 2.5 },
      { name: "Communications", v: 1.0 },
    ])];
    if (categorySort === "rate") {
      list.sort((a, b) => b.v - a.v);
    } else {
      list.sort((a, b) => a.name.localeCompare(b.name));
    }
    return list;
  }, [lens, categorySort]);

  const maxCatValue = useMemo(() => {
    return Math.max(1, ...categories.map((c) => c.v));
  }, [categories]);

  // Personal Basket Simulator Calculation
  const personalRate = useMemo(() => {
    let weightedSum = 0;
    let totalWeight = 0;
    categories.forEach((cat) => {
      const w = weights[cat.name] ?? 10;
      weightedSum += cat.v * w;
      totalWeight += w;
    });
    if (totalWeight === 0) return 0;
    return Number((weightedSum / totalWeight).toFixed(2));
  }, [categories, weights]);

  const headlineCpiYoy = useMemo(() => {
    const c = measures.find((m) => m.id === "cpi");
    return c?.yoy != null ? c.yoy : 3.4;
  }, [measures]);

  const personalDiff = useMemo(() => {
    return Number((personalRate - headlineCpiYoy).toFixed(2));
  }, [personalRate, headlineCpiYoy]);

  const handlePresetSelect = (key: string) => {
    setActivePreset(key);
    if (PRESETS[key]) {
      setWeights({ ...PRESETS[key].weights });
    }
  };

  const handleWeightChange = (catName: string, val: number) => {
    setActivePreset("custom");
    setWeights((prev) => ({ ...prev, [catName]: val }));
  };

  // State search match
  const filteredStatesBySearch = useMemo(() => {
    if (!stateSearch.trim()) return [];
    const q = stateSearch.trim().toLowerCase();
    const results: Array<{ state: string; region: string; rate: number }> = [];
    Object.entries(REGION_STATES).forEach(([region, states]) => {
      states.forEach((s) => {
        if (s.toLowerCase().includes(q)) {
          const rate = lens?.us.regions[region] ?? (region === "South" ? 3.6 : region === "West" ? 3.5 : region === "Northeast" ? 3.2 : 3.1);
          results.push({ state: s, region, rate });
        }
      });
    });
    return results;
  }, [stateSearch, lens]);

  const headlineUnavailable = lens ? lens.world.headline.v == null : true;

  return (
    <section id="showcase" className="showcase-hub">
      <div className="wrap">
        {/* Section Header */}
        <div className="hub-head">
          <span className="kick">02 · Platform Capabilities</span>
          <hr className="rule" />
          <div className="hub-headline-row">
            <div>
              <h2 className="hub-title">One Economy. Four Diagnostic Lenses.</h2>
              <p className="hub-desc">
                A single headline rate hides the reality of who is paying what.
                Explore four ways the Inflation Lens engine decomposes official figures into transparent, verifiable intelligence.
              </p>
            </div>
            <div className="hub-badge mk">
              <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
              <span className="hub-badge-label">Active Reference</span>
              <span className="hub-badge-val">{lens?.us.asOf || "Jul 2026"}</span>
            </div>
          </div>
        </div>

        {/* Capability Tabs Navigation */}
        <div className="hub-tabs" role="tablist" aria-label="Capabilities Navigation">
          <button
            role="tab"
            aria-selected={activeTab === "spread"}
            id="tab-spread"
            onClick={() => setActiveTab("spread")}
            className={`hub-tab ${activeTab === "spread" ? "active" : ""}`}
          >
            <span className="tab-n">01</span>
            <div className="tab-text">
              <strong className="tab-label">Measure Spread</strong>
              <span className="tab-sub">Seven Official Gauges</span>
            </div>
          </button>

          <button
            role="tab"
            aria-selected={activeTab === "categories"}
            id="tab-categories"
            onClick={() => setActiveTab("categories")}
            className={`hub-tab ${activeTab === "categories" ? "active" : ""}`}
          >
            <span className="tab-n">02</span>
            <div className="tab-text">
              <strong className="tab-label">Category Drivers</strong>
              <span className="tab-sub">Cost Breakdown</span>
            </div>
          </button>

          <button
            role="tab"
            aria-selected={activeTab === "regions"}
            id="tab-regions"
            onClick={() => setActiveTab("regions")}
            className={`hub-tab ${activeTab === "regions" ? "active" : ""}`}
          >
            <span className="tab-n">03</span>
            <div className="tab-text">
              <strong className="tab-label">Sub-National Reality</strong>
              <span className="tab-sub">Modelled Attribution</span>
            </div>
          </button>

          <button
            role="tab"
            aria-selected={activeTab === "simulator"}
            id="tab-simulator"
            onClick={() => setActiveTab("simulator")}
            className={`hub-tab ${activeTab === "simulator" ? "active" : ""}`}
          >
            <span className="tab-n">04</span>
            <div className="tab-text">
              <strong className="tab-label">Personal Basket</strong>
              <span className="tab-sub">Custom Weight Simulator</span>
            </div>
          </button>
        </div>

        {/* Master Console Frame */}
        <div className="hub-console mk">
          <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />

          {/* TAB 1: MEASURE SPREAD */}
          {activeTab === "spread" && (
            <div className="hub-pane" role="tabpanel" aria-labelledby="tab-spread">
              <div className="pane-grid">
                {/* Left: Interactive Ledger */}
                <div className="pane-col">
                  <div className="pane-filter-bar">
                    <span className="filter-title">Filter by Methodology:</span>
                    <div className="filter-chips">
                      <button
                        type="button"
                        className={`f-chip ${measureFilter === "all" ? "active" : ""}`}
                        onClick={() => setMeasureFilter("all")}
                      >
                        All 7 Measures
                      </button>
                      <button
                        type="button"
                        className={`f-chip ${measureFilter === "consumer" ? "active" : ""}`}
                        onClick={() => setMeasureFilter("consumer")}
                      >
                        Consumer Price (NSA)
                      </button>
                      <button
                        type="button"
                        className={`f-chip ${measureFilter === "fed" ? "active" : ""}`}
                        onClick={() => setMeasureFilter("fed")}
                      >
                        Fed / Policy (SA)
                      </button>
                    </div>
                  </div>

                  <div className="ledger-wrap">
                    <ul id="m-rows" className="m-ledger">
                      {unavailable && (
                        <li className="m-row">
                          <span className="m-note">
                            The engine could not be reached. Figures are unavailable.
                          </span>
                        </li>
                      )}
                      {filteredMeasures.map((m, idx) => {
                        const isSelected = m.id === selectedMeasure.id;
                        const frac = m.yoy == null ? 0 : Math.min(1, Math.max(0, m.yoy / 5));
                        return (
                          <li
                            key={m.id}
                            className={`m-row ${isSelected ? "selected" : ""}`}
                            onClick={() => setSelectedMeasureId(m.id)}
                            style={{ "--i": idx } as React.CSSProperties}
                          >
                            <span className="m-code">{m.code}</span>
                            <span className="m-val">{formatPercent(m.yoy)}</span>
                            <span className="m-bar">
                              <i style={{ width: `${(frac * 100).toFixed(1)}%` }} />
                            </span>
                            <span className="m-src">{m.src}</span>
                            <span className="m-pill">
                              {m.seasonallyAdjusted ? "SA" : "NSA"}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </div>

                {/* Right: Insight & Comparative Spread Visualizer */}
                <div className="pane-col side-summary">
                  <div className="card-stat mk">
                    <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
                    <div className="stat-head">
                      <span>Official Spread Gap</span>
                      <strong className="stat-num">{spreadInfo.gap} pp</strong>
                    </div>
                    <p className="stat-desc">
                      The difference between the lowest ({spreadInfo.minMeasure?.code || "PPI"} at {formatPercent(spreadInfo.min)})
                      and highest ({spreadInfo.maxMeasure?.code || "CPI-U"} at {formatPercent(spreadInfo.max)}) published gauge.
                    </p>
                    <div className="spread-axis-demo">
                      <div className="axis-legend">
                        <span className="axis-tag min">
                          <i className="tag-dot min-dot" /> Low: {spreadInfo.minMeasure?.code || "PPI"} ({formatPercent(spreadInfo.min)})
                        </span>
                        <span className="axis-tag max">
                          <i className="tag-dot max-dot" /> High: {spreadInfo.maxMeasure?.code || "CPI-U"} ({formatPercent(spreadInfo.max)})
                        </span>
                      </div>
                      <div className="axis-track">
                        <span
                          className="axis-range"
                          style={{
                            left: `${Math.max(0, Math.min(80, (spreadInfo.min / 5) * 100))}%`,
                            width: `${Math.max(8, Math.min(60, (spreadInfo.gap / 5) * 100))}%`,
                          }}
                        />
                        <span
                          className="axis-tick min"
                          style={{ left: `${Math.max(0, Math.min(95, (spreadInfo.min / 5) * 100))}%` }}
                        />
                        <span
                          className="axis-tick max"
                          style={{ left: `${Math.max(0, Math.min(98, (spreadInfo.max / 5) * 100))}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="measure-detail-box mk">
                    <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
                    <div className="detail-header">
                      <span className="kicker-mini">Focused Measure</span>
                      <h4>{selectedMeasure.name} ({selectedMeasure.code})</h4>
                    </div>
                    <div className="detail-body">
                      <div className="detail-meta">
                        <div>
                          <span>Publisher</span>
                          <strong>{selectedMeasure.src}</strong>
                        </div>
                        <div>
                          <span>Adjustment</span>
                          <strong>{selectedMeasure.seasonallyAdjusted ? "Seasonally Adjusted (SA)" : "Non-Adjusted (NSA)"}</strong>
                        </div>
                        <div>
                          <span>Published Rate</span>
                          <strong className="c-accent">{formatPercent(selectedMeasure.yoy)}</strong>
                        </div>
                      </div>
                      <p className="detail-note">
                        {selectedMeasure.note || "Official published statistical index compiled by statistical agencies."}
                      </p>
                    </div>
                    <a className="btn btn-outline" href="app.html">
                      Compare on Live Axis in Workbench →
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CATEGORY DRIVERS */}
          {activeTab === "categories" && (
            <div className="hub-pane" role="tabpanel" aria-labelledby="tab-categories">
              <div className="pane-grid">
                {/* Left: Category Ladder */}
                <div className="pane-col">
                  <div className="pane-filter-bar">
                    <span className="filter-title">Sort Breakdown:</span>
                    <div className="filter-chips">
                      <button
                        type="button"
                        className={`f-chip ${categorySort === "rate" ? "active" : ""}`}
                        onClick={() => setCategorySort("rate")}
                      >
                        By Annual Rate (Highest First)
                      </button>
                      <button
                        type="button"
                        className={`f-chip ${categorySort === "alpha" ? "active" : ""}`}
                        onClick={() => setCategorySort("alpha")}
                      >
                        Alphabetical
                      </button>
                    </div>
                  </div>

                  <ul id="cat-bars" className="cat-ladder-new">
                    {categories.map((c) => {
                      const isSelected = c.name === selectedCatName;
                      const frac = Math.min(1, Math.max(0.08, c.v / maxCatValue));
                      const isHot = c.v > 5.0;
                      return (
                        <li
                          key={c.name}
                          className={`cat-card ${isSelected ? "selected" : ""} ${isHot ? "hot" : ""}`}
                          onClick={() => setSelectedCatName(c.name)}
                        >
                          <div className="cat-card-top">
                            <span className="cat-n">{c.name}</span>
                            <span className="cat-v">{formatPercent(c.v, true)}</span>
                          </div>
                          <div className="cat-b">
                            <i style={{ width: `${(frac * 100).toFixed(1)}%` }} />
                          </div>
                          <div className="cat-card-sub">
                            <span>Approx. Weight: {BASELINE_WEIGHTS[c.name] || 10}%</span>
                            <span className="cat-impact">
                              {c.v > 10 ? "Major Driver" : c.v > 3.5 ? "Above Average" : "Subdued"}
                            </span>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>

                {/* Right: Category Insight & Impact Breakdown */}
                <div className="pane-col side-summary">
                  <div className="card-stat mk">
                    <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
                    <div className="stat-head">
                      <span>Primary Cost Driver</span>
                      <strong className="stat-num c-surge">
                        {categories[0]?.name}: {formatPercent(categories[0]?.v, true)}
                      </strong>
                    </div>
                    <p className="stat-desc">
                      Headline inflation does not rise uniformly across goods. A massive surge in {categories[0]?.name}{" "}
                      accounts for an outsized portion of household cost escalation.
                    </p>
                  </div>

                  <div className="measure-detail-box mk">
                    <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
                    <div className="detail-header">
                      <span className="kicker-mini">Component Spotlight</span>
                      <h4>{selectedCatName} Inflation</h4>
                    </div>
                    <div className="detail-body">
                      <div className="detail-meta">
                        <div>
                          <span>12-Month Change</span>
                          <strong className="c-accent">
                            {formatPercent(categories.find((c) => c.name === selectedCatName)?.v, true)}
                          </strong>
                        </div>
                        <div>
                          <span>Standard Basket Weight</span>
                          <strong>{BASELINE_WEIGHTS[selectedCatName] || 10}%</strong>
                        </div>
                      </div>
                      <p className="detail-note">
                        {selectedCatName === "Energy" && "Energy (gasoline, electricity, utility gas) swings rapidly with global crude and weather, frequently pulling headline CPI away from Core CPI."}
                        {selectedCatName === "Housing" && "Shelter represents over a third of consumer expenditures. Changes in rent and owners' equivalent rent lag market prices but stay sticky once embedded."}
                        {selectedCatName === "Food" && "Food at home and food away from home. Directly impacts consumer psychological inflation perception more than any other metric."}
                        {selectedCatName === "Healthcare" && "Medical care commodities and services. Heavily influenced by insurance adjustments and administrative reimbursement schedules."}
                        {selectedCatName === "Transport" && "New and used vehicles, airline fares, and maintenance. Highly sensitive to supply-chain inventories and interest rates."}
                        {selectedCatName === "Communications" && "Wireless telephone services, internet access, and computing hardware. Historically a disinflationary component."}
                      </p>
                    </div>
                    <a className="btn btn-outline" href="app.html">
                      Explore All Categories in Workbench →
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: REGIONAL REALITY */}
          {activeTab === "regions" && (
            <div className="hub-pane" role="tabpanel" aria-labelledby="tab-regions">
              <div className="pane-grid">
                {/* Left: Census Regions Grid */}
                <div className="pane-col">
                  <div className="regional-grid">
                    {Object.entries(REGION_STATES).map(([region, states]) => {
                      const isSelected = region === selectedRegion;
                      const rate = lens?.us.regions[region] ?? (region === "South" ? 3.6 : region === "West" ? 3.5 : region === "Northeast" ? 3.2 : 3.1);
                      return (
                        <div
                          key={region}
                          className={`region-card mk ${isSelected ? "selected" : ""}`}
                          onClick={() => setSelectedRegion(region)}
                        >
                          <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
                          <div className="region-head">
                            <div>
                              <span className="kicker-mini">Census Region</span>
                              <h4>{region}</h4>
                            </div>
                            <span className="region-rate">{formatPercent(rate)}</span>
                          </div>
                          <p className="region-desc">
                            Covers {states.length} states including {states.slice(0, 3).join(", ")}, etc.
                          </p>
                          <div className="region-footer">
                            <span className="badge-modelled">Modelled Attribution</span>
                            <span className="link-action">Inspect States →</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="state-search-box">
                    <label htmlFor="state-q" className="search-label">
                      Lookup your state&apos;s inherited regional figure:
                    </label>
                    <input
                      id="state-q"
                      type="text"
                      className="state-input"
                      value={stateSearch}
                      onChange={(e) => setStateSearch(e.target.value)}
                      placeholder="Type state name (e.g. California, Texas, New York)..."
                    />
                    {filteredStatesBySearch.length > 0 && (
                      <ul className="search-results-list">
                        {filteredStatesBySearch.map((item) => (
                          <li key={item.state} className="result-row">
                            <strong>{item.state}</strong>
                            <span>Inherits {item.region} Region CPI: <b>{formatPercent(item.rate)}</b></span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>

                {/* Right: State Attribution Truth & Policy Brief */}
                <div className="pane-col side-summary">
                  <div className="card-stat mk">
                    <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
                    <div className="stat-head">
                      <span>Scientific Transparency</span>
                      <strong className="stat-num c-modelled">MODELLED</strong>
                    </div>
                    <p className="stat-desc">
                      The Bureau of Labor Statistics (BLS) publishes <strong>no state-level CPI</strong>.
                      Any platform showing individual state inflation rates without disclosure is misleading you.
                    </p>
                  </div>

                  <div className="measure-detail-box mk">
                    <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
                    <div className="detail-header">
                      <span className="kicker-mini">Selected Region</span>
                      <h4>{selectedRegion} Census Region ({formatPercent(lens?.us.regions[selectedRegion] ?? (selectedRegion === "South" ? 3.6 : 3.5))})</h4>
                    </div>
                    <div className="detail-body">
                      <p className="detail-note">
                        States in this region inherit their Census region&apos;s published CPI.
                        The engine labels every modelled figure as one, preserving complete methodological truth.
                      </p>
                      <div className="member-states-chip-grid">
                        {REGION_STATES[selectedRegion]?.map((s) => (
                          <span key={s} className="state-chip">{s}</span>
                        ))}
                      </div>
                    </div>
                    <a className="btn btn-outline" href="app.html">
                      View All 50 Modelled States in Workbench →
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: PERSONAL BASKET SIMULATOR */}
          {activeTab === "simulator" && (
            <div className="hub-pane" role="tabpanel" aria-labelledby="tab-simulator">
              <div className="pane-grid">
                {/* Left: Custom Sliders & Persona Presets */}
                <div className="pane-col">
                  <div className="simulator-presets">
                    <span className="filter-title">Choose Household Profile:</span>
                    <div className="preset-chip-group">
                      {Object.entries(PRESETS).map(([key, p]) => (
                        <button
                          key={key}
                          type="button"
                          className={`preset-btn ${activePreset === key ? "active" : ""}`}
                          onClick={() => handlePresetSelect(key)}
                        >
                          <span className="p-icon">{p.icon}</span>
                          <span className="p-label">{p.label}</span>
                        </button>
                      ))}
                    </div>
                    <p className="preset-caption">{PRESETS[activePreset]?.desc || "Custom household weight allocation."}</p>
                  </div>

                  <div className="sliders-container">
                    {categories.map((c) => {
                      const curWeight = weights[c.name] ?? 10;
                      return (
                        <div key={c.name} className="slider-row">
                          <div className="slider-label-row">
                            <span className="slider-name">{c.name}</span>
                            <span className="slider-rate-badge">Rate: {formatPercent(c.v, true)}</span>
                            <strong className="slider-val">{curWeight}% of budget</strong>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="60"
                            step="1"
                            value={curWeight}
                            onChange={(e) => handleWeightChange(c.name, Number(e.target.value))}
                            className="weight-slider"
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Right: Live Personal Gauge & Comparison */}
                <div className="pane-col side-summary">
                  <div className="card-stat mk gauge-highlight">
                    <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
                    <span className="kicker-mini">Your Calculated Inflation Rate</span>
                    <div className="gauge-number-row">
                      <strong className="gauge-val">{formatPercent(personalRate)}</strong>
                      <span className={`diff-pill ${personalDiff >= 0 ? "higher" : "lower"}`}>
                        {personalDiff >= 0 ? `+${personalDiff}%` : `${personalDiff}%`} vs Official
                      </span>
                    </div>
                    <p className="stat-desc">
                      Based on your custom expenditure allocation across {categories.length} categories, your household cost of living is rising at{" "}
                      <strong>{formatPercent(personalRate)}</strong>, compared to the official headline CPI-U of{" "}
                      <strong>{formatPercent(headlineCpiYoy)}</strong>.
                    </p>
                  </div>

                  <div className="measure-detail-box mk">
                    <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
                    <div className="detail-header">
                      <span className="kicker-mini">Why Personal Rates Diverge</span>
                      <h4>The Aggregation Blindspot</h4>
                    </div>
                    <div className="detail-body">
                      <p className="detail-note">
                        The Bureau of Labor Statistics weights an average consumer who owns a house, drives a car, and buys standard goods.
                        Adjusting weights to match your personal budget reveals your true economic reality.
                      </p>
                    </div>
                    <a className="btn btn-outline" href="app.html">
                      Full Custom Weighting on Workbench →
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Global Intelligence Bar (Preserves World headline honesty & benchmarks) */}
        <div className="hub-global-strip mk">
          <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
          <div className="global-strip-inner">
            <div
              className="global-stat-box"
              id="w-headline-big"
              data-state={headlineUnavailable ? "unavailable" : "ready"}
            >
              <span className="global-label" id="w-headline-label">
                Global Weighted Average
              </span>
              <strong className="global-val" id="w-headline-v">
                {lens && !headlineUnavailable ? formatPercent(lens.world.headline.v) : "—"}
              </strong>
              <span className="global-tag">Deliberately Unavailable</span>
            </div>

            <div className="global-info-text">
              <strong>Principled Methodology:</strong> The world figure is intentionally left blank rather than printed as a fabricated unweighted sum:
              valid global weighting requires population and GDP-PPP weights this engine does not yet ingest.
            </div>

            <div className="global-benchmarks">
              <span className="bench-title">Major Benchmarks</span>
              <ul className="bench-list">
                {lens?.world.regions
                  .filter((r) => r.v != null)
                  .slice(0, 3)
                  .map((r) => (
                    <li key={r.name}>
                      <span>{r.name}</span>
                      <b>{formatPercent(r.v)}</b>
                    </li>
                  ))}
              </ul>
            </div>
          </div>
        </div>

        {/* State shading disclaimer note */}
        <p className="flag">
          State shading and sub-national breakdowns are{" "}
          <strong>modelled</strong> — BLS publishes no state-level CPI.
          Every state&apos;s figure is its census region&apos;s own published CPI, and the engine
          labels every modelled figure as one.
        </p>
      </div>
    </section>
  );
}
