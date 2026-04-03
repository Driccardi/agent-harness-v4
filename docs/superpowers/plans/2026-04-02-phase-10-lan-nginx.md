# Ordo Phase 10: LAN + Nginx Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `nginx.conf`, wire the PM2 `ordo-nginx` process, verify the Vite build is served on port 80, and confirm LAN devices can reach both the UI and the API. After this phase, any device on the LAN can browse to `http://<ordo-machine-ip>/` and use the full Ordo UI.

**Architecture:**
```
LAN device (browser) → port 80 (Nginx)
  /              → serve frontend/dist/ (Vite build static files)
  /api/*         → proxy_pass http://127.0.0.1:8000
  /ws/*          → proxy_pass http://127.0.0.1:8000/ws/ (WebSocket upgrade)
  /health        → proxy_pass http://127.0.0.1:8000/health
```

**Tech Stack:** Nginx (Windows native via Chocolatey or direct download), Node.js config script, Vite build (`npm run build` → `frontend/dist/`), FastAPI on port 8000, PM2 `ordo-nginx` process.

> **SECURITY NOTE — READ FIRST:** LAN access is **intentionally open with no authentication layer**. This is an explicit design decision for a single-user private home network. Do NOT add auth. Do NOT suggest adding auth. This matches the architecture spec: "LAN API access is intentionally open (no auth layer) — any device on the local network has full agent invocation access."

---

## Chunk 1: Nginx Config + Build Pipeline

### Task 1: Install Nginx (Windows Native)

**Files:**
- No files created — system installation step.

- [ ] **Step 1: Install Nginx via Chocolatey**

```powershell
choco install nginx -y
```

Expected output:
```
Chocolatey installed 1/1 packages.
```

Verify:
```bash
nginx -v
```
Expected: `nginx version: nginx/1.x.x`

If Chocolatey is not available, download the Windows binary from https://nginx.org/en/download.html and extract to `C:\nginx`. Add `C:\nginx` to `PATH`.

- [ ] **Step 2: Confirm nginx is on PATH**

```bash
where nginx
```

Expected: a path such as `C:\ProgramData\chocolatey\bin\nginx.exe` or `C:\nginx\nginx.exe`.

---

### Task 2: nginx.conf Template

**Files:**
- Create: `nginx.conf.template` (project root: `C:/Users/user/AI-Assistant Version 4/nginx.conf.template`)

- [ ] **Step 1: Create `nginx.conf.template`**

Create `C:/Users/user/AI-Assistant Version 4/nginx.conf.template` with the following content:

```nginx
worker_processes 1;
events { worker_connections 1024; }
http {
  include       mime.types;
  default_type  application/octet-stream;
  server {
    listen 80;
    server_name localhost;
    root {{FRONTEND_DIST}};
    index index.html;
    location / { try_files $uri $uri/ /index.html; }
    location /api/ {
      proxy_pass http://127.0.0.1:8000/;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
    }
    location /ws/ {
      proxy_pass http://127.0.0.1:8000/ws/;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
    }
    location /health { proxy_pass http://127.0.0.1:8000/health; }
  }
}
```

Note: `{{FRONTEND_DIST}}` is the placeholder replaced by `nginx-configure.js` at setup time with the absolute forward-slash path to `frontend/dist/`.

- [ ] **Step 2: Commit template**

```bash
git add nginx.conf.template
git commit -m "feat(nginx): add nginx.conf.template with FRONTEND_DIST placeholder"
```

Expected: Clean commit with one file added.

---

### Task 3: nginx-configure.js — Path Injection Script

**Files:**
- Create: `scripts/nginx-configure.js`
- Create: `tests/nginx-configure.test.js`

- [ ] **Step 1: Write failing unit test**

Create `C:/Users/user/AI-Assistant Version 4/tests/nginx-configure.test.js`:

```javascript
// tests/nginx-configure.test.js
// Run with: node --test tests/nginx-configure.test.js  (Node 18+)
// Or: npx jest tests/nginx-configure.test.js

const assert = require('assert');
const path = require('path');
const fs = require('fs');

// We test the core transform function in isolation.
// Extract the replacement logic from the script so it is importable.
const { buildNginxConf } = require('../scripts/nginx-configure');

const TEMPLATE = `
worker_processes 1;
events { worker_connections 1024; }
http {
  server {
    root {{FRONTEND_DIST}};
    index index.html;
  }
}
`.trim();

// Test 1: placeholder is replaced
const distPath = 'C:/Users/user/AI-Assistant Version 4/frontend/dist';
const result = buildNginxConf(TEMPLATE, distPath);
assert.ok(!result.includes('{{FRONTEND_DIST}}'), 'placeholder should be replaced');
assert.ok(result.includes(distPath), 'dist path should appear in output');
console.log('PASS: placeholder replaced');

// Test 2: backslashes are converted to forward slashes
const winPath = 'C:\\Users\\user\\AI-Assistant Version 4\\frontend\\dist';
const result2 = buildNginxConf(TEMPLATE, winPath);
assert.ok(!result2.includes('\\'), 'result should have no backslashes');
assert.ok(result2.includes('C:/Users/user'), 'forward-slash path present');
console.log('PASS: backslashes converted to forward slashes');

// Test 3: all occurrences are replaced (template has exactly one, but verify replace_all)
const doubleTemplate = TEMPLATE + '\n# {{FRONTEND_DIST}}';
const result3 = buildNginxConf(doubleTemplate, distPath);
const occurrences = (result3.match(/\{\{FRONTEND_DIST\}\}/g) || []).length;
assert.strictEqual(occurrences, 0, 'all occurrences should be replaced');
console.log('PASS: all occurrences replaced');

console.log('\nAll nginx-configure tests passed.');
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
node --test tests/nginx-configure.test.js
```

Expected: `Error: Cannot find module '../scripts/nginx-configure'`

- [ ] **Step 3: Create `scripts/nginx-configure.js`**

Create `C:/Users/user/AI-Assistant Version 4/scripts/nginx-configure.js`:

```javascript
// scripts/nginx-configure.js
// Reads nginx.conf.template, injects absolute frontend/dist path,
// writes nginx.conf to project root.
// Run: node scripts/nginx-configure.js

'use strict';

const path = require('path');
const fs = require('fs');

const PROJECT_ROOT = path.resolve(__dirname, '..');

/**
 * Replace {{FRONTEND_DIST}} placeholder in template with the given dist path.
 * Converts all backslashes to forward slashes (required by nginx on Windows).
 * @param {string} template - Contents of nginx.conf.template
 * @param {string} distPath - Absolute path to frontend/dist (may use backslashes)
 * @returns {string} - Rendered nginx.conf content
 */
function buildNginxConf(template, distPath) {
  const normalised = distPath.replace(/\\/g, '/');
  return template.replace(/\{\{FRONTEND_DIST\}\}/g, normalised);
}

function main() {
  const templatePath = path.join(PROJECT_ROOT, 'nginx.conf.template');
  const outputPath = path.join(PROJECT_ROOT, 'nginx.conf');
  const distPath = path.resolve(PROJECT_ROOT, 'frontend', 'dist');

  if (!fs.existsSync(templatePath)) {
    console.error(`ERROR: Template not found at ${templatePath}`);
    process.exit(1);
  }

  const template = fs.readFileSync(templatePath, 'utf8');
  const conf = buildNginxConf(template, distPath);
  fs.writeFileSync(outputPath, conf, 'utf8');

  console.log(`nginx.conf written to: ${outputPath}`);
  console.log(`Frontend dist path: ${distPath.replace(/\\/g, '/')}`);
}

// Allow importing for unit tests without running main
if (require.main === module) {
  main();
}

module.exports = { buildNginxConf };
```

- [ ] **Step 4: Run test — verify it passes**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
node --test tests/nginx-configure.test.js
```

Expected:
```
PASS: placeholder replaced
PASS: backslashes converted to forward slashes
PASS: all occurrences replaced

All nginx-configure tests passed.
```

- [ ] **Step 5: Run the script — verify nginx.conf is generated**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
node scripts/nginx-configure.js
```

Expected output:
```
nginx.conf written to: C:/Users/user/AI-Assistant Version 4/nginx.conf
Frontend dist path: C:/Users/user/AI-Assistant Version 4/frontend/dist
```

Verify `nginx.conf` was created:
```bash
ls "C:/Users/user/AI-Assistant Version 4/nginx.conf"
```

Open the file and confirm `{{FRONTEND_DIST}}` is replaced with the correct absolute path using forward slashes.

