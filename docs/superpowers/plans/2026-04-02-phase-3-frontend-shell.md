# Ordo Phase 3: Frontend Shell Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Electron desktop application shell — main window layout, sidebar, conversation panel, WebSocket streaming connection to FastAPI, and PTT button stub — so that after this phase you can open the app, see a sidebar with a "Main" conversation, type a message, hit `POST /agents/generalist/invoke`, and watch the response stream back in real time.

**Architecture:** Electron (native Windows desktop) wraps a Vite + TypeScript compiled frontend. The Electron main process creates a `BrowserWindow`, loads the Vite dev server in development or the compiled `dist/` in production, and exposes an IPC bridge via a preload script. No React/Vue — plain TypeScript DOM manipulation with `marked` for markdown rendering. The Vite build is kept in `frontend/` and is cleanly separated from the Python `backend/`. All API communication targets `localhost:8000` (FastAPI, Phase 1 + 2). WebSocket connects to `ws://localhost:8000/ws/{conversation_id}` for streaming token delivery.

**Tech Stack:** Electron 30+, Vite 5+, TypeScript 5+ (strict), `marked` (markdown rendering), `electron-builder` (packaging stub), Vitest (frontend unit tests), Node 20 LTS

**Phase Dependencies:** Phase 1 (FastAPI skeleton, `/health` endpoint, port 8000), Phase 2 (`POST /agents/generalist/invoke`, WebSocket `ws://localhost:8000/ws/{id}`, `GET/POST /conversations`, `GET /conversations/{id}/messages`, `POST /conversations/{id}/messages`)

---

## Chunk 1: Electron + Vite Scaffold

### Task 1: Frontend Directory and Package Configuration

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/.gitignore`

- [ ] **Step 1: Create the `frontend/` directory tree**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
mkdir -p frontend/src/api frontend/src/components frontend/src/styles frontend/electron frontend/assets
```

Expected: Directories created with no errors.

- [ ] **Step 2: Create `frontend/package.json`**

```json
{
  "name": "ordo-v4",
  "version": "4.0.0",
  "description": "Ordo V4 — Cognitive Memory-Augmented Assistant",
  "main": "electron/main.js",
  "scripts": {
    "dev": "concurrently \"vite\" \"wait-on http://localhost:5173 && electron .\"",
    "dev:vite": "vite",
    "dev:electron": "electron .",
    "build": "vite build && tsc -p tsconfig.node.json",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "marked": "^12.0.0"
  },
  "devDependencies": {
    "@types/marked": "^6.0.0",
    "@types/node": "^20.0.0",
    "concurrently": "^8.2.0",
    "electron": "^30.0.0",
    "electron-builder": "^24.13.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vite-plugin-electron": "^0.28.0",
    "vitest": "^1.5.0",
    "wait-on": "^7.2.0"
  },
  "build": {
    "appId": "com.ordo.v4",
    "productName": "Ordo",
    "directories": {
      "output": "dist-electron"
    },
    "win": {
      "target": "nsis"
    }
  }
}
```

- [ ] **Step 3: Create `frontend/tsconfig.json`** (renderer process — strict mode)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `frontend/tsconfig.node.json`** (Electron main process compilation)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022"],
    "module": "CommonJS",
    "moduleResolution": "node",
    "outDir": ".",
    "rootDir": ".",
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "resolveJsonModule": true
  },
  "include": ["electron"]
}
```

- [ ] **Step 5: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";

export default defineConfig({
  root: "src",
  publicDir: "../assets",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: "src/index.html",
        conversation: "src/conversation.html",
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
```

- [ ] **Step 6: Create `frontend/.gitignore`**

```
node_modules/
dist/
dist-electron/
.vite/
```

- [ ] **Step 7: Install dependencies**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npm install
```

Expected output: `node_modules/` created. No peer-dependency errors. Verify:
```bash
npx tsc --version
npx vite --version
```
Expected: TypeScript 5.x and Vite 5.x version strings printed.

- [ ] **Step 8: Commit scaffold**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/package.json frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/.gitignore
git commit -m "chore(frontend): initialize Electron + Vite + TypeScript scaffold"
```

Expected: Clean commit. `node_modules/` not included.

---

### Task 2: Electron Main Process and Preload Script

**Files:**
- Create: `frontend/electron/main.ts`
- Create: `frontend/electron/preload.ts`

- [ ] **Step 1: Create `frontend/electron/main.ts`**

```typescript
import { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } from "electron";
import * as path from "path";

const isDev = process.env.NODE_ENV === "development";
const VITE_DEV_URL = "http://localhost:5173";
const DIST_DIR = path.join(__dirname, "../dist");

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;

function createMainWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: "#0f0f11",
    titleBarStyle: "hidden",
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    show: false,
  });

  if (isDev) {
    win.loadURL(VITE_DEV_URL);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(path.join(DIST_DIR, "index.html"));
  }

  win.once("ready-to-show", () => {
    win.show();
  });

  win.on("closed", () => {
    mainWindow = null;
  });

  return win;
}

function createConversationWindow(conversationId: string): BrowserWindow {
  const win = new BrowserWindow({
    width: 800,
    height: 700,
    minWidth: 600,
    minHeight: 400,
    backgroundColor: "#0f0f11",
    titleBarStyle: "hidden",
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    show: false,
  });

  const params = new URLSearchParams({ conversation_id: conversationId });

  if (isDev) {
    win.loadURL(`${VITE_DEV_URL}/conversation.html?${params.toString()}`);
  } else {
    win.loadFile(path.join(DIST_DIR, "conversation.html"), {
      query: { conversation_id: conversationId },
    });
  }

  win.once("ready-to-show", () => {
    win.show();
  });

  return win;
}

function createTray(): void {
  // Use a blank 16x16 icon as placeholder — replace with real icon in Phase 8
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Show Ordo",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        } else {
          mainWindow = createMainWindow();
        }
      },
    },
    {
      label: "Hide",
      click: () => {
        mainWindow?.hide();
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        app.quit();
      },
    },
  ]);

  tray.setToolTip("Ordo v4.0");
  tray.setContextMenu(contextMenu);

  tray.on("double-click", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// IPC: open conversation in a new detached window
ipcMain.handle("open-conversation-window", (_event, conversationId: string) => {
  createConversationWindow(conversationId);
});

// IPC: window controls (custom titlebar)
ipcMain.on("window-minimize", () => mainWindow?.minimize());
ipcMain.on("window-maximize", () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});
ipcMain.on("window-close", () => mainWindow?.hide());

app.whenReady().then(() => {
  mainWindow = createMainWindow();
  createTray();
});

app.on("window-all-closed", () => {
  // Keep app running in system tray on Windows
  if (process.platform !== "darwin") {
    // do not quit — tray keeps it alive
  }
});

app.on("activate", () => {
  if (mainWindow === null) {
    mainWindow = createMainWindow();
  }
});
```

- [ ] **Step 2: Create `frontend/electron/preload.ts`**

```typescript
import { contextBridge, ipcRenderer } from "electron";

// Expose a safe, typed API surface to the renderer
contextBridge.exposeInMainWorld("ordo", {
  // Window controls
  minimize: () => ipcRenderer.send("window-minimize"),
  maximize: () => ipcRenderer.send("window-maximize"),
  close: () => ipcRenderer.send("window-close"),

  // Open a conversation in a detached window
  openConversationWindow: (conversationId: string) =>
    ipcRenderer.invoke("open-conversation-window", conversationId),

  // Platform info
  platform: process.platform,
});
```

- [ ] **Step 3: Compile Electron TypeScript to verify no errors**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx tsc -p tsconfig.node.json --noEmit
```

Expected: No output (zero errors).

- [ ] **Step 4: Commit Electron main process**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/electron/main.ts frontend/electron/preload.ts
git commit -m "feat(frontend): add Electron main process and preload IPC bridge"
```

---

### Task 3: Global Type Declarations

**Files:**
- Create: `frontend/src/types/global.d.ts`
- Create: `frontend/src/types/api.ts`

- [ ] **Step 1: Create `frontend/src/types/global.d.ts`** — type the `window.ordo` surface exposed by preload

```typescript
// Types for the IPC bridge exposed by preload.ts via contextBridge
interface OrdoAPI {
  minimize: () => void;
  maximize: () => void;
  close: () => void;
  openConversationWindow: (conversationId: string) => Promise<void>;
  platform: string;
}

declare interface Window {
  ordo: OrdoAPI;
}
```

- [ ] **Step 2: Create `frontend/src/types/api.ts`** — shared data model types

