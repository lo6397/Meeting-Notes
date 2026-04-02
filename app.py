from flask import Flask, render_template_string, request, jsonify
import anthropic
import os, json, uuid
from datetime import datetime, date

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meetings.json')

def load_meetings():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_meetings(meetings):
    with open(DATA_FILE, 'w') as f:
        json.dump(meetings, f, indent=2)

def find_meeting(mid):
    meetings = load_meetings()
    for m in meetings:
        if m['id'] == mid:
            return m, meetings
    return None, meetings

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/meetings')
def api_list():
    return jsonify(load_meetings())

@app.route('/api/meetings', methods=['POST'])
def api_create():
    d = request.json
    m = {
        'id': str(uuid.uuid4())[:8],
        'title': d.get('title', '').strip() or 'Untitled Meeting',
        'scheduledDate': d.get('scheduledDate', date.today().isoformat()),
        'scheduledTime': d.get('scheduledTime', datetime.now().strftime('%H:%M')),
        'notes': d.get('notes', ''),
        'status': d.get('status', 'scheduled'),
        'transcript': '',
        'summary': '',
        'actions': [],
        'prompts': [],
        'createdAt': datetime.now().isoformat(),
        'completedAt': ''
    }
    meetings = load_meetings()
    meetings.append(m)
    save_meetings(meetings)
    return jsonify(m)

@app.route('/api/meetings/<mid>', methods=['PUT'])
def api_update(mid):
    m, meetings = find_meeting(mid)
    if not m:
        return jsonify({'error': 'Not found'}), 404
    d = request.json
    for k in ['title','status','transcript','summary','actions','prompts','completedAt','scheduledDate','scheduledTime','notes']:
        if k in d:
            m[k] = d[k]
    save_meetings(meetings)
    return jsonify(m)

@app.route('/api/meetings/<mid>', methods=['DELETE'])
def api_delete(mid):
    meetings = load_meetings()
    meetings = [m for m in meetings if m['id'] != mid]
    save_meetings(meetings)
    return jsonify({'ok': True})

@app.route('/summarize', methods=['POST'])
def summarize():
    d = request.json
    transcript = d.get('transcript', '')
    title = d.get('title', 'Meeting')
    api_key = d.get('api_key') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'No API key. Click the gear icon to add your Anthropic API key.'}), 400
    if not transcript.strip():
        return jsonify({'error': 'No transcript to summarize.'}), 400
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": f"""You are a meeting assistant. Analyze this transcript and return ONLY valid JSON with no markdown formatting.

The JSON must have these keys:
- "summary": a concise 2-3 paragraph summary of the meeting
- "actions": an array of action item strings
- "prompts": an array of objects, each with:
  - "action": the action item this prompt is for
  - "prompt": a ready-to-paste prompt for Claude that helps complete this action item. Be specific and include context from the meeting.

Meeting title: {title}

