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
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const babelPath = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
        const files = ['WorkbenchGuards.js', 'WorkbenchNavigation.js', 'main.jsx'];
        const compiled = compile({
          babel_path: babelPath,
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
            w.WorkbenchGuards.useDirtyGuard({ owner: 'batch-editor', dirty: isDirty, message: '批次草稿未保存' });
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
            APSWorkbenchTheme: { get: () => ({ theme: 'light', error: '' }), subscribe: () => () => {}, set() {} },
            WorkbenchDensity: { get: () => ({ density: 'comfortable', error: '' }), subscribe: () => () => {}, set() {} },
            WorkbenchScrollShadows: { attach: () => () => {} },
            APSBatchAPI: { create: () => ({}) },
            ResourceControls: { Icon: () => null },
            Ico: () => null,
            WorkbenchControlStyles: () => null,
            WorkbenchControls: () => null,
            WorkbenchNumberControls: () => null,
            WorkbenchGuardHost: () => null,
            WorkbenchPageContext: {
              Provider({ remember, children }) { rememberedCallback = remember; return children; },
            },
            WorkbenchCaption: {
              Caption: () => null,
              Provider({ children }) { return children; },
            },
            WorkbenchBoundary({ children }) { return children; },
            BatchWorkspace,
            WorkbenchDashboardWorkspace: () => React.createElement('div', { 'data-workspace': 'dashboard' }, 'dashboard-mounted'),
            WorkbenchTerms: { outcomes: { unavailable: '不可用' } },
            addEventListener(type, fn) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); },
            removeEventListener(type, fn) { listeners.get(type)?.delete(fn); },
            dispatchEvent() {},
            scrollTo() {},
            scrollX: 0,
            scrollY: 20,
          });
          w.window = w;

          for (const out of compiled.outputs) vm.runInContext(out.code, w, { filename: out.path });

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
            stats: () => ({ workspaceMounts, workspaceUnmounts, dirty: w.WorkbenchGuards.hasDirty() }),
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
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const babelPath = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
        const files = [
          'WorkbenchTerms.js', 'transport.js', 'WorkbenchGuards.js', 'SystemRestoreStatus.js',
          'SystemMaintenanceAPI.js', 'SystemMaintenanceControls.jsx', 'SystemMaintenanceRecords.jsx',
          'SystemMaintenanceConfig.jsx', 'SystemLive.jsx'
        ];
        const compiled = compile({
          babel_path: babelPath,
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
          SMIcon: () => null,
          SMExport: () => null,
          SMUnavailable: () => null,
          SMStatus: () => null,
          APSWorkbenchUI: { ControlButton: 'button', MetricStrip: 'div', Metric: 'div' },
          APSSystemWorkbench: { inspectEnvironment: () => ({ schemaVersion: 1, checkedAt: '2026-10-30T08:00:00Z', protocol: 'http:', checks: [] }) },
          APSWorkbenchSystemContract: { validate: () => true },
          WorkbenchDensity: { get: () => ({ density: 'comfortable' }), subscribe: () => () => {}, set() {} },
          WorkbenchPageContext: { useSnapshot() {} },
          WorkbenchFormat: { dateTime: String, instant: String, number: String },
          WorkbenchReference: 'reference',
          WorkbenchError: 'error-box',
          WorkbenchListControls: { EmptyState: 'empty', Pager: 'pager' },
          ResourceControls: {
            Button(props) { return React.createElement('button', props, props.children); },
            Modal: 'modal',
          },
          APSResourceSession: {
            useQuery() { return { result: configPayload, error: null, loading: false }; },
          },
        });
        w.window = w;
        for (const out of compiled.outputs) vm.runInContext(out.code, w, { filename: out.path });

        const prompts = [];
        w.WorkbenchGuards.subscribe(p => prompts.push(p));

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
          const tree = renderNode(React.createElement(w.SystemMaintenanceConfig, {
            revision: '1:0', command, active: isActive, tab: currentTab,
            theme: 'light', onSetTheme() {}, pageSize: 10, onPageSize() {}, compact: false, onCompact() {},
          }));
          while (layoutEffects.length) layoutEffects.shift()();
          while (effects.length) effects.shift()();
          return tree;
        }

        let tree = renderConfig();
        tree = renderConfig();
        assert.equal(w.WorkbenchGuards.hasDirty(), false);

        const intervalInput = find(tree, n => n.type === 'input' && n.props.id === 'sm-maintenance-auto_backup_interval_minutes');
        assert.ok(intervalInput);
        intervalInput.props.onChange({ target: { value: '90' } });
        tree = renderConfig();
        assert.equal(w.WorkbenchGuards.hasDirty(), true, 'Modified config draft must register dirty guard');

        // Prompt contains exact expected message.
        const leavePromise = w.WorkbenchGuards.confirmLeave();
        const prompt = w.WorkbenchGuards.getPrompt();
        assert.ok(prompt && prompt.messages.includes('系统自动维护配置存在未保存修改，确定离开当前页面吗？'));
        w.WorkbenchGuards.resolvePrompt(prompt.id, false);
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
        assert.equal(w.WorkbenchGuards.hasDirty(), false);

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
        assert.equal(w.SystemMaintenanceAPI.collection(validCollection, 'backups'), validCollection);

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
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const babelPath = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
        const files = [
          'FieldDetail.jsx',
          'OperatorMachinePermissions.jsx',
          'BatchMaterialEditor.jsx',
          'ProcessStageEditor.jsx',
          'ProcessGroupEditor.jsx',
        ];
        const compiled = compile({
          babel_path: babelPath,
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
            FieldContract: {
              query: v => v,
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
            FieldControls: { Button: p => host.React.createElement('button', p, p.children), ErrorBox: () => null, Issues: () => null, State: () => null },
            WorkbenchControls: { usePrintLayout: () => false },
            GanttPresentation: { axis: () => ({ ticks: [{ at: 1, x: 100 }] }), taskLines: () => ({ primary: 'R-01', secondary: '' }) },
            GanttPresentationUI: { Axis: () => null },
            PlanGanttModel: { instant: v => { instantCalls++; return Date.parse(v + 'Z'); } },
            PointContract: { isPoint: () => false },
            PointGanttModel: { bounds: (s, e) => ({ start: s, end: e }) },
            PointGantt: { Marker: 'marker' },
            APSResourceSession: { useQuery: () => ({ loading: false, result: { data: { task } }, error: null }) },
            WorkbenchListControls: { EmptyState: () => null },
          });
          w.window = w;
          vm.runInContext(compiled.outputs[0].code, w);

          const renderDetail = () => host.render(() => host.React.createElement(w.FieldDetail, {
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
            APSResourceContract: { blocked: () => '' },
            APSResourceSession: {
              useQuery: (_fn, deps) => ({
                loading: false,
                error: null,
                result: { data: { page: { total: 2 }, entities: [
                  { ref: ref(10), business_code: 'M1', label: '车床1', query: deps[1] },
                  { ref: ref(11), business_code: 'M2', label: '车床2', query: deps[1] },
                ] } },
              }),
            },
            ResourceControls: {
              Button: p => host.React.createElement('button', p, p.children),
              Icon: () => null,
              ErrorBox: () => null,
              Modal: p => host.React.createElement('div', p, p.children, p.footer),
            },
            WorkbenchGuards: { useDirtyGuard: () => 'owner', confirmLeave: async () => true },
            WorkbenchTerms: { refresh_latest: '刷新' },
          });
          w.window = w;
          vm.runInContext(compiled.outputs[1].code, w);

          const entity = {
            ref: ref(20),
            business_code: 'OP1',
            label: '张三',
            write_context: { write_token: 'w'.repeat(32) },
            relationships: { machine_permissions: basePermissions },
          };
          const renderPerm = () => host.render(() => host.React.createElement(w.OperatorMachinePermissions, {
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
            APSBatchContract: {},
            APSResourceContract: { failure: m => new Error(m) },
            APSResourceSession: {
              useQuery: () => ({ loading: false, error: null, result: { meta: { snapshot_ref: 's' }, data: { page: {}, entities: [] } } }),
            },
            ResourceControls: {
              Button: p => host.React.createElement('button', p, p.children),
              Modal: p => host.React.createElement('div', p, p.children, p.footer),
              ErrorBox: () => null,
              Field: p => host.React.createElement('label', p, p.children),
            },
            ResourceForms: { Feedback: () => null },
            WorkbenchControls: { Pager: () => null },
            WorkbenchGuards: { useDirtyGuard: () => 'owner', confirmLeave: async () => true },
            WorkbenchTerms: { refresh_latest: '刷新' },
          });
          w.window = w;
          vm.runInContext(compiled.outputs[2].code, w);

          const renderMat = () => host.render(() => host.React.createElement(w.BatchMaterialEditor, {
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
            APSResourceContract: { failure: m => new Error(m), own: (o, k) => Object.prototype.hasOwnProperty.call(o, k), blocked: () => '' },
            APSProcessContract: { sourceLabel: s => s, stagePreview: v => v },
            ResourceControls: {
              Button: p => host.React.createElement('button', p, p.children),
              Modal: p => host.React.createElement('div', p, p.children, p.footer),
              Search: p => host.React.createElement('input', p),
              ErrorBox: () => null,
              Issues: () => null,
            },
            ResourceTables: { Pager: () => null },
            ResourceForms: { Feedback: () => null },
            ProcessSourcePicker: p => host.React.createElement('div', { 'data-picker': true, target: p.target }),
            WorkbenchTerms: { refresh_latest: '刷新', accept_latest: '接受' },
          });
          w.window = w;
          vm.runInContext(compiled.outputs[3].code, w);
          const origActive = w.ProcessStageEditor.active;
          w.ProcessStageEditor.active = ent => { activeCalls++; return origActive(ent); };
          vm.runInContext(compiled.outputs[4].code, w);

          const result = { data: entity, meta: { source: 'production', snapshot_ref: 's'.repeat(32) } };
          const renderGroups = () => host.render(() => host.React.createElement(w.ProcessGroupEditor, {
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
        const path = require('node:path');
        const vm = require('node:vm');
        const { compile } = require('./scripts/workbench/compile.cjs');

        const root = process.cwd();
        const appDir = path.join(root, 'frontend/workbench/app');
        const babelPath = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js');
        const files = [
          'WorkbenchTerms.js', 'transport.js', 'resource-contract.js', 'resource-api.js', 'resource-session.js',
          'ResourceControls.jsx', 'FieldEditorFields.jsx',
          'BatchContract.js', 'BatchAPI.js', 'BatchForms.jsx', 'BatchMaterialEditor.jsx',
          'BatchOperationEditor.jsx', 'BatchSplitPanel.jsx', 'BatchFiles.jsx',
          'SystemRestoreStatus.js', 'SystemMaintenanceAPI.js', 'SystemMaintenanceControls.jsx', 'SystemMaintenanceConfig.jsx'
        ];
        const compiled = compile({
          babel_path: babelPath,
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
          APSFieldReports: { iconNodes: {} },
          SMIcon: () => null, Ico: () => null,
          APSWorkbenchUI: { TransferIcon: () => null },
          WorkbenchError: () => null,
          WorkbenchFormat: { hours: String, number: String, dateTime: String },
          WorkbenchGuards: { useDirtyGuard: () => 'owner', confirmLeave: async () => true },
          WorkbenchHandlerMemory: { read: () => ({ value: '李四' }), write() {} },
          FieldContract: { quantity: String },
          FieldControls: { Button: 'button' },
          BatchControls: { BaseFields: () => null, Field: 'div', display: String },
          ResourceForms: { Feedback: () => null },
          WorkbenchControls: { Pager: () => null },
          RunAdoptionControls: { Button: 'button', Dialog: 'dialog' },
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

        // #44: relationLabels and FieldEditorFields preserve actual_machine and actual_operator labels and memoize original.
        const record = {
          completed_quantity: 5,
          actual_machine_ref: ref(1),
          actual_machine_label: 'M-01 数控车床',
          actual_operator_ref: ref(2),
          actual_operator_label: 'OP-01 王工',
        };
        let capturedOriginals = [];
        const origChoice = w.ResourceControls.Choice;
        w.ResourceControls.Choice = props => {
          capturedOriginals.push(props.original);
          return hostRender(origChoice(props));
        };
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
        hostRender(w.React.createElement(w.FieldEditorFields, {
          task, record, action: 'correct', adapter,
          draft: { completed_quantity: '5', effective_processing_hours: '1', actual_start: '', actual_end: '', actual_machine_ref: ref(1), actual_operator_ref: ref(2), remark: '', reason: '纠偏', declared_operator: '王工' },
          suggestions: {}, disabled: false, first: { current: null }, change() {}, error: null,
        }));
        const firstOriginal = capturedOriginals[0];
        assert.equal(
          JSON.stringify(w.ResourceControls.relationLabels(firstOriginal, 'actual_machine_ref')),
          JSON.stringify([{ ref: ref(1), label: 'M-01 数控车床' }])
        );
        assert.equal(
          JSON.stringify(w.ResourceControls.relationLabels(firstOriginal, 'actual_operator_ref')),
          JSON.stringify([{ ref: ref(2), label: 'OP-01 王工' }])
        );

        // Re-render with changed draft text: original reference is memoized by [record].
        capturedOriginals = [];
        cursor = 0;
        hostRender(w.React.createElement(w.FieldEditorFields, {
          task, record, action: 'correct', adapter,
          draft: { completed_quantity: '6', effective_processing_hours: '1.5', actual_start: '', actual_end: '', actual_machine_ref: ref(1), actual_operator_ref: ref(2), remark: '修改', reason: '纠偏', declared_operator: '王工' },
          suggestions: {}, disabled: false, first: { current: null }, change() {}, error: null,
        }));
        assert.strictEqual(capturedOriginals[0], firstOriginal, 'original prop must be memoized by [record]');

        // #49: BatchAPI validates receipt once on command and once on lookup (including operation_update operation_ref).
        let batchReceiptCalls = 0;
        const origBatchReceipt = w.APSBatchContract.receipt;
        w.APSBatchContract.receipt = (...args) => { batchReceiptCalls++; return origBatchReceipt(...args); };

        let mockResponse = null;
        w.fetch = async () => ({
          ok: true,
          status: 200,
          headers: { get: () => 'application/json' },
          json: async () => mockResponse,
        });

        const batchApi = w.APSBatchAPI.create();
        mockResponse = {
          ok: true, result: 'committed', receipt_ref: 'r'.repeat(32), replayed: false, warnings: [],
          data: { entity_ref: ref(50), operation_ref: ref(51) },
        };
        const cmdSlot = slots.length;
        function runBatchSession() {
          cursor = cmdSlot;
          const s = w.APSResourceSession.useCommand(batchApi);
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
        w.BatchOperationEditor({
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
        mockResponse = {
          ok: true, result: 'committed', receipt_ref: 'c'.repeat(32), replayed: true, warnings: [],
          data: { entity_ref: ref(50), operation_ref: ref(99) },
        };
        await assert.rejects(
          batchApi.lookup(storedIntent.request_key, storedIntent),
          /保存结果对应的不是当前工序/,
          'BatchAPI.lookup rejects mismatched operation_ref on operation_update'
        );
        assert.throws(
          () => w.APSBatchContract.receipt(mockResponse, 'operation_update', ref(50)),
          /保存结果对应的不是当前工序/,
          'BatchContract.receipt requires expectedOperationRef on operation_update'
        );
        assert.throws(
          () => w.APSBatchContract.receipt(mockResponse, 'update'),
          /保存结果不确定/,
          'BatchContract.receipt requires expected entity ref on non-create single-entity actions'
        );
        batchApi.clearPending(storedIntent);

        // #5: SystemMaintenanceConfig keeps dirty=true even when active=false while on config tab.
        {
          let lastGuard = null;
          w.WorkbenchGuards.useDirtyGuard = spec => { lastGuard = spec; return 'owner'; };
          w.SystemMaintenanceControls.useRead = () => ({
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
          });
          const cfgSlot = slots.length;
          function renderCfg(active, locked = false) {
            cursor = cfgSlot;
            const tree = hostRender(w.React.createElement(w.SystemMaintenanceConfig, {
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

        console.log(JSON.stringify({ ok: true }));
        """
    )
    assert report["ok"] is True
