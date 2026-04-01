import os
import json
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, jsonify

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


def summarize(notes: str) -> str:
    """Generate a simple extractive summary from meeting notes."""
    sentences = [s.strip() for s in notes.replace("\n", ". ").split(".") if s.strip()]
    if not sentences:
        return "No content to summarize."
    # Pick first sentence + any sentence containing key phrases
    key_phrases = ["action", "decision", "agree", "deadline", "next step", "follow up", "todo"]
    summary_parts = [sentences[0]]
    for s in sentences[1:]:
        if any(kw in s.lower() for kw in key_phrases):
            summary_parts.append(s)
    if len(summary_parts) == 1 and len(sentences) > 1:
        summary_parts.append(sentences[-1])
    return ". ".join(summary_parts) + "."


TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meeting Notes</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f7fa; color: #333; line-height: 1.6; }
  .container { max-width: 800px; margin: 0 auto; padding: 2rem 1rem; }
  h1 { margin-bottom: 1.5rem; color: #1a1a2e; }
  .card { background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .card h3 { color: #16213e; margin-bottom: 0.25rem; }
  .card .meta { font-size: 0.85rem; color: #888; margin-bottom: 0.75rem; }
  .card .notes { white-space: pre-wrap; margin-bottom: 0.75rem; }
  .card .summary { background: #eef6ff; border-left: 3px solid #3a86ff;
                   padding: 0.75rem; border-radius: 4px; font-size: 0.95rem; }
  .card .summary strong { color: #3a86ff; }
  form { background: #fff; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem;
         box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  label { display: block; font-weight: 600; margin-bottom: 0.25rem; margin-top: 0.75rem; }
  input[type=text], textarea { width: 100%; padding: 0.5rem; border: 1px solid #ddd;
         border-radius: 4px; font-size: 1rem; font-family: inherit; }
  textarea { min-height: 120px; resize: vertical; }
  button { margin-top: 1rem; padding: 0.6rem 1.5rem; background: #3a86ff; color: #fff;
           border: none; border-radius: 4px; font-size: 1rem; cursor: pointer; }
  button:hover { background: #2667cc; }
  .empty { text-align: center; color: #999; padding: 2rem; }
  .delete-btn { background: #e74c3c; padding: 0.3rem 0.75rem; font-size: 0.85rem;
                margin-top: 0.5rem; }
  .delete-btn:hover { background: #c0392b; }
</style>
</head>
<body>
<div class="container">
  <h1>Meeting Notes</h1>

  <form method="POST" action="/">
    <label for="title">Meeting Title</label>
    <input type="text" id="title" name="title" required placeholder="e.g. Sprint Planning">
    <label for="notes">Notes</label>
    <textarea id="notes" name="notes" required placeholder="Type or paste your meeting notes here..."></textarea>
    <button type="submit">Save &amp; Summarize</button>
  </form>

  {% if meetings %}
    {% for m in meetings|reverse %}
    <div class="card">
      <h3>{{ m.title }}</h3>
      <div class="meta">{{ m.date }}</div>
      <div class="notes">{{ m.notes }}</div>
      <div class="summary"><strong>AI Summary:</strong> {{ m.summary }}</div>
      <form method="POST" action="/delete/{{ loop.revindex0 }}" style="display:inline;padding:0;box-shadow:none;margin:0;background:none;">
        <button class="delete-btn" type="submit">Delete</button>
      </form>
    </div>
    {% endfor %}
  {% else %}
    <div class="empty">No meetings recorded yet. Add one above!</div>
  {% endif %}
</div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    meetings = load_meetings()
    if request.method == "POST":
        title = request.form.get("title", "Untitled")
        notes = request.form.get("notes", "")
        summary = summarize(notes)
        meetings.append({
            "title": title,
            "notes": notes,
            "summary": summary,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        save_meetings(meetings)
        return redirect(url_for("index"))
    return render_template_string(TEMPLATE, meetings=meetings)


@app.route("/delete/<int:idx>", methods=["POST"])
def delete(idx):
    meetings = load_meetings()
    if 0 <= idx < len(meetings):
        meetings.pop(idx)
        save_meetings(meetings)
    return redirect(url_for("index"))


@app.route("/api/meetings", methods=["GET"])
def api_meetings():
    return jsonify(load_meetings())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
