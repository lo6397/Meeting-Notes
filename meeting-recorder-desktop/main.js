const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const Anthropic = require('@anthropic-ai/sdk').default;

// --- Paths for persistent data ---
const userDataPath = app.getPath('userData');
const settingsPath = path.join(userDataPath, 'settings.json');
const meetingsPath = path.join(userDataPath, 'meetings.json');

// --- Settings (API key) ---
function loadSettings() {
  try { return JSON.parse(fs.readFileSync(settingsPath, 'utf8')); }
  catch { return {}; }
}

function saveSettings(settings) {
  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
}

// --- Meetings ---
function loadMeetings() {
  try { return JSON.parse(fs.readFileSync(meetingsPath, 'utf8')); }
  catch { return []; }
}

function saveMeetings(meetings) {
  fs.writeFileSync(meetingsPath, JSON.stringify(meetings, null, 2));
}

// --- IPC handlers ---
ipcMain.handle('get-settings', () => loadSettings());
ipcMain.handle('save-settings', (_, settings) => { saveSettings(settings); return true; });
ipcMain.handle('get-meetings', () => loadMeetings());

ipcMain.handle('summarize', async (_, { transcript, title }) => {
  const settings = loadSettings();
  const apiKey = settings.anthropic_api_key;
  if (!apiKey) return { error: 'No API key configured. Click Settings to add your Anthropic API key.' };

  try {
    const client = new Anthropic({ apiKey });
    const message = await client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 1024,
      messages: [{
        role: 'user',
        content: `Summarize this meeting transcript and extract action items. Return ONLY valid JSON with no markdown:\n{"summary": "...", "actions": ["item1", "item2"]}\n\nMeeting title: ${title}\n\nTRANSCRIPT:\n${transcript}`
      }]
    });

    const text = message.content[0].text.trim().replace(/```json/g, '').replace(/```/g, '');
    const result = JSON.parse(text);

    // Save meeting
    const meetings = loadMeetings();
    meetings.push({
      title: title || 'Untitled Meeting',
      transcript,
      summary: result.summary,
      actions: result.actions,
      date: new Date().toLocaleString()
    });
    saveMeetings(meetings);

    return result;
  } catch (e) {
    return { error: e.message };
  }
});

// --- Window ---
function createWindow() {
  const win = new BrowserWindow({
    width: 900,
    height: 750,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  win.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