- [ ] **Step 6: Add `nginx.conf` to `.gitignore`**

`nginx.conf` is a generated file and must not be committed. Open `C:/Users/user/AI-Assistant Version 4/.gitignore` and confirm (or add) the following line:

```
nginx.conf
```

- [ ] **Step 7: Commit script and test**

```bash
git add scripts/nginx-configure.js tests/nginx-configure.test.js .gitignore
git commit -m "feat(nginx): add nginx-configure.js path injection script with unit tests"
```

Expected: Clean commit with three files.

---

### Task 4: Vite Build Configuration

**Files:**
- Modify: `frontend/vite.config.ts` (verify `base: '/'`)
- Modify: `frontend/package.json` (add `build:prod` script if absent)

- [ ] **Step 1: Verify `base: '/'` in vite.config.ts**

Open `C:/Users/user/AI-Assistant Version 4/frontend/vite.config.ts`. Confirm the config includes:

```typescript
export default defineConfig({
  base: '/',
  // ...
});
```

If `base` is absent or set to a different value, update it to `'/'`.

- [ ] **Step 2: Verify build output directory**

Confirm that `build.outDir` is either absent (defaults to `dist` relative to `frontend/`) or explicitly set to `dist`. The resolved output path must be `frontend/dist/`.

```typescript
build: {
  outDir: 'dist',   // relative to frontend/ — resolves to frontend/dist/
}
```

- [ ] **Step 3: Add `build:prod` script to `frontend/package.json`**

Open `C:/Users/user/AI-Assistant Version 4/frontend/package.json`. If a `build:prod` script is not already present, add it alongside the existing `build` script:

```json
{
  "scripts": {
    "build": "vite build",
    "build:prod": "vite build --mode production"
  }
}
```

- [ ] **Step 4: Run the build — verify output**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npm run build
```

Expected output (last lines):
```
vite v5.x.x building for production...
✓ N modules transformed.
dist/index.html    x.xx kB
dist/assets/...
✓ built in Xs
```

Verify:
```bash
ls "C:/Users/user/AI-Assistant Version 4/frontend/dist/index.html"
```

Expected: file exists.

- [ ] **Step 5: Commit Vite config changes (if any were made)**

If `vite.config.ts` or `package.json` were modified:

```bash
git add frontend/vite.config.ts frontend/package.json
git commit -m "feat(frontend): ensure base:'/' and add build:prod script for LAN serving"
```

---

> **Plan document reviewer dispatch:** After completing Chunk 1, a plan-document-reviewer agent should verify: (1) `nginx.conf.template` exists in project root with the correct template, (2) `scripts/nginx-configure.js` exports `buildNginxConf` and produces a valid `nginx.conf` when run, (3) all unit tests in `tests/nginx-configure.test.js` pass, (4) `frontend/dist/index.html` exists after `npm run build`, (5) `nginx.conf` is listed in `.gitignore`.

---

## Chunk 2: Frontend LAN Config + PM2 Activation + Verification

### Task 5: Frontend API URL Strategy for LAN

**Files:**
- Create: `frontend/src/api/config.ts`

- [ ] **Step 1: Create `frontend/src/api/config.ts`**

This module provides the correct API base URL depending on the runtime context:
- **Electron:** `window.ORDO_API_BASE` is set to `'http://localhost:8000'` by the Electron preload script. The WS base is `window.ORDO_WS_BASE || 'ws://localhost:8000'`.
- **LAN browser via Nginx:** No `window.ORDO_API_BASE` is set. Use empty string `''` so all fetch calls use relative URLs (e.g. `/api/conversation`) which Nginx proxies to port 8000. WebSocket connects to `ws://<nginx-host>/ws/...` which Nginx upgrades and proxies.

Create `C:/Users/user/AI-Assistant Version 4/frontend/src/api/config.ts`:

```typescript
// frontend/src/api/config.ts
// API URL strategy: relative URLs when accessed via Nginx (LAN browser);
// absolute URLs when running inside Electron (preload sets window.ORDO_API_BASE).

declare global {
  interface Window {
    ORDO_API_BASE?: string;
    ORDO_WS_BASE?: string;
  }
}

/**
 * HTTP base URL for all REST API calls.
 * - Electron:      'http://localhost:8000'  (set by preload)
 * - LAN browser:   ''  (empty → relative URLs → Nginx proxies /api/*)
 */
export const API_BASE: string = window.ORDO_API_BASE ?? '';

/**
 * WebSocket base URL.
 * - Electron:      'ws://localhost:8000'  (set by preload)
 * - LAN browser:   ws://<same host as page> (Nginx proxies /ws/*)
 */
export const WS_BASE: string = (() => {
  if (window.ORDO_WS_BASE) return window.ORDO_WS_BASE;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}`;
})();

