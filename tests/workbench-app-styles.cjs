'use strict';

// Dependency-free source contract for the application-owned CSS layer.
// This checks declarations, not rendered geometry or full CSS syntax validity.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const DEFAULT_STYLES = path.resolve(__dirname, '../frontend/workbench/app/styles');
const PROTOTYPE_DIR = path.resolve(__dirname, '../frontend/workbench/prototype');
const APP_DIR = path.resolve(__dirname, '../frontend/workbench/app');

function listFiles(folder, extensions) {
  const files = [];
  if (!fs.existsSync(folder)) return files;
  for (const item of fs.readdirSync(folder, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const name = path.join(folder, item.name);
    if (item.isDirectory()) files.push(...listFiles(name, extensions));
    else if (item.isFile() && extensions.some(extension => item.name.endsWith(extension))) files.push(name);
  }
  return files;
}

// Custom properties are "defined" when a stylesheet declares them (app layer or imported prototype tokens)
// or when application scripts set them dynamically by name (inline style objects, setProperty calls).
function collectDefinedVariables(stylesDir) {
  const defined = new Set();
  const declaration = /(^|[;{}\s])(--[\w-]+)\s*:/g;
  const scripted = /['"`](--[\w-]+)['"`]/g;
  const stylesheets = [...listFiles(stylesDir, ['.css']), ...listFiles(PROTOTYPE_DIR, ['.css'])];
  for (const file of stylesheets) {
    let code;
    try { code = maskNonCode(fs.readFileSync(file, 'utf8')); } catch (_) { continue; }
    let match;
    while ((match = declaration.exec(code))) defined.add(match[2]);
  }
  for (const file of listFiles(APP_DIR, ['.js', '.jsx'])) {
    const source = fs.readFileSync(file, 'utf8');
    let match;
    while ((match = scripted.exec(source))) defined.add(match[1]);
  }
  return defined;
}

function maskNonCode(source) {
  const masked = source.split('');
  const blank = (start, end) => {
    for (let i = start; i < end; i++) if (masked[i] !== '\n' && masked[i] !== '\r') masked[i] = ' ';
  };
  function quotedEnd(start) {
    const quote = source[start];
    let cursor = start + 1;
    while (cursor < source.length) {
      if (source[cursor] === '\\') cursor += 2;
      else if (source[cursor++] === quote) return cursor;
    }
    throw new Error('Unterminated CSS string');
  }
  for (let cursor = 0; cursor < source.length;) {
    if (source.startsWith('/*', cursor)) {
      const end = source.indexOf('*/', cursor + 2);
      if (end < 0) throw new Error('Unterminated CSS comment');
      blank(cursor, end + 2);
      cursor = end + 2;
    } else if (source[cursor] === '"' || source[cursor] === "'") {
      const end = quotedEnd(cursor);
      blank(cursor, end);
      cursor = end;
    } else {
      const url = source.slice(cursor).match(/^url\s*\(/i);
      if (!url || (cursor > 0 && /[\w-]/.test(source[cursor - 1]))) { cursor++; continue; }
      const start = cursor;
      cursor += url[0].length;
      let depth = 1;
      while (cursor < source.length && depth > 0) {
        const character = source[cursor];
        if (character === '"' || character === "'") cursor = quotedEnd(cursor);
        else if (character === '\\') cursor += 2;
        else { if (character === '(') depth++; if (character === ')') depth--; cursor++; }
      }
      if (depth) throw new Error('Unterminated CSS url()');
      blank(start, cursor);
    }
  }
  return masked.join('');
}

function checkSource(source, filename, definedVariables = null) {
  const violations = [];
  const lines = source.split(/\r?\n/);
  const lineAt = offset => source.slice(0, offset).split('\n').length;
  const add = (rule, offset, message) => violations.push({ file: filename, line: lineAt(offset), rule, message });
  let code;
  try { code = maskNonCode(source); }
  catch (error) { return [{ file: filename, line: 1, rule: 'read-css', message: error.message }]; }
  const declarations = /(?:^|[;{}])\s*([\w-]+)\s*:\s*([^;{}]*)(?=[;}])/gm;
  let match;
  while ((match = declarations.exec(code))) {
    const property = match[1].toLowerCase();
    const value = match[2];
    const valueOffset = match.index + match[0].length - value.length;
    const color = /#[\da-f]{8}\b|#[\da-f]{6}\b|#[\da-f]{4}\b|#[\da-f]{3}\b|\brgba?\s*\(/ig;
    let found;
    while ((found = color.exec(value))) {
      add('no-literal-colors', valueOffset + found.index, 'Use a semantic CSS color token instead of ' + found[0]);
    }
    if (property === 'font-size') {
      const pixels = /(?:^|[^\w.-])(-?(?:\d+\.\d*|\.\d+))px\b/ig;
      while ((found = pixels.exec(value))) {
        if (!Number.isInteger(Number(found[1]))) {
          add('integer-font-size', valueOffset + found.index, 'Fractional pixel font-size: ' + found[1] + 'px');
        }
      }
    }
    if (property === 'z-index' && !/^\s*var\(\s*--wb-z-[\w-]+\s*\)\s*(?:!\s*important\s*)?$/i.test(value)) {
      add('z-index-token', valueOffset, 'z-index must directly use var(--wb-z-*), without a numeric fallback');
    }
    if (definedVariables) {
      // A var() whose first argument nobody defines silently renders its fallback (or nothing) and hides a broken selector state.
      const references = /var\(\s*(--[\w-]+)/g;
      while ((found = references.exec(value))) {
        if (!definedVariables.has(found[1])) add('undefined-variable', valueOffset + found.index, found[1] + ' is not defined by the app styles, prototype tokens or application scripts');
      }
    }
    const important = /!\s*important\b/ig;
    while ((found = important.exec(value))) {
      const offset = valueOffset + found.index;
      if (path.basename(filename) !== '20-controls.css') {
        add('important-file', offset, '!important is reserved for documented legacy overrides in 20-controls.css');
      }
      const previous = lines[lineAt(offset) - 2] || '';
      const comment = previous.match(/^\s*\/\*\s*override:\s*(.*?)\s*\*\/\s*$/i);
      if (!comment || !comment[1].trim()) {
        add('important-override', offset, '!important needs an override comment with selector and reason on the previous line');
      }
    }
  }
  return violations;
}

function checkDirectory(directory, options = {}) {
  const stylesDir = path.resolve(directory);
  const definedVariables = options.checkVariables ? collectDefinedVariables(stylesDir) : null;
  const files = [];
  function visit(folder) {
    for (const item of fs.readdirSync(folder, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const name = path.join(folder, item.name);
      if (item.isDirectory()) visit(name);
      else if (item.isFile() && item.name.endsWith('.css')) files.push(name);
    }
  }
  visit(stylesDir);
  if (!files.length) throw new Error('No application styles found in ' + stylesDir);
  const sources = [];
  const violations = [];
  for (const file of files) {
    const bytes = fs.readFileSync(file);
    const relative = path.relative(stylesDir, file).split(path.sep).join('/');
    sources.push({ file: relative, sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
    violations.push(...checkSource(bytes.toString('utf8'), relative, definedVariables));
  }
  return { passed: violations.length === 0, styles_dir: stylesDir, sources, violations };
}

function main(argv) {
  // The real app layer always checks var() references; fixtures opt in with --check-variables.
  const usage = 'Usage: node tests/workbench-app-styles.cjs [--styles-dir DIR] [--check-variables]';
  const args = argv.slice();
  const checkVariablesFlag = args.indexOf('--check-variables');
  if (checkVariablesFlag >= 0) args.splice(checkVariablesFlag, 1);
  if (args.length && (args.length !== 2 || args[0] !== '--styles-dir' || !args[1].trim())) throw new Error(usage);
  const directory = args.length ? args[1] : DEFAULT_STYLES;
  const report = checkDirectory(directory, { checkVariables: checkVariablesFlag >= 0 || !args.length });
  process.stdout.write(JSON.stringify(report, null, 2) + '\n');
  return report.passed ? 0 : 1;
}

module.exports = { checkSource, checkDirectory, collectDefinedVariables, main };
if (require.main === module) {
  try { process.exitCode = main(process.argv.slice(2)); }
  catch (error) { process.stderr.write(error.message + '\n'); process.exitCode = 2; }
}
