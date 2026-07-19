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
    fcfe.py              ← Fase 2.6: FCFE puro (calcular_fcfe, dois estágios)
    fcfe_valuation.py    ← Fase 2.6: orquestração ponta a ponta + sector-aware
  scripts/
    atualizar_cvm.py     ← rodar 1x por trimestre para atualizar dados CVM
  dados_cvm/             ← CSVs da CVM em disco (commitados no repo)
    cad_cia_aberta.csv
    itr_dre_YYYY.csv / itr_dfc_YYYY.csv / itr_bpp_YYYY.csv
    dfp_dre_YYYY.csv / dfp_dfc_YYYY.csv / dfp_bpp_YYYY.csv
  tests/                 ← 236 testes passando
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
- **FCFE (`valuation/fcfe.py`) — coleta de inputs via CVM (`buscar_inputs_fcfe_cvm()`)**: lucro líquido (`3.11`) e depreciação/amortização (`6.01.01.02`) reaproveitados das constantes já existentes. ΔCCL vem da conta `6.01.02` ("Variações nos Ativos e Passivos") — confirmado `ST_CONTA_FIXA="S"` (padronizada) e presente em 100% das ~450 empresas checadas em `itr_dfc_2024/2025/2026` e `dfp_dfc_2024/2025`, ao contrário de CAPEX/financiamento (`6.02.XX`/`6.03.XX`, que são `ST_CONTA_FIXA="N"` — nome/posição variam por empresa, precisam de heurística de texto ainda não implementada). Todos os 3 campos são TTM (soma dos últimos 4 trimestres) para ficarem dimensionalmente consistentes entre si
- **FCFE: inversão de sinal do ΔCCL** — a conta CVM `6.01.02` vem na convenção de IMPACTO EM CAIXA (positivo = liberou caixa/capital de giro caiu; é a mesma convenção que a CVM usa pra somar direto ao lucro líquido no cálculo do FCO). `calcular_fcfe()` espera `delta_ccl` na convenção ACADÊMICA de "aumento de capital de giro" (positivo = consumiu caixa) — sinal invertido em relação à conta CVM. `_delta_ccl_convencao_academica()` isola essa troca de sinal numa função só, testável (`+100 → -100`), pra não ficar perdida num comentário
- **FCFE: `test_fcfe.py` tinha `from fcfe import (...)` em vez de `from valuation.fcfe import (...)`** — quebrava a coleta do pytest pra suíte inteira (não só os 14 testes do arquivo); corrigido pra bater com a convenção do resto do projeto
- **FCFE: CAPEX/captação/amortização de dívida implementados via `extrair_por_texto()`** — as contas `6.02.XX` (CAPEX) e `6.03.XX` (financiamento) são `ST_CONTA_FIXA="N"` (não padronizadas): nome, posição E composição variam por empresa, e a MESMA empresa pode reordenar entre filings (confirmado na TAEE3: `6.03.03` é "Emissão de debêntures" — captação — num filing e "Pagamento de Debêntures - Principal" — amortização, sinal oposto — noutro). `extrair_por_texto(df, prefixo, incluir_padroes, excluir_padroes)` casa por `DS_CONTA` (sem acento, case-insensitive) em vez de por código, filtrando linhas-folha (3+ segmentos) dentro do prefixo do grupo. Padrões finais, validados manualmente contra 20 tickers de setores diferentes (óleo&gás, seguros, bolsa, varejo, shoppings, energia, bancos, holding, aluguel de carro, logística, bebidas, carne, educação):
  - **CAPEX** (`imobiliz|intangiv`, exclui `venda|alienac`) — CAPEX bruto, sem netting contra vendas de ativo (definição padrão de DCF/FCFE)
  - **Captação** (`captac|tomad|emiss` **E** `emprest|financiament|debentur` na mesma linha, exclui linhas que começam com `custo`) — "emiss" cobre "Emissão de debêntures" (fraseado real, confirmado na TAEE3), seguro incluir porque a segunda condição já exige um substantivo de dívida, barrando "Emissão de ações" (equity) sozinho
  - **Amortização** (`pagamento|amortiza|liquidad` **E** `emprest|financiament|debentur`, exclui `dividendo`/`arrendamento` e linhas só-de-juros) — "liquidad" cobre "Empréstimos... liquidados" (fraseado real da Minerva/BEEF3, o ticker âncora desta investigação — sem esse padrão a série ficava vazia); a exclusão de juros usa `^(?=.*juros)(?!.*principal)` **com âncora `^` obrigatória** — sem ela, `re.search()` encontra outra posição na string depois de onde "principal" já apareceu, fazendo a exclusão disparar mesmo em linhas combinadas tipo "Pagamento de principal e juros..." (bug real, pego pelo teste automatizado antes de ir pra produção)
