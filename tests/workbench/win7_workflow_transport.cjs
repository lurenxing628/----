'use strict';
// Transport for real Win7 browser acceptance. No product responses are mocked.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const http = require('node:http');
// Host Python evidence must not pass Chinese SQLite values through Windows GBK.
process.env.PYTHONIOENCODING = 'utf-8';
process.env.PYTHONUTF8 = '1';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const quote = text => "'" + String(text).replace(/'/g, "''") + "'";

function channel(root) {
  const exchange = path.join(root, 'exchange');
  const guestRoot = 'C:\\APS-Workflows-20260927';
  async function job(body, label = 'job', timeout = 180000) {
    assert(/^[a-zA-Z0-9_-]+$/.test(label));
    const name = Date.now() + '-' + label + '-' + crypto.randomBytes(4).toString('hex');
    const destination = path.join(exchange, 'jobs', name + '.ps1');
    fs.writeFileSync(destination + '.tmp', '\ufeff$ErrorActionPreference="Stop"\ntry {\n' + body + '\nexit 0\n} catch { Write-Error ($_ | Out-String) -ErrorAction Continue; exit 1 }\n', 'utf8');
    fs.renameSync(destination + '.tmp', destination);
    const result = path.join(exchange, 'results', name + '.exit');
    const deadline = Date.now() + timeout;
    while (!fs.existsSync(result)) {
      if (Date.now() > deadline) throw new Error('Guest job pending; inspect without retrying: ' + name);
      await sleep(150);
    }
    const status = Number(fs.readFileSync(result, 'utf8').replace(/^\ufeff/, '').trim());
    const logPath = path.join(exchange, 'results', name + '.log');
    const log = fs.existsSync(logPath) ? fs.readFileSync(logPath, 'utf8') : '';
    assert.equal(status, 0, 'Guest job failed: ' + name + '\n' + log.slice(-5000));
    return { name, status, logPath, log };
  }
  async function downloadFile(guid, target) {
    assert(/^[a-f0-9-]{36}$/.test(guid));
    const guestSource = guestRoot + '\\downloads\\' + guid;
    const copy = '\\\\vmware-host\\Shared Folders\\APSWorkflows20260927\\download-copies\\' + guid;
    fs.mkdirSync(path.join(exchange, 'download-copies'), { recursive: true });
    await job('$source=' + quote(guestSource) + '\n$target=' + quote(copy) + '\n'
      + 'if(-not(Test-Path -LiteralPath $source)){throw "Download is missing"}\n'
      + 'if(Test-Path -LiteralPath $target){throw "Download copy already exists"}\n'
      + '[IO.File]::Copy($source,$target,$false)', 'collect-download');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(path.join(exchange, 'download-copies', guid), target);
    return { guestSource, target, bytes: fs.statSync(target).size,
      sha256: crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex') };
  }
  return { job, downloadFile, guestRoot };
}

async function connect(chromium, root) {
  const transport = channel(root);
  const version = await new Promise((resolve, reject) => {
    http.get('http://192.168.181.128:9223/json/version', response => {
      let body = ''; response.on('data', chunk => body += chunk); response.on('end', () => {
        try { resolve(JSON.parse(body)); } catch (error) { reject(error); }
      });
    }).on('error', reject);
  });
  assert(/^Chrome\/109\./.test(version.Browser), version.Browser);
  const endpoint = version.webSocketDebuggerUrl.replace('127.0.0.1:9222', '192.168.181.128:9223').replace('localhost:9222', '192.168.181.128:9223');
  const browser = await chromium.connectOverCDP(endpoint);
  const cdp = await browser.newBrowserCDPSession();
  const downloads = new Map(), collected = [];
  cdp.on('Browser.downloadWillBegin', event => downloads.set(event.guid, { ...event, state: 'started' }));
  cdp.on('Browser.downloadProgress', event => Object.assign(downloads.get(event.guid) || {}, event));
  const newContext = browser.newContext.bind(browser);
  browser.newContext = async options => {
    const before = (await cdp.send('Target.getBrowserContexts')).browserContextIds;
    const context = await newContext({ ...options, acceptDownloads: true });
    const after = (await cdp.send('Target.getBrowserContexts')).browserContextIds;
    const created = after.filter(id => !before.includes(id)); assert.equal(created.length, 1);
    await cdp.send('Browser.setDownloadBehavior', { behavior: 'allowAndName', downloadPath: transport.guestRoot + '\\downloads',
      eventsEnabled: true, browserContextId: created[0] });
    context.on('page', page => {
      const upload = files => {
        if (Array.isArray(files)) return files.map(upload);
        if (typeof files !== 'string') return files;
        const suffix = path.extname(files).toLowerCase();
        const mimeType = suffix === '.xlsx' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
          : suffix === '.csv' ? 'text/csv' : 'application/octet-stream';
        return { name: path.basename(files), mimeType, buffer: fs.readFileSync(files) };
      };
      const prototype = Object.getPrototypeOf(page.locator('body'));
      if (!prototype.__win7BufferUploads) {
        const setInputFiles = prototype.setInputFiles;
        prototype.setInputFiles = function(files, options) { return setInputFiles.call(this, upload(files), options); };
        prototype.__win7BufferUploads = true;
      }
      page.on('filechooser', chooser => {
        const setFiles = chooser.setFiles.bind(chooser);
        chooser.setFiles = (files, options) => setFiles(upload(files), options);
      });
      page.on('download', download => {
        download.saveAs = async target => {
          const deadline = Date.now() + 60000;
          let record;
          while (Date.now() < deadline) {
            record = [...downloads.values()].find(row => !row.claimed && row.url === download.url() && row.suggestedFilename === download.suggestedFilename());
            if (record && record.state === 'completed') break;
            if (record && record.state === 'canceled') throw new Error('Real guest download was canceled');
            await sleep(100);
          }
          assert(record && record.state === 'completed', 'Real Win7 download completion not observed');
          record.claimed = true;
          const copied = await transport.downloadFile(record.guid, target);
          assert.equal(copied.bytes, record.receivedBytes);
          collected.push({ guid: record.guid, filename: record.suggestedFilename, url: record.url, ...copied });
          fs.writeFileSync(path.join(root, 'guest-downloads.json'), JSON.stringify(collected, null, 2));
        };
      });
    });
    return context;
  };
  return browser;
}

module.exports = { channel, connect, quote };
