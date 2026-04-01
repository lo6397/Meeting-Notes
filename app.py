from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Meeting Recorder</title>
<style>
  body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }
  h1 { text-align: center; margin: 0; }
  .card { background: white; border-radius: 10px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
  input[type=text] { width: 100%; padding: 10px; font-size: 15px; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 16px; box-sizing: border-box; }
  button { cursor: pointer; }
  .btn-record { background: #dc3535; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 15px; }
  .btn-record:hover { background: #b82e2e; }
  .btn-record.recording { animation: pulse 1.2s infinite; }
  .btn-stop { background: #555; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 15px; }
  .btn-stop:hover { background: #333; }
  .btn-summarize { background: #1a4fa3; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 15px; margin-top: 12px; }
  .btn-summarize:hover { background: #153d80; }
  .btn-new { background: #28a745; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 15px; margin-top: 16px; }
  .btn-new:hover { background: #1e7e34; }
  .btn-continue { background: #6c757d; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 15px; margin-top: 16px; margin-left: 8px; }
  .btn-continue:hover { background: #545b62; }
  textarea { width: 100%; height: 200px; padding: 10px; font-size: 14px; border: 1px solid #ddd; border-radius: 6px; margin-top: 12px; box-sizing: border-box; }
  #status { margin-left: 12px; color: #e53; font-size: 14px; }
  #error { color: red; margin-top: 8px; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }

  /* Summary results */
  #summary-box { margin-top: 20px; display: none; }
  #summary-box h3 { color: #1a4fa3; margin: 16px 0 8px; font-size: 1rem; }
  #summary-box h3:first-child { margin-top: 0; }
  #summary-box ul { margin-left: 20px; }
  #summary-box li { margin-bottom: 4px; font-size: 14px; }
  #summary-box p { font-size: 14px; line-height: 1.5; }

  /* AI Prompts */
  .prompt-card { background: #f8f9ff; border: 1px solid #d4deff; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; position: relative; }
  .prompt-action { font-size: 12px; font-weight: 700; color: #1a4fa3; margin-bottom: 4px; }
  .prompt-text { font-size: 13px; white-space: pre-wrap; color: #333; padding-right: 50px; line-height: 1.5; }
  .btn-copy { position: absolute; top: 10px; right: 10px; background: #1a4fa3; color: white; border: none; border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: 600; }
  .btn-copy:hover { background: #153d80; }
  .btn-copy.copied { background: #28a745; }

  /* History */
  .history { margin-top: 30px; }
  .history h2 { font-size: 1.2rem; margin-bottom: 12px; }
  .history-item { background: white; border-radius: 8px; padding: 16px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); cursor: pointer; }
  .history-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  .history-item h4 { margin: 0 0 2px; }
  .history-item .date { font-size: 12px; color: #888; }
  .history-item .preview { font-size: 13px; color: #555; margin-top: 4px; }
  .history-detail { display: none; margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee; font-size: 13px; }
  .history-detail.show { display: block; }
  .history-detail h5 { color: #1a4fa3; margin: 10px 0 4px; font-size: 13px; }
  .history-detail h5:first-child { margin-top: 0; }
  .history-detail pre { white-space: pre-wrap; font-family: inherit; margin: 0; }
  .history-detail ul { margin-left: 18px; }
  .history-detail li { margin-bottom: 3px; }
  .empty { text-align: center; color: #999; padding: 20px; font-size: 14px; }
</style>
</head>
<body>
<div style="position:relative">
  <h1>Meeting Recorder</h1>
  <button onclick="document.getElementById('settings').style.display=document.getElementById('settings').style.display==='none'?'block':'none'" style="position:absolute;top:0;right:0;background:none;border:none;font-size:22px;cursor:pointer;padding:8px" title="Settings">&#9881;</button>
</div>
<p style="text-align:center;color:#888;font-size:13px;margin:4px 0 20px">Record, transcribe, and summarize meetings with AI</p>

<div id="settings" class="card" style="display:none">
  <label style="font-weight:600;font-size:14px">Anthropic API Key</label>
  <input type="password" id="apiKey" placeholder="sk-ant-..." style="width:100%;padding:10px;font-size:14px;border:1px solid #ddd;border-radius:6px;margin-top:4px;box-sizing:border-box" />
  <p style="font-size:12px;color:#888;margin-top:4px">Saved in your browser only.</p>
</div>

<div class="card">
  <input type="text" id="title" placeholder="Meeting title (e.g. Weekly Standup)" />
  <div>
    <button class="btn-record" id="recBtn" onclick="startRecording()">Start Recording</button>
    <button class="btn-stop" onclick="stopRecording()">Stop</button>
    <span id="status"></span>
  </div>
  <textarea id="transcript" placeholder="Transcript will appear here as you speak..."></textarea>
  <div id="error"></div>
  <br>
  <button class="btn-summarize" onclick="doSummarize()">Summarize with AI</button>

  <div id="summary-box" class="card" style="margin-top:20px;display:none">
    <h3>Summary</h3>
    <p id="summary-text"></p>
    <h3>Action Items</h3>
    <ul id="action-list"></ul>
    <div id="prompts-section" style="display:none">
      <h3>AI Prompts</h3>
      <p style="font-size:12px;color:#888;margin-bottom:10px">Ready-to-paste prompts for Claude to help with each action item</p>
      <div id="prompts-list"></div>
    </div>
    <div style="margin-top:20px">
      <button class="btn-new" onclick="newMeeting()">New Meeting</button>
      <button class="btn-continue" onclick="continueMeeting()">Continue Recording</button>
    </div>
  </div>
</div>

<div class="history">
  <h2>Meeting History</h2>
  <div id="historyList"><div class="empty">No past meetings yet.</div></div>
</div>

<script>
let recognition;
let isRecording = false;

// API key persistence
const keyInput = document.getElementById('apiKey');
keyInput.value = localStorage.getItem('anthropic_api_key') || '';
keyInput.addEventListener('input', () => localStorage.setItem('anthropic_api_key', keyInput.value));

// Meeting history in localStorage
function loadHistory() {
  try { return JSON.parse(localStorage.getItem('meeting_history')) || []; }
  catch(e) { return []; }
}
function saveToHistory(meeting) {
  const h = loadHistory();
  h.push(meeting);
  localStorage.setItem('meeting_history', JSON.stringify(h));
  renderHistory();
}
function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}
function renderHistory() {
  const meetings = loadHistory();
  const el = document.getElementById('historyList');
  if (!meetings.length) { el.innerHTML = '<div class="empty">No past meetings yet.</div>'; return; }
  let html = '';
  for (let i = meetings.length - 1; i >= 0; i--) {
    const m = meetings[i];
    const preview = (m.transcript || '').substring(0, 100) + ((m.transcript || '').length > 100 ? '...' : '');
    html += '<div class="history-item" onclick="toggleDetail(this)">';
    html += '<h4>' + esc(m.title) + '</h4>';
    html += '<div class="date">' + esc(m.date) + '</div>';
    html += '<div class="preview">' + esc(preview) + '</div>';
    html += '<div class="history-detail">';
    html += '<h5>Transcript</h5><pre>' + esc(m.transcript) + '</pre>';
    if (m.summary) html += '<h5>Summary</h5><pre>' + esc(m.summary) + '</pre>';
    if (m.actions && m.actions.length) {
      html += '<h5>Action Items</h5><ul>';
      m.actions.forEach(a => { html += '<li>' + esc(a) + '</li>'; });
      html += '</ul>';
    }
    if (m.prompts && m.prompts.length) {
      html += '<h5>AI Prompts</h5>';
      m.prompts.forEach(p => {
        html += '<div class="prompt-card" style="margin-top:6px">';
        html += '<div class="prompt-action">' + esc(p.action) + '</div>';
        html += '<div class="prompt-text">' + esc(p.prompt) + '</div>';
        html += '</div>';
      });
    }
    html += '</div></div>';
  }
  el.innerHTML = html;
}
function toggleDetail(el) {
  el.querySelector('.history-detail').classList.toggle('show');
}

// Recording
function startRecording() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    document.getElementById('error').textContent = 'Speech recognition not supported. Use Chrome.';
    return;
  }
  recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  // Preserve existing text if continuing
  let existingText = document.getElementById('transcript').value;
  let fullText = existingText;

  recognition.onstart = () => {
    isRecording = true;
    document.getElementById('recBtn').textContent = 'Recording...';
    document.getElementById('recBtn').classList.add('recording');
    document.getElementById('status').textContent = 'Listening...';
    document.getElementById('error').textContent = '';
  };
  recognition.onresult = (e) => {
    let newText = '';
    for (let i = 0; i < e.results.length; i++) {
      newText += e.results[i][0].transcript + ' ';
    }
    document.getElementById('transcript').value = existingText + newText;
    fullText = existingText + newText;
  };
  recognition.onerror = (e) => {
    if (e.error === 'aborted' || e.error === 'no-speech') return;
    document.getElementById('error').textContent = 'Mic error: ' + e.error;
  };
  recognition.onend = () => {
    if (isRecording) {
      // Save what we have so far as the base for next restart
      existingText = fullText;
      setTimeout(() => { try { recognition.start(); } catch(e) {} }, 100);
    }
  };
  recognition.start();
}

function stopRecording() {
  isRecording = false;
  if (recognition) recognition.abort();
  document.getElementById('recBtn').textContent = 'Start Recording';
  document.getElementById('recBtn').classList.remove('recording');
  document.getElementById('status').textContent = 'Stopped';
}

// Summarize
async function doSummarize() {
  const transcript = document.getElementById('transcript').value.trim();
  const title = document.getElementById('title').value.trim() || 'Untitled Meeting';
  if (!transcript) { alert('No transcript yet!'); return; }

  document.getElementById('error').textContent = '';
  document.getElementById('status').textContent = 'Summarizing...';

  const res = await fetch('/summarize', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ transcript, title, api_key: localStorage.getItem('anthropic_api_key') || '' })
  });
  const data = await res.json();
  if (data.error) {
    document.getElementById('error').textContent = data.error;
    document.getElementById('status').textContent = '';
    return;
  }

  // Show summary
  document.getElementById('summary-text').textContent = data.summary;
  const list = document.getElementById('action-list');
  list.innerHTML = '';
  (data.actions || []).forEach(a => { const li = document.createElement('li'); li.textContent = a; list.appendChild(li); });

  // Show AI prompts
  const promptsSection = document.getElementById('prompts-section');
  const promptsList = document.getElementById('prompts-list');
  if (data.prompts && data.prompts.length) {
    promptsList.innerHTML = '';
    data.prompts.forEach((p, i) => {
      const card = document.createElement('div');
      card.className = 'prompt-card';
      card.innerHTML = '<div class="prompt-action">' + esc(p.action) + '</div>'
        + '<div class="prompt-text" id="pt-' + i + '">' + esc(p.prompt) + '</div>'
        + '<button class="btn-copy" onclick="copyPrompt(this,' + i + ')">Copy</button>';
      promptsList.appendChild(card);
    });
    promptsSection.style.display = 'block';
  } else {
    promptsSection.style.display = 'none';
  }

  document.getElementById('summary-box').style.display = 'block';
  document.getElementById('status').textContent = '';

  // Save to history
  saveToHistory({
    title: title,
    transcript: transcript,
    summary: data.summary,
    actions: data.actions || [],
    prompts: data.prompts || [],
    date: new Date().toLocaleString()
  });
}

function copyPrompt(btn, idx) {
  const text = document.getElementById('pt-' + idx).textContent;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
  });
}

// New meeting vs continue
function newMeeting() {
  document.getElementById('title').value = '';
  document.getElementById('transcript').value = '';
  document.getElementById('summary-box').style.display = 'none';
  document.getElementById('status').textContent = 'Ready';
  document.getElementById('error').textContent = '';
}

function continueMeeting() {
  document.getElementById('summary-box').style.display = 'none';
  document.getElementById('status').textContent = 'Ready - click Start Recording to continue';
  // Transcript is preserved, user can keep recording
}

// Init
renderHistory();
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/summarize', methods=['POST'])
def summarize():
    import anthropic, json
    from flask import request, jsonify
    data = request.json
    transcript = data.get('transcript', '')
    title = data.get('title', 'Untitled Meeting')
    api_key = data.get('api_key') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'No API key. Click the gear icon to enter your Anthropic API key.'}), 400
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
  - "prompt": a ready-to-paste prompt for Claude that helps complete this action item. Be specific and include context from the meeting. For example, if the action is "email the facilities team about the HVAC issue", write a full prompt like "Draft a professional email to the facilities team requesting..." with all the relevant details from the meeting baked in.

Meeting title: {title}

TRANSCRIPT:
{transcript}"""}]
        )
        text = message.content[0].text.strip()
        # Clean markdown wrapping if present
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        return jsonify(json.loads(text))
    except json.JSONDecodeError as e:
        return jsonify({'error': 'Failed to parse AI response. Try again.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
