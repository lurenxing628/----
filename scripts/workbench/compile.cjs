'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { Worker, MessageChannel, receiveMessageOnPort, isMainThread, parentPort, workerData } = require('node:worker_threads');
const { REACT_NAMED_EXPORTS, SANDBOX_RUNTIME_CODE, normalizeRelPath, normalizeStubs } = require('./vm-sandbox-runtime.cjs');

const ROOT_DIR = path.resolve(__dirname, '../..');
const APP_DIR = path.join(ROOT_DIR, 'frontend/workbench/app');
delete process.env.ESBUILD_BINARY_PATH;
const esbuild = require(path.join(ROOT_DIR, 'vendor/node_modules/esbuild'));
if (esbuild.version !== '0.25.12') {
  throw new Error('Expected fixed esbuild version 0.25.12, got ' + esbuild.version);
}

const dynamicImportEsmCache = new Map();
function assertNoDynamicImport(code, relPath = '') {
  const cacheKey = relPath + '\0' + code;
  if (dynamicImportEsmCache.has(cacheKey)) return dynamicImportEsmCache.get(cacheKey);
  const esm = esbuild.transformSync(code, { loader: 'jsx', format: 'esm', charset: 'utf8', logLevel: 'silent' }).code;
  if (code.includes('import')) {
    const lowered = esbuild.transformSync(code, {
      loader: 'jsx', format: 'esm', charset: 'utf8', supported: { 'dynamic-import': false }, logLevel: 'silent',
    }).code;
    if (esm !== lowered) throw new Error('Dynamic import() is forbidden in offline workbench build: ' + relPath);
  }
  dynamicImportEsmCache.set(cacheKey, esm);
  return esm;
}

const hashText = text => crypto.createHash('sha1').update(text).digest('hex');