- **FCFE: `extrair_por_texto()` NÃO reconsulta `_extrair_serie(df, cd_conta)` por código** — reaproveita o dedup de trimestre/acumulado diretamente sobre o conjunto já filtrado por `DS_CONTA`. Fazer diferente (filtrar por texto pra achar o código certo, depois reconsultar o dataframe inteiro por esse código) mistura contas diferentes que só coincidem numericamente em anos distintos — exatamente o caso da TAEE3 acima. Esse foi o bug mais sério encontrado na validação: antes da correção, WIZC3 e TAEE3 mostravam captação/amortização com sinal invertido (impossível: captação negativa, amortização positiva); depois, 0 anomalias em 20 tickers
- **FCFE: valores suspeitos viram `None`, não um número sabidamente errado** — se a captação sair negativa, ou CAPEX/amortização saírem positivos (deveriam ser sempre saída de caixa), `buscar_inputs_fcfe_cvm()` descarta o valor pra `None` em vez de expor. Confirmado em WIZC3: a própria empresa reporta "Empréstimos tomados" com valor negativo no CSV bruto da CVM (inconsistência real da empresa, não bug do filtro) — sem esse guard, isso viraria uma "nova dívida emitida" negativa, absurdo
- **FCFE: sinal de CAPEX e amortização de dívida** — a CVM reporta as duas como saída de caixa (negativa, mesma convenção do DFC inteiro). `calcular_fcfe()` espera as duas como MAGNITUDE positiva (ver `test_fcfe.py`: `capex=400`, `amortizacao_dividas=300`). `_magnitude_convencao_fcfe()` inverte o sinal, mesmo padrão de `_delta_ccl_convencao_academica()`. Captação (`novas_dividas_emitidas`) não precisa de inversão — a CVM já reporta como entrada positiva, mesma convenção que `calcular_fcfe()` espera
- **FCFE agora fica `fcfe_completo_disponivel: True`** quando os 6 campos existem (validado ponta a ponta contra BEEF3 e CSED3, com `calcular_fcfe()` rodando de verdade) — antes sempre `False`. Ainda fica `False` quando algum campo de texto genuinamente não bateu nenhuma linha pra aquele ticker (ex: PETR4/MRFG3/JBSS3 não tinham captação de dívida no período mais recente disponível — não é falha do filtro, é ausência real de movimento naquele trimestre)
- **BUG PRÉ-EXISTENTE corrigido: TTM via `.tail(4).sum()` cobria ~15 meses, não 12** — `qualidade_lucro` e `divida_bruta_ebitda` (EBITDA) em `buscar_saude_financeira_cvm()` já faziam `_extrair_serie(...).tail(4).sum()` desde a tarefa de alavancagem/câmbio, bem antes do FCFE existir. Causa raiz: o ITR **nunca** reporta o 4º trimestre isolado (só sai via DFP, como total anual) — então `.tail(4)` sobre a série só-ITR pula o Q4 do ano corrente inteiro e inclui o Q1 do ano seguinte pra compensar. Achado durante a investigação do FCFE (mesmo `.tail(4).sum()` ia ser reaproveitado ali), não introduzido por ela. Corrigido com `calcular_ttm_correto(df_itr, df_dfp, codigo_conta)`: reconstrói Q4(ano) = DFP_anual(ano) − [ITR_Q1+Q2+Q3(ano)] só quando os 3 trimestres ITR do ano estão todos presentes (nunca estima Q4 parcial), monta a série trimestral completa e soma os 4 trimestres cronologicamente mais recentes de verdade (pode cruzar virada de ano fiscal, ex: 4T25-derivado+1T26+2T26+3T26). Validado contra BEEF3: a soma do ano fiscal 2025 completo (1T25+2T25+3T25+4T25-derivado) bateu **exatamente** com o lucro anual oficial do fato relevante (R$ 848.260.000, via `dfp_dre_2025.csv`) — confirma a derivação matematicamente. `buscar_saude_financeira_cvm()` (FCO, lucro, EBIT, D&A) e `buscar_inputs_fcfe_cvm()` (lucro líquido, depreciação, ΔCCL) foram refatoradas pra usar a função nova; `tendencia_receita`/`margens_pct`/gráficos trimestrais ficaram como estavam (não são somas TTM, fora do escopo desta correção)
- **TTM corrigido: score do BEEF3 não mudou** — `divida_bruta_ebitda` foi de 4.47x pra 4.94x e `qualidade_lucro` (FCO/Lucro) de 4.5x pra 5.8x com a correção, mas o score final continuou 3.0/"Fraca" (score geral do app: "Risco Elevado / Evitar") — a alavancagem já estava acima de 4x antes e depois, então a trava crítica (`score = min(score, 4.5)`) já capava o resultado nos dois casos. O alerta já estava correto antes desta correção especificamente pro BEEF3; o bug do TTM é real e generalizado (afeta todo ticker com histórico ITR, não só BEEF3), só não mudou o veredito qualitativo deste ticker em particular
- **TTM corrigido: achado à parte durante a validação, fora de escopo** — `ITUB4` (e provavelmente todo banco/instituição financeira) não retorna dado nenhum pra `CONTA_LUCRO_LIQUIDO="3.11"`, nem antes nem depois desta correção. Bancos usam taxonomia de DRE totalmente diferente na CVM (COSIF, não IFRS industrial — `3.01`/`3.02` são "Receitas/Despesas da Intermediação Financeira", `3.05` é "Resultado Antes dos Tributos" em vez de EBIT). Pré-existente, não introduzido agora; as constantes `CONTA_*` deste arquivo nunca foram calibradas pra bancos. `calcular_ttm_correto()` lida com isso graciosamente (retorna `valor: None`, não quebra) — mas a saúde financeira via CVM segue indisponível pra bancos até alguém mapear a taxonomia COSIF separadamente
- **TTM corrigido: validado contra 8 tickers** (BEEF3, PETR4, ITUB4, JBSS3, MRFG3, ABEV3, CSED3, RENT3, MGLU3) — Q4 derivado ficou negativo em 3 casos (PETR4/2024: -R$17bi, MRFG3/2025: -R$42,5mi, CSED3/2024: -R$9,8mi). Não descartados: PETR4/2024 é plausível (Petrobras teve resultado trimestral negativo divulgado publicamente naquele período, provavelmente por impairment) e os outros dois são pequenos relativo ao anual (~6-7%), plausíveis como sazonalidade. Nenhum caso teve magnitude "obviamente absurda" (>3x o anual com sinal invertido) — se aparecer um desses no futuro, vale investigar a demonstração original daquela empresa/ano antes de confiar no valor derivado