```typescript
export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "human" | "assistant" | "system";
  content: string;
  created_at: string;
}

export interface AgentInvokeRequest {
  conversation_id: string;
  message: string;
  stream?: boolean;
}

export interface AgentInvokeResponse {
  conversation_id: string;
  message_id: string;
  content: string;
}

export interface HealthResponse {
  status: string;
  sidecars: Record<string, boolean>;
  memory: boolean;
  api: boolean;
}

export interface HeartbeatNextResponse {
  next_heartbeat_iso: string;
  seconds_until: number;
}

// WebSocket message types received from FastAPI
export type WsMessage =
  | { type: "token"; content: string }
  | { type: "done"; message_id: string }
  | { type: "error"; detail: string }
  | { type: "ping" };
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit types**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/src/types/global.d.ts frontend/src/types/api.ts
git commit -m "feat(frontend): add global type declarations and API data models"
```

---

> **Plan document reviewer dispatch:** At the end of Chunk 1, a plan-document-reviewer agent should verify: (1) `frontend/package.json` lists all required dependencies with pinned major versions, (2) `electron/main.ts` compiles with `tsc -p tsconfig.node.json --noEmit` with zero errors, (3) `electron/preload.ts` uses `contextBridge` and never exposes raw `ipcRenderer`, (4) `src/types/global.d.ts` declares `Window.ordo` matching the preload surface exactly, (5) `.gitignore` prevents `node_modules/` and `dist/` from being committed.

---

## Chunk 2: Main Window Layout, Sidebar, and Conversation Panel

### Task 4: HTML Entry Points and Base CSS

**Files:**
- Create: `frontend/src/index.html`
- Create: `frontend/src/conversation.html`
- Create: `frontend/src/styles/reset.css`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/layout.css`

- [ ] **Step 1: Create `frontend/src/styles/reset.css`**

```css
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  height: 100%;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

button {
  background: none;
  border: none;
  cursor: pointer;
  font: inherit;
  color: inherit;
}

input, textarea {
  font: inherit;
  background: none;
  border: none;
  outline: none;
  color: inherit;
}

ul, ol {
  list-style: none;
}

a {
  color: inherit;
  text-decoration: none;
}
```

- [ ] **Step 2: Create `frontend/src/styles/tokens.css`**

```css
:root {
  /* Colors */
  --bg-base:        #0f0f11;
  --bg-sidebar:     #15151a;
  --bg-surface:     #1c1c24;
  --bg-hover:       #25252f;
  --bg-active:      #2d2d3a;
  --bg-input:       #1a1a22;

  --border-subtle:  #2a2a36;
  --border-strong:  #3a3a4a;

  --text-primary:   #e8e8f0;
  --text-secondary: #9090a8;
  --text-muted:     #5a5a70;
  --text-accent:    #8b7cf6;

  --accent-purple:  #8b7cf6;
  --accent-teal:    #4ecdc4;
  --accent-red:     #ff6b6b;
  --accent-amber:   #ffd93d;
  --accent-green:   #6bcb77;

  /* Status dot colors */
  --dot-ok:         #6bcb77;
  --dot-warn:       #ffd93d;
  --dot-err:        #ff6b6b;
  --dot-off:        #5a5a70;

  /* Typography */
  --font-sans: "Segoe UI", system-ui, -apple-system, sans-serif;
  --font-mono: "Cascadia Code", "Consolas", monospace;
  --font-size-xs:   11px;
  --font-size-sm:   13px;
  --font-size-base: 14px;
  --font-size-md:   15px;
  --font-size-lg:   18px;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;

  /* Layout */
  --sidebar-width:  220px;
  --statusbar-h:    28px;
  --inputbar-h:     60px;
  --titlebar-h:     32px;

  /* Animation */
  --transition-fast: 120ms ease;
  --transition-med:  220ms ease;

  /* Border radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
```

- [ ] **Step 3: Create `frontend/src/styles/layout.css`**

```css
@import "./reset.css";
@import "./tokens.css";

/* ── Root shell ── */
body {
  font-family: var(--font-sans);
  font-size: var(--font-size-base);
  color: var(--text-primary);
  background: var(--bg-base);
  display: flex;
  flex-direction: column;
  height: 100vh;
  user-select: none;
}

/* ── Custom titlebar (replaces native) ── */
#titlebar {
  height: var(--titlebar-h);
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-3);
  -webkit-app-region: drag;
  flex-shrink: 0;
}

#titlebar .title {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

#titlebar .window-controls {
  display: flex;
  gap: var(--space-2);
  -webkit-app-region: no-drag;
}

#titlebar .window-controls button {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--dot-off);
  transition: background var(--transition-fast);
}

#titlebar .window-controls button:hover { background: var(--text-secondary); }
#titlebar .window-controls .btn-close:hover  { background: var(--accent-red); }
#titlebar .window-controls .btn-min:hover    { background: var(--accent-amber); }
#titlebar .window-controls .btn-max:hover    { background: var(--accent-green); }

/* ── Main body (sidebar + content) ── */
#app-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

/* ── Sidebar ── */
#sidebar {
  width: var(--sidebar-width);
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}

.sidebar-section {
  padding: var(--space-3) var(--space-3) var(--space-2);
}

.sidebar-section-label {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: var(--space-2);
  font-weight: 600;
}

.sidebar-section-divider {
  border: none;
  border-top: 1px solid var(--border-subtle);
  margin: 0;
}

/* Conversation list */
#conversation-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  transition: background var(--transition-fast), color var(--transition-fast);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  position: relative;
}

.conversation-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.conversation-item.active {
  background: var(--bg-active);
  color: var(--text-primary);
}

.conversation-item .conv-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--dot-off);
  flex-shrink: 0;
}

.conversation-item.active .conv-dot {
  background: var(--accent-purple);
}

.conversation-item .conv-title {
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.conversation-item .conv-new-window {
  opacity: 0;
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  transition: opacity var(--transition-fast);
  flex-shrink: 0;
}

.conversation-item:hover .conv-new-window {
  opacity: 1;
}

/* + new button */
.sidebar-add-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: color var(--transition-fast);
  border-radius: var(--radius-sm);
}

.sidebar-add-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

/* Task list (stub) */
#task-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  overflow-y: auto;
}

.task-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--transition-fast);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-item:hover {
  background: var(--bg-hover);
}

.task-item .task-icon {
  font-size: var(--font-size-xs);
  flex-shrink: 0;
}

/* Sidebar footer buttons */
#sidebar-footer {
  border-top: 1px solid var(--border-subtle);
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-footer-btn {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.sidebar-footer-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* ── Main panel ── */
#main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

/* ── Conversation view ── */
#conversation-view {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  scroll-behavior: smooth;
}

#conversation-view::-webkit-scrollbar { width: 6px; }
#conversation-view::-webkit-scrollbar-track { background: transparent; }
#conversation-view::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 3px;
}

/* Message bubbles */
.message {
  display: flex;
  flex-direction: column;
  max-width: 820px;
  gap: var(--space-1);
}

.message.human {
  align-self: flex-end;
  align-items: flex-end;
}

.message.assistant {
  align-self: flex-start;
  align-items: flex-start;
}

.message .msg-role {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0 var(--space-1);
}

.message .msg-bubble {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  line-height: 1.65;
  max-width: 100%;
}

.message.human .msg-bubble {
  background: var(--bg-active);
  border: 1px solid var(--border-strong);
  border-bottom-right-radius: var(--radius-sm);
}

.message.assistant .msg-bubble {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-bottom-left-radius: var(--radius-sm);
}

/* Markdown within assistant bubbles */
.message.assistant .msg-bubble h1,
.message.assistant .msg-bubble h2,
.message.assistant .msg-bubble h3 {
  margin: var(--space-3) 0 var(--space-2);
  color: var(--text-primary);
}
.message.assistant .msg-bubble p { margin-bottom: var(--space-3); }
.message.assistant .msg-bubble p:last-child { margin-bottom: 0; }
.message.assistant .msg-bubble code {
  font-family: var(--font-mono);
  font-size: 0.875em;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 1px 5px;
}
.message.assistant .msg-bubble pre {
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  overflow-x: auto;
  margin: var(--space-3) 0;
}
.message.assistant .msg-bubble pre code {
  background: none;
  border: none;
  padding: 0;
  font-size: var(--font-size-sm);
}
.message.assistant .msg-bubble ul,
.message.assistant .msg-bubble ol {
  list-style: disc;
  padding-left: var(--space-5);
  margin-bottom: var(--space-3);
}
.message.assistant .msg-bubble ol { list-style: decimal; }
.message.assistant .msg-bubble li { margin-bottom: var(--space-1); }
.message.assistant .msg-bubble a {
  color: var(--accent-purple);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.message.assistant .msg-bubble blockquote {
  border-left: 3px solid var(--accent-purple);
  padding-left: var(--space-4);
  color: var(--text-secondary);
  margin: var(--space-3) 0;
}

/* Streaming cursor */
.streaming-cursor::after {
  content: "▋";
  color: var(--accent-purple);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}

/* ── Input bar ── */
#input-bar {
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-base);
  padding: var(--space-3) var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
  min-height: var(--inputbar-h);
}