if (!isMainThread) {
  const workerAppDir = workerData.appDir, realAppDir = fs.realpathSync(workerAppDir);
  const EXPORT_CACHE = new Map(), FACTORY_CACHE = new Map();
  const hasOverride = (overrides, rel) => Boolean(overrides && Object.prototype.hasOwnProperty.call(overrides, rel));
  const isWithinApp = rel => !rel.startsWith('..') && !path.isAbsolute(rel);
  const readSource = (rel, overrides) => hasOverride(overrides, rel) ? overrides[rel] : fs.readFileSync(path.join(workerAppDir, rel), 'utf8');
  const stripValPrefix = k => k.startsWith('wb-val-stub:') ? k.slice(12) : (k.startsWith('wb-val:') ? k.slice(7) : null);

  function hasModuleFile(absPath, rel, overrides) {
    if (!isWithinApp(rel)) return false;
    if (hasOverride(overrides, rel)) return true;
    if (!(fs.existsSync(absPath) && fs.statSync(absPath).isFile())) return false;
    return isWithinApp(path.relative(realAppDir, fs.realpathSync(absPath)).split(path.sep).join('/'));
  }
  function formatEsbuildError(error) {
    const raw = (error && error.errors && error.errors[0] && error.errors[0].text)
      ? error.errors[0].text : (error && error.message ? error.message : String(error));
    return raw.split('wb-val-stub:').join('').split('wb-val:').join('');
  }
  function createValidationPlugin(stubs, overrides) {
    return {
      name: 'wb-val-plugin',
      setup(build) {
        build.onResolve({ filter: /^wb-val:/ }, a => ({ path: a.path.slice(7), namespace: 'wb-val' }));
        build.onResolve({ filter: /.*/ }, (args) => {
          if (!args.path.startsWith('./') && !args.path.startsWith('../')) {
            return { errors: [{ text: 'Unsupported bare or remote import specifier in offline build: ' + args.path }] };
          }
          const targetAbs = path.resolve(args.resolveDir, args.path);
          const rel = path.relative(workerAppDir, targetAbs).split(path.sep).join('/');
          const hasFile = hasModuleFile(targetAbs, rel, overrides);
          const hasStub = isWithinApp(rel) && Boolean(stubs && Object.prototype.hasOwnProperty.call(stubs, rel));
          if (!hasFile && !hasStub) return { errors: [{ text: 'Missing module in frontend/workbench/app: ' + args.path }] };
          return { path: rel, namespace: hasStub ? 'wb-val-stub' : 'wb-val' };
        });
        build.onLoad({ filter: /.*/, namespace: 'wb-val' }, (args) => {
          const rel = args.path, code = readSource(rel, overrides);
          try { assertNoDynamicImport(code, rel); } catch (err) {
            return { errors: [{ text: err && err.message ? err.message : String(err) }] };
          }
          return { contents: code, loader: 'jsx', resolveDir: path.dirname(path.join(workerAppDir, rel)) };
        });
        build.onLoad({ filter: /.*/, namespace: 'wb-val-stub' }, (args) => {
          const rel = args.path, hasFile = hasModuleFile(path.join(workerAppDir, rel), rel, overrides);
          const keys = (stubs[rel] && stubs[rel].keys) ? stubs[rel].keys : ['default'];
          const lines = hasFile ? ['export * from ' + JSON.stringify('wb-val:' + rel) + ';'] : [];
          let idx = 0;
          for (const k of keys) {
            if (k === 'default') lines.push('export default null;');
            else { const v = '_s' + (idx++); lines.push('const ' + v + ' = null; export { ' + v + ' as ' + JSON.stringify(k) + ' };'); }
          }
          return { contents: lines.join('\n'), loader: 'js', resolveDir: workerAppDir };
        });
      },
    };
  }

  async function runPass1(uniqueEntries, stubs, overrides) {
    for (const rel of uniqueEntries) {
      if (!hasModuleFile(path.join(workerAppDir, rel), rel, overrides)) throw new Error('Missing module in frontend/workbench/app: ' + rel);
    }
    let res;
    try {
      res = await esbuild.build({
        entryPoints: Object.fromEntries(uniqueEntries.map((rel, i) => ['p1_' + i, 'wb-val:' + rel])),
        bundle: true, platform: 'browser', format: 'esm', target: 'chrome109',
        charset: 'utf8', write: false, metafile: true, outdir: '/wb-p1', logLevel: 'silent',
        plugins: [createValidationPlugin(stubs, overrides)],
      });
    } catch (err) { throw new Error(formatEsbuildError(err)); }

    const reactOverridden = hasOverride(overrides, 'shared/runtime/react.js');
    const shouldInclude = rel => (rel !== 'shared/runtime/react.js' || reactOverridden) && hasModuleFile(path.join(workerAppDir, rel), rel, overrides);
    const closureMap = new Map(), graphSet = new Set(), directDepsMap = new Map();
    for (const [k, meta] of Object.entries(res.metafile.inputs)) {
      if (!k.startsWith('wb-val:')) continue;
      directDepsMap.set(k.slice(7), Array.from(new Set(meta.imports.map(imp => stripValPrefix(imp.path)).filter(Boolean))));
    }
    for (const entryRel of uniqueEntries) {
      const seen = new Set(), ordered = [];
      const visit = (key) => {
        if (seen.has(key)) return;
        seen.add(key);
        const meta = res.metafile.inputs[key];
        if (meta) for (const imp of meta.imports) if (stripValPrefix(imp.path)) visit(imp.path);
        if (key.startsWith('wb-val:') && shouldInclude(key.slice(7))) { ordered.push(key.slice(7)); graphSet.add(key.slice(7)); }
      };
      visit('wb-val:' + entryRel);
      closureMap.set(entryRel, ordered);
    }
    return { closureMap, graphRels: Array.from(graphSet), directDepsMap };
  }

  async function readStaticExports(sourcesByKey) {
    const res = await esbuild.build({
      entryPoints: Object.fromEntries(Object.keys(sourcesByKey).map(k => [k, 'wb-ex:' + k])),
      bundle: false, format: 'esm', target: 'chrome109', charset: 'utf8', write: false, metafile: true, outdir: '/wb-ex', logLevel: 'silent',
      plugins: [{
        name: 'wb-ex',
        setup(b) {
          b.onResolve({ filter: /^wb-ex:/ }, a => ({ path: a.path.slice(6), namespace: 'wb-ex' }));
          b.onLoad({ filter: /.*/, namespace: 'wb-ex' }, a => ({ contents: sourcesByKey[a.path], loader: 'jsx' }));
        },
      }],
    });
    const out = Object.create(null);
    for (const [outKey, meta] of Object.entries(res.metafile.outputs)) out[path.basename(outKey, '.js')] = meta.exports;
    return out;
  }

  async function extractExports(graphRels, stubs, overrides, stubsKey, overridesKey) {
    const exportsMap = new Map(), plainTodo = [], starTodo = [];
    for (const rel of graphRels) {
      const code = readSource(rel, overrides), ch = hashText(code), isStar = assertNoDynamicImport(code, rel).includes('export *');
      const ck = isStar ? ('star:' + rel + ':' + ch + ':' + overridesKey + ':' + stubsKey) : ('plain:' + rel + ':' + ch);
      if (EXPORT_CACHE.has(ck)) exportsMap.set(rel, EXPORT_CACHE.get(ck));
      else (isStar ? starTodo : plainTodo).push({ rel, code, ck });
    }
    if (plainTodo.length > 0) {
      const parsed = await readStaticExports(Object.fromEntries(plainTodo.map((u, i) => ['e' + i, u.code])));
      plainTodo.forEach((u, i) => { EXPORT_CACHE.set(u.ck, parsed['e' + i]); exportsMap.set(u.rel, parsed['e' + i]); });
    }
    if (starTodo.length > 0) {
      const bundled = await esbuild.build({
        entryPoints: Object.fromEntries(starTodo.map((u, i) => ['s' + i, 'wb-val:' + u.rel])),
        bundle: true, platform: 'browser', format: 'esm', target: 'chrome109', charset: 'utf8', write: false, outdir: '/wb-star', logLevel: 'silent',
        plugins: [createValidationPlugin(stubs, overrides)],
      });
      const parsed = await readStaticExports(Object.fromEntries(bundled.outputFiles.map(f => [path.basename(f.path, '.js'), f.text])));
      starTodo.forEach((u, i) => { EXPORT_CACHE.set(u.ck, parsed['s' + i]); exportsMap.set(u.rel, parsed['s' + i]); });
    }
    return exportsMap;
  }

  async function runPass2(graphRels, exportsMap, directDepsMap, stubs, overrides, stubsKey) {
    const reactOverridden = hasOverride(overrides, 'shared/runtime/react.js');
    const reactStubbed = Boolean(stubs && Object.prototype.hasOwnProperty.call(stubs, 'shared/runtime/react.js'));
    const depExportsOf = d => (d === 'shared/runtime/react.js' && !reactOverridden) ? REACT_NAMED_EXPORTS : (exportsMap.get(d) || []);
    const factoryMap = new Map(), todo = [];
    for (const rel of graphRels) {
      const code = readSource(rel, overrides), sourceHash = hashText(code), ownExports = exportsMap.get(rel) || [];
      const depSigs = (directDepsMap.get(rel) || []).map(d => [d, depExportsOf(d), stubs && stubs[d] ? stubs[d] : null]);
      const cacheKey = rel + '\0' + sourceHash + '\0' + stubsKey + '\0' + JSON.stringify([ownExports, depSigs, reactOverridden && !reactStubbed]);
      if (FACTORY_CACHE.has(cacheKey)) factoryMap.set(rel, FACTORY_CACHE.get(cacheKey));
      else todo.push({ rel, code, sourceHash, ownExports, cacheKey });
    }
    if (todo.length === 0) return factoryMap;

    const codeByRel = new Map(todo.map(u => [u.rel, u]));
    const res = await esbuild.build({
      entryPoints: Object.fromEntries(todo.map((u, i) => ['f' + i, 'wb-entry:' + u.rel])),
      bundle: true, platform: 'browser', format: 'iife', target: 'chrome109', charset: 'utf8', write: false, outdir: '/wb-p2', logLevel: 'silent',
      plugins: [{
        name: 'wb-factory-plugin',
        setup(b) {
          for (const ns of ['wb-entry', 'wb-clean', 'wb-real', 'wb-self']) {
            b.onResolve({ filter: new RegExp('^' + ns + ':') }, a => ({ path: a.path.slice(ns.length + 1), namespace: ns }));
          }
          b.onResolve({ filter: /.*/, namespace: 'wb-real' }, (a) => {
            const depRel = path.relative(workerAppDir, path.resolve(a.resolveDir, a.path)).split(path.sep).join('/');
            return { path: depRel, namespace: (depRel === 'shared/runtime/react.js' && !reactOverridden && !reactStubbed) ? 'wb-react' : 'wb-imp' };
          });
          b.onLoad({ filter: /.*/, namespace: 'wb-entry' }, a => ({ contents: 'import * as ns from ' + JSON.stringify('wb-clean:' + a.path) + ';\n', loader: 'js' }));
          b.onLoad({ filter: /.*/, namespace: 'wb-clean' }, (a) => {
            const own = codeByRel.get(a.path).ownExports, realSpec = JSON.stringify('wb-real:' + a.path);
            const contents = own.length > 0
              ? 'export { ' + own.map(n => JSON.stringify(n) + ' as ' + JSON.stringify(n)).join(', ') + ' } from ' + realSpec + ';\n'
              : 'import ' + realSpec + ';\nexport {};\n';
            return { contents, loader: 'js' };
          });
          b.onLoad({ filter: /.*/, namespace: 'wb-self' }, a => ({
            contents: 'import * as ns from ' + JSON.stringify('wb-clean:' + a.path) + ';\nglobalThis.__wbRuntime.publishLiveExports(' + JSON.stringify(a.path) + ', ns);\n',
            loader: 'js',
          }));
          b.onLoad({ filter: /.*/, namespace: 'wb-real' }, a => ({
            contents: 'import ' + JSON.stringify('wb-self:' + a.path) + ';' + codeByRel.get(a.path).code,
            loader: 'jsx', resolveDir: path.dirname(path.join(workerAppDir, a.path)),
          }));
          b.onLoad({ filter: /.*/, namespace: 'wb-react' }, () => ({ contents: 'module.exports = globalThis.__wbRuntime.react();\n', loader: 'js' }));
          b.onLoad({ filter: /.*/, namespace: 'wb-imp' }, (a) => {
            const d = a.path, hasSpec = Boolean(stubs && Object.prototype.hasOwnProperty.call(stubs, d) && stubs[d]);
            const names = Array.from(new Set([...depExportsOf(d), ...(hasSpec ? (stubs[d].keys || []) : [])]));
            const args = JSON.stringify(d) + ', ' + JSON.stringify(names) + (hasSpec ? ', ' + stubs[d].expr : '');
            return { contents: 'module.exports = globalThis.__wbRuntime.dep(' + args + ');\n', loader: 'js', resolveDir: workerAppDir };
          });
        },
      }],
    });
    for (const outFile of res.outputFiles) {
      const idx = Number(path.basename(outFile.path, '.js').slice(1)), u = todo[idx];
      const stmt = 'globalThis.__wbRuntime.registerFactory(' + JSON.stringify(u.rel) + ', ' + JSON.stringify(u.sourceHash) + ', function () {\n' + outFile.text + '});';
      FACTORY_CACHE.set(u.cacheKey, stmt);
      factoryMap.set(u.rel, stmt);
    }
    return factoryMap;
  }

  parentPort.on('message', async ({ port, ctrl, items, stubs, sourceOverrides, stubsKey, overridesKey }) => {
    try {
      const uniqueEntries = Array.from(new Set(items.map(it => it.relPath)));
      const { closureMap, graphRels, directDepsMap } = await runPass1(uniqueEntries, stubs, sourceOverrides);
      const exportsMap = await extractExports(graphRels, stubs, sourceOverrides, stubsKey, overridesKey);
      const factoryMap = await runPass2(graphRels, exportsMap, directDepsMap, stubs, sourceOverrides, stubsKey);
      const compiled = items.map(it => [
        SANDBOX_RUNTIME_CODE,
        ...closureMap.get(it.relPath).map(r => factoryMap.get(r)),
        'globalThis.__wbRuntime.runEntry(' + JSON.stringify(it.relPath) + ');',
      ].join('\n'));
      port.postMessage({ ok: true, compiled });
    } catch (error) {
      port.postMessage({ ok: false, error: error && error.message ? error.message : String(error) });
    } finally {
      Atomics.store(ctrl, 0, 1);
      Atomics.notify(ctrl, 0, 1);
    }
  });
  return;
}

