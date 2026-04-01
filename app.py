import os
import json
import re
import tempfile
from flask import Flask, render_template_string, request, jsonify
import anthropic
import openai

app = Flask(__name__)


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
  .rec-controls { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 0.5rem; }
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

  /* Audio level meter */
  .level-meter { height: 6px; border-radius: 3px; background: #eee; margin-bottom: 1rem;
                 overflow: hidden; }
  .level-meter-fill { height: 100%; width: 0%; border-radius: 3px;
                      background: linear-gradient(90deg, #28a745, #e74c3c);
                      transition: width 0.1s ease; }

  /* Mic error */
  .mic-error { background: #fdf0ef; border: 1px solid #f5c6cb; border-radius: 6px;
               padding: 0.75rem 1rem; margin-bottom: 1rem; color: #721c24; font-size: 0.9rem; }
  .mic-error strong { display: block; margin-bottom: 0.25rem; }

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
  input[type=text] { width: 100%; padding: 0.55rem; border: 1px solid #ddd;
             border-radius: 6px; font-size: 1rem; font-family: inherit; }
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

  /* AI Prompts */
  .prompt-card { background: #fff; border: 1px solid #e0e0e0; border-radius: 6px;
                 padding: 0.75rem 1rem; margin-bottom: 0.5rem; position: relative; }
  .prompt-card .prompt-label { font-size: 0.8rem; font-weight: 600; color: #3a86ff;
                               margin-bottom: 0.25rem; }
  .prompt-card .prompt-text { font-size: 0.9rem; white-space: pre-wrap; color: #333;
                              padding-right: 3.5rem; }
  .copy-btn { position: absolute; top: 0.6rem; right: 0.6rem; background: #3a86ff; color: #fff;
              border: none; border-radius: 4px; padding: 0.3rem 0.6rem; font-size: 0.75rem;
              font-weight: 600; cursor: pointer; }
  .copy-btn:hover { background: #2667cc; }
  .copy-btn.copied { background: #28a745; }

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
      <div class="level-meter" id="levelMeter" style="display:none">
        <div class="level-meter-fill" id="levelFill"></div>
      </div>
      <div id="micError"></div>
      <div id="liveTranscript" class="transcript-box"></div>
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

    <button class="btn" onclick="summarizePaste()">Summarize with AI</button>
    <div id="pasteResult"></div>
  </div>

  <!-- History -->
  <div class="history">
    <h2>Past Meetings</h2>
    <div id="historyList">
      <div class="empty">No meetings recorded yet.</div>
    </div>
  </div>
</div>

<script>
var mediaRecorder = null;
var audioChunks = [];
var micStream = null;
var audioCtx = null;
var analyser = null;
var levelRAF = null;
var fullTranscript = '';
var isRecording = false;

var MEETINGS_STORAGE = 'meeting_notes_history';

// --- localStorage helpers ---
function loadMeetingsFromStorage() {
  try { return JSON.parse(localStorage.getItem(MEETINGS_STORAGE)) || []; }
  catch(e) { return []; }
}

function saveMeetingToStorage(meeting) {
  var meetings = loadMeetingsFromStorage();
  meetings.push(meeting);
  localStorage.setItem(MEETINGS_STORAGE, JSON.stringify(meetings));
  renderHistory();
}

function escapeHtml(str) {
  var div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function renderHistory() {
  var meetings = loadMeetingsFromStorage();
  var container = document.getElementById('historyList');
  if (!meetings.length) {
    container.innerHTML = '<div class="empty">No meetings recorded yet.</div>';
    return;
  }
  var html = '';
  for (var i = meetings.length - 1; i >= 0; i--) {
    var m = meetings[i];
    var preview = m.transcript ? escapeHtml(m.transcript.substring(0, 120)) + (m.transcript.length > 120 ? '...' : '') : '';
    html += '<div class="history-card" onclick="this.querySelector(\'.expanded\').classList.toggle(\'show\')">';
    html += '<h3>' + escapeHtml(m.title) + '</h3>';
    html += '<div class="meta">' + escapeHtml(m.date) + '</div>';
    html += '<div class="preview">' + preview + '</div>';
    html += '<div class="expanded">';
    if (m.transcript) {
      html += '<div class="section"><h4>Full Transcript</h4><div class="section-body">' + escapeHtml(m.transcript) + '</div></div>';
    }
    if (m.summary) {
      html += '<div class="section"><h4>Summary</h4><div class="section-body">' + escapeHtml(m.summary) + '</div></div>';
    }
    if (m.action_items && m.action_items.length) {
      html += '<div class="section"><h4>Action Items</h4><ul>';
      m.action_items.forEach(function(item) { html += '<li>' + escapeHtml(item) + '</li>'; });
      html += '</ul></div>';
    }
    html += '</div></div>';
  }
  container.innerHTML = html;
}

// --- Init ---
window.addEventListener('DOMContentLoaded', function() {
  renderHistory();
});

// --- Tabs ---
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(function(b, i) {
    b.classList.toggle('active', (tab === 'record' && i === 0) || (tab === 'paste' && i === 1));
  });
  document.getElementById('tab-record').classList.toggle('active', tab === 'record');
  document.getElementById('tab-paste').classList.toggle('active', tab === 'paste');
}

// --- Audio level meter ---
function startLevelMeter(stream) {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  var source = audioCtx.createMediaStreamSource(stream);
  source.connect(analyser);
  var data = new Uint8Array(analyser.frequencyBinCount);
  var meter = document.getElementById('levelMeter');
  var fill = document.getElementById('levelFill');
  meter.style.display = 'block';

  function tick() {
    analyser.getByteFrequencyData(data);
    var sum = 0;
    for (var i = 0; i < data.length; i++) sum += data[i];
    var avg = sum / data.length;
    var pct = Math.min(100, (avg / 128) * 100);
    fill.style.width = pct + '%';
    levelRAF = requestAnimationFrame(tick);
  }
  tick();
}

function stopLevelMeter() {
  if (levelRAF) { cancelAnimationFrame(levelRAF); levelRAF = null; }
  if (audioCtx) { audioCtx.close().catch(function() {}); audioCtx = null; }
  document.getElementById('levelFill').style.width = '0%';
  document.getElementById('levelMeter').style.display = 'none';
}

// --- Mic error display ---
function showMicError(title, detail) {
  document.getElementById('micError').innerHTML =
    '<div class="mic-error"><strong>' + escapeHtml(title) + '</strong>' + escapeHtml(detail) + '</div>';
}

function clearMicError() {
  document.getElementById('micError').innerHTML = '';
}

// --- Recording via MediaRecorder ---
async function toggleRecording() {
  if (isRecording) { stopRecording(); return; }

  clearMicError();

  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      showMicError('Microphone access denied',
        'Please allow microphone access in your browser settings, then reload and try again.');
    } else if (err.name === 'NotFoundError') {
      showMicError('No microphone found',
        'Please connect a microphone and try again.');
    } else {
      showMicError('Microphone error', err.message);
    }
    return;
  }

  startLevelMeter(micStream);

  audioChunks = [];
  mediaRecorder = new MediaRecorder(micStream, { mimeType: getSupportedMimeType() });

  mediaRecorder.ondataavailable = function(e) {
    if (e.data.size > 0) audioChunks.push(e.data);
  };

  mediaRecorder.onstop = function() {
    // Stop mic and level meter
    stopLevelMeter();
    micStream.getTracks().forEach(function(t) { t.stop(); });
    micStream = null;

    // Send audio to server for transcription
    transcribeAudio();
  };

  mediaRecorder.start(1000); // collect chunks every second
  isRecording = true;
  document.getElementById('startBtn').textContent = 'Recording...';
  document.getElementById('startBtn').classList.add('recording');
  document.getElementById('stopBtn').disabled = false;
  document.getElementById('recStatus').textContent = 'Recording audio...';
  document.getElementById('recStatus').classList.add('live');
  document.getElementById('liveTranscript').textContent = '';
  document.getElementById('recSummarizeBtn').disabled = true;
}

function getSupportedMimeType() {
  var types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
  for (var i = 0; i < types.length; i++) {
    if (MediaRecorder.isTypeSupported(types[i])) return types[i];
  }
  return '';
}

function stopRecording() {
  if (!isRecording) return;
  isRecording = false;
  document.getElementById('startBtn').textContent = 'Start Recording';
  document.getElementById('startBtn').classList.remove('recording');
  document.getElementById('stopBtn').disabled = true;
  document.getElementById('recStatus').classList.remove('live');

  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    document.getElementById('recStatus').textContent = 'Stopping...';
    mediaRecorder.stop(); // triggers onstop -> transcribeAudio
  }
}

async function transcribeAudio() {
  if (!audioChunks.length) {
    document.getElementById('recStatus').textContent = 'No audio recorded';
    return;
  }

  document.getElementById('recStatus').textContent = '';
  document.getElementById('liveTranscript').innerHTML =
    '<span class="spinner"></span> Transcribing audio with Whisper...';

  var mimeType = getSupportedMimeType() || 'audio/webm';
  var ext = mimeType.includes('mp4') ? 'mp4' : mimeType.includes('ogg') ? 'ogg' : 'webm';
  var blob = new Blob(audioChunks, { type: mimeType });
  var formData = new FormData();
  formData.append('audio', blob, 'recording.' + ext);

  try {
    var resp = await fetch('/transcribe', { method: 'POST', body: formData });
    var data = await resp.json();

    if (data.error) {
      document.getElementById('liveTranscript').innerHTML =
        '<span class="error">' + escapeHtml(data.error) + '</span>';
      document.getElementById('recStatus').textContent = 'Transcription failed';
      return;
    }

    fullTranscript = data.text || '';
    document.getElementById('liveTranscript').textContent = fullTranscript;
    document.getElementById('recSummarizeBtn').disabled = !fullTranscript.trim();
    document.getElementById('recStatus').textContent = fullTranscript.trim() ? 'Transcription complete' : 'No speech detected in recording';
  } catch (err) {
    document.getElementById('liveTranscript').innerHTML =
      '<span class="error">Transcription request failed: ' + escapeHtml(err.message) + '</span>';
    document.getElementById('recStatus').textContent = 'Transcription failed';
  }
}

// --- Copy to clipboard ---
function copyPrompt(btn, idx) {
  var el = document.getElementById('prompt-text-' + idx);
  navigator.clipboard.writeText(el.textContent).then(function() {
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(function() { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
  });
}

// --- Summarize ---
async function callSummarize(transcript, title, resultDiv, tabId) {
  if (!transcript.trim()) { resultDiv.innerHTML = '<p class="error">No transcript to summarize.</p>'; return; }

  resultDiv.innerHTML = '<p><span class="spinner"></span> Generating summary...</p>';

  try {
    var resp = await fetch('/summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript: transcript, title: title || 'Untitled Meeting' })
    });
    var data = await resp.json();
    if (data.error) { resultDiv.innerHTML = '<p class="error">' + data.error + '</p>'; return; }

    // Save to localStorage
    saveMeetingToStorage({
      title: data.title || title || 'Untitled Meeting',
      transcript: transcript,
      summary: data.summary || '',
      action_items: data.action_items || [],
      prompts: data.prompts || [],
      date: new Date().toLocaleString()
    });

    var html = '<div class="result-card"><h3>' + escapeHtml(data.title || title || 'Meeting') + '</h3>';
    if (data.summary) {
      html += '<div class="section"><h4>Summary</h4><div class="section-body">' + escapeHtml(data.summary) + '</div></div>';
    }
    if (data.action_items && data.action_items.length) {
      html += '<div class="section"><h4>Action Items</h4><ul>';
      data.action_items.forEach(function(item) { html += '<li>' + escapeHtml(item) + '</li>'; });
      html += '</ul></div>';
    }
    if (data.prompts && data.prompts.length) {
      html += '<div class="section"><h4>AI Prompts</h4>';
      data.prompts.forEach(function(p, idx) {
        html += '<div class="prompt-card">';
        html += '<div class="prompt-label">' + escapeHtml(p.action_item) + '</div>';
        html += '<div class="prompt-text" id="prompt-text-' + idx + '">' + escapeHtml(p.prompt) + '</div>';
        html += '<button class="copy-btn" onclick="event.stopPropagation();copyPrompt(this,' + idx + ')">Copy</button>';
        html += '</div>';
      });
      html += '</div>';
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
    clearMicError();
    fullTranscript = '';
  } else {
    document.getElementById('pasteTitle').value = '';
    document.getElementById('pasteText').value = '';
    document.getElementById('pasteResult').innerHTML = '';
  }
}

function summarizeRecording() {
  callSummarize(fullTranscript.trim(), document.getElementById('recTitle').value,
                document.getElementById('recResult'), 'record');
}

function summarizePaste() {
  callSummarize(document.getElementById('pasteText').value.trim(),
                document.getElementById('pasteTitle').value,
                document.getElementById('pasteResult'), 'paste');
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/transcribe", methods=["POST"])
def transcribe():
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY not configured on server."}), 500

    if "audio" not in request.files:
        return jsonify({"error": "No audio file received."}), 400

    audio_file = request.files["audio"]

    # Determine file extension from the uploaded filename
    ext = audio_file.filename.rsplit(".", 1)[-1] if "." in audio_file.filename else "webm"

    try:
        # Save to a temp file (Whisper API needs a file-like with a name)
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            audio_file.save(tmp)
            tmp_path = tmp.name

        client = openai.OpenAI(api_key=api_key)
        with open(tmp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )

        os.unlink(tmp_path)
        return jsonify({"text": transcript.text})

    except openai.AuthenticationError:
        return jsonify({"error": "Invalid OpenAI API key."}), 401
    except Exception as e:
        # Clean up temp file on error
        if "tmp_path" in locals():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return jsonify({"error": str(e)}), 500


@app.route("/summarize", methods=["POST"])
def summarize():
    data = request.get_json()
    transcript = data.get("transcript", "")
    title = data.get("title", "Untitled Meeting")

    if not transcript.strip():
        return jsonify({"error": "No transcript provided."}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured on server."}), 500

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are a meeting assistant. Analyze the following meeting transcript "
                        "and provide:\n"
                        "1. A concise summary (2-4 paragraphs)\n"
                        "2. A list of action items (each as a short bullet)\n"
                        "3. For EACH action item, generate a ready-to-use Claude prompt that "
                        "someone could paste directly into Claude to get help completing that "
                        "action item. Each prompt should be specific, actionable, and include "
                        "relevant context from the meeting.\n\n"
                        "Respond in JSON with keys:\n"
                        '- "summary" (string)\n'
                        '- "action_items" (array of strings)\n'
                        '- "prompts" (array of objects, each with "action_item" (string) and '
                        '"prompt" (string))\n\n'
                        f"Meeting title: {title}\n\n"
                        f"Transcript:\n{transcript}"
                    ),
                }
            ],
        )

        response_text = message.content[0].text
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if match:
                result = json.loads(match.group(1))
            else:
                result = {"summary": response_text, "action_items": [], "prompts": []}

        return jsonify({
            "title": title,
            "summary": result.get("summary", ""),
            "action_items": result.get("action_items", []),
            "prompts": result.get("prompts", []),
        })

    except anthropic.AuthenticationError:
        return jsonify({"error": "Invalid Anthropic API key."}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