- **BUG CORRIGIDO: `CONTA_DEPRECIACAO_AMORTIZACAO` (posição fixa `6.01.01.02`) não é confiável — 32% de divergência, sem concentração setorial.** Auditoria completa contra as ~450 empresas de `itr_dre_2025`/`itr_dfc_2025` (ver auditoria de `CONTA_EBIT`/`CONTA_DEPRECIACAO_AMORTIZACAO` abaixo) encontrou que `ST_CONTA_FIXA="S"` significa apenas "posição obrigatória de preencher", não "sempre o mesmo conceito contábil": a posição `6.01.01.02` diverge em 140/438 empresas (32%), incluindo Petrobras (continha "Encargos, Rendimentos Financeiros..."), Sabesp ("Provisões e Variações Monetárias"), Usiminas ("Encargos e Variações Monetárias/Cambiais"), Grendene ("Resultado de equivalência patrimonial"), Whirlpool ("Lucro antes dos impostos... operações descontinuadas"), Itaú, Vale, CSN Mineração e dezenas de outras empresas "normais", sem nenhum tratamento especial de setor hoje. **Corrigido com `DEPRECIACAO_PREFIXO = "6.01.01"` + `PADRAO_DEPRECIACAO_INCLUIR/EXCLUIR`**, reaproveitando `extrair_por_texto()` (mesmo padrão do CAPEX/financiamento) — casa `deprecia|amortiza|exaust` dentro do bloco de reconciliação, excluindo variações de "amortização" de natureza financeira/tributária/receita (custo de captação/transação de dívida, juros, créditos fiscais, despesas antecipadas, receita diferida — achado ao auditar ~5700 variações reais de DS_CONTA dentro do prefixo). Se nenhuma linha bate, retorna `None` explícito — não cai de volta pra posição fixa. **Validado contra TODAS as ~450 empresas** (não amostra): **227 tiveram o valor de D&A mudado pela correção** (contagem final, já com a correção do bug de acumulado — ver abaixo — aplicada; uma primeira rodada feita antes dessa correção havia contado 231, número corrigido após re-validação; lista completa em `/tmp/dna_texto_mudancas.csv`, gerada durante a validação — não commitada). Âncora Petrobras confirmada: D&A anual DFP 2025 bateu em R$84,39bi, dentro da faixa esperada pelo Form 20-F/SEC (US$15.147mi × câmbio médio ~5,3-5,5 → R$80-83bi esperado, ~1,7% de diferença, plausível dado a aproximação cambial). `buscar_saude_financeira_cvm()` (EBITDA/`divida_bruta_ebitda`) e `buscar_inputs_fcfe_cvm()` (`depreciacao`) foram refatoradas pra usar `calcular_ttm_por_texto()` com os novos padrões, nos dois lugares. **Nota sobre os audits de "% divergência" (este de D&A, 140/438, e o de ΔCCL, 0%)**: são audits de TEXTO/POSIÇÃO (comparam `DS_CONTA` contra um regex esperado, sem soma de TTM) — ortogonais ao bug do acumulado abaixo, continuam válidos como reportados. Já o VALOR de TTM (o que entra em `divida_bruta_ebitda`/`delta_ccl`) é sensível ao acumulado: isoladamente, a correção do acumulado muda o D&A-por-texto de 23 empresas e o ΔCCL de 19 (mesmo conjunto sensível de sempre — Santander, Banco Pine, Banco Daycoval, OI, Camil, etc., ver bug abaixo)

