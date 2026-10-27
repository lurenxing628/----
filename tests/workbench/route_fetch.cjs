'use strict';
// Shared fetch-level stub for workbench Node contracts. Requests still pass through the real
// API module, APSWorkbenchTransport and validators; only the network answer is replaced.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');

const app = path.resolve(__dirname, '../../frontend/workbench/app');
const ORIGIN = 'http://127.0.0.1:8080';

function meta(overrides = {}) {
  return { source: 'production', time_basis: 'factory_local', snapshot_ref: 's'.repeat(32), request_ref: '1'.repeat(32),
    as_of: '2026-10-26T08:00:00', ...overrides };
}
// The single backend producer is web/api_responses.py query_payload / failure_payload.
function envelope(data, metaOverrides = {}, warnings = []) {
  return { ok: true, schema_version: 1, data, warnings, meta: meta(metaOverrides) };
}
function failure(code, message, { committed = false, fields = [], retryable = false, extra = {} } = {}) {
  return { ok: false, committed, error: { code, message, fields, retryable, request_ref: '1'.repeat(32) }, ...extra };
}
function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });
}
function file(content, contentType, headers = {}, status = 200) {
  return new Response(content, { status, headers: { 'Content-Type': contentType, ...headers } });
}
function text(content, contentType = 'text/html', status = 200) {
  return new Response(content, { status, headers: { 'Content-Type': contentType } });
}
function abortError() { return new DOMException('The operation was aborted.', 'AbortError'); }
function deferred() {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

function parseBody(body) {
  if (typeof body !== 'string') return body === undefined ? null : body;
  try { return JSON.parse(body); } catch (error) { return body; }
}
function matches(pattern, method, pathname) {
  const [expectedMethod, expectedPath] = pattern.split(' ');
  if (expectedMethod !== method) return false;
  const want = expectedPath.split('/'), have = pathname.split('/');
  if (want.at(-1) === '**') return have.length >= want.length - 1 && want.slice(0, -1).every((part, index) => part === '*' || part === have[index]);
  return want.length === have.length && want.every((part, index) => part === '*' || part === have[index]);
}
function find(routes, method, pathname) {
  if (typeof routes === 'function') return routes;
  const key = Object.keys(routes).find(pattern => matches(pattern, method, pathname));
  return key === undefined ? null : routes[key];
}
function toResponse(value) {
  if (value instanceof Response) return value;
  return json(value);
}

// routes: { 'GET /api/workbench/v1/x/*/y': payload | Response | (call) => payload | Response | Promise }.
// A plain object answers HTTP 200 JSON. A request without a route fails loudly. Like a browser
// fetch, an aborted request signal rejects with AbortError even while a handler is still pending.
function routeFetch(routes, { origin = ORIGIN } = {}) {
  const calls = [];
  async function fetch(input, init = {}) {
    const url = new URL(String(input), origin), method = (init.method || 'GET').toUpperCase();
    const call = { method, path: url.pathname, url, query: Object.fromEntries(url.searchParams), init,
      headers: init.headers || {}, signal: init.signal, body: parseBody(init.body) };
    calls.push(call);
    const handler = find(routes, method, url.pathname);
    if (!handler) throw new Error('Unexpected request: ' + method + ' ' + url.pathname + url.search);
    if (call.signal && call.signal.aborted) throw abortError();
    const answer = Promise.resolve().then(() => typeof handler === 'function' ? handler(call) : handler).then(toResponse);
    if (!call.signal) return answer;
    return new Promise((resolve, reject) => {
      const abort = () => reject(abortError());
      call.signal.addEventListener('abort', abort, { once: true });
      answer.then(value => { call.signal.removeEventListener('abort', abort); resolve(value); },
        error => { call.signal.removeEventListener('abort', abort); reject(error); });
    });
  }
  fetch.calls = calls;
  fetch.routes = routes;
  return fetch;
}

// Browser globals the transport needs inside a vm context. `window` may be the context itself
// or a separate object; both receive fetch/location so either lookup style reaches the stub.
function browser(context, fetch, { origin = ORIGIN } = {}) {
  const downloads = [];
  const document = context.document || { body: {} };
  document.body = document.body || {};
  document.body.appendChild = document.body.appendChild || (() => {});
  document.createElement = () => {
    const link = { click() { downloads.push({ href: link.href, filename: link.download }); }, remove() {} };
    return link;
  };
  const location = { origin, href: origin + '/workbench' };
  const globals = { fetch, URL, URLSearchParams, AbortController, AbortSignal, DOMException, CustomEvent, Response, Headers, Blob, FormData,
    TextEncoder, TextDecoder, setTimeout, clearTimeout, crypto: globalThis.crypto, location, document };
  for (const [key, value] of Object.entries(globals)) if (!(key in context) || ['fetch', 'location', 'document'].includes(key)) context[key] = value;
  if (context.window && context.window !== context) {
    Object.assign(context.window, { fetch, location, document });
    if (!context.window.crypto) context.window.crypto = globalThis.crypto;
  }
  return { downloads };
}
function loadTransport(context) {
  vm.runInContext(fs.readFileSync(path.join(app, 'transport.js'), 'utf8'), context, { filename: 'transport.js' });
  return (context.window || context).APSWorkbenchTransport;
}

// A synchronous render fixture for APSResourceSession.useQuery: the first render starts each read,
// settle() awaits them and renders again until no new read starts. Keys are the read source plus
// its dependencies, so a later render with the same request reuses the settled answer.
function settledQueries() {
  let cache = new Map(), pending = [];
  const ids = new WeakMap(); let nextId = 0;
  const identity = value => { if (!ids.has(value)) ids.set(value, ++nextId); return ids.get(value); };
  const keyOf = (load, deps) => load.toString() + '\u0000' + JSON.stringify(deps || [], (_key, value) =>
    typeof value === 'function' ? 'fn:' + identity(value) : value);
  function useQuery(load, deps, enabled = true) {
    if (!enabled) return { result: null, loading: false, error: null, reload() {} };
    const key = keyOf(load, deps);
    if (!cache.has(key)) {
      const entry = { result: null, loading: true, error: null, reload() { cache.delete(key); } };
      cache.set(key, entry);
      pending.push(Promise.resolve().then(() => load(new AbortController().signal)).then(
        result => { cache.set(key, { ...entry, result, loading: false }); },
        error => { cache.set(key, { ...entry, error, loading: false }); }));
    }
    return cache.get(key);
  }
  async function settle(render, rounds = 8) {
    for (let round = 0; round < rounds; round++) {
      const tree = render();
      if (!pending.length) return tree;
      const waiting = pending; pending = [];
      await Promise.all(waiting);
    }
    throw new Error('Reads did not settle within ' + rounds + ' renders');
  }
  return { useQuery, settle, reset() { cache = new Map(); pending = []; } };
}

module.exports = { ORIGIN, meta, envelope, failure, json, file, text, abortError, deferred, routeFetch, browser, loadTransport, settledQueries };
