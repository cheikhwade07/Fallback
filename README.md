# Fallback

Fallback is a hackathon prototype for detecting a person-down event at a construction site and getting a grounded responder briefing onto a dashboard quickly.

The local device uses a webcam and YOLOv8 pose detection. A small state machine classifies posture, waits for a sustained fall confirmation, projects the worker position into site metres, and posts an annotated event to the backend. The backend broadcasts events over Server-Sent Events (SSE), calculates the responder route, and generates a short Gemini briefing with a deterministic template fallback. The Next.js dashboard shows the alert, frozen frame, site map, route, and briefing source.

## Architecture

```text
Webcam
  |
  v
device/detect.py -- POST /api/event --> backend/main.py
  |                                      |
  |                                      +-- Gemini briefing or fallback template
  |                                      +-- SSE /api/stream
  |                                             |
  +---------------------------------------------v
                                      frontend/ dashboard
```

The project has two launch modes:

- Local development: detector, FastAPI backend, and Next.js dashboard all run on the laptop.
- Demo video / deployed mode: `run_live.py` runs only the local detector and posts to the deployed DigitalOcean server. The backend and dashboard stay on the server.

## Requirements

- Python 3.10+
- Node.js 18+
- A webcam for live detection
- Windows is the primary development target; macOS/Linux can run the processes manually.
- A Gemini API key is needed for live Gemini briefings. The dashboard still receives a deterministic fallback if Gemini is unavailable.

## Setup

From the repository root:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install -r device\requirements.txt
python -m pip install psutil

cd frontend
npm ci
cd ..
```

The launcher uses `psutil` to clear ports before starting the local stack. It is installed separately because it is a launcher dependency rather than a detector or backend dependency.

## Configuration

Create or update `.env` in the repository root:

```dotenv
GEMINI_API_KEY=replace-with-your-key
FALLBACK_SERVER=http://206.189.199.1
```

Never commit `.env`. It is ignored by `.gitignore`.

`GEMINI_API_KEY` is loaded by the backend. `FALLBACK_SERVER` is used by `run_live.py`; its default is `http://206.189.199.1` when the variable is absent. The frontend uses `http://localhost:8000` automatically in development when `NEXT_PUBLIC_API_BASE` is unset.

## Run everything locally

The simplest Windows command is:

```powershell
.venv\Scripts\python.exe run.py
```

This starts:

- FastAPI at <http://127.0.0.1:8000>
- Next.js at <http://127.0.0.1:3000>
- The webcam detector with `--conf 0.15` and `--track-conf 0.45`

Open <http://127.0.0.1:3000> in a browser. `run.py` opens child processes in visible consoles on Windows. Close those consoles when finished.

To run only the backend and frontend:

```powershell
.venv\Scripts\python.exe run.py --no-detect
```

Then launch the detector separately if needed:

```powershell
.venv\Scripts\python.exe device\detect.py --conf 0.15 --track-conf 0.45 --server http://127.0.0.1:8000
```

## Calibrate the camera

The homography maps image coordinates to the 2 m × 2 m site plan. The calibration file is intentionally ignored because it is camera-specific.

Run:

```powershell
.venv\Scripts\python.exe device\homography.py
```

Click markers `A`, `B`, `C`, and `D` in that order, then press a key to save `device/homography.json`. Redo calibration if the camera moves.

## Detector behavior

The detector maintains the following states:

```text
UPRIGHT → DOWN → FALL_CONFIRMED → RECOVERED → UPRIGHT
```

Current frame rule:

- No person or missing shoulder/hip measurements: `UNKNOWN`; this does not reset the down timer.
- `sh_hip_gap_norm < 0.26` and `aspect > 0.50`: `DOWN_FRAME`.
- Otherwise: `UPRIGHT_FRAME`.

The state machine uses a 1.5-second rolling window, enters DOWN at 0.60 down-frame fraction, exits at 0.30, and confirms after 5.0 seconds. Press `c` in the detector window to clear a latched confirmed event; press `q` to quit.

## Event flow and API

The device posts the frozen event contract to `POST /api/event`:

```json
{
  "node_id": "node-01",
  "event_type": "FALL_DETECTED",
  "x": 1.65,
  "y": 0.54,
  "fall_duration": 5.1,
  "latency_ms": 42,
  "timestamp": "2026-01-01T00:00:00Z",
  "frame_b64": "<annotated JPEG>"
}
```

Useful endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Backend health check |
| `POST /api/event` | Device event intake |
| `GET /api/stream` | SSE stream consumed by the dashboard |
| `GET /api/events` | Recent event inspection |

For a confirmed fall, the backend adds `briefing` and `briefing_source` to the streamed event. `briefing_source` is `gemini` for a successful model response or `fallback` when the deterministic template is used. The dashboard displays these as `GEMINI` and `TEMPLATE`.

The Gemini request sends only measured event facts, site geometry, and route data. It does not send `frame_b64`. The current model is `gemini-2.5-flash`; the backend disables thinking for this short briefing so the 150-token output budget is used for the response.

## Deployed demo mode

The deployed backend and frontend must already be running on the DigitalOcean droplet. From the laptop, run:

```powershell
.venv\Scripts\python.exe run_live.py
```

`run_live.py` first checks `<FALLBACK_SERVER>/api/health` with a 5-second timeout. It exits without opening the detector if the server is unavailable. On success it launches only `device/detect.py` in a new Windows console:

```text
SERVER OK    : http://206.189.199.1
DASHBOARD    : http://206.189.199.1       <- open this on the phone
DETECTOR     : launched in a new window
```

Override the server or detector thresholds when needed:

```powershell
.venv\Scripts\python.exe run_live.py --server http://206.189.199.1 --conf 0.15 --track-conf 0.45
```

## Troubleshooting

- `FALLBACK SERVER HEALTH CHECK FAILED`: check the droplet URL, nginx, and the backend service. The detector is intentionally not launched in this case.
- Dashboard does not update locally: confirm the backend is on port 8000 and that development SSE resolves to `http://localhost:8000/api/stream`.
- Briefing shows `TEMPLATE`: inspect the backend terminal. Gemini failures log the exception and traceback; verify `GEMINI_API_KEY`, network access, and the model endpoint.
- Camera cannot open: close other camera applications and check Windows camera permissions.
- Worker coordinates look wrong: recalibrate with `device/homography.py` after fixing the camera position.
- Model load fails: confirm the repository has `yolov8n-pose.pt` and that the device requirements were installed into `.venv`.

## License

See [LICENSE](LICENSE).
