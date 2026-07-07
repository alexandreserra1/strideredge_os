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

  test('treinos: mapa leaflet desenha a rota do treino com GPS', async ({ page }) => {
    // determinístico: acha via API um treino que TEM GPS e o seleciona na faixa,
    // em vez de torcer pro treino default ter trilha
    const acts = await (await page.request.get('/api/v1/activities')).json()
    let withGps: { activity_id: string; activity_name: string } | null = null
    for (const a of acts.slice(0, 12)) {          // faixa da UI mostra os recentes
      const t = await (await page.request.get(`/api/v1/activities/${a.activity_id}/track`)).json()
      if (t.points > 1) { withGps = a; break }
    }
    test.skip(!withGps, 'nenhum treino recente com GPS no banco')

    await page.goto('/')
    await page.getByRole('button', { name: 'Treinos' }).click()
    await expect(page.getByText('Percurso · Semáforo de Cadência')).toBeVisible()
    await page.getByRole('button', { name: withGps!.activity_name.split(' — ')[0].slice(0, 16) })
      .first().click()

    // a rota real vira MUITOS <path> no overlay (um por segmento colorido de cadência);
    // cada segmento tem ~1px (bbox zero = "hidden"), então o certo é asserir a contagem
    await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 20_000 })
    await expect
      .poll(() => page.locator('.leaflet-overlay-pane path').count(), { timeout: 20_000 })
      .toBeGreaterThan(50)
    await expect(page.locator('.leaflet-control-zoom')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Satélite' })).toBeVisible()
  })

  test('coach: gerar análise -> veredito REAL estruturado (streaming ou cache)', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Treinos' }).click()
    await expect(page.getByText('Veredito do Coach')).toBeVisible()

    await page.getByRole('button', { name: 'Gerar análise' }).click()
    // cache -> instantâneo; sem cache -> streama ~30s. As listas estruturadas fecham o fluxo.
    await expect(page.locator('h4', { hasText: 'Pontos fortes' })).toBeVisible({ timeout: 150_000 })
    // e é dado REAL (não o mock): o subtítulo muda quando coach.data chega da API
    await expect(page.getByText('Análise real · IA local + ciência citada')).toBeVisible()
  })

  test('análise & saúde: risco, calendário interativo e deep-link pro treino', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Análise & Saúde' }).click()
    await expect(page.getByRole('heading', { name: 'Análise & Saúde' })).toBeVisible()
    await expect(page.getByText('Risco geral de lesão')).toBeVisible()

    // strip 2 semanas com legenda
    await expect(page.getByText('Feito', { exact: true })).toBeVisible()
    await expect(page.getByText('Sem treino', { exact: true })).toBeVisible()

    // modo Mês: nome do mês atual, > desabilitado (futuro), < navega
    await page.getByRole('button', { name: 'Mês', exact: true }).click()
    const now = new Date()
    await expect(page.getByText(monthLabel(now))).toBeVisible()
    await expect(page.getByRole('button', { name: 'Próximo mês' })).toBeDisabled()
    await page.getByRole('button', { name: 'Mês anterior' }).click()
    const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1)
    await expect(page.getByText(monthLabel(prev))).toBeVisible()

    // deep-link: clicar num dia com treino abre o WorkoutDetail daquele treino
    const day = page.getByRole('button', { name: /Abrir treino de/ }).first()
    await expect(day).toBeVisible()
    await day.click()
    await expect(page.getByText('Veredito do Coach')).toBeVisible()
  })
})
