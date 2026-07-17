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
  tests/                 ← 144 testes passando
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
- **Alavancagem e descasamento cambial via CVM** — score de saúde financeira agora penaliza Dívida Bruta/EBITDA alta e descasamento cambial da dívida, com trava crítica (score ≤ 4.5) que não deixa os outros pilares diluírem um risco grave (ex: BEEF3/Minerva antes saía 6/10 sem alerta, hoje cai pra "Risco Elevado / Evitar")
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
- **CVM: bug corrigido em `_extrair_serie()`** — usava `str.startswith(codigo_conta)` (somava conta-pai com contas-filhas, ex: 3.11 + 3.11.01 + 3.11.02) e `groupby().sum()` sem separar trimestre isolado de acumulado no exercício nem remover duplicatas de comparativos entre arquivos (ITR reporta o mesmo `DT_FIM_EXERC` como trimestre E como YTD). Isso inflava receita/lucro/FCO de praticamente todo ticker com dados ITR — corrigido para igualdade exata de conta + manter só a menor duração de período por `DT_FIM_EXERC` + dedup de valores exatos antes de agregar
- **CVM: bug corrigido em `_normalizar_nome()`** — `\bS\.?A\.?\b` não fechava o `\b` final depois de um ponto (não é caractere de palavra), então "MINERVA S.A." virava "MINERVA ." em vez de "MINERVA", fazendo `buscar_cd_cvm` falhar silenciosamente para qualquer nome de `MAPA_NOMES_CVM` terminado em "S.A." — trocado por lookahead `(?=\s|$)`
- **CVM: alavancagem usa Dívida BRUTA, não líquida** — a CVM não baixa o BPA (lado do Ativo do balanço, onde ficariam Caixa/Aplicações Financeiras — só o BPP/Passivo é baixado por `atualizar_cvm.py`). Dívida Bruta = Empréstimos+Financiamentos+Debêntures+Leasing (contas `2.01.04`+`2.02.01`), sempre ≥ dívida líquida, então o erro é sempre conservador (nunca esconde alavancagem). Para Dívida Líquida real seria preciso estender `atualizar_cvm.py` para também baixar `BPA_con` (~250-350MB novos CSVs)
- **CVM: EBITDA = EBIT (conta `3.05`) + D&A TTM (conta `6.01.01.02`, primeira linha de add-back no FCO)** — não inclui depreciação de direito de uso (IFRS16) quando reportada em linha separada, o que subestima levemente o EBITDA (lado conservador do erro)
- **CVM: composição cambial da dívida** vem de `2.01.04.01.01/.02` e `2.02.01.01.01/.02` (só a sub-linha "Empréstimos e Financiamentos", que discrimina moeda — Debêntures não vêm quebradas por moeda nessa taxonomia, mas no Brasil são quase sempre em reais). Empresas 100% financiadas via debênture (ex: CSED3) não têm esse dado — campo fica `None`, sem alerta falso
- **CVM: composição cambial da RECEITA não existe em taxonomia estruturada da CVM** (só em notas explicativas de texto livre) — assumida 0% em moeda estrangeira por padrão; `OVERRIDE_PCT_RECEITA_MOEDA_ESTRANGEIRA` em `cvm_provider.py` permite popular manualmente por ticker quando houver dado publicamente confiável

## ⚠️ Problemas conhecidos

- yfinance com rate limit frequente — Fundamentus é a fonte primária
- Histórico 5 anos via yfinance falhando por rate limit
- Brapi tem limitações no plano gratuito (praticamente 1 empresa por conta) — usado apenas como fallback
- CVM bloqueia requests Python/servidor — só funciona via curl com User-Agent de browser
- Dados CVM precisam ser atualizados manualmente 1x por trimestre via `atualizar_cvm.py`
- CVM: só o BPP (Passivo) é baixado, não o BPA (Ativo) — por isso alavancagem usa Dívida Bruta, não Líquida (ver decisão técnica acima)
- CVM: `MAPA_NOMES_CVM` cobre só os tickers problemáticos já mapeados manualmente — tickers fora do mapa dependem do nome vindo do provider (Fundamentus/etc) bater com a razão social oficial da CVM após normalização, o que falha silenciosamente (`disponivel: False`) para vários tickers ainda não mapeados

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
