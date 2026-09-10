"""Prove direct dependencies from actual temporary build output, not archived DS pages."""

import ast
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.workbench.asset_sources import script_dependencies
from tests.workbench import test_assets_build as assets

AST_PROBE = r"""
const fs = require('node:fs'), babel = require(process.argv[1]);
const report = {babel: babel.version, freeVendors: [], domMembers: [], inspectors: [], liveCalls: []};
babel.transform(fs.readFileSync(process.argv[2], 'utf8'), {
  sourceType: 'script', code: false, ast: false, plugins: [() => ({visitor: {
    ReferencedIdentifier(p) {
      if (['React', 'ReactDOM'].includes(p.node.name) && !p.scope.getBinding(p.node.name))
        report.freeVendors.push(p.node.name);
    },
    'MemberExpression|OptionalMemberExpression'(p) {
      const property = p.get('property');
      if (!(p.node.computed ? property.isStringLiteral({value: 'ReactDOM'}) :
            property.isIdentifier({name: 'ReactDOM'}))) return;
      const object = p.get('object'), binding = object.isIdentifier() && object.scope.getBinding(object.node.name);
      report.domMembers.push({object: object.toString(), kind: binding && binding.kind,
        owner: binding && binding.path.parentPath.node.id && binding.path.parentPath.node.id.name});
    },
    FunctionDeclaration(p) {
      if (p.node.id.name !== 'inspectEnvironment') return;
      const binding = p.scope.parent.getBinding(p.node.id.name);
      report.inspectors.push({parameter: p.node.params[0].name,
        references: binding.referencePaths.map(ref => ref.parentPath.type)});
    }
  }})]
});
babel.transform(fs.readFileSync(process.argv[3], 'utf8'), {
  sourceType: 'script', code: false, ast: false, plugins: [() => ({visitor: {
    CallExpression(p) {
      const callee = p.get('callee');
      if (!callee.isMemberExpression() || !callee.get('property').isIdentifier({name: 'inspectEnvironment'})) return;
      const object = callee.get('object'), binding = object.scope.getBinding(object.node.name);
      const argument = p.get('arguments')[0];
      report.liveCalls.push({model: binding.path.get('init').toString(), argument: argument.toString(),
        bound: !!argument.scope.getBinding(argument.node.name)});
    }
  }})]
});
report.freeVendors = [...new Set(report.freeVendors)].sort();
console.log(JSON.stringify(report));
"""


RUNTIME_PROBE = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const context = vm.createContext({});
const run = code => vm.runInContext(code, context);
run('window = globalThis; self = globalThis; location = {protocol: "http:"};');
run(fs.readFileSync(process.argv[1], 'utf8'));
run(`var globalDomReads = 0;
  Object.defineProperty(window, 'ReactDOM', {configurable: true,
    get() {globalDomReads++; return undefined;}});`);
run(fs.readFileSync(process.argv[2], 'utf8'));
assert.equal(run('globalDomReads'), 0, 'Foundation loading must not read ReactDOM, even inside a catch');
assert.equal(run('JSON.stringify(APSDesignSystem_edbc5d.__errors)'), '[]');
assert.equal(run('typeof APSSystemWorkbench.inspectEnvironment'), 'function');
run(`var localDomReads = 0;
  var host = {React, location, get ReactDOM() {localDomReads++; return {createRoot() {}};}};
  var runtimeStatus = host => APSSystemWorkbench.inspectEnvironment(host).checks.find(row => row.id === 'runtime').status;`);
assert.equal(run('runtimeStatus(host)'), 'available');
assert.equal(run('localDomReads'), 2);
assert.equal(run('globalDomReads'), 0, 'An injected host must not be replaced with window');
assert.equal(run('runtimeStatus(window)'), 'unavailable');
assert.equal(run('globalDomReads'), 1, 'The exported model reads window only when the caller passes window');
run(`delete window.ReactDOM;`);
run(fs.readFileSync(process.argv[3], 'utf8'));
assert.equal(run('typeof ReactDOM.createRoot'), 'function', 'The actual pinned ReactDOM UMD must still load');
assert.equal(run('runtimeStatus(window)'), 'available');
assert.equal(run('runtimeStatus({React, location})'), 'unavailable', 'No fallback from an incomplete host to window');
console.log(JSON.stringify({foundationGlobalReads: 0, injectedHostReads: run('localDomReads'),
  windowReads: run('globalDomReads'), reactVersion: run('React.version'), domVersion: run('ReactDOM.version')}));
