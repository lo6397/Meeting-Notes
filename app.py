from flask import Flask, render_template_string, request, jsonify
import anthropic
import os, json, uuid
from datetime import datetime, date

app = Flask(__name__)

DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'))
os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, 'meetings.json')
EOD_FILE = os.path.join(DATA_DIR, 'eod_summaries.json')
WORKSPACE_FILE = os.path.join(DATA_DIR, 'workspace.json')

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

@app.route('/health')
def health():
    meetings = load_meetings()
    tasks = load_workspace()
    eods = load_eod()
    last_mod = 0
    for f in [DATA_FILE, WORKSPACE_FILE, EOD_FILE]:
        if os.path.exists(f):
            last_mod = max(last_mod, os.path.getmtime(f))
    return jsonify({
        'status': 'ok',
        'meetings_count': len(meetings),
        'workspace_tasks': len(tasks),
        'eod_summaries': len(eods),
        'data_dir': DATA_DIR,
        'last_updated': datetime.fromtimestamp(last_mod).isoformat() if last_mod else None
    })

@app.route('/backup')
def backup():
    import zipfile, io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in ['meetings.json', 'workspace.json', 'eod_summaries.json']:
            fpath = os.path.join(DATA_DIR, fname)
            if os.path.exists(fpath):
                zf.write(fpath, fname)
    buf.seek(0)
    from flask import send_file
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True,
                     download_name='meeting-recorder-backup-' + date.today().isoformat() + '.zip')

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

