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

## Simulator

```sh
uv run sim generate --seed 1000          # data/generated/m_1000 + data/ground_truth/m_1000 (hidden)
docker compose up -d --build             # API serves data/generated read-only
uv run sim watch m_1000 --speed 20       # terminal client for ws://localhost:8000/ws/replay/m_1000
uv run sim plausibility --set dev        # summary stats over the 20 dev seeds
```

A full 90+ minute match (events + 10 Hz tracking) takes about 6 s to simulate and write on an
Apple-silicon laptop. Seed sets: dev 1000–1019 (tuning), eval 5000–5019 (reporting only),
control 9000–9009 (no storylines).

## Develop

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                    # fast suite
uv run pytest -m slow            # plausibility over 20 dev seeds
```

## Licence

MIT. See [`LICENSE`](LICENSE).
