const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  getSettings: () => ipcRenderer.invoke('get-settings'),
  saveSettings: (s) => ipcRenderer.invoke('save-settings', s),
  getMeetings: () => ipcRenderer.invoke('get-meetings'),
  summarize: (data) => ipcRenderer.invoke('summarize', data)
});