#ptt-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-surface);
  border: 1px solid var(--border-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  cursor: pointer;
  flex-shrink: 0;
  transition: background var(--transition-fast), border-color var(--transition-fast);
  color: var(--text-secondary);
}

#ptt-btn:hover {
  background: var(--bg-hover);
  border-color: var(--accent-purple);
  color: var(--text-primary);
}

#ptt-btn[aria-pressed="true"] {
  background: var(--accent-purple);
  border-color: var(--accent-purple);
  color: #fff;
}

#message-input {
  flex: 1;
  background: var(--bg-input);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-4);
  font-size: var(--font-size-md);
  color: var(--text-primary);
  resize: none;
  min-height: 36px;
  max-height: 160px;
  overflow-y: auto;
  line-height: 1.5;
  transition: border-color var(--transition-fast);
}

#message-input:focus {
  border-color: var(--border-strong);
}

#message-input::placeholder {
  color: var(--text-muted);
}

#send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--accent-purple);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  cursor: pointer;
  flex-shrink: 0;
  transition: background var(--transition-fast), opacity var(--transition-fast);
  color: #fff;
  border: none;
}

#send-btn:hover { background: #7a6be0; }
#send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Status bar ── */
#statusbar {
  height: var(--statusbar-h);
  background: var(--bg-sidebar);
  border-top: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--space-4);
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  flex-shrink: 0;
  white-space: nowrap;
  overflow: hidden;
}

#statusbar .status-brand {
  color: var(--text-secondary);
  font-weight: 600;
}

#statusbar .status-sep { color: var(--border-strong); }

#statusbar .status-heartbeat { display: flex; align-items: center; gap: var(--space-1); }

#statusbar .status-sidecars { display: flex; align-items: center; gap: var(--space-1); }

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  background: var(--dot-off);
}
.status-dot.ok  { background: var(--dot-ok); }
.status-dot.err { background: var(--dot-err); }
.status-dot.warn { background: var(--dot-warn); }

#statusbar .status-phoenix {
  margin-left: auto;
  cursor: pointer;
  color: var(--text-muted);
  transition: color var(--transition-fast);
}
#statusbar .status-phoenix:hover { color: var(--accent-teal); }

/* ── Stub overlay panels ── */
.panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  z-index: 100;
  display: none;
  align-items: center;
  justify-content: center;
}

.panel-overlay.open { display: flex; }

