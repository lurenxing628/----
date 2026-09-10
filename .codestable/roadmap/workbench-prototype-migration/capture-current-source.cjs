'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '../../..');
const trees = ['templates', 'static', 'web', 'core', 'data', 'assets', 'installer', 'plugins',
  'tools', 'scripts', 'tests', 'frontend', 'desktop', '前端设计', '.codestable'];
const files = fs.readdirSync(root).filter(name => fs.lstatSync(path.join(root, name)).isFile()
  && (/^(?:app(?:_new_ui)?|config|validate_dist_exe)\.py$/.test(name)
    || /^requirements.*\.txt$/.test(name) || /^pyrightconfig.*\.json$/.test(name)
    || /^build_win7.*\.bat$/.test(name)
    || ['schema.sql', 'pyproject.toml', 'pytest.ini', 'ruff.toml', '.gitignore', '.gitattributes',
        '.pre-commit-config.yaml', 'AGENTS.md'].includes(name)));
const skippedDirs = new Set(['.git', '__pycache__', 'node_modules', '.pytest_cache', '.venv',
  'logs', 'backups', 'uploads', 'output']);
const excluded = [];
const inventory = [];
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const git = args => execFileSync('git', args, { cwd: root, maxBuffer: 128 * 1024 * 1024 });

function visit(relative) {
  const file = path.join(root, relative), stat = fs.lstatSync(file);
  if (stat.isSymbolicLink()) throw new Error('Review symlink before archival: ' + relative);
  if (stat.isDirectory()) {
    if (relative.split(path.sep).join('/') === '.codestable/checkup/latest') { excluded.push(relative); return; }
    if (relative.startsWith('.codestable' + path.sep) && path.basename(relative).startsWith('pytest-')) {
      excluded.push(relative); return;
    }
    if (skippedDirs.has(path.basename(relative))) { excluded.push(relative); return; }
    for (const name of fs.readdirSync(file).sort()) visit(path.join(relative, name));
    return;
  }
  if (!stat.isFile()) throw new Error('Unsupported source entry: ' + relative);
  if (/[\r\n\0]/.test(relative)) throw new Error('Invalid archival path: ' + relative);
  if (/(?:\.db(?:-(?:wal|shm))?|\.sqlite[3]?(?:-(?:wal|shm))?|\.log|\.py[co])$/i.test(relative)
      || /(?:^|\/)(?:\.env(?:\..*)?|aps_secret_key\.txt)$/.test(relative)) {
    excluded.push(relative); return;
  }
  inventory.push({ path: relative.split(path.sep).join('/'), size: stat.size,
    mode: stat.mode & 0o777, sha256: digest(fs.readFileSync(file)) });
}

if (path.resolve(git(['rev-parse', '--show-toplevel']).toString().trim()) !== root)
  throw new Error('Unexpected repository root');
const beforeStatus = git(['status', '--porcelain=v1', '-z']);
const beforeStaged = git(['diff', '--cached', '--binary']);
const beforeUnstaged = git(['diff', '--binary']);
for (const relative of [...trees, ...files]) {
  if (!fs.existsSync(path.join(root, relative))) throw new Error('Missing baseline input: ' + relative);
  visit(relative);
}
inventory.sort((a, b) => a.path.localeCompare(b.path, 'en'));
if (new Set(inventory.map(row => row.path)).size !== inventory.length) throw new Error('Duplicate baseline path');
const parent = path.join(root, 'output/workbench-migration/baselines');
fs.mkdirSync(parent, { recursive: true });
const directory = fs.mkdtempSync(path.join(parent, 'pre-retirement-'));
fs.chmodSync(directory, 0o700);
const list = path.join(directory, 'paths.nul'), archive = path.join(directory, 'source.tar.gz');
fs.writeFileSync(list, Buffer.from(inventory.map(row => row.path).join('\0') + '\0'));
execFileSync('tar', ['-czf', archive, '--null', '-T', list],
  { cwd: root, env: { ...process.env, COPYFILE_DISABLE: '1' }, maxBuffer: 16 * 1024 * 1024 });

// The archive is verified against an independent extraction, then against the unchanged source.
const restore = path.join(directory, 'restore-check');
fs.mkdirSync(restore);
execFileSync('tar', ['-xzpf', archive, '-C', restore], { maxBuffer: 16 * 1024 * 1024 });
let verified = 0;
for (const row of inventory) {
  for (const base of [restore, root]) {
    const target = path.join(base, row.path), stat = fs.lstatSync(target);
    if (!stat.isFile() || stat.size !== row.size || (stat.mode & 0o777) !== row.mode
        || digest(fs.readFileSync(target)) !== row.sha256)
      throw new Error('Baseline changed or failed restoration: ' + target);
  }
  verified++;
}
const restoredFiles = [];
function listRestored(directory, prefix = '') {
  for (const name of fs.readdirSync(directory)) {
    const target = path.join(directory, name), relative = prefix ? prefix + '/' + name : name;
    const stat = fs.lstatSync(target);
    if (stat.isDirectory()) listRestored(target, relative);
    else if (stat.isFile()) restoredFiles.push(relative);
    else throw new Error('Unexpected restored entry: ' + relative);
  }
}
listRestored(restore);
const expectedPaths = new Set(inventory.map(row => row.path));
if (restoredFiles.length !== expectedPaths.size || restoredFiles.some(file => !expectedPaths.has(file)))
  throw new Error('Restored archive membership differs from manifest');
if (!beforeStatus.equals(git(['status', '--porcelain=v1', '-z']))
    || !beforeStaged.equals(git(['diff', '--cached', '--binary']))
    || !beforeUnstaged.equals(git(['diff', '--binary'])))
  throw new Error('Git state changed during capture; retain archive as unverified and retry after review');
fs.writeFileSync(path.join(directory, 'staged.patch'), beforeStaged, { mode: 0o600 });
fs.writeFileSync(path.join(directory, 'unstaged.patch'), beforeUnstaged, { mode: 0o600 });
const manifest = {
  schema_version: 1, captured_at: new Date().toISOString(), local_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  root, head: git(['rev-parse', 'HEAD']).toString().trim(), scope: { trees, files },
  source_only: true, database_backed_up: false, product_runtime_verified: false,
  git_status_porcelain_z_base64: beforeStatus.toString('base64'),
  staged_patch_sha256: digest(beforeStaged), unstaged_patch_sha256: digest(beforeUnstaged),
  archive: { path: archive, size: fs.statSync(archive).size, sha256: digest(fs.readFileSync(archive)) },
  files: inventory, excluded, verification: { status: 'passed', files: verified, restore_directory: restore,
    source_unchanged: true, git_state_unchanged: true, method: 'extract-and-compare-size-mode-sha256' }
};
fs.writeFileSync(path.join(directory, 'manifest.json'), JSON.stringify(manifest, null, 2), { mode: 0o600 });
console.log(JSON.stringify({ status: 'PASS', directory, files: verified,
  archive_bytes: manifest.archive.size, archive_sha256: manifest.archive.sha256,
  database_backed_up: false, restored_files_verified: verified }, null, 2));
