const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");

let mainWindow = null;
let backendProcess = null;
let backendStartedByApp = false;

const DEFAULT_API_BASE = "http://127.0.0.1:8000";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function isApiHealthy(apiBase) {
  try {
    const response = await fetch(`${apiBase}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

async function waitApiReady(apiBase, timeoutMs = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await isApiHealthy(apiBase)) {
      return true;
    }
    await sleep(500);
  }
  return false;
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function syncConfigDirectory(packagedConfigDir, runtimeConfigDir) {
  if (!fs.existsSync(packagedConfigDir)) {
    return;
  }
  ensureDir(runtimeConfigDir);

  const entries = fs.readdirSync(packagedConfigDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) {
      continue;
    }

    const src = path.join(packagedConfigDir, entry.name);
    const dst = path.join(runtimeConfigDir, entry.name);

    // Keep user-edited DB settings; refresh other templates each startup.
    if (entry.name.toLowerCase() === "db.yaml") {
      if (!fs.existsSync(dst)) {
        fs.copyFileSync(src, dst);
      }
      continue;
    }

    fs.copyFileSync(src, dst);
  }
}

function prepareRuntimeRoot() {
  if (!app.isPackaged) {
    return path.resolve(__dirname, "..");
  }

  const runtimeRoot = path.join(app.getPath("userData"), "runtime");
  const runtimeConfig = path.join(runtimeRoot, "config");
  const runtimeExports = path.join(runtimeRoot, "exports");
  const runtimeLogs = path.join(runtimeRoot, "logs");
  const packagedConfig = path.join(process.resourcesPath, "config");

  ensureDir(runtimeRoot);
  ensureDir(runtimeExports);
  ensureDir(runtimeLogs);
  syncConfigDirectory(packagedConfig, runtimeConfig);

  return runtimeRoot;
}

function getBackendStartCommand(runtimeRoot) {
  if (app.isPackaged) {
    const exePath = path.join(process.resourcesPath, "backend-api", "boda-api.exe");
    return {
      command: exePath,
      args: [],
      cwd: runtimeRoot,
      env: {
        ...process.env,
        BODA_ROOT_DIR: runtimeRoot
      }
    };
  }

  const repoRoot = path.resolve(__dirname, "..");
  const pythonExe = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  const serverScript = path.join(repoRoot, "app-api", "desktop_server.py");
  return {
    command: pythonExe,
    args: [serverScript],
    cwd: repoRoot,
    env: {
      ...process.env,
      BODA_ROOT_DIR: repoRoot
    }
  };
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1200,
    minHeight: 760,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  const devUrl = process.env.BODA_WEB_URL || "http://127.0.0.1:5173";
  if (!app.isPackaged) {
    mainWindow.loadURL(devUrl);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    const indexFile = path.join(process.resourcesPath, "app-web-dist", "index.html");
    mainWindow.loadFile(indexFile);
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

async function ensureBackendRunning(runtimeRoot) {
  const apiBase = process.env.BODA_API_URL || DEFAULT_API_BASE;

  if (await isApiHealthy(apiBase)) {
    backendStartedByApp = false;
    return;
  }

  const startCmd = getBackendStartCommand(runtimeRoot);
  if (!fs.existsSync(startCmd.command)) {
    throw new Error(`后端启动文件不存在: ${startCmd.command}`);
  }

  const logDir = path.join(runtimeRoot, "logs");
  ensureDir(logDir);
  const logPath = path.join(logDir, "backend.log");
  const logStream = fs.createWriteStream(logPath, { flags: "a" });

  backendProcess = spawn(startCmd.command, startCmd.args, {
    cwd: startCmd.cwd,
    env: startCmd.env,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"]
  });
  backendStartedByApp = true;

  backendProcess.stdout.on("data", (chunk) => logStream.write(chunk));
  backendProcess.stderr.on("data", (chunk) => logStream.write(chunk));

  backendProcess.on("exit", () => {
    backendProcess = null;
    try {
      logStream.end();
    } catch {
      // ignore
    }
  });

  const ready = await waitApiReady(apiBase, 30000);
  if (!ready) {
    throw new Error(`后端启动超时，请检查配置或查看日志: ${logPath}`);
  }
}

function stopBackend() {
  if (!backendStartedByApp || !backendProcess) {
    return;
  }
  try {
    backendProcess.kill();
  } catch {
    // ignore
  }
}

ipcMain.handle("select-export-directory", async () => {
  const result = await dialog.showOpenDialog({
    title: "选择导出目录",
    properties: ["openDirectory", "createDirectory"]
  });

  if (result.canceled || !result.filePaths.length) {
    return "";
  }
  return result.filePaths[0] || "";
});

app.whenReady().then(async () => {
  const runtimeRoot = prepareRuntimeRoot();
  try {
    await ensureBackendRunning(runtimeRoot);
  } catch (error) {
    dialog.showErrorBox("后端启动失败", String(error?.message || error));
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("before-quit", () => {
  stopBackend();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