.panel-modal {
  background: var(--bg-surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  min-width: 400px;
  max-width: 600px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.panel-modal h2 {
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}

.panel-modal .panel-stub-note {
  color: var(--text-muted);
  font-size: var(--font-size-sm);
}

.panel-modal .panel-close-btn {
  align-self: flex-end;
  padding: var(--space-2) var(--space-4);
  background: var(--bg-active);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.panel-modal .panel-close-btn:hover { background: var(--bg-hover); }

/* Slide-in panel (Quick Actions) */
.slide-panel {
  position: fixed;
  top: var(--titlebar-h);
  right: 0;
  bottom: var(--statusbar-h);
  width: 340px;
  background: var(--bg-surface);
  border-left: 1px solid var(--border-strong);
  transform: translateX(100%);
  transition: transform var(--transition-med);
  z-index: 50;
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  gap: var(--space-3);
}

.slide-panel.open { transform: translateX(0); }

.slide-panel h3 {
  font-size: var(--font-size-md);
  color: var(--text-primary);
}

.slide-panel .panel-stub-note {
  color: var(--text-muted);
  font-size: var(--font-size-sm);
}
```

- [ ] **Step 4: Create `frontend/src/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src http://localhost:8000 ws://localhost:8000" />
  <title>Ordo</title>
  <link rel="stylesheet" href="./styles/layout.css" />
</head>
<body>
  <!-- Custom titlebar -->
  <div id="titlebar">
    <span class="title">Ordo</span>
    <div class="window-controls">
      <button class="btn-close"  title="Close"    aria-label="Close window"></button>
      <button class="btn-min"    title="Minimize" aria-label="Minimize window"></button>
      <button class="btn-max"    title="Maximize" aria-label="Maximize window"></button>
    </div>
  </div>

  <!-- Main body -->
  <div id="app-body">
    <!-- Sidebar -->
    <nav id="sidebar" aria-label="Navigation">
      <div class="sidebar-section">
        <div class="sidebar-section-label">Conversations</div>
        <ul id="conversation-list" aria-label="Conversations"></ul>
        <button class="sidebar-add-btn" id="new-conversation-btn" aria-label="New conversation">
          + new
        </button>
      </div>
      <hr class="sidebar-section-divider" />
      <div class="sidebar-section" style="flex:1; display:flex; flex-direction:column; min-height:0;">
        <div class="sidebar-section-label">Tasks</div>
        <ul id="task-list" aria-label="Tasks">
          <li class="task-item">
            <span class="task-icon">▶</span>
            <span>No active tasks</span>
          </li>
        </ul>
      </div>
      <div id="sidebar-footer">
        <button class="sidebar-footer-btn" id="quick-actions-btn" aria-label="Quick actions">
          ⚡ Quick Actions
        </button>
        <button class="sidebar-footer-btn" id="settings-btn" aria-label="Settings">
          ⚙ Settings
        </button>
      </div>
    </nav>

    <!-- Main panel -->
    <main id="main-panel">
      <div id="conversation-view" role="log" aria-live="polite" aria-label="Conversation">
        <!-- Messages rendered here by main.ts -->
      </div>
      <div id="input-bar">
        <button id="ptt-btn" aria-label="Push to talk (Phase 7)" aria-pressed="false" title="Push to talk — available in Phase 7">
          🎙
        </button>
        <textarea
          id="message-input"
          placeholder="Type or push to talk..."
          rows="1"
          aria-label="Message input"
        ></textarea>
        <button id="send-btn" aria-label="Send message" disabled>➤</button>
      </div>
    </main>
  </div>

  <!-- Status bar -->
  <footer id="statusbar" aria-label="Status">
    <span class="status-brand">Ordo v4.0</span>
    <span class="status-sep">·</span>
    <span class="status-heartbeat" title="Next heartbeat">
      ♡ <span id="heartbeat-countdown">--</span>
    </span>
    <span class="status-sep">·</span>
    <span class="status-sidecars" title="Sidecar health">
      <span class="status-dot" id="sidecar-dot"></span>
      <span id="sidecar-label">sidecars</span>
    </span>
    <span class="status-sep">·</span>
    <span class="status-dot" id="mem-dot" title="Memory core"></span>mem
    <span class="status-sep">·</span>
    <span class="status-dot" id="api-dot" title="API"></span>api
    <button class="status-phoenix" id="phoenix-link" title="Open Phoenix observability (port 6006)">
      ◈ Phoenix
    </button>
  </footer>

  <!-- Quick Actions slide-in panel (stub) -->
  <aside id="quick-actions-panel" class="slide-panel" aria-label="Quick Actions" aria-hidden="true">
    <h3>⚡ Quick Actions</h3>
    <p class="panel-stub-note">Quick Actions will be implemented in Phase 8.</p>
  </aside>

  <!-- Settings modal (stub) -->
  <div id="settings-overlay" class="panel-overlay" role="dialog" aria-label="Settings" aria-hidden="true">
    <div class="panel-modal">
      <h2>⚙ Settings</h2>
      <p class="panel-stub-note">Settings will be implemented in Phase 8.</p>
      <button class="panel-close-btn" id="settings-close-btn">Close</button>
    </div>
  </div>

  <script type="module" src="./main.ts"></script>
</body>
</html>
```

- [ ] **Step 5: Create `frontend/src/conversation.html`** — detached conversation window

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src http://localhost:8000 ws://localhost:8000" />
  <title>Ordo — Conversation</title>
  <link rel="stylesheet" href="./styles/layout.css" />
  <style>
    /* Detached window uses full viewport as a single conversation panel */
    body {
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    #titlebar .title { font-size: 12px; }
    #app-body { display: flex; flex: 1; min-height: 0; }
    #main-panel { flex: 1; display: flex; flex-direction: column; min-height: 0; }
  </style>
</head>
<body>
  <div id="titlebar">
    <span class="title" id="window-conv-title">Conversation</span>
    <div class="window-controls">
      <button class="btn-close"  aria-label="Close"></button>
      <button class="btn-min"    aria-label="Minimize"></button>
      <button class="btn-max"    aria-label="Maximize"></button>
    </div>
  </div>

  <div id="app-body">
    <main id="main-panel">
      <div id="conversation-view" role="log" aria-live="polite"></div>
      <div id="input-bar">
        <button id="ptt-btn" aria-label="Push to talk" aria-pressed="false" title="Phase 7">🎙</button>
        <textarea id="message-input" placeholder="Type or push to talk..." rows="1"></textarea>
        <button id="send-btn" disabled>➤</button>
      </div>
    </main>
  </div>

  <footer id="statusbar">
    <span class="status-brand">Ordo v4.0</span>
    <span class="status-sep">·</span>
    <span class="status-dot" id="api-dot"></span>api
  </footer>

  <script type="module" src="./conversation.ts"></script>
</body>
</html>
```

- [ ] **Step 6: Run Vite build to verify HTML + CSS parse without error**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vite build 2>&1 | tail -20
```

Expected: Build completes with `dist/` output, no errors. (TypeScript errors in `.ts` files are acceptable at this step since they are not yet created — Vite only processes HTML/CSS here if `.ts` entrypoints are missing, or you may need to create stub entrypoints first per Step 7.)

- [ ] **Step 7: Create stub entrypoints so Vite build completes cleanly**

Create `frontend/src/main.ts` (temporary stub — will be replaced in Chunk 3):
```typescript
// Stub — full implementation in Chunk 3 Task 7
console.log("Ordo frontend loaded");
```

Create `frontend/src/conversation.ts` (temporary stub):
```typescript
// Stub — full implementation in Chunk 3 Task 8
console.log("Conversation window loaded");
```

Re-run build:
```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vite build 2>&1 | tail -10
```

Expected: `✓ built in Xms` with no errors.

- [ ] **Step 8: Commit layout**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/src/index.html frontend/src/conversation.html frontend/src/styles/reset.css frontend/src/styles/tokens.css frontend/src/styles/layout.css frontend/src/main.ts frontend/src/conversation.ts
git commit -m "feat(frontend): add main window and conversation window HTML/CSS layout"
```

---

### Task 5: Status Bar Component

**Files:**
- Create: `frontend/src/components/statusbar.ts`
- Create: `frontend/src/tests/statusbar.test.ts`

- [ ] **Step 1: Write failing Vitest tests**

Create `frontend/src/tests/statusbar.test.ts`:
```typescript
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

// We test the pure formatting helpers, not the DOM-manipulation functions
// which require a full Electron environment

describe("formatCountdown", () => {
  // Import after setting up the module
  let formatCountdown: (seconds: number) => string;

  beforeEach(async () => {
    const mod = await import("../components/statusbar");
    formatCountdown = mod.formatCountdown;
  });

  it("formats seconds under a minute as '<Xs'", () => {
    expect(formatCountdown(45)).toBe("45s");
  });

  it("formats exactly 60 seconds as '1m'", () => {
    expect(formatCountdown(60)).toBe("1m");
  });

  it("formats minutes correctly", () => {
    expect(formatCountdown(125)).toBe("2m 5s");
  });

  it("formats zero as '0s'", () => {
    expect(formatCountdown(0)).toBe("0s");
  });

  it("formats negative as '0s'", () => {
    expect(formatCountdown(-5)).toBe("0s");
  });
});

describe("buildSidecarLabel", () => {
  let buildSidecarLabel: (sidecars: Record<string, boolean>) => string;

  beforeEach(async () => {
    const mod = await import("../components/statusbar");
    buildSidecarLabel = mod.buildSidecarLabel;
  });

  it("returns 'X/Y sidecars' count", () => {
    const sidecars = { engram: true, eidos: true, anamnesis: false };
    expect(buildSidecarLabel(sidecars)).toBe("2/3 sidecars");
  });

  it("handles all healthy", () => {
    const sidecars = { a: true, b: true };
    expect(buildSidecarLabel(sidecars)).toBe("2/2 sidecars");
  });

  it("handles empty object", () => {
    expect(buildSidecarLabel({})).toBe("0/0 sidecars");
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/statusbar.test.ts 2>&1 | tail -15
```

Expected: `Cannot find module '../components/statusbar'` — confirmed failing.

- [ ] **Step 3: Create `frontend/src/components/statusbar.ts`**

```typescript
import type { HealthResponse, HeartbeatNextResponse } from "../types/api";

const API_BASE = "http://localhost:8000";
const HEALTH_POLL_MS = 15_000;
const HEARTBEAT_POLL_MS = 30_000;

// ── Pure helper functions (exported for testing) ──────────────────────────────

export function formatCountdown(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem === 0 ? `${m}m` : `${m}m ${rem}s`;
}

export function buildSidecarLabel(sidecars: Record<string, boolean>): string {
  const total = Object.keys(sidecars).length;
  const healthy = Object.values(sidecars).filter(Boolean).length;
  return `${healthy}/${total} sidecars`;
}

// ── DOM references ────────────────────────────────────────────────────────────

function el<T extends HTMLElement>(id: string): T {
  return document.getElementById(id) as T;
}

// ── Health polling ────────────────────────────────────────────────────────────

async function fetchHealth(): Promise<void> {
  const sidecarDot = el("sidecar-dot");
  const sidecarLabel = el("sidecar-label");
  const memDot = el("mem-dot");
  const apiDot = el("api-dot");

  // Defensive: elements may not exist in conversation.html's minimal statusbar
  if (!apiDot) return;

  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data: HealthResponse = await res.json();

    apiDot.className = "status-dot ok";

    if (sidecarDot && sidecarLabel && data.sidecars) {
      const allOk = Object.values(data.sidecars).every(Boolean);
      sidecarDot.className = `status-dot ${allOk ? "ok" : "warn"}`;
      sidecarLabel.textContent = buildSidecarLabel(data.sidecars);
    }

    if (memDot) {
      memDot.className = `status-dot ${data.memory ? "ok" : "err"}`;
    }
  } catch {
    apiDot.className = "status-dot err";
    if (sidecarDot) sidecarDot.className = "status-dot err";
    if (memDot) memDot.className = "status-dot err";
  }
}

// ── Heartbeat countdown ───────────────────────────────────────────────────────

let heartbeatInterval: ReturnType<typeof setInterval> | null = null;
let secondsUntil = 0;

async function fetchHeartbeatNext(): Promise<void> {
  const countdown = el("heartbeat-countdown");
  if (!countdown) return;

  try {
    const res = await fetch(`${API_BASE}/heartbeat/next`, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data: HeartbeatNextResponse = await res.json();
    secondsUntil = data.seconds_until;
    countdown.textContent = formatCountdown(secondsUntil);
  } catch {
    countdown.textContent = "--";
  }
}

function startCountdownTick(): void {
  const countdown = el("heartbeat-countdown");
  if (!countdown) return;

  if (heartbeatInterval) clearInterval(heartbeatInterval);
  heartbeatInterval = setInterval(() => {
    secondsUntil = Math.max(0, secondsUntil - 1);
    countdown.textContent = formatCountdown(secondsUntil);
    // Refresh from server when we hit zero
    if (secondsUntil === 0) {
      void fetchHeartbeatNext();
    }
  }, 1000);
}

// ── Phoenix link ──────────────────────────────────────────────────────────────

function bindPhoenixLink(): void {
  const link = el("phoenix-link");
  if (!link) return;
  link.addEventListener("click", () => {
    // In Electron, open external URLs via shell.openExternal
    // Access via window if available, else noop (LAN browser clients will navigate)
    window.open("http://localhost:6006", "_blank");
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

export function initStatusBar(): void {
  void fetchHealth();
  void fetchHeartbeatNext();
  startCountdownTick();
  bindPhoenixLink();

  setInterval(() => void fetchHealth(), HEALTH_POLL_MS);
  setInterval(() => void fetchHeartbeatNext(), HEARTBEAT_POLL_MS);
}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/statusbar.test.ts 2>&1 | tail -20
```

Expected:
```
 ✓ src/tests/statusbar.test.ts (7)
   ✓ formatCountdown (5)
   ✓ buildSidecarLabel (3)

 Test Files  1 passed (1)
 Tests       8 passed (8)
```

- [ ] **Step 5: Commit status bar component**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/src/components/statusbar.ts frontend/src/tests/statusbar.test.ts
git commit -m "feat(frontend): add status bar component with health polling and heartbeat countdown"
```

---

### Task 6: Sidebar and Conversation List Component

**Files:**
- Create: `frontend/src/components/sidebar.ts`
- Create: `frontend/src/tests/sidebar.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/tests/sidebar.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { truncateTitle } from "../components/sidebar";

describe("truncateTitle", () => {
  it("returns title unchanged when under limit", () => {
    expect(truncateTitle("Hello", 20)).toBe("Hello");
  });

  it("truncates at limit and appends ellipsis", () => {
    expect(truncateTitle("A very long conversation title here", 20)).toBe("A very long conversa…");
  });

  it("handles empty string", () => {
    expect(truncateTitle("", 20)).toBe("");
  });

  it("handles exactly limit-length title", () => {
    expect(truncateTitle("12345", 5)).toBe("12345");
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/sidebar.test.ts 2>&1 | tail -10
```

Expected: `Cannot find module '../components/sidebar'`

- [ ] **Step 3: Create `frontend/src/components/sidebar.ts`**

```typescript
import type { Conversation } from "../types/api";

// ── Pure helpers (exported for testing) ───────────────────────────────────────

export function truncateTitle(title: string, maxLen: number): string {
  if (title.length <= maxLen) return title;
  return title.slice(0, maxLen) + "…";
}

// ── Internal state ────────────────────────────────────────────────────────────

let _conversations: Conversation[] = [];
let _activeConversationId: string | null = null;
let _onSelect: ((id: string) => void) | null = null;
let _onNewConversation: (() => void) | null = null;

// ── DOM ───────────────────────────────────────────────────────────────────────

function el<T extends HTMLElement>(id: string): T {
  return document.getElementById(id) as T;
}

function renderConversationList(): void {
  const list = el<HTMLUListElement>("conversation-list");
  list.innerHTML = "";

  for (const conv of _conversations) {
    const li = document.createElement("li");
    li.className = `conversation-item${conv.id === _activeConversationId ? " active" : ""}`;
    li.dataset["id"] = conv.id;
    li.setAttribute("role", "button");
    li.setAttribute("tabindex", "0");
    li.setAttribute("aria-selected", String(conv.id === _activeConversationId));

    const dot = document.createElement("span");
    dot.className = "conv-dot";

    const title = document.createElement("span");
    title.className = "conv-title";
    title.textContent = truncateTitle(conv.title || "Untitled", 22);

    const newWindowBtn = document.createElement("button");
    newWindowBtn.className = "conv-new-window";
    newWindowBtn.textContent = "⧉";
    newWindowBtn.setAttribute("aria-label", `Open ${conv.title} in new window`);
    newWindowBtn.title = "Open in new window";

    newWindowBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (window.ordo?.openConversationWindow) {
        void window.ordo.openConversationWindow(conv.id);
      }
    });

    li.appendChild(dot);
    li.appendChild(title);
    li.appendChild(newWindowBtn);

    li.addEventListener("click", () => {
      setActiveConversation(conv.id);
      _onSelect?.(conv.id);
    });

    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        li.click();
      }
    });

    list.appendChild(li);
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

export function setConversations(conversations: Conversation[]): void {
  _conversations = conversations;
  renderConversationList();
}

export function setActiveConversation(id: string): void {
  _activeConversationId = id;
  // Update active class without full re-render
  const items = document.querySelectorAll<HTMLElement>(".conversation-item");
  for (const item of items) {
    const isActive = item.dataset["id"] === id;
    item.classList.toggle("active", isActive);
    item.setAttribute("aria-selected", String(isActive));
  }
}

export function addConversation(conv: Conversation): void {
  _conversations.unshift(conv);
  renderConversationList();
  setActiveConversation(conv.id);
}

export function initSidebar(options: {
  onSelect: (id: string) => void;
  onNewConversation: () => void;
}): void {
  _onSelect = options.onSelect;
  _onNewConversation = options.onNewConversation;

  const newBtn = el("new-conversation-btn");
  newBtn?.addEventListener("click", () => {
    _onNewConversation?.();
  });

  // Quick Actions slide-in toggle (stub)
  const quickBtn = el("quick-actions-btn");
  const quickPanel = el("quick-actions-panel");
  quickBtn?.addEventListener("click", () => {
    const isOpen = quickPanel?.classList.toggle("open");
    quickPanel?.setAttribute("aria-hidden", String(!isOpen));
  });

  // Settings modal toggle (stub)
  const settingsBtn = el("settings-btn");
  const settingsOverlay = el("settings-overlay");
  const settingsCloseBtn = el("settings-close-btn");

  settingsBtn?.addEventListener("click", () => {
    settingsOverlay?.classList.add("open");
    settingsOverlay?.setAttribute("aria-hidden", "false");
  });

  settingsCloseBtn?.addEventListener("click", () => {
    settingsOverlay?.classList.remove("open");
    settingsOverlay?.setAttribute("aria-hidden", "true");
  });

  settingsOverlay?.addEventListener("click", (e) => {
    if (e.target === settingsOverlay) {
      settingsOverlay.classList.remove("open");
      settingsOverlay.setAttribute("aria-hidden", "true");
    }
  });

  // Window controls
  const btnClose = document.querySelector<HTMLButtonElement>(".btn-close");
  const btnMin   = document.querySelector<HTMLButtonElement>(".btn-min");
  const btnMax   = document.querySelector<HTMLButtonElement>(".btn-max");

  btnClose?.addEventListener("click", () => window.ordo?.close());
  btnMin?.addEventListener("click",   () => window.ordo?.minimize());
  btnMax?.addEventListener("click",   () => window.ordo?.maximize());
}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/sidebar.test.ts 2>&1 | tail -15
```

Expected:
```
 ✓ src/tests/sidebar.test.ts (4)
   ✓ truncateTitle (4)

 Test Files  1 passed (1)
 Tests       4 passed (4)
```

- [ ] **Step 5: Commit sidebar component**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/src/components/sidebar.ts frontend/src/tests/sidebar.test.ts
git commit -m "feat(frontend): add sidebar component with conversation list and stub panel toggles"
```

---

> **Plan document reviewer dispatch:** At the end of Chunk 2, a plan-document-reviewer agent should verify: (1) `vite build` completes without errors, (2) `vitest run` passes all 12 tests across `statusbar.test.ts` and `sidebar.test.ts`, (3) `index.html` has a Content-Security-Policy meta tag allowing `connect-src http://localhost:8000 ws://localhost:8000`, (4) the layout CSS uses CSS custom properties from `tokens.css` (no hardcoded hex colors in `layout.css`), (5) window controls in `sidebar.ts` call `window.ordo.*` methods defined in `global.d.ts`.

---

## Chunk 3: API Clients, WebSocket Streaming, and Send Flow

### Task 7: Conversations API Client

**Files:**
- Create: `frontend/src/api/conversations.ts`
- Create: `frontend/src/tests/conversations.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/tests/conversations.test.ts`:
```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock global fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("ConversationsAPI", () => {
  let api: typeof import("../api/conversations");

  beforeEach(async () => {
    vi.resetModules();
    mockFetch.mockReset();
    api = await import("../api/conversations");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("listConversations: calls GET /conversations and returns data", async () => {
    const payload = [{ id: "abc", title: "Main", created_at: "2026-01-01", updated_at: "2026-01-01" }];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => payload,
    });

    const result = await api.listConversations();
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/conversations",
      expect.objectContaining({ method: "GET" })
    );
    expect(result).toEqual(payload);
  });

  it("listConversations: throws on non-OK response", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 500 });
    await expect(api.listConversations()).rejects.toThrow("HTTP 500");
  });

  it("createConversation: calls POST /conversations with title", async () => {
    const newConv = { id: "xyz", title: "Research", created_at: "2026-01-01", updated_at: "2026-01-01" };
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => newConv });

    const result = await api.createConversation("Research");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/conversations",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
        body: JSON.stringify({ title: "Research" }),
      })
    );
    expect(result).toEqual(newConv);
  });

  it("getMessages: calls GET /conversations/{id}/messages", async () => {
    const msgs = [{ id: "m1", conversation_id: "abc", role: "human", content: "hi", created_at: "2026-01-01" }];
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => msgs });

    const result = await api.getMessages("abc");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/conversations/abc/messages",
      expect.objectContaining({ method: "GET" })
    );
    expect(result).toEqual(msgs);
  });

  it("postMessage: calls POST /conversations/{id}/messages", async () => {
    const saved = { id: "m2", conversation_id: "abc", role: "human", content: "hello", created_at: "2026-01-01" };
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => saved });

    const result = await api.postMessage("abc", "hello");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/conversations/abc/messages",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ role: "human", content: "hello" }),
      })
    );
    expect(result).toEqual(saved);
  });

  it("invokeAgent: calls POST /agents/generalist/invoke", async () => {
    const response = { conversation_id: "abc", message_id: "m3", content: "Hello there" };
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => response });

    const result = await api.invokeAgent({ conversation_id: "abc", message: "hi", stream: true });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/agents/generalist/invoke",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ conversation_id: "abc", message: "hi", stream: true }),
      })
    );
    expect(result).toEqual(response);
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/conversations.test.ts 2>&1 | tail -10
```

Expected: `Cannot find module '../api/conversations'`

- [ ] **Step 3: Create `frontend/src/api/conversations.ts`**

```typescript
import type { Conversation, Message, AgentInvokeRequest, AgentInvokeResponse } from "../types/api";

const API_BASE = "http://localhost:8000";

async function apiFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export async function listConversations(): Promise<Conversation[]> {
  return apiFetch<Conversation[]>(`${API_BASE}/conversations`, { method: "GET" });
}

export async function createConversation(title: string): Promise<Conversation> {
  return apiFetch<Conversation>(`${API_BASE}/conversations`, {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function getMessages(conversationId: string): Promise<Message[]> {
  return apiFetch<Message[]>(`${API_BASE}/conversations/${conversationId}/messages`, {
    method: "GET",
  });
}

export async function postMessage(conversationId: string, content: string): Promise<Message> {
  return apiFetch<Message>(`${API_BASE}/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ role: "human", content }),
  });
}