let workerInstance = null;
function getWorker() {
  if (!workerInstance) {
    workerInstance = new Worker(__filename, { workerData: { appDir: APP_DIR } });
    workerInstance.unref();
  }
  return workerInstance;
}

const COMPILE_CACHE = new Map();

function compile(request) {
  if (!request || !Array.isArray(request.sources) || request.sources.length === 0) {
    throw new Error('Compile request requires a non-empty sources array');
  }
  const stubs = normalizeStubs(request.stubs);
  const stubsKey = stubs ? JSON.stringify(stubs) : '', outputs = new Array(request.sources.length), uncached = [];
  let sourceOverrides = null;
  const relPaths = new Array(request.sources.length);
  for (let i = 0; i < request.sources.length; i++) {
    const src = request.sources[i];
    if (!src || typeof src.path !== 'string' || typeof src.code !== 'string') throw new Error('Each source entry requires string path and code');
    const relPath = normalizeRelPath(src.path);
    const absPath = path.resolve(APP_DIR, relPath);
    const checkRel = path.relative(APP_DIR, absPath).split(path.sep).join('/');
    if (!checkRel || checkRel.startsWith('..') || path.isAbsolute(checkRel)) {
      throw new Error('Missing module in frontend/workbench/app: ' + src.path);
    }
    relPaths[i] = relPath;
    if (!(fs.existsSync(absPath) && fs.statSync(absPath).isFile() && fs.readFileSync(absPath, 'utf8') === src.code)) {
      (sourceOverrides || (sourceOverrides = Object.create(null)))[relPath] = src.code;
    }
  }
  const overridesKey = sourceOverrides ? JSON.stringify(sourceOverrides) : '';
  for (let i = 0; i < request.sources.length; i++) {
    const src = request.sources[i], relPath = relPaths[i];
    const cacheKey = relPath + '\0' + src.code + '\0' + stubsKey + (overridesKey ? '\0' + overridesKey : '');
    if (COMPILE_CACHE.has(cacheKey)) outputs[i] = { path: src.path, code: COMPILE_CACHE.get(cacheKey) };
    else uncached.push({ index: i, path: src.path, relPath, cacheKey });
  }
  if (uncached.length > 0) {
    const { port1, port2 } = new MessageChannel(), ctrl = new Int32Array(new SharedArrayBuffer(4));
    getWorker().postMessage({ port: port2, ctrl, items: uncached.map(u => ({ relPath: u.relPath })), stubs, sourceOverrides, stubsKey, overridesKey }, [port2]);
    Atomics.wait(ctrl, 0, 0);
    const msg = receiveMessageOnPort(port1).message;
    port1.close();
    if (!msg.ok) throw new Error(msg.error);
    uncached.forEach((u, j) => { COMPILE_CACHE.set(u.cacheKey, msg.compiled[j]); outputs[u.index] = { path: u.path, code: msg.compiled[j] }; });
  }
  if (request.check_combined) new vm.Script(outputs.map(item => item.code).join('\n;\n'), { filename: 'workbench-combined.js' });
  return { outputs };
}

