// Collector for the NSE website's own history reports (the calls its "Historical Data" pages make). It runs inside a tab on
// https://www.nseindia.com (same origin, the site's own cookies), asks for one thing at a time with a pause between requests, and keeps every
// reply exactly as received. Nothing leaves the page except one file the owner lets Chrome download at the end.
//
//   const c = makeCollector();                 // start (paste this file first)
//   await c.step(30);                          // run the next 30 requests; repeat until state.status is not 'running'
//   c.download('nse_web_2010-2016.json');      // one download: {meta, items}, every item is one reply with its request
//
// The collector stops by itself when the site starts refusing requests (abortAfter failed requests in a row): hammering a firewall that has
// already said no only extends the block. Parsing and checking the file is data/nse_web.py's job, not this script's.
const DAY = 864e5;
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const iso = d => d.toISOString().slice(0, 10);
const utc = s => new Date(s + 'T00:00:00Z');
const dmy = d => `${String(d.getUTCDate()).padStart(2, '0')}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${d.getUTCFullYear()}`;
const dmon = d => `${String(d.getUTCDate()).padStart(2, '0')}-${MON[d.getUTCMonth()]}-${d.getUTCFullYear()}`;

// consecutive windows of at most `days` calendar days, both ends included
function windows(from, to, days) {
  const out = [];
  let a = utc(from);
  const z = utc(to);
  while (a <= z) {
    const b = new Date(Math.min(a.getTime() + (days - 1) * DAY, z.getTime()));
    out.push([iso(a), iso(b)]);
    a = new Date(b.getTime() + DAY);
  }
  return out;
}

// Monthly index futures expire on the last Thursday; when that is a holiday, on the trading day before. Candidates, most likely first.
function expiryCandidates(year, month) {
  let d = new Date(Date.UTC(year, month + 1, 0));
  while (d.getUTCDay() !== 4) d = new Date(d.getTime() - DAY);
  return [0, 1, 2, 3].map(k => new Date(d.getTime() - k * DAY));
}