export async function invokeAgent(request: AgentInvokeRequest): Promise<AgentInvokeResponse> {
  return apiFetch<AgentInvokeResponse>(`${API_BASE}/agents/generalist/invoke`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/conversations.test.ts 2>&1 | tail -15
```

Expected:
```
 ✓ src/tests/conversations.test.ts (6)

 Test Files  1 passed (1)
 Tests       6 passed (6)
```

- [ ] **Step 5: Commit API client**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/src/api/conversations.ts frontend/src/tests/conversations.test.ts
git commit -m "feat(frontend): add conversations API client with full CRUD and agent invoke"
```

---

### Task 8: WebSocket Client

**Files:**
- Create: `frontend/src/api/ws.ts`
- Create: `frontend/src/tests/ws.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/tests/ws.test.ts`:
```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { buildWsUrl, parseWsMessage } from "../api/ws";
import type { WsMessage } from "../types/api";

describe("buildWsUrl", () => {
  it("returns correct ws URL for a given conversation id", () => {
    expect(buildWsUrl("conv-123")).toBe("ws://localhost:8000/ws/conv-123");
  });

  it("handles UUIDs", () => {
    const id = "550e8400-e29b-41d4-a716-446655440000";
    expect(buildWsUrl(id)).toBe(`ws://localhost:8000/ws/${id}`);
  });
});