/**
 * Build a WebSocket URL for a given conversation ID.
 * @param conversationId - UUID of the conversation
 * @returns Full WebSocket URL: ws[s]://<host>/ws/<conversationId>
 */
export function wsUrl(conversationId: string): string {
  return `${WS_BASE}/ws/${conversationId}`;
}

/**
 * Build a full API URL for a given path.
 * @param path - Path starting with /  e.g. '/api/conversation'
 * @returns Full URL or relative URL depending on runtime context
 */
export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}
```

- [ ] **Step 2: Commit frontend API config**

```bash
git add frontend/src/api/config.ts
git commit -m "feat(frontend): add api/config.ts with LAN-aware relative URL strategy"
```

---

### Task 6: FastAPI `GET /lan/info` Route

**Files:**
- Modify: `backend/routers/system.py`

- [ ] **Step 1: Add `/lan/info` endpoint to `backend/routers/system.py`**

Open `C:/Users/user/AI-Assistant Version 4/backend/routers/system.py`. Add the following import and route. If the file does not yet contain the `router` declaration, add the full block; if it already exists, append only the new route.

```python
import socket
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class LanInfo(BaseModel):
    local_ip: str
    port: int
    lan_url: str


@router.get("/lan/info", response_model=LanInfo)
async def get_lan_info() -> LanInfo:
    """Return the machine's LAN IP and the full URL to reach the Ordo UI via Nginx."""
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except OSError:
        local_ip = "127.0.0.1"
    return LanInfo(
        local_ip=local_ip,
        port=8000,
        lan_url=f"http://{local_ip}/",
    )
```

Ensure this router is registered in `backend/main.py`:

```python
from backend.routers import system
app.include_router(system.router)
```

- [ ] **Step 2: Verify route is reachable (requires running FastAPI)**

```bash
curl http://localhost:8000/lan/info
```

Expected (example):
```json
{"local_ip":"192.168.1.42","port":8000,"lan_url":"http://192.168.1.42/"}
```

- [ ] **Step 3: Commit**

```bash
git add backend/routers/system.py backend/main.py
git commit -m "feat(api): add GET /lan/info returning local IP and LAN URL"
```

---

### Task 7: Electron Settings — LAN Access Section

**Files:**
- Modify: `frontend/src/panels/settings.ts`

- [ ] **Step 1: Add LAN Access section to settings panel**

Open `C:/Users/user/AI-Assistant Version 4/frontend/src/panels/settings.ts`. Locate the section rendering function and add a "LAN Access" section. The section should:

1. Call `GET /lan/info` (using `apiUrl('/lan/info')` from `api/config.ts`) on panel open.
2. Display the machine's current IP address and the full LAN URL.
3. Provide a "Copy URL" button that copies the `lan_url` to the clipboard.
4. Include a note that LAN access is intentionally open (no authentication — by design).

Add the following rendering function and call it from the settings panel's main render function, passing the settings container element:

```typescript
import { apiUrl } from '../api/config';

