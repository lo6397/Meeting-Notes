# Deployment Guide - Meeting Recorder

## Architecture

- **App code**: `app.py`, `Procfile`, `requirements.txt` — deployed via Railway from GitHub
- **User data**: `data/` directory — persisted via Railway Volume, NOT in git

## Data Files (in DATA_DIR)

| File | Contents |
|------|----------|
| `meetings.json` | All meetings (scheduled, recording, completed) |
| `workspace.json` | Master to-do list tasks |
| `eod_summaries.json` | End of Day review history |

## Environment Variables (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |
| `DATA_DIR` | No | Data storage path (default: `./data`). Set to `/data` when using Railway Volume |
| `PORT` | Auto | Set automatically by Railway |

## Making Changes Safely

1. **NEVER rewrite app.py from scratch** — always use targeted edits
2. **Test locally first**: `python app.py` then visit http://localhost:5000
3. **Verify compile**: `python -m py_compile app.py`
4. **Commit and push to main** — Railway auto-deploys

## Railway Volume Setup

1. Go to Railway project → your service
2. Click **Settings** → **Volumes**
3. Click **+ Add Volume**
4. Mount path: `/data`
5. Add environment variable: `DATA_DIR=/data`
6. Redeploy

## Backup & Restore

**Download backup**: Visit `https://your-app.up.railway.app/backup`
- Downloads a zip of all data files

**Restore from backup**:
1. Unzip the backup
2. Upload files to the Railway volume via Railway CLI:
   ```
   railway volume cp meetings.json /data/meetings.json
   ```
   Or use the app's API:
   - POST each meeting to `/api/meetings`
   - POST each task to `/api/workspace`

## Health Check

Visit `https://your-app.up.railway.app/health` to see:
- Meeting count
- Workspace task count
- Data directory path
- Last update timestamp

## Troubleshooting

- **Data lost after deploy**: Volume not attached. Check Settings → Volumes
- **ANTHROPIC_API_KEY not set**: Check Settings → Variables
- **App won't start**: Check deploy logs, run `python -m py_compile app.py` locally
