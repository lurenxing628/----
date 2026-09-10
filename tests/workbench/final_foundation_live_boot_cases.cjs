'use strict';
const assert = require('node:assert/strict');

const bootCases = [
  {id: 'boot-null', mode: 'replace-boot', value: null},
  {id: 'boot-array', mode: 'replace-boot', value: []},
  {id: 'messages-null', mode: 'replace-messages', value: null},
  {id: 'messages-object', mode: 'replace-messages', value: {}},
  {id: 'messages-string', mode: 'replace-messages', value: 'not-an-array'},
  {id: 'messages-item-null', mode: 'replace-messages', value: [null]},
  {id: 'messages-missing-category', mode: 'replace-messages', value: [{message: 'fixture message'}]},
  {id: 'messages-missing-message', mode: 'replace-messages', value: [{category: 'info'}]},
  {id: 'messages-category-number', mode: 'replace-messages', value: [{category: 1, message: 'fixture message'}]},
  {id: 'messages-message-number', mode: 'replace-messages', value: [{category: 'info', message: 1}]},
];

function injectBoot(html, specification) {
  const expression = /(<script\b[^>]*\bid=["']workbench-boot["'][^>]*>)([\s\S]*?)(<\/script>)/g;
  const matches = Array.from(html.matchAll(expression));
  assert.equal(matches.length, 1, 'Injection requires exactly one actual boot JSON script');
  const original = JSON.parse(matches[0][2]);
  assert(original && typeof original === 'object' && !Array.isArray(original), 'Warm page must have a valid boot object');
  assert(['replace-boot', 'replace-messages'].includes(specification.mode));
  const payload = specification.mode === 'replace-boot' ? specification.value : {...original, messages: specification.value};
  const raw = JSON.stringify(payload).replace(/</g, '\\u003c');
  return {payload, body: html.replace(expression, (_match, open, _old, close) => open + raw + close)};
}

if (require.main === module) {
  const original = {schema_version: 1, view: 'dashboard', messages: [], instance_label: '</script>literal'};
  const html = '<header>unchanged</header><script id="workbench-boot" type="application/json">'
    + JSON.stringify(original).replace(/</g, '\\u003c') + '</script><footer>unchanged</footer>';
  assert.equal(new Set(bootCases.map(row => row.id)).size, 10);
  for (const specification of bootCases) {
    const result = injectBoot(html, specification);
    const parsed = JSON.parse(result.body.match(/type="application\/json">([\s\S]*?)<\/script>/)[1]);
    assert.deepEqual(parsed, result.payload);
    assert(result.body.startsWith('<header>unchanged</header>') && result.body.endsWith('<footer>unchanged</footer>'));
    if (specification.mode === 'replace-messages') {
      assert.equal(parsed.schema_version, original.schema_version);
      assert.equal(parsed.instance_label, original.instance_label);
      assert.deepEqual(parsed.messages, specification.value);
    } else assert.deepEqual(parsed, specification.value);
  }
  assert.throws(() => injectBoot('<p>no boot</p>', bootCases[0]));
  assert.throws(() => injectBoot(html + html, bootCases[0]));
  console.log(JSON.stringify({definitions: bootCases.length, mutation_checks: 10, missing_or_duplicate_rejected: 2, browser_executed: false}));
}
module.exports = {bootCases, injectBoot};