"""


class FoundationDependencyScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = os.environ.get('WORKBENCH_NODE') or shutil.which('node')
        if not cls.node:
            raise RuntimeError('Foundation tests require build-host Node')
        temp = tempfile.TemporaryDirectory(prefix='aps-foundation-scope-')
        cls.addClassCleanup(temp.cleanup)
        cls.output = Path(temp.name) / 'static/workbench'
        assets.build(assets.ROOT, cls.output, cls.node)
        cls.manifest = assets.load_json(cls.output / 'asset-manifest.json')
        cls.records = {row['path']: row for row in cls.manifest['files']}
        cls.react, cls.react_dom, cls.foundation = cls.manifest['scripts'][:3]
        cls.babel = assets.ROOT / 'frontend/workbench/prototype' / assets.load_json(assets.TOOLS / 'build-order.json')['babel']['path']

    @classmethod
    def asset(cls, name):
        return cls.output / name[len('workbench/'):]

    def probe(self, code, *paths):
        result = subprocess.run([self.node, '-e', code] + [str(path) for path in paths],
                                text=True, encoding='utf-8', capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr[-5000:])
        return json.loads(result.stdout)

    def test_actual_foundation_ast_separates_parameter_reads_from_free_globals(self):
        report = self.probe(AST_PROBE, self.babel, self.asset(self.foundation), self.asset('workbench/app/SystemLive.js'))
        self.assertEqual(report['babel'], '7.29.0')
        self.assertEqual(report['freeVendors'], ['React'])
        self.assertEqual(report['domMembers'], [{'object': 'w', 'kind': 'param', 'owner': 'inspectEnvironment'}] * 2)
        self.assertEqual(report['inspectors'], [{'parameter': 'w', 'references': ['ObjectProperty']}])
        self.assertEqual(report['liveCalls'], [{'model': 'window.APSSystemWorkbench', 'argument': 'window', 'bound': False}])
        self.assertEqual(self.records[self.foundation]['dependency_symbols'], [{'path': self.react, 'symbols': ['React']}])

    def test_actual_foundation_executes_without_react_dom_and_inspects_supplied_host(self):
        report = self.probe(RUNTIME_PROBE, self.asset(self.react), self.asset(self.foundation), self.asset(self.react_dom))
        self.assertEqual(report['foundationGlobalReads'], 0)
        self.assertEqual(report['injectedHostReads'], 2)
        self.assertEqual(report['windowReads'], 1)
        self.assertEqual(report['reactVersion'], '18.3.1')
        self.assertEqual(report['domVersion'], '18.3.1-next-f1338f8080-20240426')

    def test_real_main_and_resource_controls_keep_actual_dependencies(self):
        self.assertEqual(self.records[self.react_dom]['dependency_symbols'], [{'path': self.react, 'symbols': ['React']}])
        resource = self.records['workbench/app/ResourceControls.js']['dependency_symbols']
        self.assertEqual(resource, sorted([
            {'path': 'workbench/app/resource-contract.js', 'symbols': ['APSResourceContract']},
            {'path': 'workbench/app/resource-session.js', 'symbols': ['APSResourceSession']},
            {'path': self.foundation, 'symbols': ['APSFieldReports', 'APSWorkbenchUI', 'Ico', 'SMIcon']},
            {'path': self.react, 'symbols': ['React']},
        ], key=lambda row: row['path']))
        for name in ('main', 'ResourceTableFilter', 'WorkbenchControls', 'WorkbenchNumberControls', 'ProcessSourceEditor'):
            with self.subTest(consumer=name):
                symbols = self.records['workbench/app/' + name + '.js']['dependency_symbols']
                self.assertIn({'path': self.react_dom, 'symbols': ['ReactDOM']}, symbols)
                self.assertIn({'path': self.react, 'symbols': ['React']}, symbols)
        self.assertIn({'path': 'workbench/app/ResourceControls.js', 'symbols': ['ResourceControls']},
                      self.records['workbench/app/ResourceTableFilter.js']['dependency_symbols'])

    def test_a_real_free_read_in_foundation_requires_react_dom_and_earlier_loading(self):
        vendors = [self.react, self.react_dom]
        payload = {name: self.asset(name).read_bytes() for name in vendors + [self.foundation]}
        payload[self.foundation] += b'\nReactDOM.createPortal;\n'
        result = script_dependencies(self.node, self.babel, payload, vendors + [self.foundation], vendors)
        self.assertEqual(result[self.foundation], sorted([
            {'path': self.react, 'symbols': ['React']}, {'path': self.react_dom, 'symbols': ['ReactDOM']},
        ], key=lambda row: row['path']))
        with self.assertRaisesRegex(ValueError, 'Script dependency must load earlier:.*foundation.*react-dom'):
            script_dependencies(self.node, self.babel, payload, [self.react, self.foundation, self.react_dom], vendors)

    def test_python38_syntax(self):
        ast.parse(Path(__file__).read_text(encoding='utf-8'), filename=__file__, feature_version=(3, 8))


if __name__ == '__main__':
    unittest.main()
