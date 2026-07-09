import { test, expect } from '@playwright/test'

// Smoke E2E — os fluxos que um atleta faz de verdade, contra API + Ollama reais.
// Não é cobertura total de UI (overengineering p/ 1 usuário): é o caminho crítico.

const MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
const monthLabel = (d: Date) => `${MONTHS[d.getMonth()]} ${d.getFullYear()}`

// ---------- fluxo público: landing -> login ----------

test.describe('landing pública + auth', () => {
  test('visitante vê a landing, vai pro login e entra como convidado', async ({ page }) => {
    await page.goto('/')
    // landing pública (marketing) — sem sidebar do app
    await expect(page.getByRole('button', { name: 'Começar' }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Dashboard' })).toHaveCount(0)

    await page.getByRole('button', { name: 'Login' }).click()
    await expect(page.getByRole('heading', { name: 'Bem-vindo de volta' })).toBeVisible()

    await page.getByRole('button', { name: /Continuar sem conta/ }).click()
    await expect(page.getByRole('button', { name: 'Análise & Saúde' })).toBeVisible()
  })

  test('cadastro REAL cria conta única e entra; duplicado é recusado', async ({ page }) => {
    const email = `e2e+${Date.now()}@teste.local`
    await page.goto('/')
    await page.getByRole('button', { name: 'Login' }).click()
    await page.getByRole('button', { name: 'Criar agora' }).click()

    await page.getByPlaceholder('Nome').fill('Atleta E2E')
    await page.getByPlaceholder('E-mail').fill(email)
    await page.getByPlaceholder('Senha (8+ caracteres)').fill('corrida12345')
    await page.getByPlaceholder('Confirmar senha').fill('corrida12345')
    await page.getByRole('button', { name: 'Criar conta' }).click()
    await expect(page.getByRole('button', { name: 'Análise & Saúde' })).toBeVisible({ timeout: 10_000 })

    // sair e tentar cadastrar o MESMO e-mail -> recusado (cadastro único)
    await page.getByRole('button', { name: 'Sair' }).click()
    await expect(page.getByRole('button', { name: 'Começar' }).first()).toBeVisible()
    await page.getByRole('button', { name: 'Login' }).click()
    await page.getByRole('button', { name: 'Criar agora' }).click()
    await page.getByPlaceholder('Nome').fill('Clone')
    await page.getByPlaceholder('E-mail').fill(email)
    await page.getByPlaceholder('Senha (8+ caracteres)').fill('corrida12345')
    await page.getByPlaceholder('Confirmar senha').fill('corrida12345')
    await page.getByRole('button', { name: 'Criar conta' }).click()
    await expect(page.getByText('já tem cadastro')).toBeVisible()
  })

  test('senhas diferentes no cadastro são recusadas na hora', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('button', { name: 'Criar agora' }).click()
    await page.getByPlaceholder('Nome').fill('X')
    await page.getByPlaceholder('E-mail').fill('x@teste.local')
    await page.getByPlaceholder('Senha (8+ caracteres)').fill('corrida12345')
    await page.getByPlaceholder('Confirmar senha').fill('outra-senha99')
    await page.getByRole('button', { name: 'Criar conta' }).click()
    await expect(page.getByText('As senhas não conferem.')).toBeVisible()
  })

  test('URL protegida sem sessão cai no login (nada de entrar pela URL)', async ({ page }) => {
    for (const path of ['/dashboard', '/analise', '/treinos']) {
      await page.goto(path)
      await expect(page.getByRole('heading', { name: 'Bem-vindo de volta' })).toBeVisible()
      expect(new URL(page.url()).pathname).toBe('/login')
    }
    // com sessão, a MESMA URL abre o app
    await page.addInitScript(() => localStorage.setItem('se_guest', '1'))
    await page.goto('/analise')
    await expect(page.getByRole('heading', { name: 'Análise & Saúde' })).toBeVisible()
  })
})

// ---------- app do atleta (com sessão) ----------

test.describe('app do atleta', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('se_guest', '1'))
  })

  test('app carrega: shell + dashboard renderizam', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('StriderEdge').first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Treinos' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Análise & Saúde' })).toBeVisible()
  })

  test('dashboard: calendário abre o treino com mapa REAL (deep-link)', async ({ page }) => {
    // determinístico: acha via API um treino COM GPS, navega o calendário até o mês dele
    // e clica no dia — a home é o log de treino agora (sem faixa em Treinos).
    const acts = await (await page.request.get('/api/v1/activities')).json()
    let gps: { activity_id: string; start_time: string } | null = null
    for (const a of acts.slice(0, 20)) {
      const t = await (await page.request.get(`/api/v1/activities/${a.activity_id}/track`)).json()
      if (t.points > 1) { gps = a; break }
    }
    test.skip(!gps, 'nenhum treino com GPS no banco')

    const [y, m, d] = gps!.start_time.slice(0, 10).split('-').map(Number)
    await page.goto('/dashboard')
    const now = new Date()
    const monthsBack = (now.getFullYear() * 12 + now.getMonth()) - (y * 12 + (m - 1))
    for (let i = 0; i < monthsBack; i++) await page.getByRole('button', { name: 'Mês anterior' }).click()
    await page.getByRole('button', { name: new RegExp(`^Dia ${d} — treino feito$`) }).click()

    // rota real: muitos <path> no overlay do leaflet (um por segmento de cadência)
    await expect(page.getByText('Percurso · Semáforo de Cadência')).toBeVisible()
    await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 20_000 })
    await expect
      .poll(() => page.locator('.leaflet-overlay-pane path').count(), { timeout: 20_000 })
      .toBeGreaterThan(50)
    await expect(page.getByRole('button', { name: 'Satélite' })).toBeVisible()
  })

  test('dashboard: > trava no mês atual, < navega', async ({ page }) => {
    await page.goto('/dashboard')
    const now = new Date()
    await expect(page.getByText(monthLabel(now))).toBeVisible()
    await expect(page.getByRole('button', { name: 'Próximo mês' })).toBeDisabled()
    await page.getByRole('button', { name: 'Mês anterior' }).click()
    const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    await expect(page.getByText(monthLabel(prev))).toBeVisible()
    await expect(page.getByRole('button', { name: 'Próximo mês' })).toBeEnabled()
  })

  test('coach: review da IA gera veredito REAL em Análise & Saúde', async ({ page }) => {
    await page.goto('/analise')
    await expect(page.getByRole('heading', { name: 'Review da IA' })).toBeVisible()
    await page.getByRole('button', { name: /Gerar do último treino|Regerar/ }).click()
    // cache -> instantâneo; sem cache -> streama ~30s. Listas estruturadas fecham o fluxo.
    await expect(page.locator('h4', { hasText: 'Pontos fortes' })).toBeVisible({ timeout: 150_000 })
  })

  test('análise & saúde: risco visível, SEM calendário (foi pra home)', async ({ page }) => {
    await page.goto('/analise')
    await expect(page.getByRole('heading', { name: 'Análise & Saúde' })).toBeVisible()
    await expect(page.getByText('Risco geral de lesão')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Review da IA' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Mês anterior' })).toHaveCount(0)
  })
})
