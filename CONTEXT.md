# 🧠 Contexto do Projeto: Valuation Tracker

Estou desenvolvendo o Valuation Tracker, uma ferramenta de valuation de ações brasileiras. Continuando de onde parei.

## Stack & Arquitetura

- FastAPI (Python 3.9 via pyenv) + React/TypeScript/Vite/Tailwind CSS
- Backend: porta 8000 | Frontend: porta 5173
- Proxy Vite roteia chamadas `/api` para o backend em dev; em produção o FastAPI serve `/api/*` diretamente
- 3 fontes de dados com fallback automático: **Fundamentus → Brapi → yfinance**
- Cache em memória de 10 minutos
- Selic automática via API BACEN (série 432)
- GitHub: https://github.com/AndreMarchi/valuation-tracker
- **Produção: https://valuation-tracker-production.up.railway.app**

## Métodos de Valuation

- Graham, Bazin, DCF, P/L, P/VP, EV/EBITDA, PEG Ratio, EV/Receita, Rule of 40, DCF Duas Fases
- Score de atratividade 0–10 combinando métodos válidos por setor
- CAPM dinâmico para taxa de desconto (teto 16% / piso 10%)
- WACC dinâmico (equity + dívida com tax shield 34%) (teto 20% / piso 8%)
- FCL calculado via NOPAT (EBIT × (1 - 0.34) × fator setor)
- Análise de risco político/regulatório com penalização no score
- Análise de endividamento (Dívida/EBIT, Dívida/Patrimônio)
- Restrições por setor (bancos, holdings, tech, transporte aéreo, etc.)
- Detecção automática de empresas de crescimento (>15% ao ano)
- Matriz de Consenso — avalia 3 pilares independentes e gera parecer do analista
- **Saúde Financeira via CVM** — score 0–10 com dados trimestrais reais (DRE, DFC consolidados)

## Estrutura de Arquivos Principal

```
backend/
  main.py
  pytest.ini
  .env (BRAPI_TOKEN)
  dados/
    brapi.py
    yfinance_provider.py
    fundamentus_provider.py
    provider.py          ← fallback automático
    historico.py
    selic.py
    cvm_provider.py      ← Fase 2.5: lê CSVs da CVM do disco
  valuation/
    graham.py
    bazin.py
    multiplos.py
    dcf.py
    score.py
    risco.py
    setor.py
    endividamento.py
    capm.py
    wacc.py
    nopat.py
    ev_ebitda.py
    crescimento.py
    saude_financeira.py  ← Fase 2.5: score e tendências CVM
  scripts/
    atualizar_cvm.py     ← rodar 1x por trimestre para atualizar dados CVM
  dados_cvm/             ← CSVs da CVM em disco (commitados no repo)
    cad_cia_aberta.csv
    itr_dre_YYYY.csv / itr_dfc_YYYY.csv / itr_bpp_YYYY.csv
    dfp_dre_YYYY.csv / dfp_dfc_YYYY.csv / dfp_bpp_YYYY.csv
  tests/                 ← 118 testes passando
frontend/
  src/
    App.tsx
    types.ts
  vite.config.ts
Dockerfile               ← build multi-stage: Node (frontend) + Python (backend)
railway.toml             ← deploy automático via GitHub push
```

## ✅ O que está funcionando

- Backend FastAPI rodando na porta 8000
- Frontend React/Vite rodando na porta 5173
- 118 testes automatizados passando
- Fundamentus como fonte primária (mais rápido e rico)
- Fallback automático: Fundamentus → Brapi → yfinance
- Selic automática via API BACEN
- CAPM dinâmico por setor
- WACC dinâmico com ponderação real de balanço
- FCL via NOPAT com fatores calibrados por setor
- EV/EBITDA, PEG Ratio, Rule of 40, DCF Duas Fases implementados
- Restrições por setor (bancos, holdings, transporte aéreo)
- Detecção de empresas de crescimento com DCF duas fases
- Análise de risco político e regulatório
- Análise de endividamento com alertas
- Histórico 5 anos com alertas contextuais
- Matriz de Consenso com parecer do analista
- **Watchlist com localStorage** — salvar/remover tickers, cards com score e parecer
- **Botão "Atualizar tudo"** — atualiza todos os tickers da watchlist em paralelo
- **Deploy no Railway** — URL pública, deploy automático a cada git push
- **Saúde Financeira via CVM** — gráficos trimestrais de receita, lucro e FCO
- Endpoints auxiliares: `/cache/clear`, `/selic`, `/api/*` (duplicados para produção)

