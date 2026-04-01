import os
import json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
import anthropic

app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meetings.json")


def load_meetings():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []


def save_meetings(meetings):
    with open(DATA_FILE, "w") as f:
        json.dump(meetings, f, indent=2)


TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meeting Recorder & AI Summarizer</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f0f2f5; color: #1a1a2e; line-height: 1.6; }
  .container { max-width: 860px; margin: 0 auto; padding: 1.5rem 1rem; }
  h1 { text-align: center; margin-bottom: 0.25rem; font-size: 1.75rem; }
  .subtitle { text-align: center; color: #888; margin-bottom: 1.5rem; font-size: 0.95rem; }

  /* Tabs */
  .tabs { display: flex; gap: 0; margin-bottom: 0; }
  .tab-btn { flex: 1; padding: 0.75rem; text-align: center; cursor: pointer;
             background: #e2e6ea; border: none; font-size: 1rem; font-weight: 600;
             color: #555; transition: all 0.2s; border-radius: 8px 8px 0 0; }
  .tab-btn.active { background: #fff; color: #3a86ff; box-shadow: 0 -2px 6px rgba(0,0,0,0.06); }
  .tab-panel { display: none; background: #fff; padding: 1.5rem; border-radius: 0 0 8px 8px;
               box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .tab-panel.active { display: block; }

  /* Record tab */
  .rec-controls { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1rem; }
  .rec-btn { padding: 0.7rem 1.5rem; border: none; border-radius: 6px; font-size: 1rem;
             font-weight: 600; cursor: pointer; transition: all 0.2s; }
  #startBtn { background: #e74c3c; color: #fff; }
  #startBtn:hover { background: #c0392b; }
  #startBtn.recording { animation: pulse 1.2s infinite; }
  #stopBtn { background: #555; color: #fff; }
  #stopBtn:hover { background: #333; }
  #stopBtn:disabled { opacity: 0.4; cursor: not-allowed; }
  .rec-status { font-size: 0.9rem; color: #888; }
  .rec-status.live { color: #e74c3c; font-weight: 600; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }

  /* Transcript area */
  .transcript-box { width: 100%; min-height: 180px; max-height: 350px; overflow-y: auto;
                    border: 1px solid #ddd; border-radius: 6px; padding: 0.75rem;
                    font-size: 0.95rem; background: #fafafa; white-space: pre-wrap;
                    margin-bottom: 1rem; }
  .transcript-box:empty::before { content: "Transcript will appear here...";
                                  color: #bbb; font-style: italic; }

  /* Paste tab */
  textarea { width: 100%; min-height: 200px; resize: vertical; border: 1px solid #ddd;
             border-radius: 6px; padding: 0.75rem; font-size: 0.95rem; font-family: inherit;
             margin-bottom: 1rem; }

  /* Shared */
  label { display: block; font-weight: 600; margin-bottom: 0.35rem; margin-top: 0.75rem; }
  input[type=text], input[type=password] { width: 100%; padding: 0.55rem; border: 1px solid #ddd;
             border-radius: 6px; font-size: 1rem; font-family: inherit; }
  .api-row { display: flex; gap: 0.5rem; align-items: end; margin-bottom: 1rem; }
  .api-row > div:first-child { flex: 1; }
  .btn { padding: 0.65rem 1.5rem; background: #3a86ff; color: #fff; border: none;
         border-radius: 6px; font-size: 1rem; font-weight: 600; cursor: pointer; }
  .btn:hover { background: #2667cc; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary { background: #6c757d; }
  .btn-secondary:hover { background: #545b62; }
  .btn-new { background: #28a745; margin-top: 1rem; }
  .btn-new:hover { background: #218838; }

  /* Results */
  .result-card { background: #f8f9ff; border: 1px solid #d4deff; border-radius: 8px;
                 padding: 1.25rem; margin-top: 1.25rem; }
  .result-card h3 { color: #3a86ff; margin-bottom: 0.5rem; font-size: 1.1rem; }
  .result-card .section { margin-bottom: 1rem; }
  .result-card .section:last-child { margin-bottom: 0; }
  .result-card .section h4 { color: #16213e; margin-bottom: 0.25rem; }
  .result-card .section-body { white-space: pre-wrap; }
  .result-card ul { margin-left: 1.25rem; }
  .result-card li { margin-bottom: 0.25rem; }

  /* History */
  .history { margin-top: 2rem; }
  .history h2 { margin-bottom: 1rem; font-size: 1.3rem; }
  .history-card { background: #fff; border-radius: 8px; padding: 1.25rem; margin-bottom: 0.75rem;
                  box-shadow: 0 1px 4px rgba(0,0,0,0.06); cursor: pointer; transition: all 0.2s; }
  .history-card:hover { box-shadow: 0 3px 12px rgba(0,0,0,0.1); }
  .history-card h3 { margin-bottom: 0.15rem; }
  .history-card .meta { font-size: 0.85rem; color: #888; }
  .history-card .preview { font-size: 0.9rem; color: #555; margin-top: 0.35rem; }
  .expanded { display: none; margin-top: 0.75rem; padding-top: 0.75rem;
              border-top: 1px solid #eee; }
  .expanded.show { display: block; }
  .expanded .section { margin-bottom: 0.75rem; }
  .expanded .section h4 { font-size: 0.95rem; color: #3a86ff; }
  .expanded .section-body { font-size: 0.9rem; white-space: pre-wrap; }

  .empty { text-align: center; color: #999; padding: 2rem; }
  .error { color: #e74c3c; font-weight: 600; margin-top: 0.5rem; }
  .spinner { display: inline-block; width: 18px; height: 18px; border: 3px solid #ddd;
             border-top-color: #3a86ff; border-radius: 50%; animation: spin 0.7s linear infinite;
             vertical-align: middle; margin-right: 0.5rem; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <h1>Meeting Recorder</h1>
  <p class="subtitle">Record or paste meeting notes, then get an AI-powered summary</p>

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('record')">Record</button>
    <button class="tab-btn" onclick="switchTab('paste')">Paste Transcript</button>
  </div>

  <!-- Record Tab -->
  <div id="tab-record" class="tab-panel active">
    <label for="recTitle">Meeting Title</label>
    <input type="text" id="recTitle" placeholder="e.g. Weekly Standup">

    <div style="margin-top:1rem">
      <div class="rec-controls">
        <button id="startBtn" class="rec-btn" onclick="toggleRecording()">Start Recording</button>
        <button id="stopBtn" class="rec-btn" onclick="stopRecording()" disabled>Stop</button>
        <span id="recStatus" class="rec-status">Ready</span>
      </div>
      <div id="liveTranscript" class="transcript-box"></div>
    </div>

    <div class="api-row">
      <div>
        <label for="recApiKey">Anthropic API Key</label>
        <input type="password" id="recApiKey" placeholder="sk-ant-...">
      </div>
    </div>
    <button class="btn" id="recSummarizeBtn" onclick="summarizeRecording()" disabled>
      Summarize with AI
    </button>
    <div id="recResult"></div>
  </div>

  <!-- Paste Tab -->
  <div id="tab-paste" class="tab-panel">
    <label for="pasteTitle">Meeting Title</label>
    <input type="text" id="pasteTitle" placeholder="e.g. Sprint Retro">

    <label for="pasteText" style="margin-top:1rem">Transcript</label>
    <textarea id="pasteText" placeholder="Paste your meeting transcript here..."></textarea>

    <div class="api-row">
      <div>
        <label for="pasteApiKey">Anthropic API Key</label>
        <input type="password" id="pasteApiKey" placeholder="sk-ant-...">
      </div>
    </div>
    <button class="btn" onclick="summarizePaste()">Summarize with AI</button>
    <div id="pasteResult"></div>
  </div>

  <!-- History -->
  <div class="history">
    <h2>Past Meetings</h2>
    <div id="historyList">
      {% if meetings %}
        {% for m in meetings|reverse %}
        <div class="history-card" onclick="this.querySelector('.expanded').classList.toggle('show')">
          <h3>{{ m.title }}</h3>
          <div class="meta">{{ m.date }}</div>
          <div class="preview">{{ m.transcript[:120] }}{% if m.transcript|length > 120 %}...{% endif %}</div>
          <div class="expanded">
            <div class="section">
              <h4>Full Transcript</h4>
              <div class="section-body">{{ m.transcript }}</div>
            </div>
            {% if m.summary %}
            <div class="section">
              <h4>Summary</h4>
              <div class="section-body">{{ m.summary }}</div>
            </div>
            {% endif %}
            {% if m.action_items %}
            <div class="section">
              <h4>Action Items</h4>
              <ul>{% for item in m.action_items %}<li>{{ item }}</li>{% endfor %}</ul>
            </div>
            {% endif %}
          </div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty">No meetings recorded yet.</div>
      {% endif %}
    </div>
  </div>
</div>

<script>
let recognition = null;
let isRecording = false;
let fullTranscript = '';
let interimText = '';

// Persist API key in localStorage
const STORAGE_KEY = 'anthropic_api_key';
window.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem(STORAGE_KEY) || '';
  document.getElementById('recApiKey').value = saved;
  document.getElementById('pasteApiKey').value = saved;
  document.getElementById('recApiKey').addEventListener('input', (e) => {
    localStorage.setItem(STORAGE_KEY, e.target.value);
    document.getElementById('pasteApiKey').value = e.target.value;
  });
  document.getElementById('pasteApiKey').addEventListener('input', (e) => {
    localStorage.setItem(STORAGE_KEY, e.target.value);
    document.getElementById('recApiKey').value = e.target.value;
  });
});

function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach((b, i) => {
    b.classList.toggle('active', (tab === 'record' && i === 0) || (tab === 'paste' && i === 1));
  });
  document.getElementById('tab-record').classList.toggle('active', tab === 'record');
  document.getElementById('tab-paste').classList.toggle('active', tab === 'paste');
}

function toggleRecording() {
  if (isRecording) { stopRecording(); return; }
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert('Speech recognition is not supported in this browser. Please use Chrome or Edge.');
    return;
  }
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    isRecording = true;
    document.getElementById('startBtn').textContent = 'Pause';
    document.getElementById('startBtn').classList.add('recording');
    document.getElementById('stopBtn').disabled = false;
    document.getElementById('recStatus').textContent = 'Listening...';
    document.getElementById('recStatus').classList.add('live');
  };

  recognition.onresult = (e) => {
    interimText = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) {
        fullTranscript += t + ' ';
      } else {
        interimText = t;
      }
    }
    const box = document.getElementById('liveTranscript');
    box.textContent = fullTranscript + interimText;
    box.scrollTop = box.scrollHeight;
    document.getElementById('recSummarizeBtn').disabled = fullTranscript.trim().length === 0;
  };

  recognition.onerror = (e) => {
    if (e.error === 'no-speech') return;
    console.error('Speech error:', e.error);
    document.getElementById('recStatus').textContent = 'Error: ' + e.error;
  };

  recognition.onend = () => {
    if (isRecording) { recognition.start(); }
  };

  fullTranscript = '';
  interimText = '';
  document.getElementById('liveTranscript').textContent = '';
  recognition.start();
}

function stopRecording() {
  isRecording = false;
  if (recognition) { recognition.stop(); recognition = null; }
  document.getElementById('startBtn').textContent = 'Start Recording';
  document.getElementById('startBtn').classList.remove('recording');
  document.getElementById('stopBtn').disabled = true;
  document.getElementById('recStatus').textContent = 'Stopped';
  document.getElementById('recStatus').classList.remove('live');
  document.getElementById('recSummarizeBtn').disabled = fullTranscript.trim().length === 0;
}

async function callSummarize(transcript, title, apiKey, resultDiv, tabId) {
  if (!transcript.trim()) { resultDiv.innerHTML = '<p class="error">No transcript to summarize.</p>'; return; }
  if (!apiKey.trim()) { resultDiv.innerHTML = '<p class="error">Please enter your Anthropic API key.</p>'; return; }

  resultDiv.innerHTML = '<p><span class="spinner"></span> Generating summary...</p>';

  try {
    const resp = await fetch('/summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript, title: title || 'Untitled Meeting', api_key: apiKey })
    });
    const data = await resp.json();
    if (data.error) { resultDiv.innerHTML = '<p class="error">' + data.error + '</p>'; return; }

    let html = '<div class="result-card"><h3>' + (data.title || title || 'Meeting') + '</h3>';
    if (data.summary) {
      html += '<div class="section"><h4>Summary</h4><div class="section-body">' + data.summary + '</div></div>';
    }
    if (data.action_items && data.action_items.length) {
      html += '<div class="section"><h4>Action Items</h4><ul>';
      data.action_items.forEach(item => { html += '<li>' + item + '</li>'; });
      html += '</ul></div>';
    }
    html += '</div>';
    html += '<button class="btn btn-new" onclick="resetTab(\'' + tabId + '\')">New Recording</button>';
    resultDiv.innerHTML = html;
  } catch (err) {
    resultDiv.innerHTML = '<p class="error">Request failed: ' + err.message + '</p>';
  }
}

function resetTab(tabId) {
  if (tabId === 'record') {
    document.getElementById('recTitle').value = '';
    document.getElementById('liveTranscript').textContent = '';
    document.getElementById('recResult').innerHTML = '';
    document.getElementById('recSummarizeBtn').disabled = true;
    document.getElementById('recStatus').textContent = 'Ready';
    fullTranscript = '';
    interimText = '';
  } else {
    document.getElementById('pasteTitle').value = '';
    document.getElementById('pasteText').value = '';
    document.getElementById('pasteResult').innerHTML = '';
  }
}

function summarizeRecording() {
  const transcript = fullTranscript.trim();
  const title = document.getElementById('recTitle').value;
  const apiKey = document.getElementById('recApiKey').value;
  callSummarize(transcript, title, apiKey, document.getElementById('recResult'), 'record');
}

function summarizePaste() {
  const transcript = document.getElementById('pasteText').value.trim();
  const title = document.getElementById('pasteTitle').value;
  const apiKey = document.getElementById('pasteApiKey').value;
  callSummarize(transcript, title, apiKey, document.getElementById('pasteResult'), 'paste');
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    meetings = load_meetings()
    return render_template_string(TEMPLATE, meetings=meetings)


@app.route("/summarize", methods=["POST"])
def summarize():
    data = request.get_json()
    transcript = data.get("transcript", "")
    title = data.get("title", "Untitled Meeting")
    api_key = data.get("api_key", "")

    if not transcript.strip():
        return jsonify({"error": "No transcript provided."}), 400
    if not api_key.strip():
        return jsonify({"error": "No API key provided."}), 400

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are a meeting assistant. Analyze the following meeting transcript "
                        "and provide:\n"
                        "1. A concise summary (2-4 paragraphs)\n"
                        "2. A list of action items (each as a short bullet)\n\n"
                        "Respond in JSON with keys: \"summary\" (string) and "
                        "\"action_items\" (array of strings).\n\n"
                        f"Meeting title: {title}\n\n"
                        f"Transcript:\n{transcript}"
                    ),
                }
            ],
        )

        response_text = message.content[0].text
        # Try to parse JSON from the response
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if match:
                result = json.loads(match.group(1))
            else:
                result = {"summary": response_text, "action_items": []}

        summary = result.get("summary", "")
        action_items = result.get("action_items", [])

        # Save to history
        meetings = load_meetings()
        meetings.append({
            "title": title,
            "transcript": transcript,
            "summary": summary,
            "action_items": action_items,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        save_meetings(meetings)

        return jsonify({
            "title": title,
            "summary": summary,
            "action_items": action_items,
        })

    except anthropic.AuthenticationError:
        return jsonify({"error": "Invalid API key."}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/meetings", methods=["GET"])
def api_meetings():
    return jsonify(load_meetings())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
