'use strict';
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');

function formatStream(name, text) {
  const body = text.endsWith('\r\n')
    ? text.slice(0, -2)
    : text.endsWith('\n')
      ? text.slice(0, -1)
      : text;
  return `${name}:\n${body}`;
}

function spawnNodeSync(args, options, label) {
  const result = spawnSync(
    process.execPath,
    [...process.execArgv, ...args],
    { ...options, encoding: 'utf8' }
  );
  if (result.error || result.status !== 0) {
    const meta = [`status=${result.status}`, `signal=${result.signal}`];
    if (result.error) meta.push(`error=${result.error.message}`);
    const header = `${label} failed (${meta.join(', ')})`;
    const out = result.stdout || '';
    const err = result.stderr || '';
    const parts = [];
    if (out !== '') parts.push(formatStream('stdout', out));
    if (err !== '') parts.push(formatStream('stderr', err));
    throw new assert.AssertionError({
      message: parts.length ? `${header}:\n${parts.join('\n')}` : `${header} (empty stdout and stderr)`,
      actual: result.status,
      expected: 0,
      operator: 'spawnNodeSync',
    });
  }
  return result;
}

module.exports = { spawnNodeSync };