- **BUG CORRIGIDO (mais sério, achado DURANTE a validação do D&A por texto): o DFC no ITR nunca reporta trimestre isolado — só ACUMULADO desde 1º/jan do ano fiscal.** Diferente da DRE (que reporta as duas formas — isolado E acumulado — daí a correção de trimestre/acumulado já documentada em `_extrair_serie()`), o DFC (`DFC_MI_con` — Demonstração de Fluxo de Caixa) só reporta o acumulado: `DT_INI_EXERC` é sempre 1º/jan do ano, mesmo pro "3º trimestre" (que na prática já são 9 meses acumulados). Confirmado sistematicamente: 441 de 451 empresas têm essa característica na conta FCO (`6.01`). Isso significa que `_ttm_a_partir_de_series()` (usada por `calcular_ttm_correto()` e `calcular_ttm_por_texto()`), ao tratar toda série ITR como se fosse sempre isolada — certo pra DRE, mas errado pra qualquer conta de DFC —, estava somando valores acumulados como se fossem isolados. Isso afeta **todo dado que vem do DFC**: FCO (`qualidade_lucro`), D&A (`divida_bruta_ebitda`, ver acima), ΔCCL, CAPEX e financiamento (FCFE inteiro). **Corrigido**: `_extrair_linhas()`/`_extrair_linhas_por_texto()` (renomeadas de `_extrair_serie()`/`extrair_por_texto()`, que viraram wrappers finos que colapsam em `pd.Series` — API pública inalterada) agora preservam `DT_INI` por período; `_ttm_a_partir_de_series()` detecta por trimestre se `DT_INI == 1º/jan` (acumulado, convenção DFC) ou não (isolado, convenção DRE) e isola por diferença contra o acumulado-até-o-trimestre-anterior antes de somar os últimos 4 trimestres. A fórmula generaliza a antiga (quando tudo é isolado, degenera exatamente na fórmula anterior — por isso todos os testes de DRE já existentes continuaram batendo sem alteração)
  - **Achado curioso durante a validação**: a correção deu o MESMO resultado de antes pra Petrobras (TTM de D&A/FCO idêntico) — não por engano, mas por telescopagem matemática: a janela "últimos 4 trimestres" mais comum hoje (2025T2+2025T3+2025T4-derivado+2026T1, dado que a maioria das empresas de calendário-fiscal-dezembro só tem dado até 2026T1 nesta data) faz os termos acumulados intermediários se cancelarem exatamente, resultando na mesma fórmula simplificada (`Anual − Q1 + Q1_ano_seguinte`) nos dois casos. Isso NÃO significa que o bug era inofensivo — é uma coincidência da janela temporal atual. **Validação isolada do impacto real**: comparando a lógica antiga vs nova pra TODAS as ~450 empresas na conta FCO, 22 empresas (as que estão em janelas de trimestres diferentes — dados atrasados, ano fiscal não-dezembro, etc.) mostraram diferença REAL e material, incluindo **Banco Santander (FCO TTM: R$119,4bi → R$64,4bi)**, Banco Pine (R$170M → R$2,03bi), Banco Daycoval (-R$3,27bi → -R$6,87bi) e OI (R$11,6M → -R$529,9M, inverteu de sinal). Essa lista de 22 tickers vai mudar a cada ~3 meses conforme a janela "trimestre mais recente" avança — o bug é estrutural e recorrente, não um evento único; a correção é permanente
  - **Consequência de score**: `qualidade_lucro` (FCO/Lucro) entra direto no score de saúde financeira (±1,5 ou ±0,5 dependendo da faixa — ver `valuation/saude_financeira.py`). Os 22 tickers acima (e qualquer outro que caia numa janela não-invariante no futuro) podem ter o score de saúde financeira mudado por essa correção — vale investigar caso a caso se um usuário perguntar "por que o score do Banco X mudou"
  - **Teste de equivalência**: `test_ttm_correto.py::TestConvencaoAcumuladaDoDfc` prova que a fórmula nova produz resultado idêntico à antiga quando o dado é isolado (equivalência matemática) e isola corretamente quando o dado é acumulado (réplica exata do caso real da Petrobras)

