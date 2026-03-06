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

function copyDirIfMissing(srcDir, dstDir) {
  if (!fs.existsSync(srcDir)) {
    return;
  }
  ensureDir(dstDir);
  const entries = fs.readdirSync(srcDir, { withFileTypes: true });
  for (const entry of entries) {
    const src = path.join(srcDir, entry.name);
    const dst = path.join(dstDir, entry.name);
    if (entry.isDirectory()) {
      copyDirIfMissing(src, dst);
    } else if (!fs.existsSync(dst)) {
      fs.copyFileSync(src, dst);
    }
  }
}

function prepareRuntimeRoot() {
  if (!app.isPackaged) {
    return path.resolve(__dirname, "..");
  }

  const runtimeRoot = path.join(app.getPath("userData"), "runtime");
  const runtimeConfig = path.join(runtimeRoot, "config");
  const runtimeExports = path.join(runtimeRoot, "exports");
  const packagedConfig = path.join(process.resourcesPath, "config");

  ensureDir(runtimeRoot);
  ensureDir(runtimeExports);
  copyDirIfMissing(packagedConfig, runtimeConfig);

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

  backendProcess = spawn(startCmd.command, startCmd.args, {
    cwd: startCmd.cwd,
    env: startCmd.env,
    windowsHide: true
  });
  backendStartedByApp = true;

  backendProcess.on("exit", () => {
    backendProcess = null;
  });

  const ready = await waitApiReady(apiBase, 30000);
  if (!ready) {
    throw new Error("后端启动超时，请检查数据库配置或端口占用");
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
