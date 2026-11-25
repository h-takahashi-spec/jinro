// Apps Script の最小モック + HTTP サーバー（ローカル検証用）
// usage: node gas_mock_server.js [port]
const fs = require('fs');
const vm = require('vm');
const http = require('http');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const props = { OPENAI_API_KEY: process.env.OPENAI_API_KEY || '', OPENAI_MODEL: process.env.OPENAI_MODEL || '', OPENAI_BASE_URL: process.env.OPENAI_BASE_URL || '', AWAY_SEC: process.env.AWAY_SEC || '', AWAY_GRACE_SEC: process.env.AWAY_GRACE_SEC || '' };

function makeSheet(name) {
  const rows = [];
  const sh = {
    name, rows,
    appendRow(v) { rows.push(v.slice()); },
    setFrozenRows() {},
    getLastRow() { return rows.length; },
    getLastColumn() { return rows.reduce((m, r) => Math.max(m, r.length), 0); },
    getRange(r, c, nr = 1, nc = 1) {
      return {
        getValues() {
          const out = [];
          for (let i = 0; i < nr; i++) {
            const row = rows[r - 1 + i] || [];
            const o = [];
            for (let j = 0; j < nc; j++) o.push(row[c - 1 + j] === undefined ? '' : row[c - 1 + j]);
            out.push(o);
          }
          return out;
        },
        setValue(v) { this.setValues([[v]]); },
        clearContent() { for (let i = 0; i < nr; i++) if (rows[r - 1 + i]) for (let j = 0; j < nc; j++) rows[r - 1 + i][c - 1 + j] = ''; },
        setValues(vals) {
          for (let i = 0; i < vals.length; i++) {
            const idx = r - 1 + i;
            while (rows.length <= idx) rows.push([]);
            for (let j = 0; j < vals[i].length; j++) rows[idx][c - 1 + j] = vals[i][j];
          }
        }
      };
    }
  };
  return sh;
}

const sheets = {};
const cacheStore = {};
const ctx = {
  console,
  SpreadsheetApp: {
    getActiveSpreadsheet() {
      return {
        getSheetByName: (n) => sheets[n] || null,
        insertSheet: (n) => (sheets[n] = makeSheet(n))
      };
    }
  },
  CacheService: {
    getScriptCache() {
      return {
        get: (k) => (k in cacheStore ? cacheStore[k] : null),
        put: (k, v) => { if (String(v).length > 100000) throw new Error('cache too big'); cacheStore[k] = String(v); },
        remove: (k) => { delete cacheStore[k]; },
        putAll: (o) => { for (const k in o) cacheStore[k] = String(o[k]); },
        getAll: (ks) => Object.fromEntries(ks.filter(k => k in cacheStore).map(k => [k, cacheStore[k]]))
      };
    }
  },
  LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }), getDocumentLock: () => ({ tryLock: () => true, releaseLock() {} }) },
  PropertiesService: { getScriptProperties: () => ({ getProperty: k => props[k] || null, setProperty: (k, v) => { props[k] = v; } }) },
  UrlFetchApp: {
    fetch(url, o) {
      const out = execFileSync('curl', ['-s', '-w', '\n%{http_code}', '-X', 'POST', url, '-H', 'Content-Type: application/json', '-H', 'Authorization: ' + o.headers.Authorization, '--data-binary', '@-'], { input: o.payload, maxBuffer: 1e8 }).toString();
      const i = out.lastIndexOf('\n'); const body = out.slice(0, i), code = Number(out.slice(i + 1));
      return { getResponseCode: () => code, getContentText: () => body };
    }
  },
  Utilities: { getUuid: () => crypto.randomUUID(), DigestAlgorithm: { SHA_256: 'sha256' },
    computeDigest: (alg, str) => [...crypto.createHash(alg).update(String(str), 'utf8').digest()].map(b => b > 127 ? b - 256 : b) },
  ContentService: {
    MimeType: { JSON: 'json' },
    createTextOutput(t) { return { text: t, setMimeType() { return this; } }; }
  }
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'gas', 'Code.gs'), 'utf8'), ctx);

// テスト用: キャッシュを消してシートから復元できるかを時々確認
let reqCount = 0;
const DROP_CACHE_EVERY = Number(process.env.DROP_CACHE_EVERY || 0);

const port = Number(process.argv[2] || 8787);
http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
  let body = '';
  req.on('data', (d) => (body += d));
  req.on('end', () => {
    reqCount++;
    if (DROP_CACHE_EVERY && reqCount % DROP_CACHE_EVERY === 0) for (const k of Object.keys(cacheStore)) delete cacheStore[k];
    let out;
    if (req.url.startsWith('/__sheets')) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify(Object.fromEntries(Object.entries(sheets).map(([k, v]) => [k, v.rows]))));
    }
    if (req.method === 'POST') out = ctx.doPost({ postData: { contents: body } });
    else {
      const u = new URL(req.url, 'http://x');
      out = ctx.doGet({ parameter: Object.fromEntries(u.searchParams) });
    }
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(out.text);
  });
}).listen(port, () => console.log('mock GAS on http://localhost:' + port));