async function renderLanAccessSection(container: HTMLElement): Promise<void> {
  const section = document.createElement('div');
  section.className = 'settings-section';
  section.innerHTML = `
    <h3>LAN Access</h3>
    <p class="settings-note">
      LAN access is <strong>intentionally open with no authentication</strong>.
      This is by design for a single-user private home network.
      Any device on your local network can reach the Ordo UI.
    </p>
    <div class="lan-info-row">
      <span class="label">Machine IP:</span>
      <span id="lan-ip">Loading...</span>
    </div>
    <div class="lan-info-row">
      <span class="label">LAN URL:</span>
      <a id="lan-url" href="#" target="_blank">Loading...</a>
      <button id="lan-copy-btn" class="btn-secondary">Copy URL</button>
    </div>
  `;
  container.appendChild(section);

  try {
    const res = await fetch(apiUrl('/lan/info'));
    const data: { local_ip: string; port: number; lan_url: string } = await res.json();

    const ipEl = section.querySelector<HTMLSpanElement>('#lan-ip');
    const urlEl = section.querySelector<HTMLAnchorElement>('#lan-url');
    const copyBtn = section.querySelector<HTMLButtonElement>('#lan-copy-btn');

    if (ipEl) ipEl.textContent = data.local_ip;
    if (urlEl) {
      urlEl.textContent = data.lan_url;
      urlEl.href = data.lan_url;
    }
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(data.lan_url).then(() => {
          copyBtn.textContent = 'Copied!';
          setTimeout(() => { copyBtn.textContent = 'Copy URL'; }, 2000);
        });
      });
    }
  } catch {
    const ipEl = section.querySelector<HTMLSpanElement>('#lan-ip');
    if (ipEl) ipEl.textContent = 'Unavailable (API not running)';
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/panels/settings.ts
git commit -m "feat(frontend): add LAN Access section to Settings panel with IP display and copy button"
```

---

### Task 8: PM2 Nginx Process Activation

**Files:**
- Modify: `ecosystem.config.js` (project root)

- [ ] **Step 1: Determine the absolute nginx executable path**

```bash
where nginx
```

Note the full path. Common locations:
- Chocolatey install: `C:\ProgramData\chocolatey\bin\nginx.exe`
- Manual install: `C:\nginx\nginx.exe`

- [ ] **Step 2: Update `ecosystem.config.js` — activate `ordo-nginx`**

Open `C:/Users/user/AI-Assistant Version 4/ecosystem.config.js`. Find the stub `ordo-nginx` entry which currently has a "Do not start until nginx.conf exists" comment. Replace it entirely with the following working configuration:

```javascript
{
  name: 'ordo-nginx',
  script: 'C:\\ProgramData\\chocolatey\\bin\\nginx.exe',
  // Replace the script path above with the output of `where nginx` on your machine.
  // Example for manual install: 'C:\\nginx\\nginx.exe'
  args: `-c "C:/Users/user/AI-Assistant Version 4/nginx.conf"`,
  cwd: 'C:/Users/user/AI-Assistant Version 4',
  interpreter: 'none',
  autorestart: true,
  watch: false,
  env: {
    NODE_ENV: 'production',
  },
},
```

Remove the "Do not start until nginx.conf exists in the project root" warning comment entirely.

Note: The `nginx.conf` path in `args` uses forward slashes. This is required because nginx on Windows parses this path itself.

- [ ] **Step 3: Generate nginx.conf (prerequisite)**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
node scripts/nginx-configure.js
```

Expected:
```
nginx.conf written to: C:/Users/user/AI-Assistant Version 4/nginx.conf
Frontend dist path: C:/Users/user/AI-Assistant Version 4/frontend/dist
```

- [ ] **Step 4: Start the nginx PM2 process**

```bash
pm2 start ecosystem.config.js --only ordo-nginx
```

Expected output:
```
[PM2] Starting ... in fork_mode
[PM2] Done.
┌────┬──────────────┬─────────────┬─────────┬─────────┬──────────┬────────┬──────┬───────────┐
│ id │ name         │ namespace   │ version │ mode    │ pid      │ uptime │ ↺    │ status    │
├────┼──────────────┼─────────────┼─────────┼─────────┼──────────┼────────┼──────┼───────────┤
│  N │ ordo-nginx   │ default     │ N/A     │ fork    │ XXXXX    │ 0s     │ 0    │ online    │
└────┴──────────────┴─────────────┴─────────┴─────────┴──────────┴────────┴──────┴───────────┘
```

- [ ] **Step 5: Verify PM2 status shows `ordo-nginx` online**

```bash
pm2 status
```

Expected: `ordo-nginx` row shows `status: online`.

If status is `errored`, check logs:
```bash
pm2 logs ordo-nginx --lines 50
```

Common issues and fixes:
- Nginx executable path incorrect — re-run `where nginx` and update `ecosystem.config.js`
- Port 80 already in use — run `netstat -ano | findstr :80` and stop the conflicting process
- `nginx.conf` path incorrect or file missing — re-run `node scripts/nginx-configure.js`
- `frontend/dist/` does not exist — run `npm run build` in `frontend/`

- [ ] **Step 6: Save PM2 process list**

```bash
pm2 save
```

Expected: `[PM2] Saving current process list...`

- [ ] **Step 7: Commit ecosystem.config.js**

```bash
git add ecosystem.config.js
git commit -m "feat(pm2): activate ordo-nginx process with nginx.conf path — LAN access enabled"
```

---

### Task 9: End-to-End Verification

These are manual smoke tests. All must pass before Phase 10 is considered complete.

- [ ] **Step 1: Confirm nginx.conf was generated with correct path**

```bash
node scripts/nginx-configure.js
```

Open `C:/Users/user/AI-Assistant Version 4/nginx.conf` and verify:
- No `{{FRONTEND_DIST}}` placeholder remains
- The `root` directive contains the absolute forward-slash path to `frontend/dist/`

Example expected line:
```nginx
root C:/Users/user/AI-Assistant Version 4/frontend/dist;
```

- [ ] **Step 2: Confirm Vite build output exists**

```bash
ls "C:/Users/user/AI-Assistant Version 4/frontend/dist/index.html"
```

If missing, run:
```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npm run build
```

Then restart nginx:
```bash
pm2 restart ordo-nginx
```

- [ ] **Step 3: Verify health endpoint via Nginx**

Requires FastAPI (`ordo-fastapi`) and Nginx (`ordo-nginx`) both online.

```bash
curl http://localhost/health
```

Expected:
```json
{"status":"ok"}
```

HTTP status must be `200`.

- [ ] **Step 4: Verify static UI is served**

```bash
curl -s http://localhost/ | head -5
```

Expected: HTML output beginning with `<!DOCTYPE html>` or `<html`.

Full status check:
```bash
curl -o /dev/null -s -w "%{http_code}" http://localhost/
```

Expected: `200`

- [ ] **Step 5: Verify SPA routing (non-root path returns index.html)**

```bash
curl -o /dev/null -s -w "%{http_code}" http://localhost/some/deep/route
```

Expected: `200` (Nginx `try_files` falls back to `index.html` for unknown paths, enabling client-side routing).

- [ ] **Step 6: Verify API proxy**

```bash
curl http://localhost/api/health
```

Expected: FastAPI response (e.g. `{"status":"ok"}`).

Note: `/api/` strips the prefix when proxying — the request arrives at FastAPI as `GET /health`. Confirm this FastAPI route exists and responds.

- [ ] **Step 7: Verify LAN info endpoint via Nginx**

```bash
curl http://localhost/api/lan/info
```

Expected (example):
```json
{"local_ip":"192.168.1.42","port":8000,"lan_url":"http://192.168.1.42/"}
```

- [ ] **Step 8: Verify from a LAN device**

From a separate device on the same network (phone, laptop, tablet):

1. Note the `local_ip` value from the previous step (e.g. `192.168.1.42`).
2. Open a browser and navigate to `http://192.168.1.42/`.

Expected: The Ordo UI loads fully in the browser.

3. Optional curl verification from a LAN device terminal:

```bash
curl http://192.168.1.42/health
```

Expected: `{"status":"ok"}` with HTTP `200`.

```bash
curl http://192.168.1.42/api/lan/info
```

Expected: JSON with the machine's IP and LAN URL.

- [ ] **Step 9: Final commit — mark Phase 10 complete**

```bash
git add nginx.conf.template scripts/nginx-configure.js tests/nginx-configure.test.js \
        frontend/src/api/config.ts frontend/src/panels/settings.ts \
        backend/routers/system.py backend/main.py \
        frontend/vite.config.ts frontend/package.json \
        ecosystem.config.js .gitignore
git commit -m "feat: Phase 10 complete — LAN + Nginx serving Ordo UI on port 80"
```

---

> **Plan document reviewer dispatch:** After completing Chunk 2, a plan-document-reviewer agent should verify: (1) `ecosystem.config.js` `ordo-nginx` entry is active with correct executable path and no "do not start" comment, (2) `pm2 status` shows `ordo-nginx` online, (3) `curl http://localhost/health` returns `{"status":"ok"}`, (4) `curl http://localhost/` returns HTML, (5) `frontend/src/api/config.ts` exports `API_BASE`, `WS_BASE`, `wsUrl`, and `apiUrl`, (6) `GET /lan/info` returns valid JSON with `local_ip` and `lan_url`, (7) the Settings panel renders a "LAN Access" section with no authentication prompt.
