// Runs the collector against a fake NSE: node tests/js/nse_web_collect_test.js
const assert = require('node:assert');
const {makeCollector, windows, expiryCandidates} = require('../../data/nse_web_collect.js');

const DAY = 864e5;
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const utc = s => new Date(s + 'T00:00:00Z');
const iso = d => d.toISOString().slice(0, 10);
const fromDmy = s => { const [d, m, y] = s.split('-'); return utc(`${y}-${m}-${d}`); };
const fromDmon = s => { const [d, m, y] = s.split('-'); return utc(`${y}-${String(MON.indexOf(m) + 1).padStart(2, '0')}-${d}`); };
const label = d => `${String(d.getUTCDate()).padStart(2, '0')}-${MON[d.getUTCMonth()]}-${d.getUTCFullYear()}`;
const weekdays = (a, z) => { const out = []; for (let d = a; d <= z; d = new Date(d.getTime() + DAY)) if (d.getUTCDay() % 6) out.push(d); return out; };

// a fake site: replies like NSE does (newest rows first, cut off at 70 rows), and can be told to misbehave
function fakeSite(opts = {}) {
  const calls = [];
  const site = {calls, homeVisits: 0, script: opts.script || []};
  site.fetch = async (u, o) => {
    calls.push(u);
    const reply = (status, body) => ({status, text: async () => (typeof body === 'string' ? body : JSON.stringify(body))});
    if (u === '/') { site.homeVisits++; return reply(200, '<html>home</html>'); }
    if (site.script.length) { const next = site.script.shift(); if (next) return reply(next.status, next.body); }
    const q = new URL(u, 'https://x.test').searchParams;
    const a = fromDmy(q.get('from')), z = fromDmy(q.get('to'));
    if (u.includes('generateSecurityWiseHistoricalData')) {
      const rows = weekdays(a, z).reverse().slice(0, 70).map(d => ({CH_SYMBOL: q.get('symbol'), mTIMESTAMP: label(d)}));
      return reply(200, {data: rows});
    }
    if (u.includes('foCPV')) {
      const expiry = iso(fromDmon(q.get('expiryDate')));
      const ok = (opts.expiries || []).includes(expiry);
      const stops = (opts.truncated || {})[expiry];                     // rows only up to this date
      const from = (opts.startsAt || {})[expiry];                       // rows only from this date
      const rows = ok ? weekdays(a, z).filter(d => (!stops || iso(d) <= stops) && (!from || iso(d) >= from)).reverse().slice(0, 70).map(d => ({FH_TIMESTAMP: label(d), FH_EXPIRY_DT: q.get('expiryDate')})) : [];
      return reply(200, {data: rows});
    }
    return reply(200, {data: []});
  };
  return site;
}
const quiet = {sleep: async () => {}, gapMs: 0, vixFrom: null};
let n = 0;
const test = async (name, fn) => { await fn(); n++; console.log('ok', name); };