function bundleSingleEntry(entryAbs, appDir, inputSet) {
  const realAppDir = fs.realpathSync(appDir);
  const result = esbuild.buildSync({
    entryPoints: [entryAbs], bundle: true, platform: 'browser', format: 'iife', packages: 'external',
    target: 'chrome109', charset: 'utf8', write: false, metafile: true, logLevel: 'silent',
  });
  for (const [depRelPath, inputMeta] of Object.entries(result.metafile.inputs)) {
    const depAbs = fs.realpathSync(path.resolve(depRelPath));
    const rel = path.relative(realAppDir, depAbs).split(path.sep).join('/');
    if (rel.startsWith('..') || path.isAbsolute(rel)) throw new Error('Missing module in frontend/workbench/app: ' + rel);
    assertNoDynamicImport(fs.readFileSync(depAbs, 'utf8'), rel);
    for (const imp of inputMeta.imports) if (imp.external) throw new Error('Unsupported bare or remote import specifier in offline build: ' + imp.path);
    inputSet.add(rel);
  }
  return result.outputFiles[0].text;
}

function bundleProduction(options = {}) {
  const appDir = options.appDir ? path.resolve(options.appDir) : APP_DIR, inputSet = new Set();
  const themeCode = bundleSingleEntry(path.join(appDir, 'theme.js'), appDir, inputSet);
  const mainCode = bundleSingleEntry(path.join(appDir, 'shell/main.jsx'), appDir, inputSet);
  return { outputs: [{ path: 'app/theme.js', code: themeCode }, { path: 'app/main.js', code: mainCode }], inputs: Array.from(inputSet).sort() };
}

if (require.main === module) {
  try {
    const out = process.argv.includes('--bundle-production')
      ? bundleProduction()
      : ((input => (input && input.mode === 'production' ? bundleProduction(input) : compile(input)))(JSON.parse(fs.readFileSync(0, 'utf8'))));
    process.stdout.write(JSON.stringify(out));
  } catch (error) {
    process.stderr.write(String(error && error.message ? error.message : error) + '\n');
    process.exit(1);
  }
}

module.exports = { compile, bundleProduction, normalizeRelPath };
