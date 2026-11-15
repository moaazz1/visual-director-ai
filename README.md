---
title: Visual Director AI
emoji: 🎬
colorFrom: purple
colorTo: gray
sdk: docker
app_port: 3000
---

# Visual Director AI

Phase 1 is a Next.js and Tailwind workspace backed by FastAPI. It accepts an advertising reference, runs a structured vision audit and turns three proposed creative treatments into production prompts.

## Run locally

Requires Node.js 20.9+ and Python 3.11+. From the project root open two terminals.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `VISION_API_KEY` in `.env` and start FastAPI.

```bash
.venv/bin/uvicorn api.main:app --env-file .env --host 127.0.0.1 --port 8000
```

In the second terminal run:

```bash
cd web
npm ci
npm run dev
```

Open [localhost:3000](http://localhost:3000). Upload an image or choose **Use sample image**. Optionally select and edit the Ooredoo Oman profile and supply a brief. Run the audit, select a treatment and generate its prompt. Save revisions or export the current prompt as text. Reloading in the same browser restores the last image and the latest saved audit and prompt. Unsaved form and prompt changes are held in the current tab.

## Configuration

| Setting | Where | Purpose |
| --- | --- | --- |
| `VISION_API_KEY` or `OPENAI_API_KEY` | FastAPI | Credential for live analysis |
| `VISION_MODEL`, `VISION_BASE_URL` | FastAPI | Configurable model and OpenAI Responses-compatible endpoint supporting strict structured vision output |
| `DATABASE_URL` | FastAPI | PostgreSQL via `postgresql+psycopg://...`. Defaults to local SQLite |
| `S3_BUCKET`, `S3_ENDPOINT_URL` | FastAPI | Private S3-compatible object storage using standard AWS credential discovery. Defaults to the local originals directory |
| `DATA_DIR` | FastAPI | Local data directory. Defaults to `.data` |
| `DIRECTOR_API_URL` | Next.js server | Private FastAPI URL. Defaults to `http://127.0.0.1:8000` |
| `COOKIE_SECURE=1` | FastAPI | Secure cookie flag for HTTPS deployments |

This build is configured for single-user local evaluation or a private deployment. Deploy the two processes behind private access and keep FastAPI internal. Before a multi-user rollout, add account authentication, usage limits, asset retention controls and database migrations. The browser session cookie scopes access to individual assets. Original images are saved byte-for-byte, and the audit provider receives a downsampled, orientation-corrected reference with the brief and selected brand rules.

## Code map

- `web/app/page.tsx` implements the creative workspace and its interaction states.
- `web/app/api/[...path]/route.ts` proxies allowlisted routes to FastAPI from the server.
- `api/main.py` validates and stores uploads, scopes reads to the browser session, and persists audit and prompt results.
- `api/director.py` contains the versioned director instructions and configurable Responses API adapter.
- `api/schemas.py` defines the structured review contract and compiles treatment decisions into an editing prompt.
- `api/storage.py` separates structured records from image storage.

## Checks

```bash
pip install pytest
python -m pytest
cd web && npm ci && npm run build && npm run check
```

The API test uses the bundled advertising reference and a controlled provider response to verify upload, request shape, missing configuration, malformed results, all three treatment prompts and persistence. For a live smoke test, use a configured provider key and repeat the steps above in the browser. Check that evidence is tied to the reference, assumptions are labeled, and changes preserve successful elements.

Phase 2 will add reference-guided image editing, localized masks where supported, durable generation jobs and retry states, generated asset persistence, downloads and a Before/After slider. Phase 3 will add visual QA, a browsable version timeline, a reusable profile manager and region annotations.

## Render Free

Deploy this repository as one **Web Service** using **Docker** on the **Free** instance type. A Blueprint can use the included `render.yaml`. For manual setup, leave the root directory blank and set `VISION_PROVIDER=gemini`. Enter `GEMINI_API_KEY` in Render's Environment settings. Leave billing disabled on the Google AI project for free-tier-only use. You can override the Gemini model with `VISION_MODEL`. Hosted local storage is temporary on this plan. The current audit endpoint is intended for trusted evaluations, so keep the key unset on a publicly shared demo.