function makeCollector(fetchFn, config) {
  const cfg = Object.assign({
    from: '2010-04-01', to: '2016-06-30', windowDays: 90, cap: 70, gapMs: 900, backoffMs: [3000, 10000, 30000], abortAfter: 4,
    etf: ['NIFTYBEES', 'JUNIORBEES', 'BANKBEES', 'GOLDBEES', 'LIQUIDBEES'],
    index: ['NIFTY 50', 'NIFTY NEXT 50', 'NIFTY BANK'],   // 'NIFTY MIDCAP 100' (and the other spellings tried) gets no rows from this report
    vixFrom: '2010-04-01',                            // a date: ask for India VIX from then on; null leaves it out
    fut: ['NIFTY', 'BANKNIFTY'], futLifeDays: 130,
    futMonthsFrom: {},                                // per symbol, the first month to ask for (a date); the default is `from`. Used to collect what an earlier run did not
    sleep: ms => new Promise(r => setTimeout(r, ms)),
  }, config || {});
  fetchFn = fetchFn || ((u, o) => fetch(u, o));
  const base = '/api/historicalOR/';
  const state = {status: 'running', done: 0, total: 0, items: [], failed: [], missing: [], consecutiveFailures: 0, last: null, startedAt: new Date().toISOString()};

  const url = t => {
    const range = `from=${dmy(utc(t.from))}&to=${dmy(utc(t.to))}`;
    if (t.kind === 'etf') return `${base}generateSecurityWiseHistoricalData?${range}&symbol=${t.symbol}&type=priceVolumeDeliverable&series=ALL`;
    if (t.kind === 'index') return `${base}indicesHistory?indexType=${encodeURIComponent(t.index)}&${range}`;
    if (t.kind === 'vix') return `${base}vixhistory?${range}`;
    return `${base}foCPV?${range}&instrumentType=FUTIDX&symbol=${t.symbol}&year=${utc(t.expiry).getUTCFullYear()}&expiryDate=${dmon(utc(t.expiry))}`;
  };

  // the reply's rows, or null when the site did not give a proper JSON answer (after a few tries with growing pauses)
  async function getRows(u) {
    for (let k = 0; k <= cfg.backoffMs.length; k++) {
      try {
        const r = await fetchFn(u, {credentials: 'include', headers: {Accept: 'application/json, text/plain, */*'}});
        const text = await r.text();
        state.last = {status: r.status, try: k};
        if (r.status === 200) {
          try {
            const j = JSON.parse(text);
            if (Array.isArray(j.data)) return j.data;
          } catch (e) { /* an HTML page instead of JSON: a refusal, handled like a bad status */ }
        }
        if (r.status === 401 || r.status === 403) await fetchFn('/', {credentials: 'include'}).then(x => x.text()).catch(() => {});   // cookie may have expired
      } catch (e) {
        state.last = {error: String(e).slice(0, 60), try: k};
      }
      if (k < cfg.backoffMs.length) await cfg.sleep(cfg.backoffMs[k]);
    }
    return null;
  }

  // one window; a reply at the row cap is cut off at the newest rows, so the window is halved until replies are under the cap
  async function fetchWindow(t) {
    const rows = await getRows(url(t));
    if (rows === null) return false;
    if (rows.length >= cfg.cap && t.from < t.to) {
      const a = utc(t.from).getTime(), z = utc(t.to).getTime();
      const mid = new Date(a + Math.floor((z - a) / DAY / 2) * DAY);
      await cfg.sleep(cfg.gapMs);
      const ok1 = await fetchWindow(Object.assign({}, t, {to: iso(mid)}));
      await cfg.sleep(cfg.gapMs);
      const ok2 = await fetchWindow(Object.assign({}, t, {from: iso(new Date(mid.getTime() + DAY))}));
      return ok1 && ok2;
    }
    state.items.push(Object.assign({}, t, {url: url(t), status: 200, n: rows.length, data: rows}));
    return true;
  }

  const dmonDate = s => { const [d, m, y] = s.split('-'); return new Date(Date.UTC(+y, MON.indexOf(m), +d)); };

  async function runTask(t) {
    if (t.kind !== 'fo') return fetchWindow(t);
    // a month's contract: try the candidate expiry dates until one has rows. When its rows stop well before its expiry the site has kept the contract
    // under two expiry dates (the Feb 2014 expiry moved from the 27th to the 26th when the 27th became a holiday): the days before are asked for too.
    let found = false;
    for (const exp of expiryCandidates(t.year, t.month)) {
      const first = Math.max(exp.getTime() - cfg.futLifeDays * DAY, utc(cfg.from).getTime());
      const last = Math.min(exp.getTime(), utc(cfg.to).getTime());
      const before = state.items.length;
      const ok = await fetchWindow({kind: 'fo', symbol: t.symbol, expiry: iso(exp), from: iso(new Date(first)), to: iso(new Date(last))});
      if (!ok) return false;
      const added = state.items.splice(before);
      const withRows = added.filter(i => i.n > 0);
      if (withRows.length) {
        state.items.push(...withRows);
        found = true;
        const lastRow = Math.max(...withRows.flatMap(i => i.data.map(r => dmonDate(r.FH_TIMESTAMP).getTime())));
        if (last < exp.getTime() || exp.getTime() - lastRow <= 7 * DAY) return true;     // the rows reach the expiry: this is the contract
      }
      await cfg.sleep(cfg.gapMs);                     // an empty answer (no contract expires that day) or a short one: try the day before
    }
    if (!found) state.missing.push({kind: 'fo', symbol: t.symbol, year: t.year, month: t.month + 1});
    return true;
  }

  const queue = [];
  for (const s of cfg.etf) for (const [a, b] of windows(cfg.from, cfg.to, cfg.windowDays)) queue.push({kind: 'etf', symbol: s, from: a, to: b});
  for (const n of cfg.index) for (const [a, b] of windows(cfg.from, cfg.to, cfg.windowDays)) queue.push({kind: 'index', index: n, from: a, to: b});
  if (cfg.vixFrom) for (const [a, b] of windows(cfg.vixFrom, cfg.to, cfg.windowDays)) queue.push({kind: 'vix', from: a, to: b});
  for (const s of cfg.fut) {
    const a = utc(cfg.futMonthsFrom[s] || cfg.from), z = utc(cfg.to);
    for (let y = a.getUTCFullYear(), m = a.getUTCMonth(); y < z.getUTCFullYear() || (y === z.getUTCFullYear() && m <= z.getUTCMonth()); m === 11 ? (y++, m = 0) : m++) {
      queue.push({kind: 'fo', symbol: s, year: y, month: m});
    }
  }
  state.total = queue.length;

  async function step(n) {
    let count = 0;
    while (state.status === 'running' && count < n) {
      const t = queue.shift();
      if (!t) { state.status = 'finished'; break; }
      const ok = await runTask(t);
      state.done++;
      count++;
      if (ok) {
        state.consecutiveFailures = 0;
      } else {
        state.failed.push({kind: t.kind, key: t.symbol || t.index || 'vix', from: t.from, to: t.to, year: t.year, month: t.month});
        if (++state.consecutiveFailures >= cfg.abortAfter) state.status = 'aborted';
      }
      await cfg.sleep(cfg.gapMs);
    }
    return progress();
  }

  function progress() {
    const rows = {};
    for (const it of state.items) rows[it.kind] = (rows[it.kind] || 0) + it.n;
    return {status: state.status, done: state.done, total: state.total, items: state.items.length, rows, failed: state.failed.length, missing: state.missing.length,
            consecutiveFailures: state.consecutiveFailures, last: state.last};
  }

  function download(name) {
    const meta = {collected: new Date().toISOString(), site: typeof location !== 'undefined' ? location.origin : null, script: 'data/nse_web_collect.js', cfg: Object.assign({}, cfg, {sleep: undefined}),
                  requests: state.items.length, failed: state.failed, missing: state.missing, status: state.status};
    const blob = new Blob([JSON.stringify({meta, items: state.items})], {type: 'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    return {name, bytes: blob.size, items: state.items.length};
  }

  return {state, step, progress, download, queue};
}

if (typeof module !== 'undefined') module.exports = {makeCollector, windows, expiryCandidates, dmy, dmon};