(async () => {
  await test('windows cover the span exactly once', () => {
    const w = windows('2010-04-01', '2010-12-31', 90);
    assert.deepStrictEqual(w[0], ['2010-04-01', '2010-06-29']);
    assert.deepStrictEqual(w[w.length - 1][1], '2010-12-31');
    for (let i = 1; i < w.length; i++) assert.strictEqual(iso(new Date(utc(w[i - 1][1]).getTime() + DAY)), w[i][0]);
    assert.deepStrictEqual(windows('2010-04-01', '2010-04-01', 90), [['2010-04-01', '2010-04-01']]);
  });

  await test('expiry candidates: last Thursday, then the days before it', () => {
    assert.deepStrictEqual(expiryCandidates(2015, 8).map(iso), ['2015-09-24', '2015-09-23', '2015-09-22', '2015-09-21']);
    assert.deepStrictEqual(expiryCandidates(2010, 2).map(iso)[0], '2010-03-25');
    assert.deepStrictEqual(expiryCandidates(2015, 11).map(iso)[0], '2015-12-31');
  });

  await test('a window that fills the 70-row cap is halved until nothing is lost or repeated', async () => {
    const site = fakeSite();
    const c = makeCollector(site.fetch, Object.assign({from: '2015-01-01', to: '2015-12-31', windowDays: 400, etf: ['X'], index: [], fut: []}, quiet));
    const p = await c.step(10);
    assert.strictEqual(p.status, 'finished');
    const days = c.state.items.flatMap(i => i.data.map(r => r.mTIMESTAMP));
    assert.strictEqual(days.length, weekdays(utc('2015-01-01'), utc('2015-12-31')).length);
    assert.strictEqual(new Set(days).size, days.length);
    assert.ok(c.state.items.every(i => i.n < 70 && i.status === 200 && i.url.includes('symbol=X')));
  });

  await test('futures: the month finds its expiry even when a holiday moved it, and a month with no contract is named', async () => {
    const site = fakeSite({expiries: ['2015-08-27', '2015-09-23']});
    const c = makeCollector(site.fetch, Object.assign({from: '2015-08-01', to: '2015-09-30', etf: [], index: [], fut: ['NIFTY']}, quiet));
    await c.step(10);
    const expiries = [...new Set(c.state.items.map(i => i.expiry))].sort();
    assert.deepStrictEqual(expiries, ['2015-08-27', '2015-09-23']);
    assert.deepStrictEqual(c.state.missing, []);
    const all = c.state.items.filter(i => i.expiry === '2015-09-23').flatMap(i => i.data.map(r => r.FH_TIMESTAMP));
    assert.strictEqual(new Set(all).size, all.length);
    const c2 = makeCollector(fakeSite({expiries: ['2015-08-27']}).fetch, Object.assign({from: '2015-08-01', to: '2015-09-30', etf: [], index: [], fut: ['NIFTY']}, quiet));
    await c2.step(10);
    assert.deepStrictEqual(c2.state.missing, [{kind: 'fo', symbol: 'NIFTY', year: 2015, month: 9}]);
    assert.ok(c2.state.items.every(i => i.n > 0));
  });

  await test('a futures window never starts before the collector start or ends after its end', async () => {
    const site = fakeSite({expiries: ['2010-04-29']});
    const c = makeCollector(site.fetch, Object.assign({from: '2010-04-01', to: '2010-04-20', etf: [], index: [], fut: ['NIFTY']}, quiet));
    await c.step(5);
    const it = c.state.items[0];
    assert.deepStrictEqual([it.from, it.to, it.expiry], ['2010-04-01', '2010-04-20', '2010-04-29']);     // expiry is after the end: the window stops at the end
    assert.strictEqual(it.data.length > 0, true);
  });

  await test('a refusal is retried with growing pauses and, when it ends, the work carries on', async () => {
    const pauses = [];
    const site = fakeSite({script: [{status: 503, body: 'x'}, {status: 200, body: '<html>challenge</html>'}]});
    const c = makeCollector(site.fetch, {from: '2015-01-01', to: '2015-01-31', etf: ['X'], index: [], fut: [], vixFrom: null, gapMs: 0, sleep: async ms => { pauses.push(ms); }, backoffMs: [3000, 10000, 30000]});
    await c.step(5);
    assert.strictEqual(c.state.status, 'finished');
    assert.strictEqual(c.state.items.length, 1);
    assert.deepStrictEqual(pauses.filter(p => p >= 3000), [3000, 10000]);
  });

  await test('a 403 makes the collector visit the front page again before retrying', async () => {
    const site = fakeSite({script: [{status: 403, body: 'denied'}]});
    const c = makeCollector(site.fetch, Object.assign({from: '2015-01-01', to: '2015-01-31', etf: ['X'], index: [], fut: []}, quiet, {backoffMs: [1]}));
    await c.step(5);
    assert.strictEqual(site.homeVisits, 1);
    assert.strictEqual(c.state.items.length, 1);
  });

  await test('after abortAfter tasks in a row get no answer it stops and does not keep asking', async () => {
    const site = fakeSite({script: Array(500).fill({status: 503, body: 'x'})});
    const c = makeCollector(site.fetch, Object.assign({from: '2010-04-01', to: '2012-04-01', etf: ['X'], index: [], fut: [], abortAfter: 3, backoffMs: [1]}, quiet));
    const p = await c.step(100);
    assert.strictEqual(p.status, 'aborted');
    assert.strictEqual(p.failed, 3);
    assert.strictEqual(site.calls.filter(u => u.includes('historicalOR')).length, 3 * 2);       // 2 tries each (one pause), then it stops
  });

  await test('a success resets the count of failures in a row', async () => {
    const site = fakeSite({script: [{status: 503, body: 'x'}, null, {status: 503, body: 'x'}, null]});
    const c = makeCollector(site.fetch, Object.assign({from: '2010-04-01', to: '2011-03-01', etf: ['X'], index: [], fut: [], abortAfter: 2, backoffMs: []}, quiet));
    const p = await c.step(100);
    assert.notStrictEqual(p.status, 'aborted');
  });

  await test('an empty window is kept as an item with no rows (a fact about the site), not dropped', async () => {
    const c = makeCollector(async () => ({status: 200, text: async () => JSON.stringify({data: []})}),
                            Object.assign({from: '2015-01-01', to: '2015-01-31', etf: ['X'], index: [], fut: []}, quiet));
    await c.step(5);
    assert.deepStrictEqual(c.state.items.map(i => i.n), [0]);
  });

  await test('download makes one file of {meta, items} and never includes the pause function', async () => {
    let captured = null;
    global.URL.createObjectURL = b => { captured = b; return 'blob:test'; };
    let clicks = 0;
    global.document = {createElement: () => ({click: () => clicks++, remove() {}}), body: {appendChild() {}}};
    global.location = {origin: 'https://www.nseindia.com'};
    const c = makeCollector(fakeSite().fetch, Object.assign({from: '2015-01-01', to: '2015-01-31', etf: ['X'], index: [], fut: []}, quiet));
    await c.step(5);
    const info = c.download('nse_web_test.json');
    assert.strictEqual(clicks, 1);
    assert.strictEqual(info.items, 1);
    const parsed = JSON.parse(await captured.text());
    assert.deepStrictEqual(Object.keys(parsed), ['meta', 'items']);
    assert.strictEqual(parsed.meta.site, 'https://www.nseindia.com');
    assert.strictEqual(parsed.items[0].kind, 'etf');
  });

  await test('a 200 answer that is JSON but has no data list is a refusal, not an empty window', async () => {
    const site = fakeSite({script: [{status: 200, body: '{"error":"blocked"}'}, {status: 200, body: '{"error":"blocked"}'}]});
    const c = makeCollector(site.fetch, Object.assign({from: '2015-01-01', to: '2015-01-31', etf: ['X'], index: [], fut: [], backoffMs: [1, 1], abortAfter: 9}, quiet));
    await c.step(5);
    assert.strictEqual(c.state.failed.length, 0);
    assert.strictEqual(site.calls.filter(u => u.includes('historicalOR')).length, 3);             // two refusals, then the real answer
    const c2 = makeCollector(fakeSite({script: Array(9).fill({status: 200, body: '{"error":"blocked"}'})}).fetch,
                             Object.assign({from: '2015-01-01', to: '2015-01-31', etf: ['X'], index: [], fut: [], backoffMs: [1, 1], abortAfter: 9}, quiet));
    await c2.step(5);
    assert.deepStrictEqual(c2.state.failed, [{kind: 'etf', key: 'X', from: '2015-01-01', to: '2015-01-31', year: undefined, month: undefined}]);
    assert.strictEqual(c2.state.items.length, 0);
  });

  await test('indices are asked for by name, url encoded, and each window of each index is its own item', async () => {
    const site = fakeSite();
    const c = makeCollector(site.fetch, Object.assign({from: '2015-01-01', to: '2015-06-30', windowDays: 90, etf: [], index: ['NIFTY 50', 'NIFTY BANK'], fut: []}, quiet));
    await c.step(20);
    assert.strictEqual(c.state.items.length, 2 * windows('2015-01-01', '2015-06-30', 90).length);
    assert.ok(site.calls.some(u => u.includes('indexType=NIFTY%2050&from=01-01-2015&to=31-03-2015')));
    assert.ok(site.calls.some(u => u.includes('indexType=NIFTY%20BANK')));
  });

  await test('vix is only asked for when a start date is given', async () => {
    const a = makeCollector(fakeSite().fetch, Object.assign({from: '2015-01-01', to: '2015-06-30', etf: [], index: [], fut: []}, quiet));
    const b = makeCollector(fakeSite().fetch, Object.assign({}, quiet, {from: '2015-01-01', to: '2015-06-30', etf: [], index: [], fut: [], vixFrom: '2015-04-01', windowDays: 100}));
    assert.strictEqual(a.queue.length, 0);
    assert.deepStrictEqual(b.queue.map(t => [t.kind, t.from]), [['vix', '2015-04-01']]);
  });

  await test('futMonthsFrom starts one symbol at a later month (to collect what an earlier run did not), and the window still never starts before `from`', async () => {
    const c = makeCollector(fakeSite().fetch, Object.assign({}, quiet, {from: '2010-04-01', to: '2010-06-30', etf: [], index: [], fut: ['NIFTY', 'BANKNIFTY'], futMonthsFrom: {NIFTY: '2010-06-01'}}));
    assert.deepStrictEqual(c.queue.map(t => [t.symbol, t.year, t.month]), [['NIFTY', 2010, 5], ['BANKNIFTY', 2010, 3], ['BANKNIFTY', 2010, 4], ['BANKNIFTY', 2010, 5]]);
    const d = makeCollector(fakeSite({expiries: ['2010-06-24']}).fetch, Object.assign({}, quiet, {from: '2010-04-01', to: '2010-06-30', etf: [], index: [], fut: ['NIFTY'], futMonthsFrom: {NIFTY: '2010-06-01'}}));
    await d.step(5);
    assert.strictEqual(d.state.items[0].from, '2010-04-01');
  });

  await test('a contract whose rows stop well before its expiry is also asked for under the days before (the site kept one contract under two expiry dates)', async () => {
    const site = fakeSite({expiries: ['2014-02-27', '2014-02-26'], truncated: {'2014-02-27': '2013-12-27'}, startsAt: {'2014-02-26': '2013-12-30'}});
    const c = makeCollector(site.fetch, Object.assign({}, quiet, {from: '2013-10-20', to: '2014-02-28', etf: [], index: [], fut: ['NIFTY'], futMonthsFrom: {NIFTY: '2014-02-01'}}));
    await c.step(5);
    assert.deepStrictEqual(c.state.items.map(i => i.expiry).sort(), ['2014-02-26', '2014-02-27']);
    assert.ok(c.state.items.find(i => i.expiry === '2014-02-26').data.length > 0);
    assert.deepStrictEqual(c.state.missing, []);
  });

  await test('a contract whose rows reach its expiry is not asked for under any other day', async () => {
    const site = fakeSite({expiries: ['2015-08-27', '2015-08-26']});                                       // both exist in the fake, only the first should be asked for
    const c = makeCollector(site.fetch, Object.assign({}, quiet, {from: '2015-08-01', to: '2015-08-31', etf: [], index: [], fut: ['NIFTY']}));
    await c.step(5);
    assert.deepStrictEqual(c.state.items.map(i => i.expiry), ['2015-08-27']);
    assert.strictEqual(site.calls.filter(u => u.includes('foCPV')).length, 1);
  });

  await test('a contract that stays short under every candidate day is kept and is not reported as missing', async () => {
    const c = makeCollector(fakeSite({expiries: ['2014-02-27'], truncated: {'2014-02-27': '2013-12-27'}}).fetch,
                            Object.assign({}, quiet, {from: '2013-10-20', to: '2014-02-28', etf: [], index: [], fut: ['NIFTY'], futMonthsFrom: {NIFTY: '2014-02-01'}}));
    await c.step(5);
    assert.deepStrictEqual(c.state.items.map(i => i.expiry), ['2014-02-27']);
    assert.deepStrictEqual(c.state.missing, []);
  });

  await test('a contract whose window is cut by the end date is not chased under other days just because its rows stop there', async () => {
    const site = fakeSite({expiries: ['2010-04-29', '2010-04-28']});
    const c = makeCollector(site.fetch, Object.assign({}, quiet, {from: '2010-04-01', to: '2010-04-20', etf: [], index: [], fut: ['NIFTY']}));
    await c.step(5);
    assert.deepStrictEqual(c.state.items.map(i => i.expiry), ['2010-04-29']);
    assert.strictEqual(site.calls.filter(u => u.includes('foCPV')).length, 1);
  });

  console.log(n + ' collector tests passed');
})().catch(e => { console.error(e); process.exit(1); });
