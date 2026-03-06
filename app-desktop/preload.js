const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("bodaDesktop", {
  isDesktop: true,
  selectExportDirectory: async () => ipcRenderer.invoke("select-export-directory")
});
