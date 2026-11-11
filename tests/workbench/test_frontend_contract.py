"""Frontend workbench contracts for navigation, dirty guards, memoized projections, and single-pass receipt validation."""

import json
import subprocess
from pathlib import Path

from tests._support.node_runtime_support import node_runtime

ROOT = Path(__file__).resolve().parents[2]


def _run_node(script: str) -> dict:
    wrapped = f"'use strict';\n(async () => {{\n{script}\n}})().catch(err => {{ console.error(err); process.exit(1); }});"
    result = subprocess.run(
        [node_runtime(), "-e", wrapped],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_scroll_and_context_save_errors_keep_workspace_and_dirty_guard_mounted():
    report = _run_node(
        r"""
        'use strict';
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile, bundleProduction } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const files = ['WorkbenchGuards.js', 'WorkbenchNavigation.js', 'shell/main.jsx'];
        const compiled = compile({
          sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(appDir, name), 'utf8') })),
          check_combined: false,
        });

        function createHarness(initialHref = 'http://127.0.0.1:8080/workbench?view=batches') {
          let cursor = 0, rootTree = null, replaceError = null;
          const slots = [], effects = [], layoutEffects = [], listeners = new Map(), docListeners = new Map();
          const boot = {
            schema_version: 1,
            view: 'batches',
            entry_url: '/workbench',
            trial_url: '/workbench/trial',
            help_url: '/docs/manual',
            instance_label: '本机实例',
            messages: [],
            titles: { dashboard: '值班台', batches: '批次管理', system: '系统管理' },
            enabled_views: ['dashboard', 'batches', 'system'],
            view_aliases: {},
            nav_groups: [{ title: '主导航', items: [
              { id: 'dashboard', label: '值班台', icon: 'home' },
              { id: 'batches', label: '批次管理', icon: 'box' },
              { id: 'system', label: '系统管理', icon: 'settings' },
            ] }],
          };
          const rootEl = {
            attrs: {},
            setAttribute(k, v) { this.attrs[k] = v; },
            replaceChildren() {},
          };
          const sameDeps = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
          let AppComp = null;
          const React = {
            Fragment: 'fragment',
            createElement(type, props, ...children) {
              const flat = children.flat(Infinity);
              if (props && props.ref && typeof props.ref === 'object' && props.ref.current === null) {
                props.ref.current = { clientWidth: 640, focus() {}, scrollIntoView() {}, getBoundingClientRect: () => ({ top: 100, left: 0, bottom: 120 }) };
              }
              return { type, props: { ...(props || {}), children: flat.length <= 1 ? flat[0] : flat } };
            },
            useId() { return ':r' + (cursor++) + ':'; },
            useRef(val) {
              const i = cursor++;
              if (!slots[i]) slots[i] = { current: val };
              return slots[i];
            },
            useState(init) {
              const i = cursor++;
              if (!slots[i]) slots[i] = { value: typeof init === 'function' ? init() : init };
              const slot = slots[i];
              return [slot.value, next => { slot.value = typeof next === 'function' ? next(slot.value) : next; }];
            },
            useCallback(fn, deps) { return this.useMemo(() => fn, deps); },
            useMemo(fn, deps) {
              const i = cursor++;
              if (!slots[i] || !sameDeps(slots[i].deps, deps)) slots[i] = { deps, value: fn() };
              return slots[i].value;
            },
            useLayoutEffect(fn, deps) {
              const i = cursor++;
              if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
                const prev = slots[i];
                slots[i] = { deps };
                layoutEffects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
              }
            },
            useEffect(fn, deps) {
              const i = cursor++;
              if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
                const prev = slots[i];
                slots[i] = { deps };
                effects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
              }
            },
          };

          let scheduledSave = null, isDirty = true;
          const historyObj = {
            state: { workbench: { view: 'batches', context: {}, key: 0 } },
            scrollRestoration: 'auto',
            replaceState(nextState, _title, nextUrl) {
              if (replaceError) throw replaceError;
              this.state = nextState;
              if (nextUrl) w.location.href = new URL(nextUrl, w.location.origin).href;
            },
            pushState(nextState, _title, nextUrl) {
              this.state = nextState;
              if (nextUrl) w.location.href = new URL(nextUrl, w.location.origin).href;
            },
            go() {},
          };

          let workspaceMounts = 0, workspaceUnmounts = 0, rememberedCallback = null;
          function BatchWorkspace() {
            w.__wbRuntime.getModule('WorkbenchGuards.js').useDirtyGuard({ owner: 'batch-editor', dirty: isDirty, message: '批次草稿未保存' });
            React.useEffect(() => {
              workspaceMounts++;
              return () => { workspaceUnmounts++; };
            }, []);
            return React.createElement('div', { 'data-workspace': 'batches' }, 'batches-mounted');
          }

          const w = vm.createContext({
            console, URL, Set, Map, Error, TypeError, Event: class { constructor(t) { this.type = t; } },
            performance: { now: () => 0 },
            requestAnimationFrame: () => 1,
            cancelAnimationFrame: () => {},
            setTimeout: fn => { scheduledSave = fn; return 1; },
            clearTimeout: () => { scheduledSave = null; },
            location: new URL(initialHref),
            history: historyObj,
            document: {
              title: '',
              activeElement: null,
              getElementById(id) {
                if (id === 'root') return rootEl;
                if (id === 'workbench-boot') return { textContent: JSON.stringify(boot) };
                return null;
              },
              querySelector() { return { scrollTop: 10, scrollLeft: 0, querySelectorAll: () => [] }; },
              addEventListener(type, fn) { if (!docListeners.has(type)) docListeners.set(type, new Set()); docListeners.get(type).add(fn); },
              removeEventListener(type, fn) { docListeners.get(type)?.delete(fn); },
            },
            React,
            ReactDOM: {
              createRoot() {
                return { render(el) { AppComp = el.type; } };
              },
            },
            __wbStubs: {
              'shared/runtime/theme.js': { get: () => ({ theme: 'light', error: '' }), subscribe: () => () => {}, set() {} },
              'WorkbenchDensity.js': { get: () => ({ density: 'comfortable', error: '' }), subscribe: () => () => {}, set() {} },
              'WorkbenchScrollShadows.js': { attach: () => () => {} },
              'BatchAPI.js': { create: () => ({}) },
              'ResourceControls.jsx': { Icon: () => null },
              'shared/ui/icons.jsx': { Ico: () => null },
              'WorkbenchControlStyles.jsx': () => null,
              'WorkbenchControls.jsx': () => null,
              'WorkbenchNumberControls.jsx': () => null,
              'WorkbenchGuardHost.jsx': () => null,
              'WorkbenchPageContext.jsx': {
                Provider({ remember, children }) { rememberedCallback = remember; return children; },
              },
              'WorkbenchCaption.jsx': {
                Caption: () => null,
                Provider({ children }) { return children; },
              },
              'WorkbenchBoundary.jsx': ({ children }) => children,
              'BatchWorkspace.jsx': BatchWorkspace,
              'DashboardWorkspace.jsx': () => React.createElement('div', { 'data-workspace': 'dashboard' }, 'dashboard-mounted'),
            },
            addEventListener(type, fn) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); },
            removeEventListener(type, fn) { listeners.get(type)?.delete(fn); },
            dispatchEvent() {},
            scrollTo() {},
            scrollX: 0,
            scrollY: 20,
          });
          w.window = w;

          for (const out of compiled.outputs) vm.runInContext(out.code, w, { filename: out.path });
          const WorkbenchGuards = w.__wbRuntime.getModule('WorkbenchGuards.js');

          function renderTree(node) {
            if (!node || typeof node !== 'object') return node;
            if (Array.isArray(node)) return node.map(renderTree);
            if (typeof node.type === 'function') return renderTree(node.type(node.props || {}));
            const children = node.props && node.props.children !== undefined ? renderTree(node.props.children) : undefined;
            return { ...node, props: { ...(node.props || {}), children } };
          }
          function render() {
            cursor = 0;
            rootTree = renderTree(React.createElement(AppComp, {}));
            while (layoutEffects.length) layoutEffects.shift()();
            while (effects.length) effects.shift()();
            return rootTree;
          }
          function find(node, pred) {
            if (!node || typeof node !== 'object') return null;
            if (Array.isArray(node)) {
              for (const item of node) { const hit = find(item, pred); if (hit) return hit; }
              return null;
            }
            if (pred(node)) return node;
            return find(node.props && node.props.children, pred);
          }

          return {
            w,
            render,
            find,
            setReplaceError(err) { replaceError = err; },
            setDirty(val) { isDirty = val; },
            triggerScroll() { for (const fn of docListeners.get('scroll') || []) fn(); },
            flushScheduledSave() { if (scheduledSave) { const fn = scheduledSave; scheduledSave = null; fn(); } },
            triggerPagehide() { for (const fn of listeners.get('pagehide') || []) fn(); },
            triggerPopstate() { for (const fn of listeners.get('popstate') || []) fn(); },
            getRemembered: () => rememberedCallback,
            stats: () => ({ workspaceMounts, workspaceUnmounts, dirty: WorkbenchGuards.hasDirty() }),
          };
        }

        // 1. Save / pagehide / rememberPage and onRestore replaceState error keeps workspace and dirty guard mounted.
        const h = createHarness();
        let tree = h.render();
        assert.equal(h.stats().workspaceMounts, 1);
        assert.equal(h.stats().dirty, true);

        // Trigger rememberPage while restoring is true and replaceState throws.
        h.setReplaceError(new Error('无法写入历史状态：达到配额上限'));
        h.getRemembered()({ filter: 'urgent' });
        h.triggerPagehide();
        tree = h.render();
        assert.equal(h.stats().workspaceMounts, 1);
        assert.equal(h.stats().workspaceUnmounts, 0, 'Active workspace must NOT unmount on replaceState failure');
        assert.equal(h.stats().dirty, true, 'Dirty guard must remain active');
        assert.ok(h.find(tree, n => n.props && n.props['data-workspace'] === 'batches'), 'BatchWorkspace stays mounted');
        let navAlert = h.find(tree, n => n.props && n.props.className === 'wb-navigation-error');
        assert.ok(navAlert && navAlert.props.children === '无法写入历史状态：达到配额上限');

        // Trigger onRestore via popstate when captured snapshot exists and remember throws: sets navigationError and keeps workspace mounted.
        h.setDirty(false);
        h.render();
        h.setReplaceError(new Error('恢复历史状态失败：达到配额上限'));
        h.triggerPopstate();
        tree = h.render();
        assert.equal(h.stats().workspaceMounts, 1);
        assert.equal(h.stats().workspaceUnmounts, 0);
        assert.ok(h.find(tree, n => n.props && n.props['data-workspace'] === 'batches'), 'Restored BatchWorkspace stays mounted when remember throws');
        navAlert = h.find(tree, n => n.props && n.props.className === 'wb-navigation-error');
        assert.ok(navAlert && navAlert.props.children === '恢复历史状态失败：达到配额上限');

        // 2. Unresolvable initial route still sets page.error and does not mount workspace.
        const bad = createHarness('http://127.0.0.1:8080/workbench?view=nonexistent');
        const badTree = bad.render();
        assert.equal(bad.stats().workspaceMounts, 0);
        assert.equal(bad.find(badTree, n => n.props && n.props['data-workspace'] === 'batches'), null);
        assert.ok(bad.find(badTree, n => n.props && n.props.role === 'alert' && n.props.className === 'sm-error'));

        console.log(JSON.stringify({ ok: true }));
        """
    )
    assert report["ok"] is True


def test_system_maintenance_config_dirty_guard_and_cleanup_status_contract():
    report = _run_node(
        r"""
        'use strict';
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile, bundleProduction } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const files = [
          'WorkbenchTerms.js', 'shared/network/transport.js', 'WorkbenchGuards.js', 'SystemRestoreStatus.js',
          'SystemMaintenanceAPI.js', 'SystemMaintenanceControls.jsx', 'SystemMaintenanceRecords.jsx',
          'SystemMaintenanceConfig.jsx', 'SystemLive.jsx'
        ];
        const compiled = compile({
          sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(appDir, name), 'utf8') })),
          check_combined: false,
        });

        let cursor = 0;
        const slots = [], effects = [], layoutEffects = [];
        const sameDeps = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
        const React = {
          Fragment: 'fragment',
          createElement(type, props, ...children) {
            const flat = children.flat(Infinity);
            return { type, props: { ...(props || {}), children: flat.length <= 1 ? flat[0] : flat } };
          },
          useId() { return ':id-' + (cursor++) + ':'; },
          useRef(v) { const i = cursor++; if (!slots[i]) slots[i] = { current: v }; return slots[i]; },
          useState(init) {
            const i = cursor++;
            if (!slots[i]) slots[i] = { value: typeof init === 'function' ? init() : init };
            const s = slots[i];
            return [s.value, next => { s.value = typeof next === 'function' ? next(s.value) : next; }];
          },
          useReducer(red, init) {
            const [v, set] = this.useState(init);
            return [v, act => set(old => red(old, act))];
          },
          useCallback(fn, deps) { return this.useMemo(() => fn, deps); },
          useMemo(fn, deps) {
            const i = cursor++;
            if (!slots[i] || !sameDeps(slots[i].deps, deps)) slots[i] = { deps, value: fn() };
            return slots[i].value;
          },
          useLayoutEffect(fn, deps) {
            const i = cursor++;
            if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
              const prev = slots[i];
              slots[i] = { deps };
              layoutEffects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
            }
          },
          useEffect(fn, deps) {
            const i = cursor++;
            if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
              const prev = slots[i];
              slots[i] = { deps };
              effects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
            }
          },
        };

        const configPayload = {
          data: {
            values: {
              auto_backup_enabled: 'yes',
              auto_backup_interval_minutes: 60,
              auto_backup_cleanup_enabled: 'yes',
              auto_backup_keep_days: 7,
              auto_backup_cleanup_interval_minutes: 120,
              auto_log_cleanup_enabled: 'yes',
              auto_log_cleanup_keep_days: 30,
              auto_log_cleanup_interval_minutes: 180,
            },
            defaulted_fields: [],
            write_context: { write_token: 'w'.repeat(32) },
          },
        };

        const w = vm.createContext({
          console, URL, Set, Map, Error, TypeError, Date, Math, Number, String, Boolean, Array, Object, JSON, RegExp, Promise,
          AbortController,
          setTimeout, clearTimeout,
          React,
          addEventListener() {},
          removeEventListener() {},
          document: {
            activeElement: null,
            getElementById: () => ({ focus() {} }),
          },
          __wbStubs: {
            'shared/ui/icons.jsx': { SMIcon: () => null },
            'shell/SystemManagementScreen.jsx': { SMExport: () => null, SMUnavailable: () => null, SMStatus: () => null },
            'shared/ui/Button.jsx': { ControlButton: 'button' },
            'shared/ui/Metric.jsx': { MetricStrip: 'div', Metric: 'div' },
            'shared/runtime/environment.js': { inspectEnvironment: () => ({ schemaVersion: 1, checkedAt: '2026-10-30T08:00:00Z', protocol: 'http:', checks: [] }) },
            'WorkbenchDensity.js': { get: () => ({ density: 'comfortable' }), subscribe: () => () => {}, set() {} },
            'WorkbenchPageContext.jsx': { useSnapshot() {} },
            'WorkbenchFormat.js': { dateTime: String, instant: String, number: String },
            'WorkbenchReferences.jsx': { WorkbenchReference: 'reference', WorkbenchError: 'error-box' },
            'ResourceControls.jsx': {
              Button(props) { return React.createElement('button', props, props.children); },
              Modal: 'modal',
              EmptyState: 'empty',
              Pager: 'pager',
            },
            'shared/session/query.js': {
              useQuery() { return { result: configPayload, error: null, loading: false }; },
            },
          },
        });
        w.window = w;
        for (const out of compiled.outputs) vm.runInContext(out.code, w, { filename: out.path });

        const WorkbenchGuards = w.__wbRuntime.getModule('WorkbenchGuards.js');
        const SystemMaintenanceConfig = w.__wbRuntime.getModule('SystemMaintenanceConfig.jsx').SystemMaintenanceConfig;
        const SystemMaintenanceAPI = w.__wbRuntime.getModule('SystemMaintenanceAPI.js');

        const prompts = [];
        WorkbenchGuards.subscribe(p => prompts.push(p));

        function renderNode(node) {
          if (!node || typeof node !== 'object') return node;
          if (Array.isArray(node)) return node.map(renderNode);
          if (typeof node.type === 'function') return renderNode(node.type(node.props || {}));
          const children = node.props && node.props.children !== undefined ? renderNode(node.props.children) : undefined;
          return { ...node, props: { ...(node.props || {}), children } };
        }
        function find(node, pred) {
          if (!node || typeof node !== 'object') return null;
          if (Array.isArray(node)) {
            for (const item of node) { const hit = find(item, pred); if (hit) return hit; }
            return null;
          }
          if (pred(node)) return node;
          return find(node.props && node.props.children, pred);
        }

        let currentTab = 'config', isActive = true, isSuspended = false;
        const command = { locked: false, lockedReason: '', get suspended() { return isSuspended; }, execute() {} };
        function renderConfig() {
          cursor = 0;
          const tree = renderNode(React.createElement(SystemMaintenanceConfig, {
            revision: '1:0', command, active: isActive, tab: currentTab,
            theme: 'light', onSetTheme() {}, pageSize: 10, onPageSize() {}, compact: false, onCompact() {},
          }));
          while (layoutEffects.length) layoutEffects.shift()();
          while (effects.length) effects.shift()();
          return tree;
        }

        let tree = renderConfig();
        tree = renderConfig();
        assert.equal(WorkbenchGuards.hasDirty(), false);

        const intervalInput = find(tree, n => n.type === 'input' && n.props.id === 'sm-maintenance-auto_backup_interval_minutes');
        assert.ok(intervalInput);
        intervalInput.props.onChange({ target: { value: '90' } });
        tree = renderConfig();
        assert.equal(WorkbenchGuards.hasDirty(), true, 'Modified config draft must register dirty guard');

        // Prompt contains exact expected message.
        const leavePromise = WorkbenchGuards.confirmLeave();
        const prompt = WorkbenchGuards.getPrompt();
        assert.ok(prompt && prompt.messages.includes('系统自动维护配置存在未保存修改，确定离开当前页面吗？'));
        WorkbenchGuards.resolvePrompt(prompt.id, false);
        assert.equal(await leavePromise, false);

        // Temporarily suspending read (active=false while tab==='config') preserves the unsaved draft!
        isActive = false; isSuspended = true;
        tree = renderConfig();
        isActive = true; isSuspended = false;
        tree = renderConfig();
        const afterSuspendInput = find(tree, n => n.type === 'input' && n.props.id === 'sm-maintenance-auto_backup_interval_minutes');
        assert.equal(String(afterSuspendInput.props.value), '90', 'Draft must survive temporary readSuspended pause on config tab');

        // Leaving the config tab (tab !== 'config') resets the unsaved draft back to base values.
        currentTab = 'overview'; isActive = false;
        tree = renderConfig();
        currentTab = 'config'; isActive = true;
        tree = renderConfig();
        const afterLeaveInput = find(tree, n => n.type === 'input' && n.props.id === 'sm-maintenance-auto_backup_interval_minutes');
        assert.equal(String(afterLeaveInput.props.value), '60', 'Draft resets after leaving config tab');
        assert.equal(WorkbenchGuards.hasDirty(), false);

        // #15-frontend: cleanup_event accepts partial & skipped statuses in SystemMaintenanceAPI.collection.
        const validCollection = {
          ok: true,
          schema_version: 1,
          warnings: [],
          meta: {
            as_of: '2026-10-30T08:00:00',
            request_ref: 'a'.repeat(32),
            snapshot_ref: 's'.repeat(32),
            source: 'production',
            time_basis: 'factory_local',
          },
          data: {
            scope: 'backup-files-and-maintenance-events',
            page: { number: 1, size: 10, total: 2, pages: 1 },
            capabilities: { create: true, delete: true, restore: true, blocked_reason: '', restore_reason: '' },
            create_context: { write_token: 'w'.repeat(32) },
            sources: [{ code: 'ok', message: '正常' }],
            rows: [
              {
                key: 'ev-partial',
                record_kind: 'cleanup_event',
                event_ref: 'ev-1',
                event_source: 'operation_audit',
                type: 'cleanup',
                status: 'partial',
                time: '2026-10-30T07:00:00',
                summary: '清理部分异常',
                body: '详情',
                file_capabilities: { download: false, restore: false, delete: false },
              },
              {
                key: 'ev-skipped',
                record_kind: 'cleanup_event',
                event_ref: 'ev-2',
                event_source: 'latest_job_state_only',
                type: 'cleanup',
                status: 'skipped',
                time: '2026-10-30T07:30:00',
                summary: '清理已跳过',
                body: '详情',
                file_capabilities: { download: false, restore: false, delete: false },
              },
            ],
          },
        };
        assert.equal(SystemMaintenanceAPI.collection(validCollection, 'backups'), validCollection);

        console.log(JSON.stringify({ ok: true }));
        """
    )
    assert report["ok"] is True


def test_four_interactive_views_do_zero_redundant_work_on_unrelated_state_changes():
    report = _run_node(
        r"""
        'use strict';
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile, bundleProduction } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const files = [
          'FieldDetail.jsx',
          'OperatorMachinePermissions.jsx',
          'BatchMaterialEditor.jsx',
          'ProcessStageEditor.jsx',
          'ProcessGroupEditor.jsx',
        ];
        const compiled = compile({
          sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(appDir, name), 'utf8') })),
          check_combined: false,
        });

        function createHookHost() {
          let cursor = 0;
          const slots = [], effects = [], layoutEffects = [];
          const sameDeps = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
          const React = {
            Fragment: 'fragment',
            createElement(type, props, ...children) {
              const flat = children.flat(Infinity);
              if (props && props.ref && typeof props.ref === 'object' && props.ref.current === null) {
                props.ref.current = { clientWidth: 640, focus() {}, scrollIntoView() {}, getBoundingClientRect: () => ({ top: 100, left: 0, bottom: 120 }) };
              }
              return { type, props: { ...(props || {}), children: flat.length <= 1 ? flat[0] : flat } };
            },
            useId() { return ':id-' + (cursor++) + ':'; },
            useRef(v) { const i = cursor++; if (!slots[i]) slots[i] = { current: v }; return slots[i]; },
            useState(init) {
              const i = cursor++;
              if (!slots[i]) slots[i] = { value: typeof init === 'function' ? init() : init };
              const s = slots[i];
              return [s.value, next => { s.value = typeof next === 'function' ? next(s.value) : next; }];
            },
            useReducer(red, init) {
              const [v, set] = this.useState(init);
              return [v, act => set(old => red(old, act))];
            },
            useCallback(fn, deps) { return this.useMemo(() => fn, deps); },
            useMemo(fn, deps) {
              const i = cursor++;
              if (!slots[i] || !sameDeps(slots[i].deps, deps)) slots[i] = { deps, value: fn() };
              return slots[i].value;
            },
            useLayoutEffect(fn, deps) {
              const i = cursor++;
              if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
                const prev = slots[i];
                slots[i] = { deps };
                layoutEffects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
              }
            },
            useEffect(fn, deps) {
              const i = cursor++;
              if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
                const prev = slots[i];
                slots[i] = { deps };
                effects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
              }
            },
          };
          function expand(node) {
            if (!node || typeof node !== 'object') return node;
            if (Array.isArray(node)) return node.map(expand);
            if (typeof node.type === 'function') return expand(node.type(node.props || {}));
            const children = node.props && node.props.children !== undefined ? expand(node.props.children) : undefined;
            return { ...node, props: { ...(node.props || {}), children } };
          }
          return {
            React,
            render(fn) {
              cursor = 0;
              const tree = expand(fn());
              while (layoutEffects.length) layoutEffects.shift()();
              while (effects.length) effects.shift()();
              return tree;
            },
          };
        }

        function findAll(node, pred, out = []) {
          if (!node || typeof node !== 'object') return out;
          if (Array.isArray(node)) { node.forEach(n => findAll(n, pred, out)); return out; }
          if (pred(node)) out.push(node);
          if (node.props && node.props.children !== undefined) findAll(node.props.children, pred, out);
          return out;
        }

        const ref = n => n.toString(16).padStart(48, '0');

        // 1. FieldDetail Timeline: 0 PlanGanttModel.instant calls on hover and selection.
        {
          const host = createHookHost();
          let instantCalls = 0;
          const task = {
            task_ref: ref(1),
            plan_ref: ref(2),
            operation_ref: ref(3),
            batch_id: 'B-01',
            operation_label: '10 车削',
            quantity: 10,
            batch_quantity: 10,
            planned_start: '2026-10-20T08:00:00',
            planned_end: '2026-10-20T12:00:00',
            execution: {
              execution_state: 'started',
              data_gaps: [],
              voided_reports: [],
              write_context: { capabilities: { create: true }, blocked_reasons: [] },
              reports: [
                {
                  report_ref: ref(4),
                  report_no: 'R-01',
                  recorded_against_plan_ref: ref(2),
                  completed_quantity: 5,
                  actual_start: '2026-10-20T08:30:00',
                  actual_end: '2026-10-20T10:30:00',
                  effective_processing_hours: 2,
                  actual_machine_label: 'M1',
                  actual_operator_label: 'O1',
                  remark: '',
                  write_context: { capabilities: {}, blocked_reasons: [] },
                  correction_history: [],
                },
              ],
            },
          };
          const w = vm.createContext({
            console, Math, Number, String, Boolean, Array, Object, JSON, Set, Map, Date,
            ResizeObserver: class { observe() {} disconnect() {} },
            innerWidth: 1280, innerHeight: 800,
            React: host.React,
            __wbStubs: {
              'FieldContract.js': {
                detail: v => v,
                pieceLabel: () => '整批',
                quantity: String,
                quantityReasons: {},
                blocked: () => '',
                date: String,
                display: String,
                hours: String,
                reportActions: {},
                fields: [],
              },
              'FieldControls.jsx': { Button: p => host.React.createElement('button', p, p.children), ErrorBox: () => null, Issues: () => null, State: () => null },
              'WorkbenchControls.jsx': { usePrintLayout: () => false },
              'GanttPresentation.js': { axis: () => ({ ticks: [{ at: 1, x: 100 }] }), taskLines: () => ({ primary: 'R-01', secondary: '' }) },
              'GanttPresentationUI.jsx': { Axis: () => null },
              'PlanGanttModel.js': { instant: v => { instantCalls++; return Date.parse(v + 'Z'); } },
              'PointContract.js': { isPoint: () => false },
              'PointGanttModel.js': { bounds: (s, e) => ({ start: s, end: e }) },
              'PointGantt.jsx': { Marker: 'marker' },
              'shared/session/query.js': { useQuery: () => ({ loading: false, result: { data: { task } }, error: null }) },
              'ResourceControls.jsx': { EmptyState: () => null },
              'WorkbenchReferences.jsx': { WorkbenchReference: () => null },
              'FieldVoidEditor.jsx': () => null,
              'FieldEditor.jsx': () => null,
            },
          });
          w.window = w;
          vm.runInContext(compiled.outputs[0].code, w);
          const FieldDetail = w.__wbRuntime.getModule('FieldDetail.jsx').FieldDetail;

          const renderDetail = () => host.render(() => host.React.createElement(FieldDetail, {
            adapter: {}, taskRef: ref(1), scope: {}, snapshot: 's', revision: 0,
            command: { locked: false }, editor: null, retained: null,
            onDraft() {}, onEdit() {}, onCloseEditor() {}, onDone() {}, onNavigate() {}, nextDraft: null, onContinueReady() {}, onRefresh() {},
          }));
          let tree = renderDetail();
          const toggleBtn = findAll(tree, n => n.type === 'button' && n.props.children === '作业时间线')[0];
          toggleBtn.props.onClick();
          instantCalls = 0;
          tree = renderDetail();
          assert.ok(instantCalls > 0, 'Initial timeline open parses instants once');
          instantCalls = 0;
          const bar = findAll(tree, n => n.type === 'button' && String(n.props.className || '').includes('field-timeline-bar'))[0];
          bar.props.onMouseEnter({ currentTarget: { getBoundingClientRect: () => ({ left: 20, bottom: 40 }) } });
          tree = renderDetail();
          bar.props.onClick();
          tree = renderDetail();
          bar.props.onBlur();
          tree = renderDetail();
          assert.equal(instantCalls, 0, 'Hover and selection on Timeline must do 0 PlanGanttModel.instant calls');

          // 1b. FieldDetail with real useQuery skips transient null snapshot during parent refresh and preserves nextDraft.
          const realHost = createHookHost();
          const detailCalls = [], continueResults = [];
          const realCtx = vm.createContext({
            console, Math, Number, String, Boolean, Array, Object, JSON, Set, Map, WeakMap, WeakSet, Date, Promise, Error, TypeError,
            AbortController, DOMException,
            ResizeObserver: class { observe() {} disconnect() {} },
            innerWidth: 1280, innerHeight: 800,
            React: realHost.React,
            __wbStubs: {
              'FieldContract.js': {
                detail: v => v,
                pieceLabel: () => '整批',
                quantity: String,
                quantityReasons: {},
                blocked: () => '',
                date: String,
                display: String,
                hours: String,
                reportActions: {},
                fields: [],
              },
              'FieldControls.jsx': { Button: p => realHost.React.createElement('button', p, p.children), ErrorBox: () => null, Issues: () => null, State: () => null },
              'WorkbenchControls.jsx': { usePrintLayout: () => false },
              'GanttPresentation.js': { axis: () => ({ ticks: [] }), taskLines: () => ({ primary: '', secondary: '' }) },
              'GanttPresentationUI.jsx': { Axis: () => null },
              'PlanGanttModel.js': { instant: v => Date.parse(v + 'Z') },
              'PointContract.js': { isPoint: () => false },
              'PointGanttModel.js': { bounds: (s, e) => ({ start: s, end: e }) },
              'PointGantt.jsx': { Marker: 'marker' },
              'ResourceControls.jsx': { EmptyState: () => null },
              'WorkbenchReferences.jsx': { WorkbenchReference: () => null },
              'FieldVoidEditor.jsx': () => null,
              'FieldEditor.jsx': () => null,
            },
          });
          realCtx.window = realCtx;
          vm.runInContext(compiled.outputs[0].code, realCtx);
          const RealFieldDetail = realCtx.__wbRuntime.getModule('FieldDetail.jsx').FieldDetail;
          const realAdapter = {
            async detail(targetRef, query) {
              detailCalls.push({ targetRef, snapshot_ref: query.snapshot_ref });
              return { data: { task } };
            },
          };
          let snap = null, rev = 1, pendingNextDraft = { continueAfter: true };
          const fixedScope = { plan_ref: ref(2) };
          const handleContinueReady = res => continueResults.push(res);
          const renderRealDetail = () => realHost.render(() => realHost.React.createElement(RealFieldDetail, {
            adapter: realAdapter, taskRef: ref(1), scope: fixedScope, snapshot: snap, revision: rev,
            command: { locked: false }, editor: null, retained: null,
            onDraft() {}, onEdit() {}, onCloseEditor() {}, onDone() {}, onNavigate() {},
            nextDraft: pendingNextDraft, onContinueReady: handleContinueReady, onRefresh() {},
          }));
          let waitTree = renderRealDetail();
          await Promise.resolve(); await Promise.resolve();
          waitTree = renderRealDetail();
          assert.equal(detailCalls.length, 0, 'Null snapshot during parent refresh must issue 0 detail requests');
          assert.equal(continueResults.length, 0, 'Null snapshot transition must not settle or cancel nextDraft');
          assert.equal(waitTree.props.children, '正在读取逐次报工…', 'Null snapshot transition must render loading status');

          snap = 'snap-2';
          renderRealDetail();
          for (let tick = 0; tick < 6; tick++) await Promise.resolve();
          renderRealDetail();
          assert.deepEqual(detailCalls, [{ targetRef: ref(1), snapshot_ref: 'snap-2' }], 'Ready snapshot issues exactly 1 detail request');
          assert.equal(continueResults.length, 1, 'Ready detail resolves nextDraft continuation once');
          assert.equal(continueResults[0].task_ref, ref(1));
        }

        // 2. OperatorMachinePermissions: 0 row scans on search/query/selected changes.
        {
          const host = createHookHost();
          let originalReads = 0, stateRowReads = 0;
          const basePermissions = [
            new Proxy({ machine_ref: ref(10), business_code: 'M1', label: '车床1', skill_level: 'normal', is_primary: 'no' }, {
              get(target, prop) { if (prop === 'machine_ref') originalReads++; return target[prop]; },
            }),
          ];
          basePermissions.map = fn => Array.prototype.map.call(basePermissions, (row, idx, arr) => {
            const out = fn(row, idx, arr);
            return out && out.business_code !== undefined
              ? new Proxy(out, { get(target, prop) { if (prop === 'machine_ref') stateRowReads++; return target[prop]; } })
              : out;
          });
          const w = vm.createContext({
            console, Math, Number, String, Boolean, Array, Object, JSON, Set, Map,
            AbortController,
            React: host.React,
            __wbStubs: {
              'resource-contract.js': { blocked: () => '' },
              'shared/session/query.js': {
                useQuery: (_fn, deps) => ({
                  loading: false,
                  error: null,
                  result: { data: { page: { total: 2 }, entities: [
                    { ref: ref(10), business_code: 'M1', label: '车床1', query: deps[1] },
                    { ref: ref(11), business_code: 'M2', label: '车床2', query: deps[1] },
                  ] } },
                }),
              },
              'ResourceControls.jsx': {
                Button: p => host.React.createElement('button', p, p.children),
                Icon: () => null,
                ErrorBox: () => null,
                Modal: p => host.React.createElement('div', p, p.children, p.footer),
              },
              'WorkbenchGuards.js': { useDirtyGuard: () => 'owner', confirmLeave: async () => true },
              'WorkbenchTerms.js': { refresh_latest: '刷新' },
            },
          });
          w.window = w;
          vm.runInContext(compiled.outputs[1].code, w);
          const OperatorMachinePermissions = w.__wbRuntime.getModule('OperatorMachinePermissions.jsx').OperatorMachinePermissions;

          const entity = {
            ref: ref(20),
            business_code: 'OP1',
            label: '张三',
            write_context: { write_token: 'w'.repeat(32) },
            relationships: { machine_permissions: basePermissions },
          };
          const renderPerm = () => host.render(() => host.React.createElement(OperatorMachinePermissions, {
            adapter: {}, entity, source: 'production', command: { phase: 'idle', locked: false, reset() {} },
            onClose() {}, Feedback: () => null,
          }));
          let tree = renderPerm();
          originalReads = 0;
          stateRowReads = 0;
          const searchInput = findAll(tree, n => n.type === 'input' && n.props['aria-label'] === '搜索可关联设备')[0];
          searchInput.props.onChange({ target: { value: '车床' } });
          tree = renderPerm();
          const form = findAll(tree, n => n.type === 'form')[0];
          form.props.onSubmit({ preventDefault() {} });
          tree = renderPerm();
          const select = findAll(tree, n => n.type === 'select' && n.props['aria-label'] === '选择关联设备')[0];
          select.props.onChange({ target: { value: ref(11) } });
          tree = renderPerm();
          // Across 3 renders (search, query, selected), original is read 0 times and rows[0].machine_ref is read only once per render for <tr key={row.machine_ref}> (total 3),
          // never re-running fields(rows), fields(original), or choices.filter(rows.some).
          assert.equal(originalReads, 0, 'original machine_permissions must do 0 machine_ref reads on search/query/selected changes');
          assert.equal(stateRowReads, 3, 'rows[0].machine_ref must be read only once per render for <tr key>, with 0 choices.filter(rows.some) scans');
          let stringifyCalls = 0;
          const origStringify = w.JSON.stringify;
          w.JSON.stringify = (...args) => { stringifyCalls++; return origStringify(...args); };
          searchInput.props.onChange({ target: { value: '车床2' } });
          tree = renderPerm();
          // PermissionSelect renders 2 selects per row (each with value + 3/2 options = 7 JSON.stringify calls), 0 for fields(rows)/fields(original).
          w.JSON.stringify = origStringify;
          assert.equal(stringifyCalls, 7, 'Search change must do 0 JSON.stringify calls on fields(rows) or fields(original)');
        }

        // 3. BatchMaterialEditor: 0 operation scans and 0 op.label reads on material search changes (#28).
        {
          const host = createHookHost();
          let opScans = 0, labelReads = 0;
          const operations = [
            new Proxy({ ref: ref(30), sequence: 10, label: '下料', piece_id: null }, {
              get(target, prop) {
                if (prop === 'piece_id') opScans++;
                if (prop === 'label') labelReads++;
                return target[prop];
              },
            }),
          ];
          const entity = {
            ref: ref(31),
            business_code: 'B-100',
            write_context: { write_token: 'w'.repeat(32) },
            operations,
            materials: {
              requirements: [
                { row_key: 'rk1', material_ref: ref(32), business_code: 'MAT-1', label: '钢材', unit: 'kg', required_quantity: 5, available_quantity: 2, operation_ref: null, arrivals: [] },
              ],
            },
          };
          const w = vm.createContext({
            console, Math, Number, String, Boolean, Array, Object, JSON, Set, Map,
            React: host.React,
            __wbStubs: {
              'BatchContract.js': {},
              'resource-contract.js': { failure: m => new Error(m) },
              'shared/session/query.js': {
                useQuery: () => ({ loading: false, error: null, result: { meta: { snapshot_ref: 's' }, data: { page: {}, entities: [] } } }),
              },
              'ResourceControls.jsx': {
                Button: p => host.React.createElement('button', p, p.children),
                Modal: p => host.React.createElement('div', p, p.children, p.footer),
                ErrorBox: () => null,
                Field: p => host.React.createElement('label', p, p.children),
                Pager: () => null,
              },
              'ResourceForms.jsx': { Feedback: () => null },
              'WorkbenchControls.jsx': { Pager: () => null },
              'WorkbenchGuards.js': { useDirtyGuard: () => 'owner', confirmLeave: async () => true },
              'WorkbenchTerms.js': { refresh_latest: '刷新' },
            },
          });
          w.window = w;
          vm.runInContext(compiled.outputs[2].code, w);
          const BatchMaterialEditor = w.__wbRuntime.getModule('BatchMaterialEditor.jsx').BatchMaterialEditor;

          const renderMat = () => host.render(() => host.React.createElement(BatchMaterialEditor, {
            adapter: {}, entity, command: { phase: 'idle', locked: false, clearRejection() {}, reset() {} },
            onCommitted() {}, onClose() {},
          }));
          let tree = renderMat();
          assert.equal(opScans, 1);
          assert.equal(labelReads, 1);
          opScans = 0;
          labelReads = 0;
          const search = findAll(tree, n => n.type === 'input' && n.props['aria-label'] === '搜索物料')[0];
          search.props.onChange({ target: { value: '铝合金' } });
          tree = renderMat();
          assert.equal(opScans, 0, 'Material search input change must do 0 scans of entity.operations');
          assert.equal(labelReads, 0, 'Material search input change must do 0 reads of op.label');
        }

        // 4. ProcessGroupEditor: memoizes E.active(entity), preserves operation sequence order in members, and does 0 scans on total_days change.
        {
          const host = createHookHost();
          let activeCalls = 0, sourceScans = 0, sequenceReads = 0;
          const op1 = new Proxy({ ref: ref(41), sequence: 10, label: '热处理', source: 'external', status: 'active', external_group_ref: null, supplier_label: '供方A' }, {
            get(t, p) { if (p === 'source') sourceScans++; return t[p]; },
          });
          const op2 = new Proxy({ ref: ref(42), sequence: 20, label: '表处', source: 'external', status: 'active', external_group_ref: null, supplier_label: '供方A' }, {
            get(t, p) { if (p === 'source') sourceScans++; return t[p]; },
          });
          const trackedOp = new Proxy({ ref: ref(43), sequence: 30, label: '停用工序', source: 'external', status: 'inactive', external_group_ref: null, supplier_label: '供方A' }, {
            get(t, p) { if (p === 'sequence') sequenceReads++; return t[p]; },
          });
          const entity = {
            ref: ref(40),
            operations: [op1, op2, trackedOp],
            external_groups: [],
            workflow: { route: { state: 'confirmed' }, source: { state: 'confirmed' }, hours: { state: 'unconfirmed' } },
            write_context: { write_token: 'w'.repeat(32) },
          };
          const w = vm.createContext({
            console, Math, Number, String, Boolean, Array, Object, JSON, Set, Map,
            AbortController,
            requestAnimationFrame: () => 1,
            cancelAnimationFrame: () => {},
            document: { body: {} },
            React: host.React,
            ReactDOM: { createPortal: el => el },
            __wbStubs: {
              'resource-contract.js': { failure: m => new Error(m), own: (o, k) => Object.prototype.hasOwnProperty.call(o, k), blocked: () => '' },
              'ProcessContract.js': { sourceLabel: s => s, stagePreview: v => v },
              'ResourceControls.jsx': {
                Button: p => host.React.createElement('button', p, p.children),
                Modal: p => host.React.createElement('div', p, p.children, p.footer),
                Search: p => host.React.createElement('input', p),
                ErrorBox: () => null,
                Issues: () => null,
              },
              'ResourceTables.jsx': { Pager: () => null },
              'ResourceForms.jsx': { Feedback: () => null },
              'ProcessSourceEditor.jsx': { ProcessSourcePicker: p => host.React.createElement('div', { 'data-picker': true, target: p.target }) },
              'WorkbenchTerms.js': { refresh_latest: '刷新', accept_latest: '接受' },
            },
          });
          w.window = w;
          vm.runInContext(compiled.outputs[3].code, w);
          const origActive = w.__wbRuntime.getModule('ProcessStageEditor.jsx').active;
          w.__wbRuntime.setStub('ProcessStageEditor.jsx', { active: ent => { activeCalls++; return origActive(ent); } });
          vm.runInContext(compiled.outputs[4].code, w);
          const ProcessGroupEditor = w.__wbRuntime.getModule('ProcessGroupEditor.jsx').ProcessGroupEditor;

          const result = { data: entity, meta: { source: 'production', snapshot_ref: 's'.repeat(32) } };
          const renderGroups = () => host.render(() => host.React.createElement(ProcessGroupEditor, {
            adapter: {}, result, command: { phase: 'idle', locked: false }, disabled: false, onDirty() {}, onClose() {},
          }));
          let tree = renderGroups();
          assert.equal(activeCalls, 1, 'E.active(entity) called once on mount');

          // Start a new group and click op2 (sequence 20) BEFORE op1 (sequence 10).
          const addBtn = findAll(tree, n => n.type === 'button' && n.props.children === '新增外协段')[0];
          addBtn.props.onClick();
          tree = renderGroups();
          const check20 = findAll(tree, n => n.type === 'input' && n.props['aria-label'] === '外协段包含工序 20')[0];
          check20.props.onChange({ target: { checked: true } });
          tree = renderGroups();
          const check10 = findAll(tree, n => n.type === 'input' && n.props['aria-label'] === '外协段包含工序 10')[0];
          check10.props.onChange({ target: { checked: true } });
          tree = renderGroups();

          // Verify start_sequence is 10 and end_sequence is 20 even though 20 was clicked first!
          const pickBtn = findAll(tree, n => n.type === 'button' && n.props.children === '选择整段供应商')[0];
          pickBtn.props.onClick();
          tree = renderGroups();
          const picker = findAll(tree, n => n.props && n.props['data-picker'] === true)[0];
          assert.equal(JSON.stringify(picker.props.target.group), JSON.stringify({ start_sequence: 10, end_sequence: 20 }));

          // Now change total_days (lead_time_days): E.active must be called 0 times and externalOperations filter must run 0 times.
          activeCalls = 0;
          assert.equal(sequenceReads, 0);
          const daysInput = findAll(tree, n => n.type === 'input' && n.props['aria-label'] === '整段外协周期')[0];
          sourceScans = 0;
          daysInput.props.onChange({ target: { value: '5' } });
          tree = renderGroups();
          assert.equal(activeCalls, 0, 'Changing total_days must do 0 E.active(entity) calls');
          assert.equal(sequenceReads, 0, 'Inactive operation in entity.operations must have 0 sequence reads before and after total_days change');
          // Only the 2 visible table rows in paging.rows read row.source 4 times each for JSX cell rendering (2 * 4 = 8), 0 in E.active / members / elsewhere.
          assert.equal(sourceScans, 8, 'Changing total_days does 0 operation scans in E.active, members, or elsewhere');
        }

        console.log(JSON.stringify({ ok: true }));
        """
    )
    assert report["ok"] is True


def test_field_editor_choices_and_single_receipt_validation():
    report = _run_node(
        r"""
        'use strict';
        const assert = require('node:assert/strict');
        const fs = require('node:fs');
        const os = require('node:os');
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile, bundleProduction } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const files = [
          'WorkbenchTerms.js', 'shared/network/transport.js', 'resource-contract.js', 'resource-api.js', 'shared/session/command-session.js',
          'ResourceControls.jsx', 'FieldEditorFields.jsx',
          'BatchContract.js', 'BatchAPI.js', 'BatchForms.jsx', 'BatchMaterialEditor.jsx',
          'BatchOperationEditor.jsx', 'BatchSplitPanel.jsx', 'BatchFiles.jsx',
          'SystemRestoreStatus.js', 'SystemMaintenanceAPI.js', 'SystemMaintenanceControls.jsx', 'SystemMaintenanceConfig.jsx'
        ];
        const compiled = compile({
          sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(appDir, name), 'utf8') })),
          check_combined: false,
        });

        const ref = n => n.toString(16).padStart(48, '0');
        const w = vm.createContext({
          console, URL, URLSearchParams, AbortController, Set, Map, WeakMap, WeakSet, Error, TypeError, DOMException,
          Math, Number, String, Boolean, Array, Object, JSON, RegExp, Promise, Date, FormData: class {},
          setTimeout, clearTimeout, queueMicrotask,
          crypto: { getRandomValues: b => b.fill(7) },
          CustomEvent: class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } },
          location: new URL('http://127.0.0.1:8080/workbench'),
          sessionStorage: {
            data: new Map(),
            getItem(k) { return this.data.has(k) ? this.data.get(k) : null; },
            setItem(k, v) { this.data.set(k, v); },
            removeItem(k) { this.data.delete(k); },
          },
          localStorage: {
            data: new Map(),
            getItem(k) { return this.data.has(k) ? this.data.get(k) : null; },
            setItem(k, v) { this.data.set(k, v); },
            removeItem(k) { this.data.delete(k); },
          },
          navigator: { locks: { request: (_k, _o, fn) => fn({}) } },
          document: { body: {}, activeElement: null, addEventListener() {}, removeEventListener() {} },
          addEventListener() {}, removeEventListener() {}, dispatchEvent() {},
          __wbStubs: {
            'shared/ui/icons.jsx': { SMIcon: () => null, Ico: () => null, TransferIcon: () => null },
            'WorkbenchReferences.jsx': { WorkbenchError: () => null, WorkbenchReference: () => null },
            'WorkbenchFormat.js': { hours: String, number: String, dateTime: String },
            'WorkbenchGuards.js': { useDirtyGuard: () => 'owner', confirmLeave: async () => true },
            'WorkbenchHandlerMemory.js': { read: () => ({ value: '李四' }), write() {} },
            'FieldContract.js': { quantity: String },
            'FieldControls.jsx': { Button: 'button' },
            'BatchControls.jsx': { BaseFields: () => null, Field: 'div', display: String },
            'ResourceForms.jsx': { Feedback: () => null },
            'WorkbenchControls.jsx': { Pager: () => null },
            'RunAdoptionControls.jsx': { Button: 'button', Dialog: 'dialog' },
          },
        });
        w.window = w;

        let cursor = 0;
        const slots = [], effects = [];
        const sameDeps = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
        w.React = {
          Fragment: 'fragment',
          Children: { only: c => c, map: (c, fn) => Array.isArray(c) ? c.map(fn) : c ? [fn(c)] : [] },
          createContext: def => ({ _current: def, Provider: p => p.children }),
          useContext: ctx => ctx._current,
          createElement(type, props, ...children) {
            const flat = children.flat(Infinity);
            return { type, props: { ...(props || {}), children: flat.length <= 1 ? flat[0] : flat } };
          },
          cloneElement(el, props) { return { ...el, props: { ...(el.props || {}), ...props } }; },
          useId() { return ':id-' + (cursor++) + ':'; },
          useRef(v) { const i = cursor++; if (!slots[i]) slots[i] = { current: v }; return slots[i]; },
          useState(init) {
            const i = cursor++;
            if (!slots[i]) slots[i] = { value: typeof init === 'function' ? init() : init };
            const s = slots[i];
            return [s.value, next => { s.value = typeof next === 'function' ? next(s.value) : next; }];
          },
          useReducer(red, init) {
            const [v, set] = this.useState(init);
            return [v, act => set(old => red(old, act))];
          },
          useCallback(fn, deps) { return this.useMemo(() => fn, deps); },
          useMemo(fn, deps) {
            const i = cursor++;
            if (!slots[i] || !sameDeps(slots[i].deps, deps)) slots[i] = { deps, value: fn() };
            return slots[i].value;
          },
          useLayoutEffect() {},
          useEffect(fn, deps) {
            const i = cursor++;
            if (!slots[i] || !sameDeps(slots[i].deps, deps)) {
              const prev = slots[i];
              slots[i] = { deps };
              effects.push(() => { if (prev && prev.cleanup) prev.cleanup(); slots[i].cleanup = fn(); });
            }
          },
        };
        w.ReactDOM = { createPortal: el => el };

        for (const out of compiled.outputs) vm.runInContext(out.code, w, { filename: out.path });

        const ResourceControls = w.__wbRuntime.getModule('ResourceControls.jsx');
        const FieldEditorFields = w.__wbRuntime.getModule('FieldEditorFields.jsx').FieldEditorFields;
        const APSBatchContract = w.__wbRuntime.getModule('BatchContract.js');
        const APSBatchAPI = w.__wbRuntime.getModule('BatchAPI.js');
        const APSResourceSession = w.__wbRuntime.getModule('shared/session/command-session.js');
        const BatchOperationEditor = w.__wbRuntime.getModule('BatchOperationEditor.jsx').BatchOperationEditor;
        const SystemMaintenanceConfig = w.__wbRuntime.getModule('SystemMaintenanceConfig.jsx').SystemMaintenanceConfig;

        // #44: relationLabels and FieldEditorFields preserve actual_machine and actual_operator labels and memoize original.
        const record = {
          completed_quantity: 5,
          actual_machine_ref: ref(1),
          actual_machine_label: 'M-01 数控车床',
          actual_operator_ref: ref(2),
          actual_operator_label: 'OP-01 王工',
        };
        let capturedOriginals = [];
        const origChoice = ResourceControls.Choice;
        w.__wbRuntime.setStub('ResourceControls.jsx', {
          Choice: props => {
            capturedOriginals.push(props.original);
            return hostRender(origChoice(props));
          },
        });
        function hostRender(node) {
          if (!node || typeof node !== 'object') return node;
          if (Array.isArray(node)) return node.map(hostRender);
          if (typeof node.type === 'function') return hostRender(node.type(node.props || {}));
          const children = node.props && node.props.children !== undefined ? hostRender(node.props.children) : undefined;
          return { ...node, props: { ...(node.props || {}), children } };
        }
        const task = { source: 'internal', execution: { known_completed_quantity: 5, remaining_quantity: 5, target_quantity: 10, unknown_record_count: 0 } };
        const adapter = {
          choices: async () => ({
            ok: true, schema_version: 1, warnings: [],
            meta: { as_of: '2026-10-30T08:00:00', request_ref: 'a'.repeat(32), snapshot_ref: 's'.repeat(32), source: 'production', time_basis: 'factory_local' },
            data: { kind: 'choices', page: { number: 1, size: 50, total: 0, pages: 1, sort: [] }, entities: [] },
          }),
        };
        cursor = 0;
        hostRender(w.React.createElement(FieldEditorFields, {
          task, record, action: 'correct', adapter,
          draft: { completed_quantity: '5', effective_processing_hours: '1', actual_start: '', actual_end: '', actual_machine_ref: ref(1), actual_operator_ref: ref(2), remark: '', reason: '纠偏', declared_operator: '王工' },
          suggestions: {}, disabled: false, first: { current: null }, change() {}, error: null,
        }));
        const firstOriginal = capturedOriginals[0];
        assert.equal(
          JSON.stringify(ResourceControls.relationLabels(firstOriginal, 'actual_machine_ref')),
          JSON.stringify([{ ref: ref(1), label: 'M-01 数控车床' }])
        );
        assert.equal(
          JSON.stringify(ResourceControls.relationLabels(firstOriginal, 'actual_operator_ref')),
          JSON.stringify([{ ref: ref(2), label: 'OP-01 王工' }])
        );

        // Re-render with changed draft text: original reference is memoized by [record].
        capturedOriginals = [];
        cursor = 0;
        hostRender(w.React.createElement(FieldEditorFields, {
          task, record, action: 'correct', adapter,
          draft: { completed_quantity: '6', effective_processing_hours: '1.5', actual_start: '', actual_end: '', actual_machine_ref: ref(1), actual_operator_ref: ref(2), remark: '修改', reason: '纠偏', declared_operator: '王工' },
          suggestions: {}, disabled: false, first: { current: null }, change() {}, error: null,
        }));
        assert.strictEqual(capturedOriginals[0], firstOriginal, 'original prop must be memoized by [record]');

        // #49: BatchAPI validates receipt once on command and once on lookup (including operation_update operation_ref).
        let batchReceiptCalls = 0;
        const origBatchReceipt = APSBatchContract.receipt;
        w.__wbRuntime.setStub('BatchContract.js', {
          receipt: (...args) => { batchReceiptCalls++; return origBatchReceipt(...args); },
        });

        let mockResponse = null;
        w.fetch = async () => ({
          ok: true,
          status: 200,
          headers: { get: () => 'application/json' },
          json: async () => mockResponse,
        });

        const batchApi = APSBatchAPI.create();
        mockResponse = {
          ok: true, result: 'committed', receipt_ref: 'r'.repeat(32), replayed: false, warnings: [],
          data: { entity_ref: ref(50), operation_ref: ref(51) },
        };
        const cmdSlot = slots.length;
        function runBatchSession() {
          cursor = cmdSlot;
          const s = APSResourceSession.useCommand(batchApi);
          while (effects.length) effects.shift()();
          return s;
        }
        let session = runBatchSession();
        await session.submit('batch', 'operation_update', ref(50), { write_token: 'w'.repeat(32) }, { operation_ref: ref(51), fields: { setup_hours: 2 } });
        session = runBatchSession();
        assert.equal(session.phase, 'done');
        assert.equal(batchReceiptCalls, 1, 'BatchAPI.command validates receipt once');

        // Mount BatchOperationEditor when command is already done: it must NOT re-call B.receipt!
        let committedCalls = 0;
        const opEditorSlot = slots.length;
        cursor = opEditorSlot;
        BatchOperationEditor({
          adapter: { operationChoices: async () => ({ data: { machines: [], operators: [], suppliers: [], authorizations: [] } }) },
          entity: { ref: ref(50), write_context: { write_token: 'w'.repeat(32), capabilities: { 'batch.operation_update': true }, blocked_reasons: [] } },
          operation: { ref: ref(51), sequence: 10, label: '车削', source: 'internal', external_group: null },
          source: 'production',
          command: session,
          onCommitted: () => { committedCalls++; },
          onClose() {},
        });
        while (effects.length) effects.shift()();
        assert.equal(committedCalls, 1);
        assert.equal(batchReceiptCalls, 1, 'BatchOperationEditor must not re-validate receipt');
        session.reset();

        // Recovery lookup on operation_update validates operation_ref from persisted pendingRecord!
        const storedIntent = { kind: 'batch', action: 'operation_update', ref: ref(50), operation_ref: ref(51), request_key: 'resource-' + 'a'.repeat(48) };
        batchApi.savePending(storedIntent);
        assert.equal(JSON.parse(w.sessionStorage.getItem(batchApi.pendingKey)).operation_ref, ref(51));
        const mismatchReceipt = {
          ok: true, result: 'committed', receipt_ref: 'c'.repeat(32), replayed: true, warnings: [],
          data: { entity_ref: ref(50), operation_ref: ref(99) },
        };
        mockResponse = {
          state: 'recorded', receipt: mismatchReceipt, may_be_in_flight: false, resolution: 'recorded',
        };
        await assert.rejects(
          batchApi.lookup(storedIntent.request_key, storedIntent),
          /保存结果对应的不是当前工序/,
          'BatchAPI.lookup rejects mismatched operation_ref on operation_update'
        );
        assert.throws(
          () => APSBatchContract.receipt(mismatchReceipt, 'operation_update', ref(50)),
          /保存结果对应的不是当前工序/,
          'BatchContract.receipt requires expectedOperationRef on operation_update'
        );
        assert.throws(
          () => APSBatchContract.receipt(mismatchReceipt, 'update'),
          /保存结果不确定/,
          'BatchContract.receipt requires expected entity ref on non-create single-entity actions'
        );
        batchApi.clearPending(storedIntent);

        // #5: SystemMaintenanceConfig keeps dirty=true even when active=false while on config tab.
        {
          let lastGuard = null;
          w.__wbRuntime.setStub('WorkbenchGuards.js', {
            useDirtyGuard: spec => { lastGuard = spec; return 'owner'; },
            confirmLeave: async () => true,
          });
          w.__wbRuntime.setStub('SystemMaintenanceControls.jsx', {
            useRead: () => ({
              loading: false,
              error: null,
              data: {
                data: {
                  section: { state: 'available', message: '正常', error: null },
                  write_token: 't'.repeat(32),
                  write_blocked_reasons: [],
                  defaulted_fields: [],
                  values: {
                    auto_backup_enabled: true,
                    auto_backup_interval_minutes: 60,
                    auto_backup_cleanup_enabled: true,
                    auto_backup_keep_days: 7,
                    auto_backup_cleanup_interval_minutes: 120,
                    auto_log_cleanup_enabled: true,
                    auto_log_cleanup_keep_days: 14,
                    auto_log_cleanup_interval_minutes: 180,
                  },
                },
              },
            }),
          });
          const cfgSlot = slots.length;
          function renderCfg(active, locked = false) {
            cursor = cfgSlot;
            const tree = hostRender(w.React.createElement(SystemMaintenanceConfig, {
              revision: 1,
              active,
              tab: 'config',
              command: { locked, maintenanceRequired: false, execute: async () => true },
            }));
            while (effects.length) effects.shift()();
            return tree;
          }
          renderCfg(true);
          let tree = renderCfg(true);
          assert.equal(lastGuard.dirty, false);
          function findInput(node) {
            if (!node || typeof node !== 'object') return null;
            if (Array.isArray(node)) {
              for (const child of node) { const found = findInput(child); if (found) return found; }
              return null;
            }
            if (node.type === 'input' && node.props && node.props.type === 'number') return node;
            return node.props ? findInput(node.props.children) : null;
          }
          const numInput = findInput(tree);
          assert.ok(numInput, 'SystemMaintenanceConfig number input should be rendered');
          numInput.props.onChange({ target: { value: '90' } });
          renderCfg(true, true);
          assert.equal(lastGuard.dirty, true);
          assert.equal(lastGuard.locked, true);
          renderCfg(false, true);
          assert.equal(lastGuard.dirty, true, 'SystemMaintenanceConfig must preserve dirty=true when active=false');
          assert.equal(lastGuard.locked, false, 'SystemMaintenanceConfig must set locked=false when active=false');
        }

        // Compiler contract: re-export validation and transitive domain dependencies across shared modules.
        assert.throws(
          () => compile({ sources: [{ path: 'BatchContract.js', code: "export { nonExistent } from './resource-contract.js';" }] }),
          /No matching export in "resource-contract\.js" for import "nonExistent"/,
          'Re-export of non-existent symbol must fail with No matching export'
        );
        {
          const isolatedCode = compile({
            sources: [{ path: 'resource-api.js', code: fs.readFileSync(path.join(appDir, 'resource-api.js'), 'utf8') }],
            check_combined: false,
          }).outputs[0].code;
          const isoCtx = vm.createContext({
            console, Set, Map, WeakMap, WeakSet, Object, Array, String, Number, Boolean, Promise, Error, TypeError,
            AbortController, DOMException,
            React: {
              useRef: v => ({ current: v }),
              useState: v => [typeof v === 'function' ? v() : v, () => {}],
              useEffect() {},
              useCallback: fn => fn,
              useMemo: fn => fn(),
            },
          });
          isoCtx.window = isoCtx;
          vm.runInContext(isolatedCode, isoCtx, { filename: 'resource-api.js' });
          const countsRes = isoCtx.__wbRuntime.getModule('resource-api.js').useCounts({ summary: async () => ({}) }, 'production');
          assert.ok(countsRes && 'machine' in countsRes && 'summary' in countsRes,
            'useCounts() in isolated context resolves transitive C.nodes from resource-contract.js without preloading window.APSResourceContract');

          // Circular dependency: hoisted export function is callable and returns 7 during child evaluation, while uninitialized export default / const is undefined and dereferencing throws TypeError.
          const cycleHoisted = compile({
            sources: [
              {
                path: 'BatchContract.js',
                code: "import BatchAPI from './BatchAPI.js'; export function f() { return 7; } export const x = 1; export default { f, x, childVal: BatchAPI.val };",
              },
              {
                path: 'BatchAPI.js',
                code: "import BatchContract, { f, x } from './BatchContract.js'; const val = f(); export default { val, xDuringEval: x, defaultDuringEval: BatchContract };",
              },
            ],
            check_combined: false,
          });
          const hoistedCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
          hoistedCtx.window = hoistedCtx;
          vm.runInContext(cycleHoisted.outputs[0].code, hoistedCtx, { filename: 'BatchContract.js' });
          assert.equal(hoistedCtx.__wbRuntime.getModule('BatchAPI.js').val, 7, 'Child module top-level call to parent hoisted export function must return 7');
          assert.equal(hoistedCtx.__wbRuntime.getModule('BatchAPI.js').xDuringEval, undefined, 'Parent export const must still be undefined during child evaluation');
          assert.equal(hoistedCtx.__wbRuntime.getModule('BatchAPI.js').defaultDuringEval, undefined, 'Parent export default must still be undefined during child evaluation');
          assert.equal(hoistedCtx.__wbRuntime.getModule('BatchContract.js').childVal, 7, 'Parent receives child export computed from hoisted function');

          const cycleDerefDefault = compile({
            sources: [
              {
                path: 'BatchContract.js',
                code: "import './BatchAPI.js'; export function f() { return 7; } export default { create() { return f(); } };",
              },
              {
                path: 'BatchAPI.js',
                code: "import BatchContract, { f } from './BatchContract.js'; const ok = f(); const D = BatchContract; D.create(); export default { ok };",
              },
            ],
            check_combined: false,
          });
          const cycleCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
          cycleCtx.window = cycleCtx;
          assert.throws(
            () => vm.runInContext(cycleDerefDefault.outputs[0].code, cycleCtx, { filename: 'BatchContract.js' }),
            err => err.name === 'TypeError' && /Cannot read properties of undefined/.test(err.message),
            'Top-level dereference of parent export default in circular child module must throw TypeError'
          );

          const cycleSelfOut = compile({
            sources: [{
              path: 'BatchAPI.js',
              code: "import BatchAPI, { f as selfF } from './BatchAPI.js'; export function f() { return 7; } assert.equal(selfF(), 7); const D = BatchAPI; D.create(); export default {};",
            }],
            check_combined: false,
          }).outputs[0].code;
          const selfCtx = vm.createContext({ console, assert, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
          selfCtx.window = selfCtx;
          assert.throws(
            () => vm.runInContext(cycleSelfOut, selfCtx, { filename: 'BatchAPI.js' }),
            err => err.name === 'TypeError' && /Cannot read properties of undefined/.test(err.message),
            'Top-level dereference of an evaluating circular module must throw TypeError instead of returning a lazy proxy'
          );

          // Shared module singleton across multiple entries in the same vm.Context sandbox.
          const sharedThemeEntries = compile({
            sources: [
              {
                path: 'a.js',
                code: "import { subscribe as subscribeTheme } from './shared/runtime/theme.js'; export default { listen: subscribeTheme };",
              },
              {
                path: 'b.js',
                code: "import { set as setTheme } from './shared/runtime/theme.js'; export default { update: setTheme };",
              },
            ],
            check_combined: false,
          });
          const themeObserved = [];
          const themeCtx = vm.createContext({
            console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError,
            localStorage: {
              store: new Map(),
              getItem(k) { return this.store.has(k) ? this.store.get(k) : null; },
              setItem(k, v) { this.store.set(k, v); },
            },
            document: {
              cookie: '',
              documentElement: { setAttribute() {} },
            },
            addEventListener() {},
            removeEventListener() {},
          });
          themeCtx.window = themeCtx;
          for (const out of sharedThemeEntries.outputs) {
            vm.runInContext(out.code, themeCtx, { filename: out.path });
          }
          const unsubTheme = themeCtx.__wbRuntime.getModule('a.js').listen(ev => themeObserved.push(ev));
          themeCtx.__wbRuntime.getModule('b.js').update('dark');
          unsubTheme();
          assert.equal(
            JSON.stringify(themeObserved),
            JSON.stringify([{ theme: 'dark', error: '' }]),
            'Two entries importing ./shared/runtime/theme.js must share a single theme runtime instance'
          );

          // Default import from a module without export default fails at compile time.
          assert.throws(
            () => compile({
              sources: [
                { path: 'a.js', code: "import b from './b.js'; export const value = b;" },
                { path: 'b.js', code: "export const present = 7;" },
              ],
            }),
            /No matching export in "b\.js" for import "default"/,
            'Default import of module without export default must fail with No matching export for default'
          );

          // Shared pending-store.js and transport.js singleton identity and shared pageSlots across all load orders.
          for (const order of [
            ['shared/session/pending-store.js', 'shared/network/transport.js', 'pending-consumer.js'],
            ['shared/network/transport.js', 'shared/session/pending-store.js', 'pending-consumer.js'],
            ['pending-consumer.js', 'shared/session/pending-store.js', 'shared/network/transport.js'],
          ]) {
            const sources = order.map(name => ({
              path: name,
              code: name === 'pending-consumer.js'
                ? "import { pendingStore } from './shared/session/pending-store.js'; export default { pendingStore };"
                : fs.readFileSync(path.join(appDir, name), 'utf8'),
            }));
            const compiledOrder = compile({ sources, check_combined: false });
            let failWrite = false;
            const backing = new Map();
            const pendingCtx = vm.createContext({
              console, URL, Set, Map, WeakMap, WeakSet, Object, Array, String, Number, Boolean, JSON, RegExp, Promise, Error, TypeError,
              AbortController, DOMException,
              CustomEvent: class { constructor(t, init) { this.type = t; this.detail = init && init.detail; } },
              localStorage: {
                getItem(k) { return backing.has(k) ? backing.get(k) : null; },
                setItem(k, v) {
                  if (failWrite) throw new Error('QuotaExceededError');
                  backing.set(k, String(v));
                },
                removeItem(k) {
                  if (failWrite) throw new Error('QuotaExceededError');
                  backing.delete(k);
                },
              },
              addEventListener() {},
              removeEventListener() {},
              dispatchEvent() {},
            });
            pendingCtx.window = pendingCtx;
            for (const out of compiledOrder.outputs) {
              vm.runInContext(out.code, pendingCtx, { filename: out.path });
            }
            const transportMod = pendingCtx.__wbRuntime.getModule('shared/network/transport.js');
            const pendingStoreMod = pendingCtx.__wbRuntime.getModule('shared/session/pending-store.js');
            const consumerMod = pendingCtx.__wbRuntime.getModule('pending-consumer.js');
            assert.equal(transportMod.pendingStore, undefined, 'transport.js must not re-export pendingStore');
            assert.equal(
              pendingStoreMod.pendingStore,
              consumerMod.pendingStore,
              'shared/session/pending-store.js and imported pendingStore must be strictly === for order ' + order.join(' -> ')
            );
            const storeOpts = {
              key: 'aps_workbench_singleton_probe_v1',
              validate: v => Boolean(v && typeof v === 'object' && typeof v.phase === 'string'),
              readError: '读取待确认状态失败',
              writeError: '写入待确认状态失败',
              conflictError: '待确认状态冲突',
            };
            const storeFromModule = pendingStoreMod.pendingStore(storeOpts);
            const storeFromImport = consumerMod.pendingStore(storeOpts);
            const initialPending = { phase: 'pending', request_key: 'req-singleton-1' };
            const settledDone = { phase: 'done', request_key: 'req-singleton-1' };
            storeFromModule.save(initialPending, null);
            assert.deepEqual(storeFromImport.read(), initialPending);
            failWrite = true;
            assert.throws(
              () => storeFromModule.save(settledDone, initialPending),
              err => err.message === '写入待确认状态失败' && err.saved && err.saved.phase === 'done' && err.saved.request_key === 'req-singleton-1',
              'Settlement write failure via pendingStore must attach saved state'
            );
            assert.throws(
              () => storeFromImport.read(),
              err => err.message === '写入待确认状态失败' && err.saved && err.saved.phase === 'done' && err.saved.request_key === 'req-singleton-1',
              'read() via direct pending-store.js import must observe the same unflushed saved state from shared pageSlots'
            );
          }

          // Production bundle and test compiler reject remote/bare imports and dynamic import().
          const tmpAppDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wb-offline-guard-'));
          try {
            fs.mkdirSync(path.join(tmpAppDir, 'shell'), { recursive: true });
            fs.writeFileSync(path.join(tmpAppDir, 'theme.js'), 'import "https://example.invalid/x.js";\n', 'utf8');
            fs.writeFileSync(path.join(tmpAppDir, 'shell/main.jsx'), 'export default {};\n', 'utf8');
            assert.throws(
              () => bundleProduction({ appDir: tmpAppDir }),
              /Unsupported bare or remote import specifier in offline build: https:\/\/example\.invalid\/x\.js/,
              'bundleProduction must reject static remote import specifiers'
            );

            fs.writeFileSync(path.join(tmpAppDir, 'theme.js'), 'export const theme = "light";\n', 'utf8');
            fs.writeFileSync(path.join(tmpAppDir, 'shell/main.jsx'), 'export const load = () => import("https://example.invalid/x.js");\n', 'utf8');
            assert.throws(
              () => bundleProduction({ appDir: tmpAppDir }),
              /Dynamic import\(\) is forbidden in offline workbench build: shell\/main\.jsx/,
              'bundleProduction must reject dynamic import() expressions'
            );

            fs.writeFileSync(
              path.join(tmpAppDir, 'shell/main.jsx'),
              "export const note = 'x//y'; export const load = () => import('https://example.invalid/x.js');\n",
              'utf8'
            );
            assert.throws(
              () => bundleProduction({ appDir: tmpAppDir }),
              /Dynamic import\(\) is forbidden in offline workbench build: shell\/main\.jsx/,
              'bundleProduction must reject dynamic import() after a string literal containing //'
            );

            fs.writeFileSync(
              path.join(tmpAppDir, 'shell/main.jsx'),
              "export const load = () => `${import('https://example.invalid/x.js')}`;\n",
              'utf8'
            );
            assert.throws(
              () => bundleProduction({ appDir: tmpAppDir }),
              /Dynamic import\(\) is forbidden in offline workbench build: shell\/main\.jsx/,
              'bundleProduction must reject dynamic import() inside template literal ${...}'
            );

            fs.writeFileSync(
              path.join(tmpAppDir, 'shell/main.jsx'),
              "if (1) /'/; export const load = () => import('https://example.invalid/x.js');\n",
              'utf8'
            );
            assert.throws(
              () => bundleProduction({ appDir: tmpAppDir }),
              /Dynamic import\(\) is forbidden in offline workbench build: shell\/main\.jsx/,
              'bundleProduction must reject dynamic import() after condition regex literal'
            );

            for (const blockSnippet of [
              "if (1) {} /'/; export const load = () => import('https://example.invalid/x.js');\n",
              "try {} finally {} /'/; export const load = () => import('https://example.invalid/x.js');\n",
            ]) {
              fs.writeFileSync(path.join(tmpAppDir, 'shell/main.jsx'), blockSnippet, 'utf8');
              assert.throws(
                () => bundleProduction({ appDir: tmpAppDir }),
                /Dynamic import\(\) is forbidden in offline workbench build: shell\/main\.jsx/,
                'bundleProduction must reject dynamic import() after block-closed regex literal'
              );
            }

            fs.writeFileSync(
              path.join(tmpAppDir, 'shell/main.jsx'),
              'const fakeImport = "import \'./ghost.js\'";\nexport default { fakeImport };\n',
              'utf8'
            );
            const okBundle = bundleProduction({ appDir: tmpAppDir });
            assert.equal(okBundle.outputs.length, 2, 'bundleProduction must not treat string literal import as missing module');

            fs.writeFileSync(path.join(tmpAppDir, 'shell/export-probe.js'), 'export const obj = { ok: 1, missing: 2 };\n', 'utf8');
            fs.writeFileSync(path.join(tmpAppDir, 'shell/main.jsx'), "import { missing } from './export-probe.js';\nexport default { missing };\n", 'utf8');
            assert.throws(
              () => bundleProduction({ appDir: tmpAppDir }),
              /No matching export/,
              'bundleProduction must reject importing object property name as top-level export'
            );

            fs.writeFileSync(
              path.join(tmpAppDir, 'shell/sub.js'),
              'export const x = 1;\nexport const y = () => import("https://example.invalid/x.js");\n',
              'utf8'
            );
            fs.writeFileSync(
              path.join(tmpAppDir, 'shell/main.jsx'),
              'import {\n  x,\n  y\n} from "./sub.js";\nexport default { x, y };\n',
              'utf8'
            );
            assert.throws(
              () => bundleProduction({ appDir: tmpAppDir }),
              /Dynamic import\(\) is forbidden in offline workbench build: shell\/sub\.js/,
              'bundleProduction must traverse multiline import statements and reject downstream dynamic import()'
            );

            fs.writeFileSync(
              path.join(tmpAppDir, 'b.js'),
              'export const x = () => import("https://example.invalid/x.js");\nexport { x as "run-dyn" };\n',
              'utf8'
            );
            fs.writeFileSync(
              path.join(tmpAppDir, 'shell/main.jsx'),
              'import { "run-dyn" as go } from "../b.js";\nexport default { go };\n',
              'utf8'
            );
            assert.throws(
              () => bundleProduction({ appDir: tmpAppDir }),
              /Dynamic import\(\) is forbidden in offline workbench build: b\.js/,
              'bundleProduction must traverse string-named imports and reject downstream dynamic import()'
            );

            fs.writeFileSync(
              path.join(tmpAppDir, 'b.js'),
              'const val = () => import("https://example.invalid/x.js");\nexport { val as "x;y" };\n',
              'utf8'
            );
            fs.writeFileSync(
              path.join(tmpAppDir, 'shell/main.jsx'),
              'import { "x;y" as go } from "../b.js";\nglobalThis.probe = go;\n',
              'utf8'
            );
            assert.throws(
              () => bundleProduction({ appDir: tmpAppDir }),
              /Dynamic import\(\) is forbidden in offline workbench build: b\.js/,
              'bundleProduction must traverse string-named imports containing semicolons and reject downstream dynamic import()'
            );
          } finally {
            fs.rmSync(tmpAppDir, { recursive: true, force: true });
          }

          assert.throws(
            () => compile({
              sources: [{ path: 'BatchContract.js', code: 'export const load = () => import("https://example.invalid/x.js");' }],
            }),
            /Dynamic import\(\) is forbidden in offline workbench build/,
            'Test compiler must also reject dynamic import() expressions'
          );

          assert.throws(
            () => compile({
              sources: [{ path: 'BatchContract.js', code: "export const note = 'x//y'; export const load = () => import('https://example.invalid/x.js');" }],
            }),
            /Dynamic import\(\) is forbidden in offline workbench build/,
            'Test compiler must reject dynamic import() after a string literal containing //'
          );

          assert.throws(
            () => compile({
              sources: [{ path: 'BatchContract.js', code: "export const load = () => `${import('https://example.invalid/x.js')}`;" }],
            }),
            /Dynamic import\(\) is forbidden in offline workbench build/,
            'Test compiler must reject dynamic import() inside template literal ${...}'
          );

          assert.throws(
            () => compile({
              sources: [{ path: 'BatchContract.js', code: "if (1) /'/; export const load = () => import('https://example.invalid/x.js');" }],
            }),
            /Dynamic import\(\) is forbidden in offline workbench build/,
            'Test compiler must reject dynamic import() after condition regex literal'
          );

          for (const blockSnippet of [
            "if (1) {} /'/; export const load = () => import('https://example.invalid/x.js');",
            "try {} finally {} /'/; export const load = () => import('https://example.invalid/x.js');",
          ]) {
            assert.throws(
              () => compile({
                sources: [{ path: 'BatchContract.js', code: blockSnippet }],
              }),
              /Dynamic import\(\) is forbidden in offline workbench build/,
              'Test compiler must reject dynamic import() after block-closed regex literal'
            );
          }

          for (const csvOrder of [
            [
              { path: 'csv-consumer.js', code: "import { csvCell } from './shared/csv.js'; export default { run: () => csvCell('v') };" },
              { path: 'shared/csv.js', code: "export function csvCell(v) { return 'overridden:' + v; } export default { csvCell };" },
            ],
            [
              { path: 'shared/csv.js', code: "export function csvCell(v) { return 'overridden:' + v; } export default { csvCell };" },
              { path: 'csv-consumer.js', code: "import { csvCell } from './shared/csv.js'; export default { run: () => csvCell('v') };" },
            ],
          ]) {
            const csvCompiled = compile({ sources: csvOrder, check_combined: false });
            const csvCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
            csvCtx.window = csvCtx;
            for (const out of csvCompiled.outputs) {
              vm.runInContext(out.code, csvCtx, { filename: out.path });
            }
            assert.equal(
              csvCtx.__wbRuntime.getModule('csv-consumer.js').run(),
              'overridden:v',
              'Shared module sourceOverrides must be consumed regardless of source order'
            );
          }

          for (const namedOrder of [
            [
              { path: 'b.js', code: 'export const x = 1; export default { x: 2 };' },
              { path: 'a.js', code: "import { x } from './b.js'; export default { x };" },
            ],
            [
              { path: 'a.js', code: "import { x } from './b.js'; export default { x };" },
              { path: 'b.js', code: 'export const x = 1; export default { x: 2 };' },
            ],
          ]) {
            const namedCompiled = compile({ sources: namedOrder, check_combined: false });
            const namedCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
            namedCtx.window = namedCtx;
            for (const out of namedCompiled.outputs) {
              vm.runInContext(out.code, namedCtx, { filename: out.path });
            }
            assert.equal(
              namedCtx.__wbRuntime.getModule('a.js').x,
              1,
              'Named import must resolve direct named export (1) instead of default property (2)'
            );
          }

          assert.throws(
            () => compile({
              sources: [
                { path: 'export-probe.js', code: 'export const obj = { ok: 1, missing: 2 };' },
                { path: 'consumer.js', code: "import { missing } from './export-probe.js'; export default { missing };" },
              ],
            }),
            /No matching export in "export-probe\.js" for import "missing"/,
            'Test compiler must not treat object literal property names inside export const as top-level exports'
          );

          assert.throws(
            () => compile({
              sources: [
                { path: 'string-export-probe.js', code: 'export const ok = 1; const fake = "export { missing }";' },
                { path: 'consumer.js', code: "import { missing } from './string-export-probe.js'; export default { missing };" },
              ],
            }),
            /No matching export in "string-export-probe\.js" for import "missing"/,
            'Test compiler must not treat string literal "export { missing }" as a real module export'
          );

          const fakeImportCompiled = compile({
            sources: [{ path: 'BatchContract.js', code: 'const fake = "import \'./ghost.js\'"; export default { fake };' }],
            check_combined: false,
          });
          assert.equal(fakeImportCompiled.outputs.length, 1, 'Test compiler must not treat string literal "import \'./ghost.js\'" as a real import');

          const multilineCompiled = compile({
            sources: [
              { path: 'b.js', code: 'export const x = 1;\nexport const y = 2;\n' },
              { path: 'a.js', code: "import {\n  x,\n  y\n} from './b.js';\nexport default { sum: x + y };\n" },
            ],
            check_combined: false,
          });
          const multilineCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
          multilineCtx.window = multilineCtx;
          for (const out of multilineCompiled.outputs) {
            vm.runInContext(out.code, multilineCtx, { filename: out.path });
          }
          assert.equal(multilineCtx.__wbRuntime.getModule('a.js').sum, 3, 'Multiline named import must resolve all imported bindings');

          assert.throws(
            () => compile({
              sources: [
                { path: 'b.js', code: 'export const x = 1;\n' },
                { path: 'a.js', code: "import {\n  x,\n  missing\n} from './b.js';\nexport default { x, missing };\n" },
              ],
            }),
            /No matching export in "b\.js" for import "missing"/,
            'Multiline named import of non-existent export must fail at compile time'
          );

          for (const sharedNamedOrder of [
            [
              { path: 'shared/runtime/theme.js', code: 'export const x = 1; export default { x: 2 };' },
              { path: 'theme-consumer.js', code: "import { x } from './shared/runtime/theme.js'; export default { x };" },
            ],
            [
              { path: 'theme-consumer.js', code: "import { x } from './shared/runtime/theme.js'; export default { x };" },
              { path: 'shared/runtime/theme.js', code: 'export const x = 1; export default { x: 2 };' },
            ],
          ]) {
            const sharedNamedCompiled = compile({ sources: sharedNamedOrder, check_combined: false });
            const sharedNamedCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
            sharedNamedCtx.window = sharedNamedCtx;
            for (const out of sharedNamedCompiled.outputs) {
              vm.runInContext(out.code, sharedNamedCtx, { filename: out.path });
            }
            assert.equal(
              sharedNamedCtx.__wbRuntime.getModule('theme-consumer.js').x,
              1,
              'Shared module named import must resolve direct named export (1) instead of default property (2)'
            );
          }

          for (const primDefaultOrder of [
            [
              { path: 'b.js', code: "export const length = 7; export default 'foo';" },
              { path: 'a.js', code: "import { length } from './b.js'; export default { length };" },
            ],
            [
              { path: 'a.js', code: "import { length } from './b.js'; export default { length };" },
              { path: 'b.js', code: "export const length = 7; export default 'foo';" },
            ],
          ]) {
            const primCompiled = compile({ sources: primDefaultOrder, check_combined: false });
            const primCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
            primCtx.window = primCtx;
            for (const out of primCompiled.outputs) {
              vm.runInContext(out.code, primCtx, { filename: out.path });
            }
            assert.equal(
              primCtx.__wbRuntime.getModule('a.js').length,
              7,
              'Named import { length } must resolve exported length (7) without boxing primitive string default'
            );
          }

          const strNamedCompiled = compile({
            sources: [
              { path: 'b.js', code: 'const val = 7; export { val as "x-y" };' },
              { path: 'a.js', code: 'import { "x-y" as x } from "./b.js"; export default { x };' },
            ],
            check_combined: false,
          });
          const strNamedCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
          strNamedCtx.window = strNamedCtx;
          for (const out of strNamedCompiled.outputs) {
            vm.runInContext(out.code, strNamedCtx, { filename: out.path });
          }
          assert.equal(strNamedCtx.__wbRuntime.getModule('a.js').x, 7, 'String-named export and import must resolve to 7');

          for (const fnDefaultOrder of [
            [
              { path: 'b.js', code: 'export const length = 7; export default function f(a, b) { return a + b; }' },
              { path: 'a.js', code: "import { length } from './b.js'; export default { length };" },
            ],
            [
              { path: 'a.js', code: "import { length } from './b.js'; export default { length };" },
              { path: 'b.js', code: 'export const length = 7; export default function f(a, b) { return a + b; }' },
            ],
          ]) {
            const fnCompiled = compile({ sources: fnDefaultOrder, check_combined: false });
            const fnCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
            fnCtx.window = fnCtx;
            for (const out of fnCompiled.outputs) {
              vm.runInContext(out.code, fnCtx, { filename: out.path });
            }
            assert.equal(
              fnCtx.__wbRuntime.getModule('a.js').length,
              7,
              'Named import { length } must resolve exported length (7) instead of function default.length (2)'
            );
          }

          for (const sharedFnDefaultOrder of [
            [
              { path: 'shared/runtime/theme.js', code: 'export const length = 7; export default function f(a, b) { return a + b; }' },
              { path: 'theme-consumer.js', code: "import { length } from './shared/runtime/theme.js'; export default { length };" },
            ],
            [
              { path: 'theme-consumer.js', code: "import { length } from './shared/runtime/theme.js'; export default { length };" },
              { path: 'shared/runtime/theme.js', code: 'export const length = 7; export default function f(a, b) { return a + b; }' },
            ],
          ]) {
            const sharedFnCompiled = compile({ sources: sharedFnDefaultOrder, check_combined: false });
            const sharedFnCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
            sharedFnCtx.window = sharedFnCtx;
            for (const out of sharedFnCompiled.outputs) {
              vm.runInContext(out.code, sharedFnCtx, { filename: out.path });
            }
            assert.equal(
              sharedFnCtx.__wbRuntime.getModule('theme-consumer.js').length,
              7,
              'Shared module named import { length } must resolve exported length (7) instead of function default.length (2)'
            );
          }

          assert.throws(
            () => compile({
              sources: [
                { path: 'a.js', code: 'export const x = 1;' },
                { path: 'b.js', code: 'export const x = 2;' },
                { path: 'c.js', code: "export * from './a.js'; export * from './b.js';" },
                { path: 'd.js', code: "import { x } from './c.js'; export default { x };" },
              ],
            }),
            /No matching export in "c\.js" for import "x"|Ambiguous import/,
            'Ambiguous export * of same symbol from multiple modules must be rejected at compile time'
          );

          // String-named exports/imports with comma, "as", semicolon, brace, and empty string in both sandbox and production.
          for (const specialName of ['x,y', 'x as y', '', 'x;y', 'x}y']) {
            const specialSources = [
              { path: 'b.js', code: `const val = 7; export { val as ${JSON.stringify(specialName)} };` },
              { path: 'a.js', code: `import { ${JSON.stringify(specialName)} as x } from './b.js'; export default { x };` },
            ];
            for (const ordered of [specialSources, [...specialSources].reverse()]) {
              const specialCompiled = compile({ sources: ordered, check_combined: false });
              const specialCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
              specialCtx.window = specialCtx;
              for (const out of specialCompiled.outputs) {
                vm.runInContext(out.code, specialCtx, { filename: out.path });
              }
              assert.equal(specialCtx.__wbRuntime.getModule('a.js').x, 7, `Sandbox string export name ${JSON.stringify(specialName)} must resolve to 7`);
            }
            const specDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wb-spec-name-'));
            try {
              fs.mkdirSync(path.join(specDir, 'shell'), { recursive: true });
              fs.writeFileSync(path.join(specDir, 'theme.js'), 'export const theme = "light";\n', 'utf8');
              fs.writeFileSync(path.join(specDir, 'b.js'), specialSources[0].code, 'utf8');
              fs.writeFileSync(
                path.join(specDir, 'shell/main.jsx'),
                `import { ${JSON.stringify(specialName)} as x } from '../b.js'; globalThis.probe = x;\n`,
                'utf8'
              );
              const prodOuts = bundleProduction({ appDir: specDir }).outputs;
              const prodCtx = vm.createContext({});
              for (const out of prodOuts) vm.runInContext(out.code, prodCtx);
              assert.equal(prodCtx.probe, 7, `Production string export name ${JSON.stringify(specialName)} must resolve to 7`);
            } finally {
              fs.rmSync(specDir, { recursive: true, force: true });
            }
          }

          // Diamond export * forwarding the same source binding succeeds in both sandbox and production.
          const diamondSources = [
            { path: 'base.js', code: 'export const x = 7;' },
            { path: 'left.js', code: 'export * from "./base.js";' },
            { path: 'right.js', code: 'export * from "./base.js";' },
            { path: 'middle.js', code: 'export * from "./left.js"; export * from "./right.js";' },
            { path: 'consumer.js', code: 'import { x } from "./middle.js"; export default { x };' },
          ];
          const diamondCompiled = compile({ sources: diamondSources, check_combined: false });
          const diamondCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
          diamondCtx.window = diamondCtx;
          for (const out of diamondCompiled.outputs) {
            vm.runInContext(out.code, diamondCtx, { filename: out.path });
          }
          assert.equal(diamondCtx.__wbRuntime.getModule('consumer.js').x, 7, 'Same-origin diamond export * must resolve to 7 in sandbox');
          {
            const diamondDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wb-diamond-'));
            try {
              fs.mkdirSync(path.join(diamondDir, 'shell'), { recursive: true });
              fs.writeFileSync(path.join(diamondDir, 'theme.js'), 'export const theme = "light";\n', 'utf8');
              for (const s of diamondSources.slice(0, 4)) {
                fs.writeFileSync(path.join(diamondDir, s.path), s.code, 'utf8');
              }
              fs.writeFileSync(path.join(diamondDir, 'shell/main.jsx'), 'import { x } from "../middle.js"; globalThis.probe = x;\n', 'utf8');
              const prodOuts = bundleProduction({ appDir: diamondDir }).outputs;
              const prodCtx = vm.createContext({});
              for (const out of prodOuts) vm.runInContext(out.code, prodCtx);
              assert.equal(prodCtx.probe, 7, 'Same-origin diamond export * must resolve to 7 in production');
            } finally {
              fs.rmSync(diamondDir, { recursive: true, force: true });
            }
          }

          // Inherited prototype properties (call, toString) of default export do not shadow named exports in either loading order.
          for (const [key, defExpr] of [['call', 'function f() {}'], ['toString', '{}']]) {
            const inhSources = [
              { path: 'inherited.js', code: `export const ${key} = 7; export default ${defExpr};` },
              { path: 'inheritedconsumer.js', code: `import { ${key} } from './inherited.js'; export default { value: ${key} };` },
            ];
            for (const ordered of [inhSources, [...inhSources].reverse()]) {
              const inhCompiled = compile({ sources: ordered, check_combined: false });
              const inhCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
              inhCtx.window = inhCtx;
              for (const out of inhCompiled.outputs) {
                vm.runInContext(out.code, inhCtx, { filename: out.path });
              }
              assert.equal(
                inhCtx.__wbRuntime.getModule('inheritedconsumer.js').value,
                7,
                `Named export ${key} must not be shadowed by inherited default property`
              );
            }
          }

          // Default export with throwing getter is not invoked during module initialization.
          const getterCompiled = compile({
            sources: [{
              path: 'getter-probe.js',
              code: 'globalThis.count = 0; const o = {}; Object.defineProperty(o, "x", { get() { globalThis.count++; throw new Error("getter-bug"); } }); export default o;',
            }],
            check_combined: false,
          });
          const getterCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
          getterCtx.window = getterCtx;
          for (const out of getterCompiled.outputs) {
            vm.runInContext(out.code, getterCtx, { filename: out.path });
          }
          assert.equal(getterCtx.count, 0, 'Throwing accessor on default export must be called 0 times during module initialization');

          // Codex R13-1: Unicode named export (export const café = 7) resolves to 7 in both VM sandbox and bundleProduction.
          {
            const unicodeSources = [
              { path: 'unicode-dep.js', code: 'export const café = 7;' },
              { path: 'unicode-consumer.js', code: "import { café } from './unicode-dep.js'; export default { café };" },
            ];
            for (const ordered of [unicodeSources, [...unicodeSources].reverse()]) {
              const unicodeCompiled = compile({ sources: ordered, check_combined: false });
              const unicodeCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
              unicodeCtx.window = unicodeCtx;
              for (const out of unicodeCompiled.outputs) {
                vm.runInContext(out.code, unicodeCtx, { filename: out.path });
              }
              assert.equal(unicodeCtx.__wbRuntime.getModule('unicode-consumer.js').café, 7, 'Unicode named export café must resolve to 7 in VM sandbox');
            }
            const unicodeDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wb-unicode-'));
            try {
              fs.mkdirSync(path.join(unicodeDir, 'shell'), { recursive: true });
              fs.writeFileSync(path.join(unicodeDir, 'theme.js'), 'export const theme = "light";\n', 'utf8');
              fs.writeFileSync(path.join(unicodeDir, 'unicode-dep.js'), 'export const café = 7;\n', 'utf8');
              fs.writeFileSync(path.join(unicodeDir, 'shell/main.jsx'), 'import { café } from "../unicode-dep.js"; globalThis.probe = café;\n', 'utf8');
              const prodOuts = bundleProduction({ appDir: unicodeDir }).outputs;
              const prodCtx = vm.createContext({});
              for (const out of prodOuts) vm.runInContext(out.code, prodCtx);
              assert.equal(prodCtx.probe, 7, 'Unicode named export café must resolve to 7 in bundleProduction');
            } finally {
              fs.rmSync(unicodeDir, { recursive: true, force: true });
            }
          }

          // Codex R13-2: Foo.js with `export const Foo = 1; export default 2;` default import resolves to 2 in both VM and bundleProduction, and window.Foo === undefined.
          {
            const fooSources = [
              { path: 'Foo.js', code: 'export const Foo = 1; export default 2;' },
              { path: 'foo-consumer.js', code: "import FooDefault, { Foo as FooNamed } from './Foo.js'; export const defVal = FooDefault; export const namedVal = FooNamed;" },
            ];
            for (const ordered of [fooSources, [...fooSources].reverse()]) {
              const fooCompiled = compile({ sources: ordered, check_combined: false });
              const fooCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
              fooCtx.window = fooCtx;
              for (const out of fooCompiled.outputs) {
                vm.runInContext(out.code, fooCtx, { filename: out.path });
              }
              const fooConsumer = fooCtx.__wbRuntime.getModule('foo-consumer.js');
              assert.equal(fooConsumer.defVal, 2, 'Default import from Foo.js must resolve to 2 in VM sandbox');
              assert.equal(fooConsumer.namedVal, 1, 'Named import Foo from Foo.js must resolve to 1 in VM sandbox');
              assert.equal(fooCtx.window.Foo, undefined, 'Foo.js must not leak window.Foo in VM sandbox');
            }
            const fooDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wb-foo-'));
            try {
              fs.mkdirSync(path.join(fooDir, 'shell'), { recursive: true });
              fs.writeFileSync(path.join(fooDir, 'theme.js'), 'export const theme = "light";\n', 'utf8');
              fs.writeFileSync(path.join(fooDir, 'Foo.js'), 'export const Foo = 1; export default 2;\n', 'utf8');
              fs.writeFileSync(path.join(fooDir, 'shell/main.jsx'), 'import FooDefault from "../Foo.js"; globalThis.probe = FooDefault;\n', 'utf8');
              const prodOuts = bundleProduction({ appDir: fooDir }).outputs;
              const prodCtx = vm.createContext({ window: {} });
              for (const out of prodOuts) vm.runInContext(out.code, prodCtx);
              assert.equal(prodCtx.probe, 2, 'Default import from Foo.js must resolve to 2 in bundleProduction');
              assert.equal(prodCtx.window.Foo, undefined, 'Foo.js must not leak window.Foo in bundleProduction');
            } finally {
              fs.rmSync(fooDir, { recursive: true, force: true });
            }
          }

          // Codex R13-3: Exporting and importing "__esModule" resolves to 7 in both VM sandbox and bundleProduction.
          {
            const esmSources = [
              { path: 'esm-flag.js', code: 'const x = 7; export { x as "__esModule" };' },
              { path: 'esm-consumer.js', code: 'import { "__esModule" as flag } from "./esm-flag.js"; export const value = flag;' },
            ];
            for (const ordered of [esmSources, [...esmSources].reverse()]) {
              const esmCompiled = compile({ sources: ordered, check_combined: false });
              const esmCtx = vm.createContext({ console, Object, Array, Set, Map, WeakMap, WeakSet, Error, TypeError });
              esmCtx.window = esmCtx;
              for (const out of esmCompiled.outputs) {
                vm.runInContext(out.code, esmCtx, { filename: out.path });
              }
              assert.equal(esmCtx.__wbRuntime.getModule('esm-consumer.js').value, 7, 'Importing "__esModule" must resolve to 7 in VM sandbox');
            }
            const esmDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wb-esm-flag-'));
            try {
              fs.mkdirSync(path.join(esmDir, 'shell'), { recursive: true });
              fs.writeFileSync(path.join(esmDir, 'theme.js'), 'export const theme = "light";\n', 'utf8');
              fs.writeFileSync(path.join(esmDir, 'esm-flag.js'), 'const x = 7; export { x as "__esModule" };\n', 'utf8');
              fs.writeFileSync(path.join(esmDir, 'shell/main.jsx'), 'import { "__esModule" as flag } from "../esm-flag.js"; globalThis.probe = flag;\n', 'utf8');
              const prodOuts = bundleProduction({ appDir: esmDir }).outputs;
              const prodCtx = vm.createContext({});
              for (const out of prodOuts) vm.runInContext(out.code, prodCtx);
              assert.equal(prodCtx.probe, 7, 'Importing "__esModule" must resolve to 7 in bundleProduction');
            } finally {
              fs.rmSync(esmDir, { recursive: true, force: true });
            }
          }

          assert.throws(
            () => compile({ sources: [{ path: 'shell/../../outside.js', code: 'export const x = 1;' }] }),
            /Missing module in frontend\/workbench\/app/,
            'compile must reject relative .. escape out of frontend/workbench/app'
          );
          assert.throws(
            () => compile({ sources: [{ path: 'frontend/workbench/app/../../../outside.js', code: 'export const x = 1;' }] }),
            /Missing module in frontend\/workbench\/app/,
            'compile must reject prefixed relative .. escape out of frontend/workbench/app'
          );
        }

        console.log(JSON.stringify({ ok: true }));
        """
    )
    assert report["ok"] is True


def test_build_strict_module_style_asset_and_retired_cleanup_contracts(tmp_path, monkeypatch):
    import importlib
    import shutil
    import sys

    import pytest

    for mod_name in (
        "scripts.workbench.asset_sources",
        "scripts.workbench.entry_bundle",
        "scripts.workbench.build",
    ):
        monkeypatch.delitem(sys.modules, mod_name, raising=False)
    build_mod, node = importlib.import_module("scripts.workbench.build"), node_runtime()
    project_root, output_dir = tmp_path / "repo", tmp_path / "static_workbench"
    app_dir = project_root / "frontend/workbench/app"
    shutil.copytree(ROOT / "frontend/workbench/vendor", project_root / "frontend/workbench/vendor")
    for sub in ("shell", "styles", "assets"):
        (app_dir / sub).mkdir(parents=True)
    for rel, content in (
        ("theme.js", 'export const theme = "light";\n'),
        ("shared.js", "export const value = 7;\n"),
        ("shell/main.jsx", 'import { value } from "../shared.js"; globalThis.ready = value;\n'),
        ("styles/index.css", '@import "./tokens.css";\n@import "./typography.css";\n'),
        ("styles/tokens.css", ":root { --ink: #111; }\n"),
        ("styles/typography.css", '@font-face { font-family: "Test"; src: url("../assets/MicrosoftYaHei-Regular.ttf"); }\n'),
        ("assets/logo-mark.svg", "<svg/>"),
        ("assets/lucide-LICENSE", "ISC\n"),
    ):
        (app_dir / rel).write_text(content, encoding="utf-8")
    (app_dir / "assets/MicrosoftYaHei-Regular.ttf").write_bytes(b"TTF")

    for orphan_rel in ("orphan.js", "shell/orphan.jsx"):
        orphan = app_dir / orphan_rel
        orphan.write_text("export const unused = 1;\n", encoding="utf-8")
        with pytest.raises(ValueError, match=r"JS module graph out of sync; missing=; unlisted=" + orphan_rel):
            build_mod.build(project_root, output_dir, node)
        orphan.unlink()
    with pytest.raises(ValueError, match=r"JS module graph out of sync; missing=missing\.js; unlisted="):
        build_mod.verify_js_module_graph(app_dir, ["theme.js", "shared.js", "shell/main.jsx", "missing.js"])

    for target_rel, extra_rel, missing_pat, extra_pat in (
        ("styles/tokens.css", "styles/extra.css", r"Live styles not ready; missing=tokens\.css; unlisted=", r"Live styles not ready; missing=; unlisted=extra\.css"),
        ("assets/logo-mark.svg", "assets/unlisted.svg", r"App assets out of sync; missing=app/assets/logo-mark\.svg; unlisted=", r"App assets out of sync; missing=; unlisted=app/assets/unlisted\.svg"),
    ):
        target_file, extra_file = app_dir / target_rel, app_dir / extra_rel
        saved = target_file.read_bytes()
        target_file.unlink()
        with pytest.raises(ValueError, match=missing_pat):
            build_mod.build(project_root, output_dir, node)
        target_file.write_bytes(saved)
        extra_file.write_text("extra\n", encoding="utf-8")
        with pytest.raises(ValueError, match=extra_pat):
            build_mod.build(project_root, output_dir, node)
        extra_file.unlink()

    for stale_rel in (
        "prototype/assets/MicrosoftYaHei-Regular.ttf", "prototype/assets/logo-mark.svg",
        "prototype/ui_kits/workbench/assets/lucide-LICENSE", "prototype/styles.css",
        "/".join(("assets", "foundation-0123456789abcdef.js")), "app/styles/legacy/old.css", "app/assets/stale/old.svg", "app/retired.js",
    ):
        stale_file = output_dir / stale_rel
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        stale_file.write_bytes(b"stale")

    built = build_mod.build(project_root, output_dir, node)
    assert built["status"] == "built"
    for removed in ("prototype", "assets", "app/styles", "app/assets/stale", "app/retired.js"):
        assert not (output_dir / removed).exists()
    for kept in ("app/theme.js", "app/main.js", "app/workbench.css", "app/assets/logo-mark.svg", "app/assets/lucide-LICENSE", "app/assets/MicrosoftYaHei-Regular.ttf"):
        assert (output_dir / kept).is_file()
    manifest = json.loads((output_dir / "asset-manifest.json").read_text(encoding="utf-8"))
    assert manifest["icon"] == "workbench/app/assets/logo-mark.svg"
    assert manifest["notices"][2] == "workbench/app/assets/lucide-LICENSE"


def test_vendor_react_metadata_size_contracts_and_esbuild_already_installed_short_circuit(tmp_path, monkeypatch):
    import io
    import tarfile

    import pytest

    from scripts.workbench import vendor_react

    def make_tarball(members):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as archive:
            for rel_path, content in members.items():
                info = tarfile.TarInfo(name="package/" + rel_path)
                info.size = len(content)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(content))
        return buf.getvalue()

    wrong_version_react_tarball = make_tarball({
        "umd/react.production.min.js": b"/* react umd */",
        "LICENSE": b"Permission is hereby granted",
        "package.json": json.dumps({
            "name": "react",
            "version": "18.2.0",
            "license": "MIT",
        }).encode("utf-8"),
    })
    react_meta_url = f"https://registry.npmjs.org/react/{vendor_react.VERSION}"
    react_tar_url = f"https://registry.npmjs.org/react/-/react-{vendor_react.VERSION}.tgz"

    def fake_read_url_react(url):
        if url == react_meta_url:
            return json.dumps({
                "name": "react",
                "version": vendor_react.VERSION,
                "license": "MIT",
                "dist": {
                    "tarball": react_tar_url,
                },
            }).encode("utf-8")
        if url == react_tar_url:
            return wrong_version_react_tarball
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(vendor_react, "read_url", fake_read_url_react)
    with pytest.raises(ValueError, match=r"Package payload identity mismatch"):
        vendor_react.checked_payload("react")

    manifest = vendor_react.load_esbuild_manifest()
    pkg_tar_url = manifest["package"]["tarball"]
    plat_spec = manifest["platforms"]["win32-x64"]
    plat_tar_url = plat_spec["tarball"]
    optional_deps = {f"@esbuild/{key}": vendor_react.ESBUILD_VERSION for key in vendor_react.ESBUILD_PLATFORMS}
    pkg_json_bytes = json.dumps({
        "name": "esbuild",
        "version": vendor_react.ESBUILD_VERSION,
        "optionalDependencies": optional_deps,
    }).encode("utf-8")
    valid_pkg_tarball = make_tarball({
        "package.json": pkg_json_bytes,
        "lib/main.js": b"x" * 16,
        "bin/esbuild": b"y" * 8,
    })
    custom_manifest_path = tmp_path / "esbuild-manifest.json"
    custom_manifest = json.loads((ROOT / "scripts/workbench/esbuild-manifest.json").read_text(encoding="utf-8"))
    custom_manifest["package"]["files"]["package.json"]["size"] = len(pkg_json_bytes)
    custom_manifest["package"]["files"]["lib/main.js"]["size"] = 16
    custom_manifest["package"]["files"]["bin/esbuild"]["size"] = 8
    custom_manifest["platforms"]["win32-x64"]["binary_size"] = 1024
    custom_manifest_path.write_text(json.dumps(custom_manifest), encoding="utf-8")

    wrong_size_plat_tarball = make_tarball({
        "package.json": json.dumps({"name": "@esbuild/win32-x64", "version": vendor_react.ESBUILD_VERSION}).encode("utf-8"),
        "esbuild.exe": b"MZ-truncated",
    })
    esbuild_root = tmp_path / "esbuild_repo"

    def fake_read_url_esbuild(url):
        if url == pkg_tar_url:
            return valid_pkg_tarball
        if url == plat_tar_url:
            return wrong_size_plat_tarball
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(vendor_react, "read_url", fake_read_url_esbuild)
    with pytest.raises(ValueError, match=r"esbuild binary size mismatch"):
        vendor_react.install_esbuild_vendor(
            root=esbuild_root,
            platform_key="win32-x64",
            manifest_path=custom_manifest_path,
        )

    def forbidden_read_url(_url):
        raise AssertionError("install_esbuild_vendor must not call read_url when local vendor passes verification")

    monkeypatch.setattr(vendor_react, "read_url", forbidden_read_url)
    short_circuited = vendor_react.install_esbuild_vendor(root=ROOT)
    assert short_circuited["status"] == "already_installed"
    assert short_circuited["version"] == vendor_react.ESBUILD_VERSION