## 📌 Decisões técnicas tomadas

- `httpx` usa `response.json()` síncrono (sem `await`) — mocks usam `MagicMock` não `AsyncMock`
- Fundamentus retorna LPA, VPA, PL, PVP sem casas decimais (dividir por 100)
- FCL calculado via NOPAT (não mais lucro líquido) — mais preciso por setor
- WACC substitui ajuste manual de taxa de desconto — usa ponderação equity/dívida real
- Selic atual: 14.50% (atualizada automaticamente via BACEN)
- Taxa CAPM teto 16% / piso 10% — WACC teto 20% / piso 8%
- Crescimento negativo em empresa lucrativa → usa mínimo 2% no DCF
- Setores cíclicos limitam crescimento a 8% máximo
- Holdings identificadas por ticker (ITSA3/4) não pelo setor do Fundamentus
- `"from backend import dados"` aparece espontaneamente no `main.py` — remover com: `sed -i '' '1d' main.py`
- Embraer usa ticker `EMBJ3` no Fundamentus (não `EMBR3`)
- Frontend: `App.tsx` refatorado em componentes isolados por seção — fácil de expandir
- **Deploy**: Dockerfile multi-stage — Stage 1: `npm run build` (frontend) → Stage 2: Python + estáticos
- **Produção**: rotas `/api/*` duplicadas no FastAPI (o proxy Vite só funciona em dev)
- **CVM**: bloqueio de IP em servidores — dados baixados localmente via `atualizar_cvm.py` (usa curl) e commitados
- **CVM**: usa dados `_con` (consolidado), não `_ind` (individual) — essencial para holdings e grupos
- **CVM**: `ESCALA_MOEDA = MIL` → valores em milhares → multiplica por 1000 antes de dividir por 1M
- **CVM**: mapeamento ticker → CD_CVM via `cad_cia_aberta.csv` + busca por nome normalizado
- **CVM**: `CD_CVM` no CSV tem zeros à esquerda (ex: `009512`) — usar `.zfill(6)` no filtro
- **Frontend gráficos CVM**: valores `>= 1000M` exibidos em B (bilhões)

## ⚠️ Problemas conhecidos

- yfinance com rate limit frequente — Fundamentus é a fonte primária
- Histórico 5 anos via yfinance falhando por rate limit
- Brapi tem limitações no plano gratuito (praticamente 1 empresa por conta) — usado apenas como fallback
- CVM bloqueia requests Python/servidor — só funciona via curl com User-Agent de browser
- Dados CVM precisam ser atualizados manualmente 1x por trimestre via `atualizar_cvm.py`

## 🗺️ Roadmap

| Fase | Descrição | Status |
|------|-----------|--------|
| 1 | Motor de valuation completo (todos os métodos + frontend) | ✅ Completa |
| 2 | Watchlist (localStorage) + Deploy Railway | ✅ Completa |
| 2.5 | Saúde Financeira via dados CVM (DRE/DFC trimestrais) | ✅ Completa |
| 3 | Supabase + Auth (watchlist por usuário, multi-device) | 🔲 Próxima |
| 4 | Produto: relatório PDF, comparativo entre tickers | 🔲 Futura |

## 🎯 Próximo passo (foco do próximo chat)

**Fase 3 — Supabase + Auth:**
- Criar projeto no Supabase Cloud
- Trocar `localStorage` por tabela Supabase (`watchlist` por usuário)
- Adicionar login com email/senha ou Google OAuth
- Multi-device: watchlist sincronizada em qualquer dispositivo
- Variável de ambiente `SUPABASE_URL` e `SUPABASE_ANON_KEY` no Railway

## 📋 Notas sobre dados CVM

URLs reais dos ZIPs (um por ano, contém todos os CSVs):
```
https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip
https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip
```
CSVs extraídos de cada ZIP: `DRE_con`, `DFC_MI_con`, `BPP_con`
Cadastro: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv`
