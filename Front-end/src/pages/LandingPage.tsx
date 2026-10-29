import { useEffect, useState } from "react";
import { ShowcaseStage } from "../components/landing/ShowcaseStage";
import type { LensData } from "../types/lens";
import { formatPercent } from "../utils/format";

interface LandingPageProps {
  initialLens: LensData | null;
  initialUnavailable: boolean;
}

export function LandingPage({
  initialLens,
  initialUnavailable,
}: LandingPageProps) {
  const [lens] = useState<LensData | null>(initialLens);
  const [unavailable] = useState<boolean>(initialUnavailable);
  const [heroQuery, setHeroQuery] = useState("");

  useEffect(() => {
    document.body.dataset.hero = "stack";
    document.body.dataset.search = "console";
    document.body.dataset.showcase = "panel";
    document.body.dataset.system = "cells";
    if (unavailable) {
      document.body.setAttribute("data-lens", "unavailable");
    } else {
      document.body.removeAttribute("data-lens");
    }
  }, [unavailable]);

  const handleHeroSearch = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const q = heroQuery.trim();
    window.location.href = q
      ? `app.html?q=${encodeURIComponent(q)}`
      : "app.html";
  };

  const cpi = lens?.us.measures.find((m) => m.id === "cpi");
  const cpiLabel = `US headline CPI${
    cpi?.period ? ` · ${cpi.period}` : ""
  }`;
  const spreadText = lens?.us.spread
    ? `${formatPercent(lens.us.spread.lo)}–${formatPercent(lens.us.spread.hi)}`
    : "—";

  return (
    <>
      <div id="lens-alert" role="alert" hidden={!unavailable}>
        {unavailable
          ? "The engine could not be reached. Figures on this page are unavailable."
          : ""}
      </div>

      <header className="top">
        <div className="bar">
          <span className="brand">
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
          </span>
          <nav>
            <a href="#showcase">Showcase</a>
            <a href="#engine">Engine</a>
            <a href="#sources">Sources</a>
            <a href="app.html">Workbench</a>
          </nav>
          <a className="btn btn-primary" href="app.html">
            Open the engine
          </a>
        </div>
      </header>

      <main>
        <section className="hero wrap">
          <div className="hero-grid">
            <div>
              <h1 className="display">
                <span className="l">One number</span>
                <span className="l">
                  hides <em>seven</em>.
                </span>
              </h1>
              <p className="lede">
                Inflation Lens computes inflation across every measure at once —
                consumer, producer, chained, trimmed, regional, by category —
                and shows you where they disagree. That gap is the story a
                single headline rate cannot tell.
              </p>

              <div className="search">
                <div className="sconsole mk">
                  <i className="tl" />
                  <i className="tr" />
                  <i className="bl" />
                  <i className="br" />
                  <form
                    className="sfield"
                    id="hero-search"
                    onSubmit={handleHeroSearch}
                  >
                    <span className="ic">
                      <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      >
                        <circle cx="11" cy="11" r="7" />
                        <path d="M16.2 16.2 21 21" />
                      </svg>
                    </span>
                    <input
                      id="hero-q"
                      type="search"
                      value={heroQuery}
                      onChange={(e) => setHeroQuery(e.target.value)}
                      placeholder="Search United States or Euro area"
                      aria-label="Search a geography"
                    />
                    <button type="submit" className="go">
                      Compute
                    </button>
                  </form>
                </div>
                <p className="hints">
                  <span>Try</span>
                  <a href="app.html?q=United+States">United States</a>
                  <a href="app.html?q=Euro+area">Euro area</a>
                </p>
              </div>
            </div>

            <aside className="hero-aside">
              <div className="plate mk">
                <i className="tl" />
                <i className="tr" />
                <i className="bl" />
                <i className="br" />
                <div className="head">
                  <span>United States · live</span>
                  <span>Jul 2026</span>
                </div>
                <ul>
                  <li>
                    Headline CPI <b>3.4%</b>
                  </li>
                  <li>
                    Core CPI <b>2.5%</b>
                  </li>
                  <li>
                    Core PCE <b>3.3%</b>
                  </li>
                  <li>
                    Trimmed-mean PCE <b>2.2%</b>
                  </li>
                  <li>
                    PPI final demand <b>4.7%</b>
                  </li>
                </ul>
                <p className="foot">
                  Five official measures of the same month, 2.5 points apart.
                  The engine carries all of them and never picks one for you.
                </p>
              </div>
            </aside>
          </div>

          <dl className="strip">
            <div>
              <dt id="strip-cpi-label">{cpiLabel}</dt>
              <dd id="strip-cpi">{lens ? formatPercent(cpi?.yoy) : "—"}</dd>
            </div>
            <div>
              <dt>Measure spread</dt>
              <dd id="strip-spread">{spreadText}</dd>
            </div>
            <div>
              <dt>Global median</dt>
              <dd id="strip-median">
                {lens ? formatPercent(lens.world.median.v) : "—"}
              </dd>
            </div>
            <div>
              <dt>Economies covered</dt>
              <dd id="strip-economies">
                {lens ? lens.world.economies ?? "—" : "—"}
              </dd>
            </div>
          </dl>
        </section>

        <ShowcaseStage lens={lens} unavailable={unavailable} />

        <section className="sec wrap" id="engine">
          <span className="kick">03 · What the engine does</span>
          <hr className="rule" />
          <h2 className="big-h">Built to disagree with itself.</h2>
          <p className="say">
            Most inflation tools pick one series and print it. Inflation Lens
            runs every published measure in parallel, aligns them on one
            calendar, and treats the disagreement between them as the primary
            output rather than noise to be smoothed away.
          </p>

          <div className="cells">
            <div className="cell mk">
              <i className="tl" />
              <i className="tr" />
              <i className="bl" />
              <i className="br" />
              <span className="n">01</span>
              <h3>Every measure, in parallel</h3>
              <p>
                CPI-U, CPI-W, chained CPI, PCE, core PCE, trimmed-mean PCE and
                PPI final demand, computed on the same date axis. Where they
                diverge, the engine says by how much and which component is
                responsible.
              </p>
            </div>
            <div className="cell mk">
              <i className="tl" />
              <i className="tr" />
              <i className="bl" />
              <i className="br" />
              <span className="n">02</span>
              <h3>Down to the basket line</h3>
              <p>
                Every headline decomposes into its components with weights
                attached — shelter, energy, food, services — so you can see that
                two-thirds of a monthly print came from one line, and rebuild
                the index with your own basket.
              </p>
            </div>
            <div className="cell mk">
              <i className="tl" />
              <i className="tr" />
              <i className="bl" />
              <i className="br" />
              <span className="n">03</span>
              <h3>Read at the level you live at</h3>
              <p>
                National, regional and modelled state estimates, with revisions
                kept in view. Every figure carries its publisher, reference
                period and release date, and modelled values are never printed
                as observed.
              </p>
            </div>
          </div>

          <div className="pipe">
            <div className="stg">
              <div className="n">01</div>
              <h3>Ingest</h3>
              <p>
                Seven publishers polled on their own release calendars. Raw
                releases stored verbatim, never overwritten.
              </p>
            </div>
            <div className="stg">
              <div className="n">02</div>
              <h3>Align</h3>
              <p>
                Reference periods, seasonal adjustment and base years reconciled
                onto one axis so measures are comparable.
              </p>
            </div>
            <div className="stg">
              <div className="n">03</div>
              <h3>Decompose</h3>
              <p>
                Each index broken into components with published weights, so
                contribution is attributable, not asserted.
              </p>
            </div>
            <div className="stg">
              <div className="n">04</div>
              <h3>Model</h3>
              <p>
                Sub-national estimates attributed from published regional
                series. Flagged as modelled everywhere they appear.
              </p>
            </div>
            <div className="stg">
              <div className="n">05</div>
              <h3>Publish</h3>
              <p>
                Every figure leaves with its source, period, release date and
                revision history attached. No orphan numbers.
              </p>
            </div>
          </div>
        </section>

        <section className="sec wrap ledger-sec" id="sources">
          <span className="kick">04 · Where every number comes from</span>
          <hr className="rule" />
          <h2 className="big-h">The whole ledger, open.</h2>
          <p className="say">
            Inflation Lens publishes no proprietary index. Every figure on this
            page and in the engine traces to an official statistical release,
            listed here with its series, coverage and calendar. If you
            can&apos;t reproduce one of our numbers from these sources, that is
            a bug.
          </p>

          <table className="src">
            <thead>
              <tr>
                <th>Publisher</th>
                <th>Series drawn</th>
                <th>Coverage</th>
                <th>Latest release</th>
                <th>Next</th>
              </tr>
            </thead>
            <tbody id="src-rows">
              {lens?.sources.map((s) => (
                <tr key={s.org}>
                  <td className="org">
                    <a href={s.url} target="_blank" rel="noopener noreferrer">
                      {s.org}
                    </a>
                    <span className="full">{s.full}</span>
                  </td>
                  <td>{s.series}</td>
                  <td>{s.cov}</td>
                  <td className="dt">{s.latest}</td>
                  <td className="dt">{s.next}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="note">
            <strong>Known limits, stated plainly</strong>
            No statistical agency publishes state-level CPI. Where this page
            shades individual states, the value is that state&apos;s census
            region&apos;s own published BLS regional CPI — not a per-state
            estimate — and it is labelled modelled wherever it appears, because
            attributing a whole region&apos;s figure to one state is still an
            interpretive step. The world figure is deliberately left unavailable
            rather than shown as a computed average: it would require population
            and GDP-PPP weights this engine does not yet ingest, and an
            unweighted number under a weighted label would be worse than none.
            Figures for the past ten to twelve months are subject to revision by
            their publishers; the engine keeps every prior vintage rather than
            silently restating history.
          </div>
        </section>

        <section className="close wrap">
          <span className="kick">05 · The workbench</span>
          <hr className="rule" />
          <h2 className="big-h">Search anything. Get every measure.</h2>
          <p className="say">
            A country or your own weights, with every measure the engine carries
            returned at once and the sources attached.
          </p>
          <div className="row">
            <a className="btn-lg" href="app.html">
              Open the engine
            </a>
            <a className="btn-lg ghost" href="#sources">
              Read the methodology
            </a>
          </div>
        </section>

        <footer className="wrap">
          <span>
            Inflation Lens · figures as published to{" "}
            <span id="as-of">{lens?.asOf || "16 August 2026"}</span>
          </span>
          <span>
            Built on the Industry design system · geometry: Natural Earth
            (public domain)
          </span>
        </footer>
      </main>
    </>
  );
}