def load_eod():
    if os.path.exists(EOD_FILE):
        try:
            with open(EOD_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_eod(summaries):
    with open(EOD_FILE, 'w') as f:
        json.dump(summaries, f, indent=2)

@app.route('/api/eod', methods=['GET'])
def api_eod_list():
    return jsonify(load_eod())

@app.route('/api/eod', methods=['POST'])
def api_eod_create():
    d = request.json
    entry = {
        'id': str(uuid.uuid4())[:8],
        'date': d.get('date', date.today().isoformat()),
        'prompt': d.get('prompt', ''),
        'selectedActions': d.get('selectedActions', []),
        'schedule': d.get('schedule', {}),
        'meetings': d.get('meetings', []),
        'createdAt': datetime.now().isoformat()
    }
    summaries = load_eod()
    summaries.append(entry)
    save_eod(summaries)
    return jsonify(entry)

@app.route('/api/eod/<eid>', methods=['DELETE'])
def api_eod_delete(eid):
    summaries = load_eod()
    summaries = [s for s in summaries if s['id'] != eid]
    save_eod(summaries)
    return jsonify({'ok': True})

def load_workspace():
    if os.path.exists(WORKSPACE_FILE):
        try:
            with open(WORKSPACE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_workspace(tasks):
    with open(WORKSPACE_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)

@app.route('/api/workspace', methods=['GET'])
def api_ws_list():
    return jsonify(load_workspace())

@app.route('/api/workspace', methods=['POST'])
def api_ws_create():
    d = request.json
    task = {
        'id': str(uuid.uuid4())[:8],
        'text': d.get('text', '').strip(),
        'source': d.get('source', 'manual'),
        'meetingId': d.get('meetingId'),
        'priority': d.get('priority', 'medium'),
        'dueDate': d.get('dueDate'),
        'aiPrompt': d.get('aiPrompt'),
        'completed': False,
        'completedAt': None,
        'createdAt': datetime.now().isoformat()
    }
    tasks = load_workspace()
    tasks.append(task)
    save_workspace(tasks)
    return jsonify(task)

@app.route('/api/workspace/<tid>', methods=['PUT'])
def api_ws_update(tid):
    tasks = load_workspace()
    for t in tasks:
        if t['id'] == tid:
            d = request.json
            for k in ['text','priority','dueDate','completed','completedAt']:
                if k in d:
                    t[k] = d[k]
            save_workspace(tasks)
            return jsonify(t)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/workspace/<tid>', methods=['DELETE'])
def api_ws_delete(tid):
    tasks = load_workspace()
    tasks = [t for t in tasks if t['id'] != tid]
    save_workspace(tasks)
    return jsonify({'ok': True})

@app.route('/api/chat', methods=['POST'])
def api_chat():
    d = request.json
    messages = d.get('messages', [])
    api_key = d.get('api_key') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'No API key configured.'}), 400
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system="You are a helpful assistant for the COO of Vellum Health, a mobile IV services company serving skilled nursing facilities. Be direct, actionable, and concise. Consider HIPAA compliance where relevant.",
            messages=messages
        )
        return jsonify({'text': resp.content[0].text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            model="claude-haiku-4-5-20251001",
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
.main{display:flex;gap:28px;min-height:500px}
.left-panel{width:340px;flex-shrink:0}
.right-panel{flex:1;background:#fff;border-radius:10px;padding:28px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
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
textarea{width:100%;min-height:120px;max-height:200px;padding:10px;font-size:14px;border:1px solid #ddd;border-radius:6px;font-family:inherit;resize:vertical;margin:10px 0 14px;overflow-y:auto}
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
/* Tabs */
.app-tabs{display:flex;gap:0;margin-bottom:16px;border-bottom:2px solid #ddd;overflow-x:auto;-webkit-overflow-scrolling:touch}
.app-tab{padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer;border:none;background:none;color:#888;border-bottom:2px solid transparent;margin-bottom:-2px;white-space:nowrap;flex-shrink:0}
.app-tab.active{color:#1a4fa3;border-bottom-color:#1a4fa3}
.app-tab:hover{color:#1a4fa3}
.tab-content{display:none}.tab-content.active{display:block}
/* Workspace */
.ws-stats{display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.ws-stat{background:#fff;border-radius:8px;padding:10px 16px;box-shadow:0 1px 3px rgba(0,0,0,.05);text-align:center;flex:1;min-width:100px}
.ws-stat .num{font-size:1.3rem;font-weight:700;color:#1a4fa3}.ws-stat .label{font-size:11px;color:#888}
.ws-filters{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}
.ws-filter{padding:5px 12px;font-size:12px;border-radius:15px;border:1px solid #ddd;background:#fff;cursor:pointer;font-weight:600;color:#555}
.ws-filter.active{background:#1a4fa3;color:#fff;border-color:#1a4fa3}
.ws-task{display:flex;align-items:flex-start;gap:10px;background:#fff;border-radius:8px;padding:12px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.ws-task.done{opacity:.5}
.ws-task input[type=checkbox]{margin-top:4px;width:18px;height:18px;flex-shrink:0}
.ws-task-body{flex:1}
.ws-task-text{font-size:14px}
.ws-task-meta{display:flex;gap:8px;margin-top:4px;flex-wrap:wrap;align-items:center}
.ws-tag{font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600}
.ws-tag-source{background:#e9ecef;color:#555}
.ws-tag-date{background:#fff3cd;color:#856404}
.ws-tag-high{background:#f8d7da;color:#721c24;cursor:pointer}
.ws-tag-medium{background:#fff3cd;color:#856404;cursor:pointer}
.ws-tag-low{background:#d4edda;color:#155724;cursor:pointer}
.ws-tag-due-today{background:#fff3cd;color:#856404;font-weight:700}
.ws-tag-overdue{background:#f8d7da;color:#721c24;font-weight:700}
.ws-sort-bar{display:flex;gap:6px;margin-bottom:10px;align-items:center;font-size:12px;color:#888}
.ws-sort-bar span{margin-right:4px}
.ws-sort-btn{padding:4px 10px;font-size:11px;border-radius:4px;border:1px solid #ddd;background:#fff;cursor:pointer;font-weight:600;color:#555}
.ws-sort-btn.active{background:#1a4fa3;color:#fff;border-color:#1a4fa3}
.ws-task-actions{display:flex;gap:4px;flex-shrink:0;align-items:center}
.ws-task-actions select{font-size:11px;padding:2px 4px;border:1px solid #ddd;border-radius:4px}
.ws-task-actions input[type=date]{font-size:11px;padding:2px 4px;border:1px solid #ddd;border-radius:4px}
.ws-completed-toggle{background:none;border:none;color:#1a4fa3;font-size:13px;font-weight:600;cursor:pointer;padding:8px 0;display:block}
.ws-add-form{display:flex;gap:8px;margin-bottom:16px}
.ws-add-form input[type=text]{flex:1}
.action-add-btn{background:#28a745;color:#fff;border:none;border-radius:4px;padding:3px 8px;font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap}
.action-add-btn:hover{background:#1e7e34}
.action-add-btn.added{background:#6c757d;cursor:default}
/* Ask Claude button */
.btn-ask{background:linear-gradient(135deg,#1a4fa3,#6f42c1);color:#fff;border:none;border-radius:4px;padding:3px 10px;font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap}
.btn-ask:hover{opacity:.85}
/* Chat */
.chat-container{max-width:800px;margin:0 auto}
.chat-back{font-size:13px;color:#1a4fa3;cursor:pointer;background:none;border:none;font-weight:600;margin-bottom:10px;padding:0}
.chat-back:hover{text-decoration:underline}
.chat-source{font-size:12px;color:#6f42c1;background:#f3efff;padding:4px 10px;border-radius:6px;margin-bottom:10px;display:none}
.chat-messages{background:#fff;border-radius:10px;padding:16px;min-height:300px;max-height:500px;overflow-y:auto;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.chat-msg{margin-bottom:14px}
.chat-msg-user{text-align:right}
.chat-msg-user .chat-bubble{background:#1a4fa3;color:#fff;display:inline-block;padding:10px 14px;border-radius:12px 12px 2px 12px;max-width:85%;text-align:left;font-size:14px;line-height:1.5}
.chat-msg-assistant .chat-bubble{background:#f0f2f5;color:#1a1a2e;display:inline-block;padding:10px 14px;border-radius:12px 12px 12px 2px;max-width:85%;font-size:14px;line-height:1.5;white-space:pre-wrap}
.chat-msg-highlight .chat-bubble{box-shadow:0 0 0 2px #6f42c1}
.chat-input-row{display:flex;gap:8px}
.chat-input-row textarea{flex:1;height:60px;resize:none;padding:10px;font-size:14px;border:1px solid #ddd;border-radius:8px;font-family:inherit}
.chat-typing{font-size:13px;color:#888;padding:6px 0;font-style:italic}
/* EOD */
.eod-btn{background:linear-gradient(135deg,#1a4fa3,#6f42c1);color:#fff;border:none;padding:10px 20px;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer}
.eod-btn:hover{opacity:.9}
.eod-overlay{display:none;position:fixed;inset:0;background:#f0f2f5;z-index:200;overflow-y:auto}
.eod-overlay.show{display:block}
.eod-container{max-width:1100px;margin:0 auto;padding:24px}
.eod-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
.eod-header h2{font-size:1.4rem}
.eod-main{display:flex;gap:24px}
.eod-left,.eod-right{flex:1;background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.eod-group{margin-bottom:16px}
.eod-group h4{color:#1a4fa3;font-size:.9rem;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid #eee}
.eod-item{display:flex;align-items:flex-start;gap:8px;padding:6px 0;font-size:14px}
.eod-item input[type=checkbox]{margin-top:3px;width:16px;height:16px}
.eod-bulk{display:flex;gap:8px;margin-bottom:12px}
.eod-bulk button{font-size:12px;padding:4px 10px}
.eod-right label{font-weight:600;font-size:13px;display:block;margin:12px 0 4px}
.eod-right label:first-child{margin-top:0}
.eod-right input,.eod-right select,.eod-right textarea{width:100%;padding:8px;font-size:14px;border:1px solid #ddd;border-radius:6px;font-family:inherit}
.eod-right textarea{height:80px;resize:vertical}
.eod-actions{display:flex;gap:8px;margin-top:20px;flex-wrap:wrap}
.eod-prompt-box{background:#f8f9ff;border:1px solid #d4deff;border-radius:8px;padding:16px;margin-top:20px;white-space:pre-wrap;font-size:13px;line-height:1.5;max-height:400px;overflow-y:auto;font-family:inherit}
.past-eod{margin-top:24px}
.past-eod h3{margin-bottom:10px;font-size:1rem}
.past-eod-card{background:#fff;border-radius:8px;padding:14px;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,.05);display:flex;justify-content:space-between;align-items:center}
.past-eod-card .info{font-size:14px}.past-eod-card .date{font-size:12px;color:#888}
@media(max-width:768px){.main{flex-direction:column}.left-panel{width:100%}.eod-main{flex-direction:column}}
</style>
</head>
<body>
<div class="app">
<header>
  <h1>Meeting Recorder</h1>
  <div style="display:flex;gap:10px;align-items:center">
    <button class="eod-btn" onclick="showEOD()">&#127769; End of Day Review</button>
    <button class="gear-btn" onclick="toggleSettings()" title="Settings">&#9881;</button>
  </div>
</header>

<div id="settingsPanel" class="card" style="display:none;background:#fff;border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)">
  <label>Anthropic API Key</label>
  <input type="password" id="apiKey" placeholder="sk-ant-...">
  <p style="font-size:12px;color:#888;margin-top:4px">Saved in your browser only.</p>
</div>

<div class="app-tabs">
  <button class="app-tab active" onclick="switchAppTab('meetings')">&#128197; Today</button>
  <button class="app-tab" onclick="switchAppTab('workspace')">&#9745; Workspace</button>
  <button class="app-tab" onclick="switchAppTab('past')">&#128214; Past</button>
  <button class="app-tab" onclick="switchAppTab('chat')" id="chatTabBtn">&#128172; Chat</button>
</div>

<div id="tab-meetings" class="tab-content active">
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
</div><!-- end tab-meetings -->

<div id="tab-workspace" class="tab-content">
  <div class="ws-stats" id="wsStats"></div>
  <div class="ws-filters" id="wsFilters">
    <button class="ws-filter active" onclick="setWsFilter('all')">All</button>
    <button class="ws-filter" onclick="setWsFilter('high')">High</button>
    <button class="ws-filter" onclick="setWsFilter('medium')">Medium</button>
    <button class="ws-filter" onclick="setWsFilter('low')">Low</button>
    <button class="ws-filter" onclick="setWsFilter('due-today')">Due Today</button>
    <button class="ws-filter" onclick="setWsFilter('overdue')">Overdue</button>
    <button class="ws-filter" onclick="setWsFilter('this-week')">This Week</button>
    <button class="ws-filter" onclick="setWsFilter('completed')">Completed</button>
  </div>
  <div class="ws-sort-bar">
    <span>Sort by:</span>
    <button class="ws-sort-btn active" onclick="setWsSort('priority')">Priority</button>
    <button class="ws-sort-btn" onclick="setWsSort('due')">Due Date</button>
    <button class="ws-sort-btn" onclick="setWsSort('added')">Date Added</button>
    <button class="ws-sort-btn" onclick="setWsSort('alpha')">A-Z</button>
  </div>
  <div class="ws-add-form">
    <input type="text" id="wsNewTask" placeholder="Add a new task..." onkeydown="if(event.key==='Enter')addManualTask()">
    <button class="btn btn-start" onclick="addManualTask()">+ Add</button>
  </div>
  <div id="wsList"></div>
  <button class="ws-completed-toggle" id="wsCompletedToggle" onclick="toggleCompletedTasks()" style="display:none"></button>
  <div id="wsCompletedList" style="display:none"></div>
</div>

<div id="tab-past" class="tab-content">
<div class="past-section" style="margin-top:0">
  <h2>Past Meetings</h2>
  <div class="search-box"><input type="text" id="searchBox" placeholder="Search by title or date..." oninput="searchPast(this.value)"></div>
  <div id="pastList"><div class="empty">No past meetings yet.</div></div>
</div>
</div>

<div id="tab-chat" class="tab-content">
<div class="chat-container">
  <button class="chat-back" id="chatBack" onclick="goBackFromChat()" style="display:none"></button>
  <div class="chat-source" id="chatSource"></div>
  <div class="chat-messages" id="chatMessages">
    <div class="empty">Start a conversation with Claude, or click "Ask Claude" from any task or meeting.</div>
  </div>
  <div class="chat-typing" id="chatTyping" style="display:none">Claude is thinking...</div>
  <div class="chat-input-row">
    <textarea id="chatInput" placeholder="Type a message..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChatMsg();}"></textarea>
    <button class="btn btn-blue" onclick="sendChatMsg()">Send</button>
  </div>
</div>
</div>

<!-- EOD Overlay -->
<div class="eod-overlay" id="eodOverlay">
<div class="eod-container">
  <div class="eod-header">
    <h2>End of Day Review</h2>
    <button class="btn btn-gray" onclick="hideEOD()">Back to Meetings</button>
  </div>
  <div class="eod-main">
    <div class="eod-left">
      <h3 style="margin-bottom:10px">Today's Action Items</h3>
      <div class="eod-bulk">
        <button class="btn btn-sm btn-outline" onclick="eodSelectAll()">Select All</button>
        <button class="btn btn-sm btn-gray" onclick="eodClearAll()">Clear All</button>
      </div>
      <div id="eodActions"><div class="empty">No completed meetings today.</div></div>
      <h4 style="margin-top:16px;color:#6f42c1;font-size:.9rem">Carry-over Tasks from Workspace</h4>
      <div id="eodCarryover"><div class="empty" style="font-size:13px">No incomplete workspace tasks.</div></div>
    </div>
    <div class="eod-right">
      <h3 style="margin-bottom:10px">Schedule Inputs</h3>
      <label>What time do you start tomorrow?</label>
      <input type="time" id="eodStartTime" value="08:00">
      <label>How many hours are you available?</label>
      <input type="number" id="eodHours" value="8" min="1" max="16" step="0.5">
      <label>Any existing commitments tomorrow?</label>
      <textarea id="eodCommitments" placeholder="e.g. 10am dentist, 2pm board meeting..."></textarea>
      <label>Priorities for tomorrow?</label>
      <select id="eodPriority">
        <option value="Mixed">Mixed</option>
        <option value="Catch up">Catch up</option>
        <option value="Strategic">Strategic</option>
      </select>
    </div>
  </div>
  <div class="eod-actions" style="margin-top:20px">
    <button class="eod-btn" onclick="generateMasterPrompt()">Generate Master Prompt</button>
  </div>
  <div id="eodPromptArea" style="display:none">
    <div class="eod-prompt-box" id="eodPromptText"></div>
    <div class="eod-actions">
      <button class="btn-ask" style="padding:8px 16px;font-size:14px" onclick="sendEODToChat()">Send to Claude &#10024;</button>
      <button class="btn btn-blue" onclick="copyEODPrompt()">Copy Prompt</button>
      <button class="btn btn-start" onclick="window.open('https://claude.ai','_blank')">Open Claude</button>
      <button class="btn btn-purple" onclick="downloadEODPrompt()">Download as .txt</button>
    </div>
  </div>
  <div class="past-eod" id="pastEODSection">
    <h3>Past EOD Summaries</h3>
    <div id="pastEODList"><div class="empty">No past summaries.</div></div>
  </div>
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
    html += '<button class="btn-ask" onclick="askClaudePastMeeting(\'' + m.id + '\')">Ask Claude &#10024;</button>';
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
  (m.actions||[]).forEach(function(a, idx) {
    var li = document.createElement('li');
    li.style.cssText = 'display:flex;align-items:center;gap:8px';
    li.innerHTML = '<span style="flex:1">' + escHtml(a) + '</span>';
    var inWs = wsTaskExists(a, m.id);
    var btn = document.createElement('button');
    btn.className = 'action-add-btn' + (inWs ? ' added' : '');
    btn.textContent = inWs ? '\u2713 In Workspace' : '+ Workspace';
    if (!inWs) btn.onclick = function() { addToWorkspace(a, m.title, m.id, btn, m.prompts); };
    li.appendChild(btn);
    list.appendChild(li);
  });
  var pa = document.getElementById('promptsArea');
  var pl = document.getElementById('promptsList');
  if (m.prompts && m.prompts.length) {
    pl.innerHTML = '';
    m.prompts.forEach(function(p, i) {
      pl.innerHTML += '<div class="prompt-card"><div class="prompt-action">' + escHtml(p.action) + '</div>'
        + '<div class="prompt-text" id="pt-' + i + '">' + escHtml(p.prompt) + '</div>'
        + '<button class="btn-copy" onclick="copyPrompt(this,' + i + ')">Copy</button>'
        + '<button class="btn-ask" style="position:absolute;top:10px;right:70px" onclick="sendToClaudeChat(document.getElementById(\'pt-' + i + '\').textContent,\'Prompt: ' + escHtml(p.action).replace(/'/g,"\\'") + '\')">Ask Claude &#10024;</button></div>';
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

// --- App Tabs ---
function switchAppTab(tab) {
  document.querySelectorAll('.app-tab').forEach(function(b) { b.classList.remove('active'); });
  document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
  document.getElementById('tab-' + tab).classList.add('active');
  var tabs = document.querySelectorAll('.app-tab');
  if (tab === 'meetings') tabs[0].classList.add('active');
  else if (tab === 'workspace') { tabs[1].classList.add('active'); renderWorkspace(); }
  else if (tab === 'past') tabs[2].classList.add('active');
  else if (tab === 'chat') tabs[3].classList.add('active');
}

// --- Workspace ---
var allTasks = [];
var wsFilter = 'all';
var wsSort = 'priority';
var showCompleted = false;

async function loadWorkspace() {
  try { var r = await fetch('/api/workspace'); allTasks = await r.json(); } catch(e) { allTasks = []; }
}

function wsTaskExists(text, meetingId) {
  return allTasks.some(function(t) { return t.text === text && t.meetingId === meetingId; });
}

async function addToWorkspace(text, source, meetingId, btn, prompts) {
  // Find the matching AI prompt for this action item
  var aiPrompt = null;
  if (prompts && prompts.length) {
    var match = prompts.find(function(p) { return p.action === text; });
    if (match) aiPrompt = match.prompt;
  }
  var res = await fetch('/api/workspace', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ text:text, source:source, meetingId:meetingId, priority:'medium', aiPrompt:aiPrompt }) });
  var task = await res.json();
  allTasks.push(task);
  if (btn) { btn.textContent = '\u2713 In Workspace'; btn.classList.add('added'); btn.onclick = null; }
}

async function addManualTask() {
  var input = document.getElementById('wsNewTask');
  var text = input.value.trim();
  if (!text) return;
  await fetch('/api/workspace', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ text:text, source:'manual', priority:'medium' }) });
  input.value = '';
  await loadWorkspace();
  renderWorkspace();
}

async function toggleWsTask(id) {
  var t = allTasks.find(function(x){return x.id===id;});
  if (!t) return;
  var now = t.completed ? null : new Date().toISOString();
  await fetch('/api/workspace/'+id, { method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ completed:!t.completed, completedAt:now }) });
  t.completed = !t.completed;
  t.completedAt = now;
  renderWorkspace();
}

async function updateWsPriority(id, val) {
  await fetch('/api/workspace/'+id, { method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ priority:val }) });
  var t = allTasks.find(function(x){return x.id===id;}); if (t) t.priority = val;
  renderWorkspace();
}

async function updateWsDue(id, val) {
  await fetch('/api/workspace/'+id, { method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ dueDate:val||null }) });
  var t = allTasks.find(function(x){return x.id===id;}); if (t) t.dueDate = val||null;
  renderWorkspace();
}

async function deleteWsTask(id) {
  await fetch('/api/workspace/'+id, { method:'DELETE' });
  allTasks = allTasks.filter(function(t){return t.id!==id;});
  renderWorkspace();
}

function setWsFilter(f) {
  wsFilter = f;
  document.querySelectorAll('.ws-filter').forEach(function(b) { b.classList.remove('active'); });
  event.target.classList.add('active');
  renderWorkspace();
}

function setWsSort(s) {
  wsSort = s;
  document.querySelectorAll('.ws-sort-btn').forEach(function(b) { b.classList.remove('active'); });
  event.target.classList.add('active');
  renderWorkspace();
}

async function cyclePriority(id) {
  var t = allTasks.find(function(x){return x.id===id;});
  if (!t || t.completed) return;
  var cycle = {low:'medium', medium:'high', high:'low'};
  var next = cycle[t.priority] || 'medium';
  await fetch('/api/workspace/'+id, { method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ priority:next }) });
  t.priority = next;
  renderWorkspace();
}

function toggleCompletedTasks() {
  showCompleted = !showCompleted;
  renderWorkspace();
}

function getWeekEnd() {
  var d = new Date(); var day = d.getDay(); var diff = 7 - day;
  d.setDate(d.getDate() + diff); return d.toISOString().split('T')[0];
}

function filterTasks(tasks) {
  var todayStr = today();
  var weekEnd = getWeekEnd();
  switch(wsFilter) {
    case 'high': return tasks.filter(function(t){return !t.completed && t.priority==='high';});
    case 'medium': return tasks.filter(function(t){return !t.completed && t.priority==='medium';});
    case 'low': return tasks.filter(function(t){return !t.completed && t.priority==='low';});
    case 'due-today': return tasks.filter(function(t){return !t.completed && t.dueDate===todayStr;});
    case 'overdue': return tasks.filter(function(t){return !t.completed && t.dueDate && t.dueDate<todayStr;});
    case 'this-week': return tasks.filter(function(t){return !t.completed && t.dueDate && t.dueDate>=todayStr && t.dueDate<=weekEnd;});
    case 'completed': return tasks.filter(function(t){return t.completed;});
    default: return tasks;
  }
}

function renderWorkspace() {
  var todayStr = today();
  var weekEnd = getWeekEnd();
  var incomplete = allTasks.filter(function(t){return !t.completed;});
  var dueToday = allTasks.filter(function(t){return !t.completed && t.dueDate===todayStr;});
  var overdue = allTasks.filter(function(t){return !t.completed && t.dueDate && t.dueDate<todayStr;});
  var highP = allTasks.filter(function(t){return !t.completed && t.priority==='high';});
  var weekStart = new Date(); weekStart.setDate(weekStart.getDate() - weekStart.getDay());
  var completedWeek = allTasks.filter(function(t){return t.completed && t.completedAt && t.completedAt>=weekStart.toISOString();});
  document.getElementById('wsStats').innerHTML =
    '<div class="ws-stat"><div class="num">'+incomplete.length+'</div><div class="label">Open Tasks</div></div>'
    +'<div class="ws-stat"><div class="num">'+dueToday.length+'</div><div class="label">Due Today</div></div>'
    +'<div class="ws-stat"><div class="num">'+(overdue.length||0)+'</div><div class="label">Overdue</div></div>'
    +'<div class="ws-stat"><div class="num">'+highP.length+'</div><div class="label">High Priority</div></div>'
    +'<div class="ws-stat"><div class="num">'+completedWeek.length+'</div><div class="label">Done This Week</div></div>';

  var filtered = filterTasks(allTasks);
  var open = filtered.filter(function(t){return !t.completed;});
  var done = filtered.filter(function(t){return t.completed;});
  // Sort
  var po = {high:0,medium:1,low:2};
  switch(wsSort) {
    case 'priority': open.sort(function(a,b){return (po[a.priority]||1)-(po[b.priority]||1);}); break;
    case 'due': open.sort(function(a,b){return (a.dueDate||'9999')< (b.dueDate||'9999')?-1:1;}); break;
    case 'added': open.sort(function(a,b){return (b.createdAt||'').localeCompare(a.createdAt||'');}); break;
    case 'alpha': open.sort(function(a,b){return (a.text||'').toLowerCase().localeCompare((b.text||'').toLowerCase());}); break;
  }

  var el = document.getElementById('wsList');
  if (!open.length && wsFilter !== 'completed') { el.innerHTML = '<div class="empty">No tasks match this filter.</div>'; }
  else { el.innerHTML = open.map(renderTaskCard).join(''); }

  var toggle = document.getElementById('wsCompletedToggle');
  var cList = document.getElementById('wsCompletedList');
  if (done.length) {
    toggle.style.display = '';
    toggle.textContent = (showCompleted ? '\u25BC' : '\u25B6') + ' Completed (' + done.length + ')';
    cList.style.display = showCompleted ? '' : 'none';
    cList.innerHTML = done.map(renderTaskCard).join('');
  } else { toggle.style.display = 'none'; cList.style.display = 'none'; }
}

function renderTaskCard(t) {
  var todayStr = today();
  var cls = 'ws-task' + (t.completed ? ' done' : '');
  var html = '<div class="' + cls + '">';
  html += '<input type="checkbox" ' + (t.completed ? 'checked' : '') + ' onchange="toggleWsTask(\'' + t.id + '\')">';
  html += '<div class="ws-task-body">';
  html += '<div class="ws-task-text">' + escHtml(t.text) + '</div>';
  html += '<div class="ws-task-meta">';
  html += '<span class="ws-tag ws-tag-source">From: ' + escHtml(t.source) + '</span>';
  // Clickable priority badge
  var pLabel = {high:'High',medium:'Medium',low:'Low'}[t.priority||'medium'] || 'Medium';
  if (!t.completed) {
    html += '<span class="ws-tag ws-tag-' + (t.priority||'medium') + '" onclick="cyclePriority(\'' + t.id + '\')" title="Click to change priority">' + pLabel + '</span>';
  } else {
    html += '<span class="ws-tag ws-tag-' + (t.priority||'medium') + '">' + pLabel + '</span>';
  }
  // Due date with overdue/today highlighting
  if (t.dueDate) {
    var dueCls = 'ws-tag ws-tag-date';
    if (!t.completed && t.dueDate < todayStr) dueCls = 'ws-tag ws-tag-overdue';
    else if (!t.completed && t.dueDate === todayStr) dueCls = 'ws-tag ws-tag-due-today';
    html += '<span class="' + dueCls + '">Due: ' + t.dueDate + '</span>';
  }
  html += '<span style="font-size:11px;color:#aaa">' + (t.createdAt||'').split('T')[0] + '</span>';
  html += '</div></div>';
  html += '<div class="ws-task-actions">';
  if (!t.completed) {
    html += '<input type="date" value="'+(t.dueDate||'')+'" onchange="updateWsDue(\'' + t.id + '\',this.value)" title="Set due date">';
  }
  if (!t.completed) {
    html += '<button class="btn-ask" onclick="askClaudeWorkspaceTask(\'' + t.id + '\')">Ask Claude &#10024;</button>';
  }
  html += '<button class="btn-icon" onclick="deleteWsTask(\'' + t.id + '\')" title="Delete">&#128465;</button>';
  html += '</div></div>';
  return html;
}

// --- End of Day ---
var eodPromptGenerated = '';

function showEOD() {
  document.getElementById('eodOverlay').classList.add('show');
  document.getElementById('eodPromptArea').style.display = 'none';
  eodPromptGenerated = '';
  renderEODActions();
  loadPastEOD();
}
function hideEOD() {
  document.getElementById('eodOverlay').classList.remove('show');
}

function renderEODActions() {
  var todayStr = today();
  var completed = allMeetings.filter(function(m) { return m.scheduledDate === todayStr && m.status === 'completed' && m.actions && m.actions.length; });
  var el = document.getElementById('eodActions');
  if (!completed.length) { el.innerHTML = '<div class="empty">No completed meetings with action items today.</div>'; return; }
  var html = '';
  completed.forEach(function(m) {
    html += '<div class="eod-group"><h4>' + escHtml(m.title) + ' (' + formatTime(m.scheduledTime) + ')</h4>';
    m.actions.forEach(function(a, i) {
      html += '<div class="eod-item"><input type="checkbox" checked data-meeting="' + escHtml(m.id) + '" data-action="' + i + '" class="eod-cb"><span>' + escHtml(a) + '</span></div>';
    });
    html += '</div>';
  });
  el.innerHTML = html;
  // Carry-over workspace tasks
  var carryover = allTasks.filter(function(t){return !t.completed;});
  var cel = document.getElementById('eodCarryover');
  if (!carryover.length) { cel.innerHTML = '<div class="empty" style="font-size:13px">No incomplete workspace tasks.</div>'; }
  else {
    var ch = '';
    carryover.forEach(function(t) {
      ch += '<div class="eod-item"><input type="checkbox" checked class="eod-ws-cb" data-wsid="' + t.id + '"><span>' + escHtml(t.text) + ' <span class="ws-tag ws-tag-source" style="font-size:10px">'+escHtml(t.source)+'</span></span></div>';
    });
    cel.innerHTML = ch;
  }
}

function eodSelectAll() { document.querySelectorAll('.eod-cb,.eod-ws-cb').forEach(function(cb) { cb.checked = true; }); }
function eodClearAll() { document.querySelectorAll('.eod-cb,.eod-ws-cb').forEach(function(cb) { cb.checked = false; }); }

function getSelectedActions() {
  var selected = [];
  document.querySelectorAll('.eod-cb:checked').forEach(function(cb) {
    var mid = cb.getAttribute('data-meeting');
    var aidx = parseInt(cb.getAttribute('data-action'));
    var m = allMeetings.find(function(x) { return x.id === mid; });
    if (m && m.actions[aidx]) {
      selected.push({ meeting: m.title, action: m.actions[aidx] });
    }
  });
  return selected;
}

function getTodayMeetingSummaries() {
  var todayStr = today();
  return allMeetings.filter(function(m) { return m.scheduledDate === todayStr && m.status === 'completed'; })
    .map(function(m) { return { title: m.title, summary: m.summary, time: m.scheduledTime }; });
}

function generateMasterPrompt() {
  var selected = getSelectedActions();
  // Gather carry-over workspace tasks
  var carryoverSelected = [];
  document.querySelectorAll('.eod-ws-cb:checked').forEach(function(cb) {
    var tid = cb.getAttribute('data-wsid');
    var t = allTasks.find(function(x){return x.id===tid;});
    if (t) carryoverSelected.push(t);
  });
  if (!selected.length && !carryoverSelected.length) { alert('Please select at least one action item.'); return; }

  var startTime = document.getElementById('eodStartTime').value || '08:00';
  var hours = document.getElementById('eodHours').value || '8';
  var commitments = document.getElementById('eodCommitments').value.trim();
  var priority = document.getElementById('eodPriority').value;
  var meetings = getTodayMeetingSummaries();

  var tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  var tomorrowStr = tomorrow.toLocaleDateString('en-US', { weekday:'long', month:'long', day:'numeric', year:'numeric' });

  var prompt = '';
  prompt += '=== CONTEXT ===\n\n';
  prompt += 'You are an AI assistant helping the COO of Vellum Health, a mobile IV services company serving skilled nursing facilities. The COO manages clinical operations, scheduling, HR, finance, and client relationships. Always consider HIPAA compliance. Be direct and actionable.\n\n';

  prompt += '=== TODAY\'S ACCOMPLISHMENTS ===\n\n';
  if (meetings.length) {
    meetings.forEach(function(m) {
      prompt += '* ' + m.title + ' (' + formatTime(m.time) + ')\n';
      if (m.summary) prompt += '  ' + m.summary.substring(0, 200) + '\n';
      prompt += '\n';
    });
  } else {
    prompt += 'No meetings completed today.\n\n';
  }

  prompt += '=== SELECTED ACTION ITEMS ===\n\n';
  var grouped = {};
  selected.forEach(function(s) {
    if (!grouped[s.meeting]) grouped[s.meeting] = [];
    grouped[s.meeting].push(s.action);
  });
  var num = 1;
  Object.keys(grouped).forEach(function(mtg) {
    prompt += 'From "' + mtg + '":\n';
    grouped[mtg].forEach(function(a) {
      prompt += '  ' + num + '. ' + a + '\n';
      num++;
    });
    prompt += '\n';
  });

  if (carryoverSelected.length) {
    prompt += '=== CARRY-OVER TASKS FROM WORKSPACE ===\n\n';
    carryoverSelected.forEach(function(t, i) {
      prompt += '  ' + (num+i) + '. ' + t.text + ' [' + t.priority + ' priority' + (t.dueDate ? ', due ' + t.dueDate : '') + ', from: ' + t.source + ']\n';
    });
    prompt += '\n';
  }

  prompt += '=== INSTRUCTIONS ===\n\n';
  prompt += 'Please do the following:\n\n';
  prompt += '1. For each action item above, provide a specific solution or draft the deliverable needed (email, document, workflow, etc.)\n\n';
  prompt += '2. Create an optimized schedule for ' + tomorrowStr + ' starting at ' + formatTime(startTime) + ' with ' + hours + ' hours available';
  if (commitments) prompt += ', accounting for: ' + commitments;
  prompt += '\n\n';
  prompt += '3. Group similar tasks together to minimize context switching\n\n';
  prompt += '4. Flag any items that are urgent or time-sensitive\n\n';
  prompt += '5. Suggest which items to delegate vs handle personally\n\n';
  prompt += '6. End with a prioritized top 3 focus areas for tomorrow\n\n';
  prompt += 'Priority mode: ' + priority + '\n';

  eodPromptGenerated = prompt;
  document.getElementById('eodPromptText').textContent = prompt;
  document.getElementById('eodPromptArea').style.display = '';

  // Save to server
  fetch('/api/eod', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      date: today(),
      prompt: prompt,
      selectedActions: selected,
      schedule: { startTime: startTime, hours: hours, commitments: commitments, priority: priority },
      meetings: meetings.map(function(m) { return m.title; })
    })
  }).then(function() { loadPastEOD(); });
}

function copyEODPrompt() {
  navigator.clipboard.writeText(eodPromptGenerated).then(function() {
    var btns = document.querySelectorAll('.eod-actions .btn-blue');
    if (btns.length > 1) { var b = btns[1]; b.textContent = 'Copied!'; setTimeout(function(){ b.textContent = 'Copy Prompt'; }, 2000); }
  });
}

function downloadEODPrompt() {
  var blob = new Blob([eodPromptGenerated], { type: 'text/plain' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'EOD-Review-' + today() + '.txt';
  a.click();
  URL.revokeObjectURL(url);
}

async function loadPastEOD() {
  try {
    var res = await fetch('/api/eod');
    var data = await res.json();
    var el = document.getElementById('pastEODList');
    if (!data.length) { el.innerHTML = '<div class="empty">No past summaries.</div>'; return; }
    data.sort(function(a, b) { return (b.createdAt || '').localeCompare(a.createdAt || ''); });
    var html = '';
    data.forEach(function(e) {
      html += '<div class="past-eod-card">';
      html += '<div class="info"><strong>EOD Review</strong> <span class="date">' + formatDate(e.date) + '</span>';
      html += ' &mdash; ' + (e.selectedActions || []).length + ' action items, ' + (e.meetings || []).length + ' meetings</div>';
      html += '<div style="display:flex;gap:6px">';
      html += '<button class="btn btn-sm btn-purple" onclick="downloadPastEOD(\'' + e.id + '\')">Download</button>';
      html += '<button class="btn-icon" onclick="deletePastEOD(\'' + e.id + '\')" title="Delete">&#128465;</button>';
      html += '</div></div>';
    });
    el.innerHTML = html;
    window._eodData = data;
  } catch(err) {}
}

function downloadPastEOD(id) {
  var entry = (window._eodData || []).find(function(e) { return e.id === id; });
  if (!entry || !entry.prompt) return;
  var blob = new Blob([entry.prompt], { type: 'text/plain' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = 'EOD-Review-' + entry.date + '.txt';
  a.click();
  URL.revokeObjectURL(url);
}

async function deletePastEOD(id) {
  if (!confirm('Delete this EOD summary?')) return;
  await fetch('/api/eod/' + id, { method: 'DELETE' });
  loadPastEOD();
}

// --- Claude Chat ---
var chatHistory = []; // {role, content}
var previousTab = 'meetings';

function sendToClaudeChat(message, sourceLabel) {
  previousTab = getCurrentTab();
  switchAppTab('chat');
  document.getElementById('chatBack').style.display = '';
  document.getElementById('chatBack').textContent = '\u2190 Back to ' + previousTab;
  if (sourceLabel) {
    document.getElementById('chatSource').style.display = '';
    document.getElementById('chatSource').textContent = 'Sending from: ' + sourceLabel;
  }
  document.getElementById('chatInput').value = message;
  sendChatMsg(true);
}

function getCurrentTab() {
  if (document.getElementById('tab-meetings').classList.contains('active')) return 'meetings';
  if (document.getElementById('tab-workspace').classList.contains('active')) return 'workspace';
  if (document.getElementById('tab-past').classList.contains('active')) return 'past';
  return 'meetings';
}

function goBackFromChat() {
  switchAppTab(previousTab);
  document.getElementById('chatBack').style.display = 'none';
  document.getElementById('chatSource').style.display = 'none';
}

async function sendChatMsg(highlight) {
  var input = document.getElementById('chatInput');
  var text = input.value.trim();
  if (!text) return;
  input.value = '';

  chatHistory.push({ role: 'user', content: text });
  renderChatMessages(highlight);

  document.getElementById('chatTyping').style.display = '';

  try {
    var res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: chatHistory, api_key: localStorage.getItem('anthropic_api_key') || '' })
    });
    var data = await res.json();
    document.getElementById('chatTyping').style.display = 'none';
    if (data.error) {
      chatHistory.push({ role: 'assistant', content: 'Error: ' + data.error });
    } else {
      chatHistory.push({ role: 'assistant', content: data.text });
    }
    renderChatMessages(false);
  } catch (err) {
    document.getElementById('chatTyping').style.display = 'none';
    chatHistory.push({ role: 'assistant', content: 'Request failed: ' + err.message });
    renderChatMessages(false);
  }
}

function renderChatMessages(highlightLast) {
  var el = document.getElementById('chatMessages');
  var html = '';
  chatHistory.forEach(function(msg, i) {
    var cls = 'chat-msg chat-msg-' + msg.role;
    if (highlightLast && msg.role === 'user' && i === chatHistory.length - 1) cls += ' chat-msg-highlight';
    html += '<div class="' + cls + '"><div class="chat-bubble">' + escHtml(msg.content) + '</div></div>';
  });
  if (!html) html = '<div class="empty">Start a conversation with Claude, or click "Ask Claude" from any task or meeting.</div>';
  el.innerHTML = html;
  el.scrollTop = el.scrollHeight;
}

function askClaudeWorkspaceTask(id) {
  var t = allTasks.find(function(x) { return x.id === id; });
  if (!t) return;
  var msg;
  if (t.aiPrompt) {
    msg = t.aiPrompt;
  } else {
    msg = 'I have a task: ' + t.text + '\nPriority: ' + (t.priority || 'medium') + (t.dueDate ? '\nDue: ' + t.dueDate : '') + (t.source && t.source !== 'manual' ? '\nThis came from: ' + t.source : '') + '\nPlease help me complete this with specific actionable steps.';
  }
  sendToClaudeChat(msg, 'Task: ' + t.text.substring(0, 40));
}

function askClaudePastMeeting(id) {
  var m = allMeetings.find(function(x) { return x.id === id; });
  if (!m) return;
  var incompleteActions = (m.actions || []).join(', ') || 'None listed';
  var msg = 'Here is a past meeting summary I\'d like help with:\nMeeting: ' + m.title + ' on ' + formatDate(m.scheduledDate) + '\nSummary: ' + (m.summary || 'No summary') + '\nAction items: ' + incompleteActions + '\nWhat should I prioritize and how should I approach these?';
  sendToClaudeChat(msg, 'Meeting: ' + m.title);
}

function sendEODToChat() {
  if (!eodPromptGenerated) return;
  hideEOD();
  sendToClaudeChat(eodPromptGenerated, 'End of Day Review');
}

// --- Init ---
loadMeetings();
loadWorkspace();
</script>
</body>
</html>

"""

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
