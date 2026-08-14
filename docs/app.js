// ---------------------------------------------------------------------------
// Race Desk — dashboard rendering. No build step, no framework: this reads
// static JSON written by scripts/fetch_data.py and renders it into the page.
// ---------------------------------------------------------------------------

const ELECTION_DAY_UTC = new Date("2026-11-03T05:00:00Z"); // midnight ET, Nov 3 2026

function startCountdown() {
  function tick() {
    const now = new Date();
    const diffMs = ELECTION_DAY_UTC - now;
    const daysEl = document.getElementById("cd-days");
    const hoursEl = document.getElementById("cd-hours");
    const minsEl = document.getElementById("cd-mins");

    if (diffMs <= 0) {
      daysEl.textContent = "0";
      hoursEl.textContent = "0";
      minsEl.textContent = "0";
      return;
    }
    const totalMinutes = Math.floor(diffMs / 60000);
    const days = Math.floor(totalMinutes / (60 * 24));
    const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
    const mins = totalMinutes % 60;

    daysEl.textContent = days;
    hoursEl.textContent = String(hours).padStart(2, "0");
    minsEl.textContent = String(mins).padStart(2, "0");
  }
  tick();
  setInterval(tick, 30000);
}

function formatUpdatedAt(iso) {
  if (!iso) return "not yet run";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

// Choice labels coming out of VoteHub vary: the national generic-ballot
// subject uses literal "Dem"/"Rep", but individual race polls may use
// candidate names instead. This makes a best-effort color guess from the
// label text and falls back to a neutral, position-based color otherwise.
function colorForChoice(label, position) {
  const lower = (label || "").toLowerCase();
  if (/\bdem/.test(lower)) return "var(--dem)";
  if (/\brep\b|gop/.test(lower)) return "var(--rep)";
  return position === 0 ? "var(--accent)" : "var(--text-muted)";
}

function topChoices(averages, count = 2) {
  return Object.entries(averages || {})
    .filter(([, pct]) => typeof pct === "number")
    .sort((a, b) => b[1] - a[1])
    .slice(0, count);
}

function buildSparkline(history, leadingLabel) {
  if (!history || history.length < 2 || !leadingLabel) return "";
  const points = history
    .map(h => (h.polling_averages || {})[leadingLabel])
    .filter(v => typeof v === "number");
  if (points.length < 2) return "";

  const w = 280, h = 36, pad = 3;
  const min = Math.min(...points), max = Math.max(...points);
  const range = Math.max(max - min, 1);

  const coords = points.map((v, i) => {
    const x = pad + (i / (points.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <polyline points="${coords}" fill="none" stroke="var(--dem)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
  </svg>`;
}

function renderOddsBox(label, odds) {
  if (!odds) {
    return `<div class="odds-box">
      <span class="odds-label">${label}</span>
      <span class="odds-empty">No matching market found</span>
    </div>`;
  }

  const ranked = (odds.outcomes || [])
    .filter(o => typeof o.probability_pct === "number")
    .slice()
    .sort((a, b) => b.probability_pct - a.probability_pct);
  const top = ranked[0];

  return `<div class="odds-box">
    <span class="odds-label">${label}</span>
    <span class="odds-value">${top ? top.probability_pct + "%" : "—"}</span>
    <a class="odds-sub" href="${odds.url}" target="_blank" rel="noopener">${top ? top.outcome : (odds.event_title || "")}</a>
  </div>`;
}

function renderCard(race, history) {
  const leaders = topChoices(race.polling.averages, 2);
  const hasPolling = leaders.length >= 2;
  const total = hasPolling ? leaders[0][1] + leaders[1][1] : 100;
  const leadingLabel = leaders.length ? leaders[0][0] : null;

  return `
    <article class="race-card" data-chamber="${race.chamber}">
      <div class="race-card-header">
        <span class="chip chip-${race.chamber}">${race.chamber}</span>
        <h2>${race.label}</h2>
      </div>

      ${hasPolling ? `
        <div>
          <div class="polling-bar">
            <div style="width:${(leaders[0][1] / total * 100).toFixed(1)}%; background:${colorForChoice(leaders[0][0], 0)}"></div>
            <div style="width:${(leaders[1][1] / total * 100).toFixed(1)}%; background:${colorForChoice(leaders[1][0], 1)}"></div>
          </div>
          <div class="polling-figures">
            <span class="figure" style="color:${colorForChoice(leaders[0][0], 0)}">${leaders[0][0]} ${leaders[0][1]}%</span>
            <span class="figure" style="color:${colorForChoice(leaders[1][0], 1)}">${leaders[1][0]} ${leaders[1][1]}%</span>
          </div>
          <div class="polling-caption">${race.polling.polls_used} polls averaged &middot; VoteHub</div>
        </div>
      ` : `<div class="odds-empty">No recent polling matched for this race yet.</div>`}

      ${buildSparkline(history, leadingLabel) ? `<div class="sparkline-wrap">${buildSparkline(history, leadingLabel)}</div>` : ""}

      <div class="odds-row">
        ${renderOddsBox("Kalshi", race.kalshi)}
        ${renderOddsBox("Polymarket", race.polymarket)}
      </div>

      <div class="card-footer">
        <span>Most recent poll: ${formatUpdatedAt(race.polling.most_recent_poll_date)}</span>
      </div>
    </article>
  `;
}

async function fetchHistory(raceId) {
  try {
    const resp = await fetch(`data/history/${raceId}.json`, { cache: "no-store" });
    if (!resp.ok) return [];
    return await resp.json();
  } catch {
    return [];
  }
}

function applyFilter(filter) {
  document.querySelectorAll(".race-card").forEach(card => {
    const show = filter === "all" || card.dataset.chamber === filter;
    card.style.display = show ? "" : "none";
  });
}

async function init() {
  startCountdown();

  const grid = document.getElementById("race-grid");
  const lastUpdatedEl = document.getElementById("last-updated");
  const sampleBanner = document.getElementById("sample-banner");

  let data;
  try {
    const resp = await fetch("data/latest.json", { cache: "no-store" });
    data = await resp.json();
  } catch (err) {
    grid.innerHTML = `<p class="odds-empty">Couldn't load race data (${err.message}). If you're running this locally, serve the /docs folder over HTTP rather than opening index.html directly — browsers block fetch() on file:// URLs.</p>`;
    return;
  }

  lastUpdatedEl.textContent = data.generated_at
    ? `Last updated ${formatUpdatedAt(data.generated_at)}`
    : "Not yet run — showing placeholder data";

  if (data.sample_data) {
    sampleBanner.hidden = false;
  }

  const cardsHtml = await Promise.all(
    data.races.map(async race => {
      const history = await fetchHistory(race.id);
      return renderCard(race, history);
    })
  );
  grid.innerHTML = cardsHtml.join("");

  document.querySelectorAll(".filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      applyFilter(btn.dataset.filter);
    });
  });
}

init();