- **Efeito colateral encontrado e corrigido: `MAPA_NOMES_CVM["SBSP3"]` tinha um erro de digitação pré-existente** ("CIA SANEAMENTO BASICO EST SAO PAULO" — "EST" abreviado errado — em vez de "ESTADO"), quebrando silenciosamente a busca da Sabesp na CVM desde que o mapeamento foi criado (não relacionado ao bug de D&A/acumulado, achado ao tentar validar Sabesp como um dos tickers de regressão). Corrigido pra "ESTADO" por extenso — Sabesp agora disponível: `divida_bruta_ebitda=3,34x`, score 7,0/"Boa", 1 alerta de alavancagem elevada (não crítica)

- **Verificação de veredito pós-correção (D&A + acumulado) em tickers com resultado já documentado ou testado**:
  - **BEEF3/Minerva: score/alerta NÃO mudou** (continua 3,0/"Fraca", trava crítica "Risco Elevado / Evitar") — Minerva não estava na lista de 227 tickers com D&A mudado (a posição fixa já era correta pra essa empresa especificamente) nem na lista de 22 tickers afetados pelo bug de acumulado (janela atual é a telescópica invariante)
  - **PETR4/Petrobras: `divida_bruta_ebitda` mudou de 2,41x (errado, D&A subestimado pela posição fixa) pra 1,61x (correto)** — mas as duas caem na mesma faixa neutra de score (1,0x–2,5x, sem pontuação), então o score final não mudou, só o número exibido ficou mais preciso
  - **SBSP3/Sabesp: ficou disponível pela primeira vez** (bug de digitação não relacionado, ver acima) — 7,0/"Boa"
  - **USIM5/Usiminas: `divida_bruta_ebitda` continua `None`** (EBIT TTM atual é negativo — guarda pré-existente de `ebitda_ttm > 0` em `buscar_saude_financeira_cvm()`, não afetada por esta correção) — score 1,0/"Crítica" vem de `qualidade_lucro` negativo (-1,27x) e margem líquida negativa, não de alavancagem

- **`CONTA_EBIT` (`3.05`): decisão — manter posição fixa, documentar como dívida técnica de baixo impacto.** A mesma auditoria completa encontrou divergência em 19/459 empresas (4,1%), mas 95% concentrada em bancos/seguradoras — setores onde o resto do pipeline (`CONTA_LUCRO_LIQUIDO`/`3.11`) já retorna indisponível por taxonomia COSIF (ver nota sobre ITUB4 acima), ou seja, já efetivamente excluídos do pipeline de saúde financeira. Diferente do D&A, o EBIT não tem um padrão de texto limpo e estável tipo `deprecia|amortiza|exaust` — "Resultado Antes do Resultado Financeiro e dos Tributos" tem fraseado muito mais variável entre empresas, tornando uma correção por texto mais arriscada (maior chance de falso-positivo) pra um ganho pequeno (4,1% de divergência, já isolado em setores sem uso prático). Correção adiada até que apareça evidência de impacto real fora de bancos/seguradoras

