import { defineConfig } from '@playwright/test'

// Smoke E2E de UI: navegador real -> Vite -> proxy /api -> FastAPI -> DuckDB -> Ollama.
// Pré-requisito: API (uvicorn :8000) e Ollama no ar — igual ao tests/test_e2e.py do backend.
export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,                      // coach real pode levar ~30s + margem
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,           // aproveita um dev server já aberto
    timeout: 30_000,
  },
})
