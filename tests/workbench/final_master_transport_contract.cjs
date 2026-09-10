'use strict';
const assert = require('node:assert/strict');
const {isCanceledRead} = require('./final_master_probe_support.cjs');
const base = 'http://127.0.0.1:12345';
const cases = [
  ['GET', '/api/workbench/v1/process-table/facets/business_code', 'net::ERR_ABORTED', true],
  ['POST', '/api/workbench/v1/entities/batch/query', 'net::ERR_ABORTED', true],
  ['POST', '/api/workbench/v1/entities/batch/facets', 'net::ERR_ABORTED', true],
  ['POST', '/api/workbench/v1/entities/material/facets', 'net::ERR_ABORTED', true],
  ['POST', '/api/workbench/v1/entities/material/facet-selection', 'net::ERR_ABORTED', true],
  ['POST', '/api/workbench/v1/entities/op_type/facets', 'net::ERR_ABORTED', true],
  ['POST', '/api/workbench/v1/entities/material/commands', 'net::ERR_ABORTED', false],
  ['DELETE', '/api/workbench/v1/entities/material/facets', 'net::ERR_ABORTED', false],
  ['PUT', '/api/workbench/v1/entities/material/facets', 'net::ERR_ABORTED', false],
  ['POST', '/api/workbench/v1/entities/unknown/facets', 'net::ERR_ABORTED', false],
  ['POST', '/api/workbench/v1/entities/batch/facet-selection', 'net::ERR_ABORTED', false],
  ['POST', '/api/workbench/v1/entities/material/facets/confirm', 'net::ERR_ABORTED', false],
  ['POST', '/api/workbench/v1/entities/material/facets', 'net::ERR_CONNECTION_REFUSED', false],
  ['GET', '/api/workbench/v1/entities/material', 'net::ERR_FAILED', false],
  ['GET', '/unrelated?path=/api/workbench/', 'net::ERR_ABORTED', false],
  ['POST', '/api/workbench/v1/entities/material', 'net::ERR_ABORTED', false]
];
cases.forEach(([method, path, error, expected]) => assert.equal(isCanceledRead(method, base + path, error), expected, method + ' ' + path + ' ' + error));
console.log(JSON.stringify({cases: cases.length, failed: 0, scope: 'unit transport classification, not backend or browser acceptance'}));