- **FCFE: integração ponta a ponta concluída** — `valuation/fcfe_valuation.py::calcular_valuation_fcfe()` liga `buscar_inputs_fcfe_cvm()` → `calcular_fcfe()` → `valuation_fcfe_dois_estagios()`, exposto em `dados_finais["fcfe"]` no endpoint `/api/valuation/{ticker}` (mesmo endpoint que já tem a rota `/api/*` duplicada de produção — não foi criada rota separada). Card de frontend `FcfeSection.tsx` renderizado ao lado do card de Cenários DCF.
  - **Ke reaproveitado do CAPM, não recalculado**: `taxa_capm` (já calculado em `main.py` via `calcular_capm()`) é passado direto como `ke` — FCFE desconta a custo de capital PRÓPRIO, não a WACC (`taxa_desconto`), porque o fluxo já é líquido dos efeitos de dívida (diferente do FCFF/DCF, que desconta a WACC)
  - **Crescimento explícito e g_perpetuo: decisão explícita do usuário — espelham o DCF Duas Fases, não o DCF principal.** O app já tinha DOIS DCFs com premissas de crescimento diferentes e nenhuma delas vindo de `crescimento.py` (ambas são constantes/cadeias hardcoded direto em `main.py`): o DCF principal usa uma cadeia de clamps CVM/Fundamentus + `g_perpetuo=0.03` hardcoded; o DCF Duas Fases usa `min(crescimento_5a, 0.30)` (crescimento bruto do Fundamentus) + `g_perpetuo=0.04` hardcoded. Perguntado ao usuário qual delas o FCFE deveria espelhar pra a comparação lado a lado ser consistente — escolhido o **DCF Duas Fases**: `taxa_crescimento_explicito = min(crescimento_5a, 0.30)`, `g_perpetuo = 0.04`, `anos_explicitos = 5` (mesmos valores, mesma fonte, reutilizados literalmente em `main.py`, não recalculados)
  - **Sector-aware via `eh_setor_bancario_ou_segurador()`**: mesmo critério de correspondência parcial de `setor.py::get_configuracao_setor()` contra as 3 chaves financeiras (`Bancos`, `Seguradoras`, `Intermediários Financeiros`) — bancos/seguradoras retornam `{"disponivel": False, "erro": "FCFE indisponível — taxonomia COSIF/SUSEP não suportada"}` **sem sequer consultar a CVM** (curto-circuito antes de `buscar_inputs_fcfe_cvm()`, testado com `assert_not_called()`). Bug pego durante os testes: string vazia é substring de qualquer coisa em Python (`"" in "bancos"` → `True`), então um `setor` vazio/ausente casaria incorretamente como banco — guard explícito adicionado (`if not setor_limpo: return False`). O mesmo padrão de correspondência em `setor.py::get_configuracao_setor()` tinha a MESMA vulnerabilidade pra string vazia — **corrigido depois, numa tarefa pontual separada**: guard `if setor_limpo:` em volta do loop de correspondência parcial, mesma lógica da correção acima. Testes de regressão em `test_setor.py` (`test_setor_vazio_nao_cai_em_classificacao_especifica`, `test_setor_none_nao_cai_em_classificacao_especifica`)
  - **`fcfe_completo_disponivel: False` propaga como indisponibilidade explícita com os campos parciais visíveis** (`inputs_parciais`), não tenta calcular com dado faltando — nem `fcfe_ano_base` nem `projecao` aparecem no retorno nesse caso, e o frontend mostra os campos que já batiam num `<details>` colapsável
  - **Achado real durante a validação end-to-end com BEEF3: FCFE ano-base e valor justo por ação deram NEGATIVOS** (`fcfe = -R$4,97bi`, `valor_justo_por_acao ≈ -R$54 a -R$73` dependendo do dia/janela TTM). Causa: a Minerva fez uma desalavancagem pontual grande no TTM mais recente (amortização de ~R$11,5bi contra captação de ~R$5,9bi, líquido de ~-R$5,6bi) — isso não é bug de extração (mesmos números validados durante a auditoria do ΔCCL/D&A), é uma característica conhecida e inerente do modelo de FCFE em 2 estágios: um evento de financiamento pontual no ano-base é projetado crescendo `(1+g)^n` por 5 anos + perpetuidade, amplificando um evento não-recorrente numa "premissa permanente". O frontend mostra um aviso explícito quando `valor_justo_por_acao <= 0`, orientando a não interpretar como preço-alvo direto nesses casos
  - **Validado manualmente no navegador**: BEEF3 (não-financeiro) mostra o card completo com os números acima; ITUB4 (`setor = "Intermediários Financeiros"`) mostra a mensagem de indisponibilidade, sem quebrar o resto da página
  - Testes em `tests/test_fcfe_valuation.py` (16 testes): fluxo completo com valores reais da BEEF3, `num_acoes` inválido, detecção de setor bancário/segurador (incluindo o guard de string vazia), curto-circuito sem consultar CVM pra bancos/seguradoras, `fcfe_completo_disponivel=False` propagando sem quebrar, CVM totalmente indisponível

