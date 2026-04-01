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
  h1 { text-align: center; }
  .card { background: white; border-radius: 10px; padding: 24px; margin-bottom: 20px; }
  input[type=text] { width: 100%; padding: 10px; font-size: 15px; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 16px; }
  .btn-record { background: #dc3535; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 15px; cursor: pointer; }
  .btn-stop { background: #555; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 15px; cursor: pointer; }
  .btn-summarize { background: #1a4fa3; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 15px; cursor: pointer; margin-top: 12px; }
  textarea { width: 100%; height: 200px; padding: 10px; font-size: 14px; border: 1px solid #ddd; border-radius: 6px; margin-top: 12px; }
  #status { margin-left: 12px; color: #e53; font-size: 14px; }
  #summary-box { margin-top: 20px; display: none; }
  #error { color: red; margin-top: 8px; }
</style>
</head>
<body>
<h1>Meeting Recorder</h1>
<div class="card">
  <input type="text" id="title" placeholder="Meeting title (e.g. Weekly Standup)" />
  <div>
    <button class="btn-record" onclick="startRecording()">Start Recording</button>
    <button class="btn-stop" onclick="stopRecording()">Stop</button>
    <span id="status"></span>
  </div>
  <textarea id="transcript" placeholder="Transcript will appear here as you speak..."></textarea>
  <div id="error"></div>
  <br>
  <button class="btn-summarize" onclick="summarize()">Summarize with AI</button>
</div>

<div id="summary-box" class="card">
  <h3>Summary</h3>
  <p id="summary-text"></p>
  <h3>Action Items</h3>
  <ul id="action-list"></ul>
</div>

<script>
let recognition;
let isRecording = false;

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
  let fullText = '';
  recognition.onstart = () => {
    isRecording = true;
    document.getElementById('status').textContent = 'Listening...';
    document.getElementById('error').textContent = '';
  };
  recognition.onresult = (e) => {
    fullText = '';
    for (let i = 0; i < e.results.length; i++) {
      fullText += e.results[i][0].transcript + ' ';
    }
    document.getElementById('transcript').value = fullText;
  };
  recognition.onerror = (e) => {
    if (e.error === 'no-speech') return;
    document.getElementById('error').textContent = 'Mic error: ' + e.error;
  };
  recognition.onend = () => {
    if (isRecording) {
      try {
        recognition.start();
      } catch(e) {
        // already started, ignore
      }
    }
  };
  recognition.start();
}

function stopRecording() {
  isRecording = false;
  if (recognition) recognition.abort();
  document.getElementById('status').textContent = 'Stopped';
}

async function summarize() {
  const transcript = document.getElementById('transcript').value.trim();
  if (!transcript) { alert('No transcript yet!'); return; }
  document.getElementById('status').textContent = 'Summarizing...';
  const res = await fetch('/summarize', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ transcript })
  });
  const data = await res.json();
  if (data.error) { document.getElementById('error').textContent = data.error; return; }
  document.getElementById('summary-text').textContent = data.summary;
  const list = document.getElementById('action-list');
  list.innerHTML = '';
  data.actions.forEach(a => { const li = document.createElement('li'); li.textContent = a; list.appendChild(li); });
  document.getElementById('summary-box').style.display = 'block';
  document.getElementById('status').textContent = '';
}
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
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'ANTHROPIC_API_KEY not set'}), 400
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": f"""Summarize this meeting transcript and extract action items. Return ONLY valid JSON with no markdown:
{{"summary": "...", "actions": ["item1", "item2"]}}

TRANSCRIPT:
{transcript}"""}]
        )
        text = message.content[0].text.strip().replace('```json','').replace('```','')
        return jsonify(json.loads(text))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
