# Restaurant Ops — live frontend

A Vite + React + TypeScript app consuming the FastAPI live order feed in
`../realtime/`. Independent of the Python/uv toolchain — see the root
`README.md`'s "Running the React frontend" section and
`../docs/architecture.md`'s "React frontend" section for the full
picture (pages, data flow, why Tailwind + recharts instead of Tremor).

```bash
npm install
npm run dev
```

Requires the backend running first: `uv run uvicorn realtime.main:app --reload`
from the repo root.

## Scripts

- `npm run dev` — start the Vite dev server.
- `npm run build` — type-check (`tsc -b`) and build for production.
- `npm run lint` — `oxlint`.
- `npm run test` — `vitest run`.