## ⚠️ Problemas conhecidos

- yfinance com rate limit frequente — Fundamentus é a fonte primária
- Histórico 5 anos via yfinance falhando por rate limit
- Brapi tem limitações no plano gratuito (praticamente 1 empresa por conta) — usado apenas como fallback
- CVM bloqueia requests Python/servidor — só funciona via curl com User-Agent de browser
- Dados CVM precisam ser atualizados manualmente 1x por trimestre via `atualizar_cvm.py`
- CVM: só o BPP (Passivo) é baixado, não o BPA (Ativo) — por isso alavancagem usa Dívida Bruta, não Líquida (ver decisão técnica acima)
- CVM: `MAPA_NOMES_CVM` cobre só os tickers problemáticos já mapeados manualmente — tickers fora do mapa dependem do nome vindo do provider (Fundamentus/etc) bater com a razão social oficial da CVM após normalização, o que falha silenciosamente (`disponivel: False`) para vários tickers ainda não mapeados
- **`fco_trimestral`/gráficos trimestrais de DFC podem estar rotulados errado — achado durante a investigação do bug de acumulado, NÃO corrigido ainda.** `buscar_saude_financeira_cvm()` usa `_extrair_serie(dfc, CONTA_FCO)` direto (fora do caminho de TTM) pra montar o gráfico trimestral de FCO exibido no frontend — como o DFC é acumulado (não isolado, ver acima), esses pontos provavelmente representam "acumulado desde 1º/jan" rotulados como se fossem o fluxo daquele trimestre isolado, pra a maioria das empresas. Decisão desta sessão: focar a correção no TTM (que afeta score/alertas, maior gravidade) e deixar o gráfico como dívida técnica separada — mudar o comportamento de um gráfico já exibido é uma decisão de produto (isolar por diferença mudaria os NÚMEROS mostrados no gráfico pra praticamente todo ticker) que não estava no escopo pedido, então precisa de confirmação explícita antes de mexer
- **FCFE: cobertura de captação/amortização varia bastante por ticker** — bancos/seguradoras-holding (ITUB4, BBAS3, BBSE3, CXSE3) não têm captação/amortização de dívida via este filtro (consistente com o gap de taxonomia COSIF já documentado, e agora tratado explicitamente via `eh_setor_bancario_ou_segurador()` — ver decisão técnica de integração do FCFE); mesmo fora de bancos, alguns tickers legitimamente não têm captação no trimestre mais recente disponível (PETR4, MRFG3, JBSS3 no momento desta validação) — `None`/vazio nesses casos é o comportamento correto, não uma falha a corrigir

## 🗺️ Roadmap

| Fase | Descrição | Status |
|------|-----------|--------|
| 1 | Motor de valuation completo (todos os métodos + frontend) | ✅ Completa |
| 2 | Watchlist (localStorage) + Deploy Railway | ✅ Completa |
| 2.5 | Saúde Financeira via dados CVM (DRE/DFC trimestrais) | ✅ Completa |
| 2.6 | FCFE — Valuation de Equity via CVM (ponta a ponta) | ✅ Completa |
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