describe("parseWsMessage", () => {
  it("parses a token message", () => {
    const raw = JSON.stringify({ type: "token", content: "Hello" });
    const msg: WsMessage = parseWsMessage(raw);
    expect(msg.type).toBe("token");
    if (msg.type === "token") {
      expect(msg.content).toBe("Hello");
    }
  });

  it("parses a done message", () => {
    const raw = JSON.stringify({ type: "done", message_id: "m1" });
    const msg: WsMessage = parseWsMessage(raw);
    expect(msg.type).toBe("done");
  });

  it("parses an error message", () => {
    const raw = JSON.stringify({ type: "error", detail: "Something went wrong" });
    const msg: WsMessage = parseWsMessage(raw);
    expect(msg.type).toBe("error");
    if (msg.type === "error") {
      expect(msg.detail).toBe("Something went wrong");
    }
  });

  it("parses a ping message", () => {
    const raw = JSON.stringify({ type: "ping" });
    const msg: WsMessage = parseWsMessage(raw);
    expect(msg.type).toBe("ping");
  });

  it("throws on invalid JSON", () => {
    expect(() => parseWsMessage("not json")).toThrow();
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/ws.test.ts 2>&1 | tail -10
```

Expected: `Cannot find module '../api/ws'`

- [ ] **Step 3: Create `frontend/src/api/ws.ts`**

```typescript
import type { WsMessage } from "../types/api";

const WS_BASE = "ws://localhost:8000";
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS  = 30_000;
const RECONNECT_JITTER  = 500;

// ── Pure helpers (exported for testing) ───────────────────────────────────────

export function buildWsUrl(conversationId: string): string {
  return `${WS_BASE}/ws/${conversationId}`;
}

export function parseWsMessage(raw: string): WsMessage {
  return JSON.parse(raw) as WsMessage;
}

// ── ConversationSocket class ──────────────────────────────────────────────────

export type TokenHandler = (token: string) => void;
export type DoneHandler  = (messageId: string) => void;
export type ErrorHandler = (detail: string) => void;
export type StateHandler = (state: "connecting" | "open" | "closed") => void;

export interface ConversationSocketOptions {
  conversationId: string;
  onToken: TokenHandler;
  onDone: DoneHandler;
  onError: ErrorHandler;
  onStateChange?: StateHandler;
}

export class ConversationSocket {
  private ws: WebSocket | null = null;
  private conversationId: string;
  private opts: ConversationSocketOptions;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _destroyed = false;

  constructor(opts: ConversationSocketOptions) {
    this.conversationId = opts.conversationId;
    this.opts = opts;
    this.connect();
  }

  private connect(): void {
    if (this._destroyed) return;

    const url = buildWsUrl(this.conversationId);
    this.opts.onStateChange?.("connecting");

    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.opts.onStateChange?.("open");
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const msg = parseWsMessage(event.data);
        this.dispatch(msg);
      } catch {
        this.opts.onError("Received invalid message from server");
      }
    };

    ws.onclose = () => {
      if (this._destroyed) return;
      this.opts.onStateChange?.("closed");
      this.scheduleReconnect();
    };

    ws.onerror = () => {
      // onerror is always followed by onclose — let onclose handle reconnect
      this.opts.onError("WebSocket connection error");
    };
  }

  private dispatch(msg: WsMessage): void {
    switch (msg.type) {
      case "token":
        this.opts.onToken(msg.content);
        break;
      case "done":
        this.opts.onDone(msg.message_id);
        break;
      case "error":
        this.opts.onError(msg.detail);
        break;
      case "ping":
        // keepalive — no action needed
        break;
    }
  }

  private scheduleReconnect(): void {
    if (this._destroyed) return;
    const delay = Math.min(
      RECONNECT_BASE_MS * 2 ** this.reconnectAttempts + Math.random() * RECONNECT_JITTER,
      RECONNECT_MAX_MS
    );
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  /** Change the active conversation — reconnects WebSocket to new conversation_id */
  switchConversation(conversationId: string): void {
    this.conversationId = conversationId;
    this.reconnectAttempts = 0;
    this.close(false);
    this.connect();
  }

  private close(destroy: boolean): void {
    if (destroy) this._destroyed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
  }

  /** Permanently close — no reconnect */
  destroy(): void {
    this.close(true);
  }

  get readyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }
}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/ws.test.ts 2>&1 | tail -15
```

Expected:
```
 ✓ src/tests/ws.test.ts (7)
   ✓ buildWsUrl (2)
   ✓ parseWsMessage (5)

 Test Files  1 passed (1)
 Tests       7 passed (7)
```

- [ ] **Step 5: Commit WebSocket client**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/src/api/ws.ts frontend/src/tests/ws.test.ts
git commit -m "feat(frontend): add WebSocket client with auto-reconnect and conversation switching"
```

---

### Task 9: Conversation View Component and Markdown Rendering

**Files:**
- Create: `frontend/src/components/conversation-view.ts`
- Create: `frontend/src/tests/conversation-view.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/tests/conversation-view.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { buildMessageId, escapeHtml } from "../components/conversation-view";

describe("buildMessageId", () => {
  it("returns a string starting with 'msg-'", () => {
    const id = buildMessageId("abc123");
    expect(id).toBe("msg-abc123");
  });
});

describe("escapeHtml", () => {
  it("escapes angle brackets", () => {
    expect(escapeHtml("<script>")).toBe("&lt;script&gt;");
  });

  it("escapes ampersand", () => {
    expect(escapeHtml("a & b")).toBe("a &amp; b");
  });

  it("escapes double quotes", () => {
    expect(escapeHtml('say "hi"')).toBe("say &quot;hi&quot;");
  });

  it("leaves safe text unchanged", () => {
    expect(escapeHtml("Hello world")).toBe("Hello world");
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/conversation-view.test.ts 2>&1 | tail -10
```

Expected: `Cannot find module '../components/conversation-view'`

- [ ] **Step 3: Create `frontend/src/components/conversation-view.ts`**

```typescript
import { marked } from "marked";
import type { Message } from "../types/api";

// Configure marked for safe, synchronous rendering
marked.setOptions({ async: false });

// ── Pure helpers (exported for testing) ───────────────────────────────────────

export function buildMessageId(messageId: string): string {
  return `msg-${messageId}`;
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── DOM helpers ───────────────────────────────────────────────────────────────

function getView(): HTMLElement {
  return document.getElementById("conversation-view") as HTMLElement;
}

function scrollToBottom(): void {
  const view = getView();
  view.scrollTop = view.scrollHeight;
}

// ── Render a single complete message ─────────────────────────────────────────

export function renderMessage(msg: Message): void {
  const view = getView();

  const wrapper = document.createElement("div");
  wrapper.className = `message ${msg.role}`;
  wrapper.id = buildMessageId(msg.id);

  const roleEl = document.createElement("div");
  roleEl.className = "msg-role";
  roleEl.textContent = msg.role === "human" ? "You" : "Ordo";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  if (msg.role === "assistant") {
    bubble.innerHTML = marked.parse(msg.content) as string;
  } else {
    // Human messages: escape HTML, preserve newlines
    bubble.innerHTML = escapeHtml(msg.content).replace(/\n/g, "<br>");
  }

  wrapper.appendChild(roleEl);
  wrapper.appendChild(bubble);
  view.appendChild(wrapper);
  scrollToBottom();
}

// ── Streaming message support ─────────────────────────────────────────────────

let _streamingEl: HTMLElement | null = null;
let _streamingBubble: HTMLElement | null = null;
let _streamingContent = "";

/** Create a placeholder assistant message element for streaming into. */
export function beginStreamingMessage(): void {
  const view = getView();

  const wrapper = document.createElement("div");
  wrapper.className = "message assistant streaming";

  const roleEl = document.createElement("div");
  roleEl.className = "msg-role";
  roleEl.textContent = "Ordo";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble streaming-cursor";

  wrapper.appendChild(roleEl);
  wrapper.appendChild(bubble);
  view.appendChild(wrapper);

  _streamingEl = wrapper;
  _streamingBubble = bubble;
  _streamingContent = "";
  scrollToBottom();
}

/** Append a token to the in-progress streaming message. */
export function appendStreamingToken(token: string): void {
  if (!_streamingBubble) return;
  _streamingContent += token;
  _streamingBubble.innerHTML = marked.parse(_streamingContent) as string;
  scrollToBottom();
}

/** Finalize the streaming message: remove cursor class, set final id. */
export function finalizeStreamingMessage(messageId: string): void {
  if (!_streamingEl || !_streamingBubble) return;
  _streamingBubble.classList.remove("streaming-cursor");
  _streamingEl.classList.remove("streaming");
  _streamingEl.id = buildMessageId(messageId);
  _streamingEl = null;
  _streamingBubble = null;
  _streamingContent = "";
}

/** Abort streaming — remove the in-progress element entirely. */
export function abortStreamingMessage(): void {
  _streamingEl?.remove();
  _streamingEl = null;
  _streamingBubble = null;
  _streamingContent = "";
}

// ── Render history ────────────────────────────────────────────────────────────

export function renderHistory(messages: Message[]): void {
  const view = getView();
  view.innerHTML = "";
  for (const msg of messages) {
    renderMessage(msg);
  }
}

/** Clear conversation view — call before loading a new conversation. */
export function clearView(): void {
  getView().innerHTML = "";
}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/conversation-view.test.ts 2>&1 | tail -15
```

Expected:
```
 ✓ src/tests/conversation-view.test.ts (5)
   ✓ buildMessageId (1)
   ✓ escapeHtml (4)

 Test Files  1 passed (1)
 Tests       5 passed (5)
```

- [ ] **Step 5: Commit conversation view**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/src/components/conversation-view.ts frontend/src/tests/conversation-view.test.ts
git commit -m "feat(frontend): add conversation view component with markdown rendering and streaming support"
```

---

### Task 10: Input Bar Component and Send Flow

**Files:**
- Create: `frontend/src/components/input-bar.ts`
- Create: `frontend/src/tests/input-bar.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/tests/input-bar.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { normalizeInput } from "../components/input-bar";

describe("normalizeInput", () => {
  it("trims leading and trailing whitespace", () => {
    expect(normalizeInput("  hello  ")).toBe("hello");
  });

  it("returns empty string for blank input", () => {
    expect(normalizeInput("   ")).toBe("");
  });

  it("preserves internal content", () => {
    expect(normalizeInput("hello world")).toBe("hello world");
  });

  it("preserves internal newlines", () => {
    expect(normalizeInput("line1\nline2")).toBe("line1\nline2");
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/input-bar.test.ts 2>&1 | tail -10
```

Expected: `Cannot find module '../components/input-bar'`

- [ ] **Step 3: Create `frontend/src/components/input-bar.ts`**

```typescript
// ── Pure helpers (exported for testing) ───────────────────────────────────────

export function normalizeInput(text: string): string {
  return text.trim();
}

// ── State ─────────────────────────────────────────────────────────────────────

type SendHandler = (content: string) => Promise<void>;

let _onSend: SendHandler | null = null;
let _isSending = false;

// ── DOM refs ──────────────────────────────────────────────────────────────────

function getInput(): HTMLTextAreaElement {
  return document.getElementById("message-input") as HTMLTextAreaElement;
}

function getSendBtn(): HTMLButtonElement {
  return document.getElementById("send-btn") as HTMLButtonElement;
}

// ── Auto-resize textarea ──────────────────────────────────────────────────────

function autoResize(textarea: HTMLTextAreaElement): void {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
}

// ── Send gating ───────────────────────────────────────────────────────────────

function updateSendState(): void {
  const input = getInput();
  const sendBtn = getSendBtn();
  if (!input || !sendBtn) return;
  const hasContent = normalizeInput(input.value).length > 0;
  sendBtn.disabled = !hasContent || _isSending;
}

function setSending(sending: boolean): void {
  _isSending = sending;
  const input = getInput();
  const sendBtn = getSendBtn();
  if (!input || !sendBtn) return;
  input.disabled = sending;
  sendBtn.disabled = sending;
  if (!sending) input.focus();
}

// ── Trigger send ──────────────────────────────────────────────────────────────

async function triggerSend(): Promise<void> {
  const input = getInput();
  if (!input || _isSending) return;

  const content = normalizeInput(input.value);
  if (!content || !_onSend) return;

  setSending(true);
  input.value = "";
  autoResize(input);

  try {
    await _onSend(content);
  } finally {
    setSending(false);
    updateSendState();
  }
}

// ── PTT stub ──────────────────────────────────────────────────────────────────

function bindPttButton(): void {
  const pttBtn = document.getElementById("ptt-btn");
  if (!pttBtn) return;

  pttBtn.addEventListener("click", () => {
    // Phase 7 will implement actual PTT — this is a stub
    const input = getInput();
    if (input) {
      input.focus();
      input.placeholder = "PTT available in Phase 7…";
      setTimeout(() => {
        input.placeholder = "Type or push to talk...";
      }, 2000);
    }
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

export function initInputBar(onSend: SendHandler): void {
  _onSend = onSend;

  const input = getInput();
  const sendBtn = getSendBtn();

  if (!input || !sendBtn) return;

  // Auto-resize
  input.addEventListener("input", () => {
    autoResize(input);
    updateSendState();
  });

  // Enter to send (Shift+Enter for newline)
  input.addEventListener("keydown", (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void triggerSend();
    }
  });

  // Send button click
  sendBtn.addEventListener("click", () => {
    void triggerSend();
  });

  bindPttButton();
  updateSendState();
}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run src/tests/input-bar.test.ts 2>&1 | tail -15
```

Expected:
```
 ✓ src/tests/input-bar.test.ts (4)
   ✓ normalizeInput (4)

 Test Files  1 passed (1)
 Tests       4 passed (4)
```

- [ ] **Step 5: Commit input bar**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/src/components/input-bar.ts frontend/src/tests/input-bar.test.ts
git commit -m "feat(frontend): add input bar component with auto-resize, send gating, and PTT stub"
```

---

### Task 11: Main Entry Point — Wire Everything Together

**Files:**
- Modify: `frontend/src/main.ts` (replace stub)
- Create: `frontend/src/conversation.ts` (replace stub, full detached window implementation)

- [ ] **Step 1: Replace `frontend/src/main.ts` stub with full implementation**

```typescript
import { initStatusBar } from "./components/statusbar";
import { initSidebar, setConversations, addConversation, setActiveConversation } from "./components/sidebar";
import { initInputBar } from "./components/input-bar";
import {
  renderHistory,
  clearView,
  renderMessage,
  beginStreamingMessage,
  appendStreamingToken,
  finalizeStreamingMessage,
  abortStreamingMessage,
} from "./components/conversation-view";
import {
  listConversations,
  createConversation,
  getMessages,
  postMessage,
  invokeAgent,
} from "./api/conversations";
import { ConversationSocket } from "./api/ws";
import type { Conversation } from "./types/api";

// ── State ─────────────────────────────────────────────────────────────────────

let activeConversationId: string | null = null;
let socket: ConversationSocket | null = null;

// ── Conversation loading ───────────────────────────────────────────────────────

async function loadConversation(conversationId: string): Promise<void> {
  activeConversationId = conversationId;
  setActiveConversation(conversationId);
  clearView();

  const messages = await getMessages(conversationId).catch(() => []);
  renderHistory(messages);

  // Switch WebSocket to the new conversation
  if (socket) {
    socket.switchConversation(conversationId);
  } else {
    socket = new ConversationSocket({
      conversationId,
      onToken: (token) => appendStreamingToken(token),
      onDone: (messageId) => finalizeStreamingMessage(messageId),
      onError: (detail) => {
        abortStreamingMessage();
        console.error("WebSocket error:", detail);
      },
      onStateChange: (state) => {
        const apiDot = document.getElementById("api-dot");
        if (apiDot) {
          apiDot.className = `status-dot ${state === "open" ? "ok" : state === "connecting" ? "warn" : "err"}`;
        }
      },
    });
  }
}

// ── Send flow ─────────────────────────────────────────────────────────────────

async function handleSend(content: string): Promise<void> {
  if (!activeConversationId) return;

  // 1. Render human message immediately (optimistic)
  const tempId = `temp-${Date.now()}`;
  renderMessage({ id: tempId, conversation_id: activeConversationId, role: "human", content, created_at: new Date().toISOString() });

  // 2. Persist human turn
  await postMessage(activeConversationId, content).catch(console.error);

  // 3. Begin streaming assistant response placeholder
  beginStreamingMessage();

  // 4. Invoke agent — streaming response arrives via WebSocket
  await invokeAgent({
    conversation_id: activeConversationId,
    message: content,
    stream: true,
  }).catch((err: unknown) => {
    abortStreamingMessage();
    console.error("Agent invoke failed:", err);
  });
}

// ── New conversation flow ─────────────────────────────────────────────────────

async function handleNewConversation(): Promise<void> {
  const title = `Conversation ${new Date().toLocaleDateString()}`;
  const conv: Conversation = await createConversation(title).catch(() => ({
    id: crypto.randomUUID(),
    title,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }));

  addConversation(conv);
  await loadConversation(conv.id);
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  initStatusBar();

  initSidebar({
    onSelect: (id) => void loadConversation(id),
    onNewConversation: () => void handleNewConversation(),
  });

  initInputBar(handleSend);

  // Load conversation list
  const conversations = await listConversations().catch(() => [] as Conversation[]);

  if (conversations.length === 0) {
    // Create the default "Main" conversation on first run
    const main = await createConversation("Main").catch(() => ({
      id: crypto.randomUUID(),
      title: "Main",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }));
    conversations.push(main);
  }

  setConversations(conversations);
  await loadConversation(conversations[0]!.id);
}

void main();
```

- [ ] **Step 2: Replace `frontend/src/conversation.ts` stub with detached window implementation**

```typescript
// Detached conversation window — loaded with ?conversation_id= URL param
import { initStatusBar } from "./components/statusbar";
import { initInputBar } from "./components/input-bar";
import {
  renderHistory,
  renderMessage,
  beginStreamingMessage,
  appendStreamingToken,
  finalizeStreamingMessage,
  abortStreamingMessage,
} from "./components/conversation-view";
import { getMessages, postMessage, invokeAgent } from "./api/conversations";
import { ConversationSocket } from "./api/ws";

const params = new URLSearchParams(window.location.search);
const conversationId = params.get("conversation_id");

if (!conversationId) {
  document.body.innerHTML = "<p style='color:red;padding:2rem'>Missing conversation_id parameter</p>";
  throw new Error("No conversation_id in URL");
}

// Update title
const titleEl = document.getElementById("window-conv-title");
if (titleEl) titleEl.textContent = `Conversation ${conversationId.slice(0, 8)}`;

// Bind window controls
const btnClose = document.querySelector<HTMLButtonElement>(".btn-close");
const btnMin   = document.querySelector<HTMLButtonElement>(".btn-min");
const btnMax   = document.querySelector<HTMLButtonElement>(".btn-max");
btnClose?.addEventListener("click", () => window.ordo?.close());
btnMin?.addEventListener("click",   () => window.ordo?.minimize());
btnMax?.addEventListener("click",   () => window.ordo?.maximize());

// WebSocket
const socket = new ConversationSocket({
  conversationId,
  onToken: (token) => appendStreamingToken(token),
  onDone: (messageId) => finalizeStreamingMessage(messageId),
  onError: (detail) => {
    abortStreamingMessage();
    console.error("WebSocket error:", detail);
  },
  onStateChange: (state) => {
    const apiDot = document.getElementById("api-dot");
    if (apiDot) {
      apiDot.className = `status-dot ${state === "open" ? "ok" : state === "connecting" ? "warn" : "err"}`;
    }
  },
});

// Load history
getMessages(conversationId)
  .then(renderHistory)
  .catch(console.error);

// Send handler
async function handleSend(content: string): Promise<void> {
  renderMessage({
    id: `temp-${Date.now()}`,
    conversation_id: conversationId!,
    role: "human",
    content,
    created_at: new Date().toISOString(),
  });

  await postMessage(conversationId!, content).catch(console.error);
  beginStreamingMessage();

  await invokeAgent({
    conversation_id: conversationId!,
    message: content,
    stream: true,
  }).catch((err: unknown) => {
    abortStreamingMessage();
    console.error("Agent invoke failed:", err);
  });
}

initStatusBar();
initInputBar(handleSend);
```

- [ ] **Step 3: Run TypeScript check across all renderer sources**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx tsc --noEmit 2>&1
```

Expected: Zero TypeScript errors.

- [ ] **Step 4: Run full Vite build**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vite build 2>&1 | tail -15
```

Expected: `✓ built in Xms` — `dist/` contains `index.html`, `conversation.html`, and bundled JS/CSS assets.

- [ ] **Step 5: Run all Vitest tests**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run 2>&1 | tail -25
```

Expected:
```
 ✓ src/tests/statusbar.test.ts (8)
 ✓ src/tests/sidebar.test.ts (4)
 ✓ src/tests/conversations.test.ts (6)
 ✓ src/tests/ws.test.ts (7)
 ✓ src/tests/conversation-view.test.ts (5)
 ✓ src/tests/input-bar.test.ts (4)

 Test Files  6 passed (6)
 Tests      34 passed (34)
```

- [ ] **Step 6: Integration smoke test — launch Electron in dev mode**

Ensure FastAPI is running (`pm2 start` or `uvicorn main:app --port 8000`), then:

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
set NODE_ENV=development && npx electron .
```

Verify manually:
- [ ] App window opens (1280x800, dark theme)
- [ ] Sidebar shows "Main" conversation with purple active dot
- [ ] Status bar shows "Ordo v4.0" and polls `/health`
- [ ] Type a message and press Enter — message appears in conversation view
- [ ] Agent response streams in token by token via WebSocket
- [ ] Clicking "+ new" creates a new conversation
- [ ] Quick Actions button opens the slide-in panel stub
- [ ] Settings button opens the modal stub with "Close" button
- [ ] System tray icon appears; double-click shows the window

- [ ] **Step 7: Commit final wired application**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/src/main.ts frontend/src/conversation.ts
git commit -m "feat(frontend): wire main entry point — full send/stream flow with conversation management"
```

---

### Task 12: Vitest Config and Full Test Run

**Files:**
- Create: `frontend/vitest.config.ts`

- [ ] **Step 1: Create `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/tests/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/api/**", "src/components/**"],
      exclude: ["src/main.ts", "src/conversation.ts"],
    },
  },
});
```

- [ ] **Step 2: Install jsdom for Vitest**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npm install --save-dev @vitest/coverage-v8 jsdom
```

Expected: Packages installed with no errors.

- [ ] **Step 3: Run full test suite with coverage**

```bash
cd "C:/Users/user/AI-Assistant Version 4/frontend"
npx vitest run --coverage 2>&1 | tail -30
```

Expected: All 34 tests pass. Coverage report printed for `src/api/` and `src/components/`.

- [ ] **Step 4: Commit Vitest config**

```bash
cd "C:/Users/user/AI-Assistant Version 4"
git add frontend/vitest.config.ts frontend/package.json
git commit -m "chore(frontend): add Vitest config with jsdom environment and coverage reporting"
```

---

> **Plan document reviewer dispatch:** At the end of Chunk 3, a plan-document-reviewer agent should verify: (1) `npx vitest run` produces 34 passing tests across 6 test files, (2) `npx tsc --noEmit` from `frontend/` reports zero errors in strict mode, (3) `npx vite build` completes with a valid `dist/` containing `index.html` and `conversation.html`, (4) `frontend/src/main.ts` calls all six component init functions and has a `handleSend` function that follows the three-step flow: post human message → `beginStreamingMessage` → `invokeAgent`, (5) `ConversationSocket` in `ws.ts` calls `switchConversation` (not `destroy` + new instance) when loading a new conversation in the main window — this preserves the WebSocket connection object and avoids opening multiple connections, (6) `conversation.ts` reads `conversation_id` from `URLSearchParams` and guards against a missing param by throwing before any DOM manipulation.