TRANSCRIPT:
{transcript}"""}]
        )
        text = message.content[0].text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        return jsonify(json.loads(text))
    except json.JSONDecodeError:
        return jsonify({'error': 'Failed to parse AI response. Try again.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meeting Recorder</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#1a1a2e}
.app{max-width:1200px;margin:0 auto;padding:16px}
header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
header h1{font-size:1.5rem}
.gear-btn{background:none;border:none;font-size:22px;cursor:pointer;padding:6px}
.main{display:flex;gap:20px;min-height:500px}
.left-panel{width:340px;flex-shrink:0}
.right-panel{flex:1;background:#fff;border-radius:10px;padding:24px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.panel-title{font-size:1rem;color:#555;margin-bottom:12px}
.today-card{background:#fff;border-radius:8px;padding:14px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.06);cursor:pointer;border-left:4px solid #ccc;transition:all .15s}
.today-card:hover{box-shadow:0 2px 8px rgba(0,0,0,.1)}
.today-card.active{border-left-color:#1a4fa3;background:#f5f8ff}
.today-card.status-recording{border-left-color:#dc3535}
.today-card.status-completed{border-left-color:#28a745}
.today-card h4{font-size:.95rem;margin-bottom:2px}
.today-card .time{font-size:.8rem;color:#888}
.badge{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;margin-left:6px;vertical-align:middle}
.badge-scheduled{background:#e9ecef;color:#666}
.badge-recording{background:#dc3535;color:#fff;animation:pulse 1.2s infinite}
.badge-completed{background:#28a745;color:#fff}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.card-actions{margin-top:8px;display:flex;gap:6px}
.btn{padding:6px 14px;border:none;border-radius:5px;font-size:13px;font-weight:600;cursor:pointer}
.btn-sm{padding:5px 10px;font-size:12px}
.btn-start{background:#28a745;color:#fff}.btn-start:hover{background:#1e7e34}
.btn-stop{background:#dc3535;color:#fff}.btn-stop:hover{background:#b82e2e}
.btn-blue{background:#1a4fa3;color:#fff}.btn-blue:hover{background:#153d80}
.btn-purple{background:#6f42c1;color:#fff}.btn-purple:hover{background:#5a32a3}
.btn-gray{background:#6c757d;color:#fff}.btn-gray:hover{background:#545b62}
.btn-outline{background:#fff;color:#1a4fa3;border:1px solid #1a4fa3}.btn-outline:hover{background:#f0f4ff}
.btn:disabled{opacity:.4;cursor:not-allowed}
.panel-actions{display:flex;gap:8px;margin-top:14px}
.panel-actions .btn{flex:1;padding:10px;font-size:14px}
textarea{width:100%;height:200px;padding:10px;font-size:14px;border:1px solid #ddd;border-radius:6px;font-family:inherit;resize:vertical;margin:10px 0}
input[type=text],input[type=password],input[type=date],input[type=time]{width:100%;padding:9px;font-size:14px;border:1px solid #ddd;border-radius:6px;font-family:inherit}
label{display:block;font-weight:600;font-size:13px;margin:10px 0 4px}
.error{color:#dc3535;font-size:13px;margin:4px 0}
.status-text{font-size:13px;color:#888;margin:4px 0}
.status-text.live{color:#dc3535;font-weight:600}
.timer{font-size:1.1rem;font-weight:700;color:#dc3535;margin:6px 0}
#noSelection{text-align:center;color:#999;padding:80px 20px;font-size:15px}
.result-section{margin-top:20px;padding-top:16px;border-top:1px solid #eee}
.result-section h3{color:#1a4fa3;font-size:.95rem;margin:14px 0 6px}.result-section h3:first-child{margin-top:0}
.result-section p,.result-section pre{font-size:14px;line-height:1.5;white-space:pre-wrap;font-family:inherit}
.result-section ul{margin-left:20px;font-size:14px}.result-section li{margin-bottom:4px}
.prompt-card{background:#f8f9ff;border:1px solid #d4deff;border-radius:8px;padding:12px;margin-bottom:8px;position:relative}
.prompt-action{font-size:12px;font-weight:700;color:#1a4fa3;margin-bottom:3px}
.prompt-text{font-size:13px;white-space:pre-wrap;color:#333;padding-right:50px;line-height:1.5}
.btn-copy{position:absolute;top:10px;right:10px;background:#1a4fa3;color:#fff;border:none;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:600;cursor:pointer}
.btn-copy:hover{background:#153d80}.btn-copy.copied{background:#28a745}
.result-actions{display:flex;gap:8px;margin-top:16px;flex-wrap:wrap}
.past-section{margin-top:30px}
.past-section h2{font-size:1.15rem;margin-bottom:10px}
.search-box{margin-bottom:14px}
.past-card{background:#fff;border-radius:8px;padding:14px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.05);display:flex;justify-content:space-between;align-items:flex-start}
.past-card .past-info{flex:1;cursor:pointer}
.past-card h4{font-size:.9rem;margin-bottom:2px}
.past-card .date{font-size:12px;color:#888}
.past-card .preview{font-size:13px;color:#555;margin-top:4px}
.past-card .past-actions{display:flex;gap:6px;align-items:center;flex-shrink:0;margin-left:10px}
.btn-icon{background:none;border:none;font-size:16px;cursor:pointer;padding:4px;color:#ccc}.btn-icon:hover{color:#dc3535}
.empty{text-align:center;color:#999;padding:20px;font-size:14px}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:100;justify-content:center;align-items:center}
.modal-overlay.show{display:flex}
.modal{background:#fff;border-radius:10px;padding:24px;width:440px;max-width:95vw;box-shadow:0 8px 30px rgba(0,0,0,.15)}
.modal h2{font-size:1.1rem;margin-bottom:8px}
.modal-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px}
@media(max-width:768px){.main{flex-direction:column}.left-panel{width:100%}}
</style>
</head>
<body>
<div class="app">
<header>
  <h1>Meeting Recorder</h1>
  <button class="gear-btn" onclick="toggleSettings()" title="Settings">&#9881;</button>
</header>

<div id="settingsPanel" class="card" style="display:none;background:#fff;border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)">
  <label>Anthropic API Key</label>
  <input type="password" id="apiKey" placeholder="sk-ant-...">
  <p style="font-size:12px;color:#888;margin-top:4px">Saved in your browser only.</p>
</div>

<div class="main">
  <div class="left-panel">
    <div class="panel-title" id="todayLabel">Today's Meetings</div>
    <div id="todayList"><div class="empty">No meetings scheduled.</div></div>
    <div class="panel-actions">
      <button class="btn btn-outline" onclick="showAddModal()">+ Add Meeting</button>
      <button class="btn btn-gray" onclick="adHocMeeting()">Ad Hoc</button>
    </div>
  </div>
  <div class="right-panel">
    <div id="noSelection">Select a meeting from the left panel, or start an ad hoc meeting.</div>
    <div id="activeArea" style="display:none">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 id="activeTitleEl" style="font-size:1.1rem"></h3>
        <span id="activeTime" style="font-size:.85rem;color:#888"></span>
      </div>
      <div id="recControls" style="margin-top:12px;display:flex;gap:8px;align-items:center">
        <button class="btn btn-start" id="startBtn" onclick="startRec()">Start Recording</button>
        <button class="btn btn-stop" id="stopBtn" onclick="stopRec()" style="display:none">Stop Recording</button>
        <span id="statusText" class="status-text"></span>
      </div>
      <div id="timerEl" class="timer" style="display:none">00:00</div>
      <textarea id="transcript" placeholder="Transcript will appear here. You can also type or paste text."></textarea>
      <div id="error" class="error"></div>
      <button class="btn btn-blue" id="sumBtn" onclick="doSummarize()" disabled style="margin-top:8px">Summarize with AI</button>
      <div id="resultArea" class="result-section" style="display:none">
        <h3>Summary</h3>
        <pre id="summaryText"></pre>
        <h3>Action Items</h3>
        <ul id="actionList"></ul>
        <div id="promptsArea" style="display:none">
          <h3>AI Prompts</h3>
          <p style="font-size:12px;color:#888;margin-bottom:8px">Ready-to-paste prompts for Claude</p>
          <div id="promptsList"></div>
        </div>
        <div class="result-actions">
          <button class="btn btn-purple" onclick="downloadPkg(activeMeetingId)">Download Package</button>
          <button class="btn btn-start" onclick="clearRight()">New Meeting</button>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="past-section">
  <h2>Past Meetings</h2>
  <div class="search-box"><input type="text" id="searchBox" placeholder="Search by title or date..." oninput="searchPast(this.value)"></div>
  <div id="pastList"><div class="empty">No past meetings yet.</div></div>
</div>
</div>

<!-- Add Meeting Modal -->
<div class="modal-overlay" id="addModal">
<div class="modal">
  <h2>Add Meeting</h2>
  <form onsubmit="addMeeting(event)">
    <label for="addTitle">Title *</label>
    <input type="text" id="addTitle" required placeholder="e.g. Weekly Standup">
    <label for="addDate">Date</label>
    <input type="date" id="addDate">
    <label for="addTime">Time</label>
    <input type="time" id="addTime">
    <label for="addNotes">Notes / Agenda</label>
    <textarea id="addNotes" style="height:80px" placeholder="Optional agenda items..."></textarea>
    <div class="modal-actions">
      <button type="button" class="btn btn-gray" onclick="hideAddModal()">Cancel</button>
      <button type="submit" class="btn btn-blue">Save</button>
    </div>
  </form>
</div>
</div>


<script>
var allMeetings = [];
var activeMeetingId = null;
var recognition = null;
var isRecording = false;
var timerInterval = null;
var timerSeconds = 0;

// --- Settings ---
var keyInput = document.getElementById('apiKey');
keyInput.value = localStorage.getItem('anthropic_api_key') || '';
keyInput.addEventListener('input', function() { localStorage.setItem('anthropic_api_key', keyInput.value); });
function toggleSettings() {
  var el = document.getElementById('settingsPanel');
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

// --- Helpers ---
function escHtml(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function today() { return new Date().toISOString().split('T')[0]; }
function formatTime(t) {
  if (!t) return '';
  var parts = t.split(':'); var h = parseInt(parts[0]); var m = parts[1];
  var ampm = h >= 12 ? 'PM' : 'AM'; h = h % 12 || 12;
  return h + ':' + m + ' ' + ampm;
}
function formatDate(d) {
  if (!d) return '';
  var parts = d.split('-');
  return parseInt(parts[1]) + '/' + parseInt(parts[2]) + '/' + parts[0];
}
function roundTime() {
  var now = new Date(); var m = Math.ceil(now.getMinutes() / 15) * 15;
  now.setMinutes(m, 0, 0);
  return now.toTimeString().slice(0,5);
}

// --- API ---
async function loadMeetings() {
  try {
    var res = await fetch('/api/meetings');
    allMeetings = await res.json();
  } catch(e) { allMeetings = []; }
  renderToday();
  renderPast();
}

async function apiCreate(data) {
  var res = await fetch('/api/meetings', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) });
  return await res.json();
}

async function apiUpdate(id, data) {
  var res = await fetch('/api/meetings/' + id, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) });
  return await res.json();
}

async function apiDelete(id) {
  await fetch('/api/meetings/' + id, { method:'DELETE' });
}

// --- Render Today ---
function renderToday() {
  var todayStr = today();
  document.getElementById('todayLabel').textContent = "Today's Meetings - " + formatDate(todayStr);
  var list = allMeetings.filter(function(m) { return m.scheduledDate === todayStr; });
  list.sort(function(a,b) { return (a.scheduledTime||'').localeCompare(b.scheduledTime||''); });
  var el = document.getElementById('todayList');
  if (!list.length) { el.innerHTML = '<div class="empty">No meetings scheduled for today.</div>'; return; }
  var html = '';
  list.forEach(function(m) {
    var cls = 'today-card status-' + m.status;
    if (m.id === activeMeetingId) cls += ' active';
    html += '<div class="' + cls + '" onclick="selectMeeting(\'' + m.id + '\')">';
    html += '<h4>' + escHtml(m.title);
    if (m.status === 'scheduled') html += ' <span class="badge badge-scheduled">Scheduled</span>';
    else if (m.status === 'recording') html += ' <span class="badge badge-recording">Recording</span>';
    else if (m.status === 'completed') html += ' <span class="badge badge-completed">Completed</span>';
    html += '</h4>';
    html += '<div class="time">' + formatTime(m.scheduledTime) + '</div>';
    if (m.notes) html += '<div style="font-size:12px;color:#888;margin-top:3px">' + escHtml(m.notes.substring(0,60)) + '</div>';
    html += '</div>';
  });
  el.innerHTML = html;
}


// --- Render Past ---
var searchQuery = '';
function renderPast() {
  var todayStr = today();
  var list = allMeetings.filter(function(m) { return m.status === 'completed' && m.scheduledDate !== todayStr; });
  if (searchQuery) {
    var q = searchQuery.toLowerCase();
    list = list.filter(function(m) { return (m.title||'').toLowerCase().includes(q) || (m.scheduledDate||'').includes(q); });
  }
  list.sort(function(a,b) { return (b.completedAt||b.createdAt||'').localeCompare(a.completedAt||a.createdAt||''); });
  var el = document.getElementById('pastList');
  if (!list.length) { el.innerHTML = '<div class="empty">No past meetings' + (searchQuery ? ' matching "'+escHtml(searchQuery)+'"' : '') + '.</div>'; return; }
  var html = '';
  list.forEach(function(m) {
    var preview = (m.summary||'').substring(0,100) + ((m.summary||'').length > 100 ? '...' : '');
    html += '<div class="past-card">';
    html += '<div class="past-info" onclick="selectMeeting(\'' + m.id + '\')">';
    html += '<h4>' + escHtml(m.title) + '</h4>';
    html += '<div class="date">' + formatDate(m.scheduledDate) + ' at ' + formatTime(m.scheduledTime) + '</div>';
    if (preview) html += '<div class="preview">' + escHtml(preview) + '</div>';
    html += '</div>';
    html += '<div class="past-actions">';
    html += '<button class="btn btn-sm btn-purple" onclick="downloadPkg(\'' + m.id + '\')">Download</button>';
    html += '<button class="btn-icon" onclick="deleteMeeting(\'' + m.id + '\')" title="Delete">&#128465;</button>';
    html += '</div></div>';
  });
  el.innerHTML = html;
}
function searchPast(q) { searchQuery = q; renderPast(); }

// --- Select Meeting ---
function selectMeeting(id) {
  activeMeetingId = id;
  var m = allMeetings.find(function(x) { return x.id === id; });
  if (!m) return;
  document.getElementById('noSelection').style.display = 'none';
  document.getElementById('activeArea').style.display = 'block';
  document.getElementById('activeTitleEl').textContent = m.title;
  document.getElementById('activeTime').textContent = formatTime(m.scheduledTime) + ' - ' + formatDate(m.scheduledDate);
  document.getElementById('transcript').value = m.transcript || '';
  document.getElementById('error').textContent = '';
  document.getElementById('statusText').textContent = '';
  document.getElementById('timerEl').style.display = 'none';

  if (m.status === 'recording') {
    document.getElementById('startBtn').style.display = 'none';
    document.getElementById('stopBtn').style.display = '';
    document.getElementById('statusText').textContent = 'Recording...';
    document.getElementById('statusText').classList.add('live');
    document.getElementById('sumBtn').disabled = true;
  } else if (m.status === 'completed') {
    document.getElementById('startBtn').style.display = 'none';
    document.getElementById('stopBtn').style.display = 'none';
    document.getElementById('sumBtn').disabled = true;
    showResults(m);
  } else {
    document.getElementById('startBtn').style.display = '';
    document.getElementById('stopBtn').style.display = 'none';
    document.getElementById('sumBtn').disabled = !(m.transcript && m.transcript.trim());
  }

  if (m.status !== 'completed') {
    document.getElementById('resultArea').style.display = 'none';
  }
  renderToday();
}

function showResults(m) {
  document.getElementById('summaryText').textContent = m.summary || '';
  var list = document.getElementById('actionList');
  list.innerHTML = '';
  (m.actions||[]).forEach(function(a) { var li = document.createElement('li'); li.textContent = a; list.appendChild(li); });
  var pa = document.getElementById('promptsArea');
  var pl = document.getElementById('promptsList');
  if (m.prompts && m.prompts.length) {
    pl.innerHTML = '';
    m.prompts.forEach(function(p, i) {
      pl.innerHTML += '<div class="prompt-card"><div class="prompt-action">' + escHtml(p.action) + '</div>'
        + '<div class="prompt-text" id="pt-' + i + '">' + escHtml(p.prompt) + '</div>'
        + '<button class="btn-copy" onclick="copyPrompt(this,' + i + ')">Copy</button></div>';
    });
    pa.style.display = '';
  } else { pa.style.display = 'none'; }
  document.getElementById('resultArea').style.display = '';
}

function clearRight() {
  activeMeetingId = null;
  document.getElementById('noSelection').style.display = '';
  document.getElementById('activeArea').style.display = 'none';
  document.getElementById('resultArea').style.display = 'none';
  renderToday();
}

// --- Add Meeting ---
function showAddModal() {
  document.getElementById('addDate').value = today();
  document.getElementById('addTime').value = roundTime();
  document.getElementById('addTitle').value = '';
  document.getElementById('addNotes').value = '';
  document.getElementById('addModal').classList.add('show');
  document.getElementById('addTitle').focus();
}
function hideAddModal() { document.getElementById('addModal').classList.remove('show'); }
async function addMeeting(e) {
  e.preventDefault();
  var m = await apiCreate({
    title: document.getElementById('addTitle').value.trim(),
    scheduledDate: document.getElementById('addDate').value,
    scheduledTime: document.getElementById('addTime').value,
    notes: document.getElementById('addNotes').value.trim()
  });
  hideAddModal();
  allMeetings.push(m);
  renderToday(); renderPast();
  selectMeeting(m.id);
}

async function adHocMeeting() {
  var m = await apiCreate({
    title: 'Ad Hoc Meeting',
    scheduledDate: today(),
    scheduledTime: new Date().toTimeString().slice(0,5),
    status: 'scheduled'
  });
  allMeetings.push(m);
  renderToday();
  selectMeeting(m.id);
  startRec();
}


// --- Recording ---
function startTimer() {
  timerSeconds = 0;
  document.getElementById('timerEl').style.display = '';
  document.getElementById('timerEl').textContent = '00:00';
  timerInterval = setInterval(function() {
    timerSeconds++;
    var m = String(Math.floor(timerSeconds/60)).padStart(2,'0');
    var s = String(timerSeconds%60).padStart(2,'0');
    document.getElementById('timerEl').textContent = m + ':' + s;
  }, 1000);
}
function stopTimer() {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
}

async function startRec() {
  if (!activeMeetingId) return;
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { document.getElementById('error').textContent = 'Speech recognition not supported. Use Chrome.'; return; }

  await apiUpdate(activeMeetingId, { status: 'recording' });
  var m = allMeetings.find(function(x){return x.id===activeMeetingId;});
  if (m) m.status = 'recording';
  renderToday();

  document.getElementById('startBtn').style.display = 'none';
  document.getElementById('stopBtn').style.display = '';
  document.getElementById('statusText').textContent = 'Listening...';
  document.getElementById('statusText').classList.add('live');
  document.getElementById('sumBtn').disabled = true;
  startTimer();

  recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-US';
  var existingText = document.getElementById('transcript').value;
  var fullText = existingText;

  recognition.onresult = function(e) {
    var newText = '';
    for (var i = 0; i < e.results.length; i++) {
      newText += e.results[i][0].transcript + ' ';
    }
    document.getElementById('transcript').value = existingText + newText;
    fullText = existingText + newText;
  };
  recognition.onerror = function(e) {
    if (e.error === 'aborted' || e.error === 'no-speech') return;
    document.getElementById('error').textContent = 'Mic error: ' + e.error;
  };
  recognition.onend = function() {
    if (isRecording) {
      existingText = fullText;
      setTimeout(function() { try { recognition.start(); } catch(e) {} }, 100);
    }
  };
  isRecording = true;
  recognition.start();
}

async function stopRec() {
  isRecording = false;
  if (recognition) { try { recognition.abort(); } catch(e){} recognition = null; }
  stopTimer();
  document.getElementById('startBtn').style.display = '';
  document.getElementById('stopBtn').style.display = 'none';
  document.getElementById('statusText').textContent = 'Stopped';
  document.getElementById('statusText').classList.remove('live');
  document.getElementById('timerEl').style.display = 'none';

  var transcript = document.getElementById('transcript').value.trim();
  document.getElementById('sumBtn').disabled = !transcript;

  if (activeMeetingId) {
    await apiUpdate(activeMeetingId, { status: 'scheduled', transcript: transcript });
    var m = allMeetings.find(function(x){return x.id===activeMeetingId;});
    if (m) { m.status = 'scheduled'; m.transcript = transcript; }
    renderToday();
  }
}

// --- Summarize ---
async function doSummarize() {
  var transcript = document.getElementById('transcript').value.trim();
  if (!transcript) return;
  var m = allMeetings.find(function(x){return x.id===activeMeetingId;});
  if (!m) return;

  document.getElementById('error').textContent = '';
  document.getElementById('statusText').textContent = 'Summarizing...';
  document.getElementById('sumBtn').disabled = true;

  try {
    var res = await fetch('/summarize', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ transcript:transcript, title:m.title, api_key: localStorage.getItem('anthropic_api_key')||'' })
    });
    var data = await res.json();
    if (data.error) { document.getElementById('error').textContent = data.error; document.getElementById('statusText').textContent = ''; document.getElementById('sumBtn').disabled = false; return; }

    m.transcript = transcript;
    m.summary = data.summary || '';
    m.actions = data.actions || [];
    m.prompts = data.prompts || [];
    m.status = 'completed';
    m.completedAt = new Date().toISOString();

    await apiUpdate(m.id, { status:'completed', transcript:transcript, summary:m.summary, actions:m.actions, prompts:m.prompts, completedAt:m.completedAt });

    document.getElementById('statusText').textContent = '';
    document.getElementById('startBtn').style.display = 'none';
    document.getElementById('stopBtn').style.display = 'none';
    showResults(m);
    renderToday(); renderPast();
  } catch(err) {
    document.getElementById('error').textContent = 'Request failed: ' + err.message;
    document.getElementById('sumBtn').disabled = false;
  }
}

function copyPrompt(btn, idx) {
  var text = document.getElementById('pt-' + idx).textContent;
  navigator.clipboard.writeText(text).then(function() {
    btn.textContent = 'Copied!'; btn.classList.add('copied');
    setTimeout(function() { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
  });
}

// --- Download ---
function buildPackageText(m) {
  var c = '='.repeat(45) + '\n  ' + m.title + '\n' + '='.repeat(45) + '\n';
  c += 'Date: ' + formatDate(m.scheduledDate) + ' at ' + formatTime(m.scheduledTime) + '\n\n';
  c += '-'.repeat(45) + '\n  TRANSCRIPT\n' + '-'.repeat(45) + '\n\n' + (m.transcript||'') + '\n\n';
  c += '-'.repeat(45) + '\n  SUMMARY\n' + '-'.repeat(45) + '\n\n' + (m.summary||'') + '\n\n';
  c += '-'.repeat(45) + '\n  ACTION ITEMS\n' + '-'.repeat(45) + '\n\n';
  (m.actions||[]).forEach(function(a,i) { c += '  ' + (i+1) + '. [ ] ' + a + '\n'; });
  c += '\n';
  if (m.prompts && m.prompts.length) {
    c += '-'.repeat(45) + '\n  AI PROMPTS (paste into Claude)\n' + '-'.repeat(45) + '\n\n';
    m.prompts.forEach(function(p,i) { c += '--- Prompt '+(i+1)+': '+p.action+' ---\n\n'+p.prompt+'\n\n'; });
  }
  return c;
}
function downloadPkg(id) {
  var m = allMeetings.find(function(x){return x.id===id;});
  if (!m) return;
  var content = buildPackageText(m);
  var safeTitle = m.title.replace(/[^a-zA-Z0-9 ]/g,'').replace(/\s+/g,'-');
  var dateStr = m.scheduledDate || today();
  var blob = new Blob([content], {type:'text/plain'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a'); a.href = url; a.download = safeTitle+'-'+dateStr+'.txt'; a.click();
  URL.revokeObjectURL(url);
}

// --- Delete ---
async function deleteMeeting(id) {
  if (!confirm('Delete this meeting?')) return;
  await apiDelete(id);
  allMeetings = allMeetings.filter(function(m){return m.id !== id;});
  if (activeMeetingId === id) clearRight();
  renderToday(); renderPast();
}

// --- Init ---
loadMeetings();
</script>
</body>
</html>

"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
