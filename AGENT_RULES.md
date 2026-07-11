# PROJECT CONTEXT (do not relitigate, do not redesign)

Hackathon project "Fallback": man-down detection. My lane = ML pipeline (laptop webcam) + entire webapp. 36-hour deadline. Speed over elegance; no refactors unless something is broken.

## Repo layout (create as needed)
- device/ — webcam pipeline: pose, fall logic, homography, event POST
- backend/ — FastAPI
- frontend/ — Next.js dashboard
- shared/ — event schema reference

## Locked architecture
- YOLOv8n-pose (ultralytics), laptop webcam, 17 COCO keypoints
- Rule-based fall logic: bbox aspect ratio (wider than tall) AND shoulder-hip vertical gap collapsed → state machine UPRIGHT → DOWN → FALL_CONFIRMED (down >= 3s, configurable N) → RECOVERED
- Homography: 4 floor markers clicked once in the image, cv2.getPerspectiveTransform, matrix saved to JSON file, ankle keypoint → (x, y) metres
- Event contract, FROZEN, POST to /api/event:
  {"node_id": "node-01", "event_type": "FALL_DETECTED" | "HEARTBEAT" | "RECOVERED",
   "x": 3.2, "y": 1.4, "fall_duration": 7.4, "latency_ms": 38,
   "timestamp": "<ISO8601>", "frame_b64": "<annotated jpeg, downscaled to <=640px wide>"}
- Backend: FastAPI receives events, pushes to frontend via SSE
- Frontend beats in order: red alert + annotated frame + live "DOWN 00:07" counter → site plan + dot → A* route (grid over obstacle rectangles, door → dot) → Gemini briefing (grounded only in event JSON + site geometry passed in the prompt, must never invent geometry) → ElevenLabs TTS of the briefing
- Deploy target: DigitalOcean Droplet

## Rules for the agent
- One step at a time. I give numbered task prompts. Do only that task.
- Every task ends with a runnable command and a manual test I can perform. State both.
- Prefer minimal code. No abstractions for hypothetical future needs. No tests beyond the manual check.
- NEVER modify the event contract.
- Python 3.10+, use a venv. Node 18+ for frontend.
- If a dependency or API detail is uncertain, say so explicitly instead of guessing.
