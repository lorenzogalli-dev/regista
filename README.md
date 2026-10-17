# Ground Truth Football

A multi-agent system on Microsoft Foundry that turns a live stream of synthetic football events and tracking into explainable, personalised on-screen intelligence, and measures how often its explanations are right against a hidden ground truth the agents never see.

> Work in progress for the Microsoft × Premier League Hackathon. All data is synthetic; all clubs, players, venues and competitions are fictional.

- Technical spec: [`SPEC.md`](SPEC.md)
- Design direction: [`DESIGN.md`](DESIGN.md)
- Progress: [`STATUS.md`](STATUS.md)

## Run locally

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node 22.

```sh
cp .env.example .env            # optional for now; model settings are needed from D3
docker compose up -d --build    # PostgreSQL + API on :8000
curl localhost:8000/health      # {"status":"ok","db":"ok"}

cd web && npm install && npm run dev   # front-end on :5173, proxies the API
```

## Develop

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
```

## Licence

MIT. See [`LICENSE`](LICENSE).
