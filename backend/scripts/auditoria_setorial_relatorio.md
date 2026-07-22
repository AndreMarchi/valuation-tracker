# Auditoria Setorial — Valuation Tracker

Gerado em 22/07/2026 01:05 · 327 tickers cobertos, 39 com erro na coleta.

## Resumo executivo

- **41** setores reais têm pelo menos 1 dicionário em fallback (de 41 setores encontrados)
- **327** tickers estão em setores com 2+ colunas em fallback (candidatos mais fortes a bug)
- **31** tickers têm os 3 métodos de fluxo de caixa aplicáveis simultaneamente (base da Parte 2)
- **81** tickers têm CAGR de receita E de lucro disponíveis (base da Parte 3)
- **97** tickers com beta fora de [0.15, 2.5]; **0** ocorrências de Ke/WACC fora de [8%, 35%]

**Achado incidental (fora dos 4 tipos pedidos, encontrado ao implementar a Parte 4):** `valuation/wacc.py::calcular_wacc()` usa `dados.get("selic", 0.145)` — `main.py` nunca injeta o Selic real nesse dict antes de chamar a função (só `scanner/trabalhador.py` faz isso), então o WACC do DCF principal em produção sempre usa 14,5% hardcoded, não o Selic real buscado via `buscar_selic_atual()` (que já é usado corretamente pro CAPM/Ke, umas linhas antes). Não corrigido por este script — é uma ferramenta de diagnóstico.

### Candidatos pra checagem manual primeiro

1. setor **Diversos** (15 tickers, 8 colunas em fallback)
1. setor **Tecidos, Vestuário e Calçados** (15 tickers, 8 colunas em fallback)
1. setor **Exploração de Imóveis** (12 tickers, 8 colunas em fallback)
1. setor **Comércio e Distribuição** (11 tickers, 8 colunas em fallback)
1. setor **Serv.Méd.Hospit. Análises e Diagnósticos** (10 tickers, 8 colunas em fallback)
1. ticker **DOTZ3** (amplitude de 2968.0pp entre DCF/DCF-2-fases/FCFE)
1. ticker **BEEF3** (amplitude de 1530.9pp entre DCF/DCF-2-fases/FCFE)
1. ticker **MGLU3** (amplitude de 1230.1pp entre DCF/DCF-2-fases/FCFE)
1. ticker **PRIO3** (gap CAGR receita−lucro de 41.8pp)
1. ticker **RENT3** (gap CAGR receita−lucro de 38.3pp)

## Parte 1 — Matriz de cobertura setor × dicionário

Ordenado por nº de colunas em fallback (desc), depois por nº de tickers afetados (desc) — setores no topo são os candidatos mais prováveis a bug ainda não descoberto.

| Setor | Tickers | Nº fallback | BETA_POR_SETOR | EV_EBITDA_MEDIO_SETOR | PSR_MEDIO_SETOR | SETORES_REGULADOS | SETORES_CICLICOS_main.py | SETORES_CICLICOS_trabalhador.py | setor.py (substring) | nopat.py (FATOR_CONVERSAO_NOPAT) | fcfe_valuation.py (COSIF/SUSEP) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Diversos | 15 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Tecidos, Vestuário e Calçados | 15 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Exploração de Imóveis | 12 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Comércio e Distribuição | 11 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Serv.Méd.Hospit. Análises e Diagnósticos | 10 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Programas e Serviços | 9 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Máquinas e Equipamentos | 9 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Agropecuária | 8 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Químicos | 7 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Viagens e Lazer | 7 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Serviços Diversos | 7 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Previdência e Seguros | 7 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Água e Saneamento | 6 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Madeira e Papel | 5 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Construção e Engenharia | 5 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Holdings Diversificadas | 4 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Serviços Financeiros Diversos | 4 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Produtos de Uso Pessoal e de Limpeza | 3 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Automóveis e Motocicletas | 3 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Hoteis e Restaurantes | 3 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Medicamentos e Outros Produtos | 2 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Utilidades Domésticas | 2 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Outros | 2 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Computadores e Equipamentos | 2 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Industrials | 1 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Financial Services | 1 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Equipamentos | 1 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Consumer Cyclical | 1 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Bebidas | 1 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Mídia | 1 | 8 | fallback | fallback | fallback | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Telecomunicações | 8 | 7 | fallback | fallback | fallback | bate | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Material de Transporte | 7 | 7 | fallback | fallback | bate | fallback | fallback | fallback | fallback_padrao | fallback_padrao | n/a |
| Petróleo, Gás e Biocombustíveis | 14 | 5 | bate | bate | fallback | fallback | fallback | fallback | fallback_dinamico | bate | n/a |
| Energia Elétrica | 35 | 3 | bate | bate | fallback | bate | fallback | fallback | bate | bate | n/a |
| Construção Civil | 23 | 3 | bate | bate | bate | fallback | fallback | fallback | bate | bate | n/a |
| Intermediários Financeiros | 23 | 3 | bate | bate | fallback | bate | fallback | fallback | bate | bate | bancário/segurador |
| Varejo | 19 | 3 | bate | bate | bate | fallback | fallback | fallback | bate | bate | n/a |
| Transporte | 13 | 3 | bate | bate | fallback | fallback | bate | bate | fallback_padrao | bate | n/a |
| Siderurgia e Metalurgia | 7 | 3 | bate | bate | fallback | fallback | bate | bate | fallback_padrao | bate | n/a |
| Mineração | 4 | 3 | bate | bate | fallback | fallback | bate | bate | fallback_padrao | bate | n/a |
| Alimentos | 10 | 2 | bate | bate | bate | fallback | bate | bate | fallback_padrao | bate | n/a |

**Detalhe do fallback dinâmico/nopat por setor** (colunas com mecanismo não-óbvio):

| Setor | setor.py: branch usado | nopat.py: fator observado |
|---|---|---|
| Diversos | CONFIGURACAO_PADRAO | 0.65 |
| Tecidos, Vestuário e Calçados | CONFIGURACAO_PADRAO | 0.65 |
| Exploração de Imóveis | CONFIGURACAO_PADRAO | 0.65 |
| Comércio e Distribuição | CONFIGURACAO_PADRAO | 0.65 |
| Serv.Méd.Hospit. Análises e Diagnósticos | CONFIGURACAO_PADRAO | 0.65 |
| Programas e Serviços | CONFIGURACAO_PADRAO | 0.65 |
| Máquinas e Equipamentos | CONFIGURACAO_PADRAO | 0.65 |
| Agropecuária | CONFIGURACAO_PADRAO | 0.65 |
| Químicos | CONFIGURACAO_PADRAO | 0.65 |
| Viagens e Lazer | CONFIGURACAO_PADRAO | 0.65 |
| Serviços Diversos | CONFIGURACAO_PADRAO | 0.65 |
| Previdência e Seguros | CONFIGURACAO_PADRAO | 0.65 |
| Água e Saneamento | CONFIGURACAO_PADRAO | 0.65 |
| Madeira e Papel | CONFIGURACAO_PADRAO | 0.65 |
| Construção e Engenharia | CONFIGURACAO_PADRAO | 0.65 |
| Holdings Diversificadas | CONFIGURACAO_PADRAO | 0.65 |
| Serviços Financeiros Diversos | CONFIGURACAO_PADRAO | 0.65 |
| Produtos de Uso Pessoal e de Limpeza | CONFIGURACAO_PADRAO | 0.65 |
| Automóveis e Motocicletas | CONFIGURACAO_PADRAO | 0.65 |
| Hoteis e Restaurantes | CONFIGURACAO_PADRAO | 0.65 |
| Medicamentos e Outros Produtos | CONFIGURACAO_PADRAO | 0.65 |
| Utilidades Domésticas | CONFIGURACAO_PADRAO | 0.65 |
| Outros | CONFIGURACAO_PADRAO | 0.65 |
| Computadores e Equipamentos | CONFIGURACAO_PADRAO | 0.65 |
| Industrials | CONFIGURACAO_PADRAO | 0.65 |
| Financial Services | CONFIGURACAO_PADRAO | 0.65 |
| Equipamentos | CONFIGURACAO_PADRAO | 0.65 |
| Consumer Cyclical | CONFIGURACAO_PADRAO | 0.65 |
| Bebidas | CONFIGURACAO_PADRAO | 0.65 |
| Mídia | CONFIGURACAO_PADRAO | 0.65 |
| Telecomunicações | CONFIGURACAO_PADRAO | 0.65 |
| Material de Transporte | CONFIGURACAO_PADRAO | 0.65 |
| Petróleo, Gás e Biocombustíveis | petróleo/gás | 0.45 |
| Energia Elétrica | Energia Elétrica | 0.6 |
| Construção Civil | Construção Civil | 0.6 |
| Intermediários Financeiros | Intermediários Financeiros | 0.0 |
| Varejo | Varejo | 0.75 |
| Transporte | CONFIGURACAO_PADRAO | 0.4 |
| Siderurgia e Metalurgia | CONFIGURACAO_PADRAO | 0.5 |
| Mineração | CONFIGURACAO_PADRAO | 0.55 |
| Alimentos | CONFIGURACAO_PADRAO | 0.5 |

## Parte 2 — Divergência entre DCF principal / DCF Duas Fases / FCFE

Amplitude = maior margem de segurança menos menor margem, entre os 3 métodos (só tickers onde os 3 rodaram). Ordenado decrescente — topo é o candidato mais provável a reproduzir a mesma inconsistência já vista em BEEF3/VULC3.

| Ticker | Setor | Amplitude (pp) | DCF principal | DCF Duas Fases | FCFE |
|---|---|---|---|---|---|
| DOTZ3 | Diversos | 2968.0 | 467.7 | -17.9 | -2500.3 |
| BEEF3 | Alimentos | 1530.9 | -87.1 | 15.2 | -1515.7 |
| MGLU3 | Varejo | 1230.1 | -78.2 | -87.3 | 1142.9 |
| ETER3 | Construção e Engenharia | 1010.8 | -133.7 | -15.2 | -1026.0 |
| AZZA3 | Varejo | 415.6 | -12.5 | 254.9 | 403.1 |
| VULC3 | Tecidos, Vestuário e Calçados | 365.8 | -56.3 | 309.5 | 200.4 |
| MGEL3 | Siderurgia e Metalurgia | 340.2 | -299.0 | 41.2 | -275.6 |
| SMTO3 | Alimentos | 332.0 | -155.8 | -15.5 | 176.1 |
| CALI3 | Construção Civil | 309.6 | -65.3 | 206.1 | 244.2 |
| NEOE3 | Energia Elétrica | 200.7 | -130.3 | -19.8 | 70.4 |
| RAIL3 | Transporte | 200.2 | -106.2 | -70.6 | -270.8 |
| ZAMP3 | Hoteis e Restaurantes | 195.7 | -116.5 | -86.0 | -281.7 |
| CSED3 | Diversos | 182.5 | 0.5 | 151.4 | -31.1 |
| TOTS3 | Programas e Serviços | 147.1 | -67.0 | -62.6 | 80.1 |
| GMAT3 | Comércio e Distribuição | 130.6 | -25.2 | 105.4 | 6.2 |
| UGPA3 | Petróleo, Gás e Biocombustíveis | 111.2 | -105.1 | -50.4 | 6.1 |
| PNVL3 | Comércio e Distribuição | 107.4 | -96.7 | -30.6 | 10.8 |
| MRSA3B | Transporte | 105.0 | -93.2 | -1.1 | -106.1 |
| TAEE11 | Energia Elétrica | 101.8 | -100.9 | 0.9 | -5.1 |
| CPFE3 | Energia Elétrica | 98.9 | -80.3 | -25.6 | 18.5 |
| VITT3 | Químicos | 95.3 | -108.1 | -49.2 | -12.8 |
| SLCE3 | Agropecuária | 83.8 | -106.5 | -80.5 | -22.6 |
| ENEV3 | Energia Elétrica | 69.3 | -108.0 | -56.7 | -126.0 |
| KEPL3 | Máquinas e Equipamentos | 68.0 | -65.3 | -41.3 | 2.7 |
| RENT3 | Diversos | 46.7 | -73.7 | -68.7 | -27.0 |
| EUCA3 | Madeira e Papel | 37.8 | -55.4 | -33.8 | -71.6 |
| GEPA3 | Energia Elétrica | 32.3 | -129.0 | -96.7 | -100.0 |
| ALPA3 | Tecidos, Vestuário e Calçados | 26.4 | -74.2 | -51.4 | -47.9 |
| B3SA3 | Serviços Financeiros Diversos | 23.5 | -71.7 | -48.9 | -48.2 |
| LUXM3 | Transporte | 19.6 | -88.5 | -68.9 | -87.3 |
| WEGE3 | Máquinas e Equipamentos | 13.6 | -76.1 | -66.9 | -80.5 |

## Parte 3 — CAGR Receita 5a − CAGR Lucro 5a

Não prova o bug de crescimento-de-receita-pra-projetar-lucro sozinho, mas ordena por probabilidade do efeito ser relevante. "Dado insuficiente" ≠ 0 — não conta como gap zero.

**81 tickers com os dois CAGRs disponíveis, 246 com dado insuficiente/piso.**

| Ticker | Setor | Gap (pp) | CAGR Receita 5a | CAGR Lucro (CVM) |
|---|---|---|---|---|
| PRIO3 | Petróleo, Gás e Biocombustíveis | 41.8 | 36.8% | -5.0% |
| RENT3 | Diversos | 38.3 | 40.1% | 1.8% |
| HOOT4 | Hoteis e Restaurantes | 37.7 | 32.7% | -5.0% |
| ALOS3 | Exploração de Imóveis | 36.3 | 31.3% | -5.0% |
| WLMM3 | Varejo | 21.6 | 16.6% | -5.0% |
| MULT3 | Exploração de Imóveis | 14.1 | 19.9% | 5.8% |
| LEVE3 | Automóveis e Motocicletas | 14.1 | 9.1% | -5.0% |
| HBOR3 | Construção Civil | 13.0 | 8.0% | -5.0% |
| INTB3 | Computadores e Equipamentos | 12.9 | 7.9% | -5.0% |
| SMTO3 | Alimentos | 11.2 | 6.2% | -5.0% |
| MDNE3 | Construção Civil | 11.2 | 41.2% | 30.0% |
| EUCA3 | Madeira e Papel | 10.9 | 5.9% | -5.0% |
| PEAB3 | Holdings Diversificadas | 10.6 | 40.6% | 30.0% |
| AZZA3 | Varejo | 9.8 | 39.8% | 30.0% |
| CGRA3 | Varejo | 8.3 | 3.3% | -5.0% |
| CSMG3 | Água e Saneamento | 8.2 | 9.5% | 1.3% |
| CAMB3 | Tecidos, Vestuário e Calçados | 8.1 | 5.6% | -2.5% |
| ENEV3 | Energia Elétrica | 8.1 | 38.1% | 30.0% |
| ODER4 | Alimentos | 7.9 | 2.9% | -5.0% |
| CEBR3 | Energia Elétrica | 7.8 | 7.9% | 0.1% |
| BEES3 | Intermediários Financeiros | 7.5 | 10.0% | 2.5% |
| SLCE3 | Agropecuária | 7.4 | 2.4% | -5.0% |
| TOTS3 | Programas e Serviços | 5.3 | 15.1% | 9.8% |
| WEGE3 | Máquinas e Equipamentos | 5.1 | 12.6% | 7.5% |
| MTSA3 | Industrials | 5.0 | 0% | -5.0% |
| ETER3 | Construção e Engenharia | 4.9 | -0.1% | -5.0% |
| DXCO3 | Madeira e Papel | 4.8 | -0.2% | -5.0% |
| KEPL3 | Máquinas e Equipamentos | 4.6 | -0.4% | -5.0% |
| PTNT3 | Tecidos, Vestuário e Calçados | 4.3 | -0.7% | -5.0% |
| TAEE11 | Energia Elétrica | 4.3 | 11.8% | 7.5% |
| VITT3 | Químicos | 4.2 | -0.8% | -5.0% |
| CALI3 | Construção Civil | 3.7 | 33.7% | 30.0% |
| UGPA3 | Petróleo, Gás e Biocombustíveis | 3.5 | 4.0% | 0.5% |
| FLRY3 | Serv.Méd.Hospit. Análises e Diagnósticos | 3.0 | 22.1% | 19.1% |
| PETR3 | Petróleo, Gás e Biocombustíveis | 2.1 | -2.9% | -5.0% |
| HAGA3 | Construção e Engenharia | 1.6 | -3.4% | -5.0% |
| CPFE3 | Energia Elétrica | 1.3 | 3.1% | 1.8% |
| ABEV3 | Bebidas | 1.2 | 4.6% | 3.4% |
| SAUD3 | Serv.Méd.Hospit. Análises e Diagnósticos | 0.8 | 7.5% | 6.7% |
| GGBR3 | Siderurgia e Metalurgia | -0.1 | -5.1% | -5.0% |
| GMAT3 | Comércio e Distribuição | -0.1 | 22.6% | 22.7% |
| GOAU3 | Siderurgia e Metalurgia | -0.1 | -5.1% | -5.0% |
| VALE3 | Mineração | -0.3 | -5.3% | -5.0% |
| FESA3 | Siderurgia e Metalurgia | -0.6 | -5.6% | -5.0% |
| MRSA3B | Transporte | -0.8 | 13.0% | 13.8% |
| NEOE3 | Energia Elétrica | -0.8 | 4.9% | 5.7% |
| B3SA3 | Serviços Financeiros Diversos | -2.1 | 3.2% | 5.3% |
| PNVL3 | Comércio e Distribuição | -2.6 | 13.2% | 15.8% |
| TECN3 | Tecidos, Vestuário e Calçados | -3.2 | 9.6% | 12.8% |
| BBAS3 | Intermediários Financeiros | -3.6 | -8.6% | -5.0% |
| BMEB3 | Intermediários Financeiros | -3.9 | 23.4% | 27.3% |
| DIRR3 | Construção Civil | -4.0 | 26.0% | 30.0% |
| CSUD3 | Serviços Diversos | -4.6 | 4.9% | 9.5% |
| RSUL4 | Material de Transporte | -5.0 | 4.1% | 9.1% |
| GRND3 | Tecidos, Vestuário e Calçados | -5.2 | 2.3% | 7.5% |
| PSSA3 | Previdência e Seguros | -5.8 | 15.8% | 21.6% |
| BBSE3 | Previdência e Seguros | -6.5 | 0% | 6.5% |
| SOND3 | Construção e Engenharia | -6.9 | 23.1% | 30.0% |
| TRIS3 | Construção Civil | -8.1 | 19.8% | 27.9% |
| LUXM3 | Transporte | -8.7 | 2.4% | 11.1% |

_(+21 tickers adicionais, omitidos por brevidade)_

## Parte 4 — Sanity checks de parâmetro fora de faixa plausível

### Beta fora de [0.15, 2.5] — 97 tickers

| Ticker | Setor | Beta |
|---|---|---|
| CEGR3 | Energia Elétrica | -0.55 |
| EPAR3 | Varejo | -0.51 |
| GPAR3 | Energia Elétrica | -0.5 |
| MAPT3 | Outros | -0.49 |
| BDLL3 | Máquinas e Equipamentos | -0.38 |
| GSHP3 | Exploração de Imóveis | -0.34 |
| SOND3 | Construção e Engenharia | -0.31 |
| AGXY3 | Agropecuária | -0.26 |
| SEQL3 | Serviços Diversos | -0.21 |
| TXRX3 | Tecidos, Vestuário e Calçados | -0.21 |
| AMER3 | Varejo | -0.21 |
| FIGE3 | Outros | -0.21 |
| PEAB3 | Holdings Diversificadas | -0.2 |
| ENMT3 | Energia Elétrica | -0.19 |
| WLMM3 | Varejo | -0.18 |
| RECV3 | Petróleo, Gás e Biocombustíveis | -0.16 |
| BRAV3 | Petróleo, Gás e Biocombustíveis | -0.15 |
| SMTO3 | Alimentos | -0.15 |
| PETR3 | Petróleo, Gás e Biocombustíveis | -0.14 |
| VITT3 | Químicos | -0.14 |
| LAND3 | Agropecuária | -0.12 |
| RAIL3 | Transporte | -0.11 |
| CEED3 | Energia Elétrica | -0.11 |
| CTSA3 | Tecidos, Vestuário e Calçados | -0.1 |
| FRAS3 | Material de Transporte | -0.09 |
| WEGE3 | Máquinas e Equipamentos | -0.08 |
| DOHL3 | Tecidos, Vestuário e Calçados | -0.08 |
| RSUL4 | Material de Transporte | -0.07 |
| MSPA3 | Madeira e Papel | -0.05 |
| OSXB3 | Petróleo, Gás e Biocombustíveis | -0.05 |
| MDIA3 | Alimentos | -0.05 |
| NUTR3 | Químicos | -0.04 |
| PGMN3 | Comércio e Distribuição | -0.04 |
| BPAR3 | Intermediários Financeiros | -0.04 |
| CGAS3 | Energia Elétrica | -0.04 |
| EKTR3 | Energia Elétrica | -0.04 |
| AGRO3 | Agropecuária | -0.03 |
| INTB3 | Computadores e Equipamentos | -0.03 |
| TAEE11 | Energia Elétrica | -0.02 |
| DTCY3 | Serviços Diversos | -0.01 |

### Ke ou WACC fora de [8%, 35%] — 0 ocorrências

Nenhum.

### Teto de crescimento batido EXATAMENTE (30% — DCF Duas Fases/FCFE)

Cap ativo não é necessariamente erro — mas muitos tickers do MESMO setor batendo sempre no mesmo teto é padrão sistemático, não caso isolado.

**DCF Duas Fases / FCFE (30%):**

| Setor | Nº tickers no teto | Tickers |
|---|---|---|
| Construção Civil | 5 | AVLL3, CALI3, CYRE3, DIRR3, MDNE3 |
| Varejo | 2 | AZZA3, SBFG3 |
| Diversos | 2 | RENT3, CSED3 |
| Holdings Diversificadas | 1 | PEAB3 |
| Equipamentos | 1 | BALM3 |
| Água e Saneamento | 1 | SBSP3 |
| Construção e Engenharia | 1 | SOND3 |
| Intermediários Financeiros | 1 | BRSR3 |
| Tecidos, Vestuário e Calçados | 1 | VULC3 |
| Utilidades Domésticas | 1 | WHRL3 |
| Máquinas e Equipamentos | 1 | EALT3 |
| Material de Transporte | 1 | EMBJ3 |
| Energia Elétrica | 1 | ENEV3 |
| Alimentos | 1 | MNPR3 |

### Dívida líquida/patrimônio ou dívida/EBIT negativos de forma suspeita — 36 tickers

_(critério: as duas razões negativas ao mesmo tempo, ou uma delas extremamente negativa — caixa líquido moderado é normal, ex. WEGE3, e não entra aqui)_

| Ticker | Setor | Dívida/EBIT | Dívida/Patrimônio |
|---|---|---|---|
| AHEB3 | Viagens e Lazer | -1.52 | -0.28 |
| ALOS3 | Exploração de Imóveis | -1.51 | -0.17 |
| PETZ3 | Varejo | -0.2 | -0.03 |
| ATED3 | Diversos | -4.13 | -0.09 |
| PSSA3 | Previdência e Seguros | -0.38 | -0.84 |
| B3SA3 | Serviços Financeiros Diversos | -0.09 | -0.03 |
| BALM3 | Equipamentos | -1.18 | -0.3 |
| RSUL4 | Material de Transporte | -0.32 | -0.1 |
| SAUD3 | Serv.Méd.Hospit. Análises e Diagnósticos | -0.72 | -0.37 |
| BMOB3 | Programas e Serviços | -1.95 | -0.32 |
| SOND3 | Construção e Engenharia | -0.91 | -0.61 |
| CAMB3 | Tecidos, Vestuário e Calçados | -0.94 | -0.18 |
| TIMS3 | Telecomunicações | -15.92 | -0.12 |
| CEBR3 | Energia Elétrica | -3.12 | -0.4 |
| CGRA3 | Varejo | -1.59 | -0.18 |
| ABEV3 | Bebidas | -0.81 | -0.18 |
| USIM3 | Siderurgia e Metalurgia | -0.58 | -0.02 |
| AFLT3 | Energia Elétrica | -0.41 | -0.07 |
| VSPT3 | Transporte | -0.87 | -0.08 |
| WEGE3 | Máquinas e Equipamentos | -0.39 | -0.19 |
| WIZC3 | Previdência e Seguros | -0.01 | -0.01 |
| CURY3 | Construção Civil | -0.26 | -0.26 |
| DEXP3 | Químicos | -0.84 | -0.09 |
| DTCY3 | Serviços Diversos | 0 | -7.63 |
| FESA3 | Siderurgia e Metalurgia | -4.42 | -0.19 |
| GRND3 | Tecidos, Vestuário e Calçados | -2.65 | -0.2 |
| INTB3 | Computadores e Equipamentos | -0.64 | -0.11 |
| KEPL3 | Máquinas e Equipamentos | -0.28 | -0.05 |
| LJQQ3 | Varejo | -98.63 | -0.6 |
| LPSB3 | Exploração de Imóveis | -1.65 | -0.31 |
| LREN3 | Varejo | -0.4 | -0.14 |
| LUXM3 | Transporte | -0.36 | -0.05 |
| LWSA3 | Programas e Serviços | -1.72 | -0.13 |
| MDIA3 | Alimentos | -0.62 | -0.06 |
| MLAS3 | Computadores e Equipamentos | -2.41 | -0.06 |
| MNPR3 | Alimentos | -1.92 | -0.63 |


## Tickers com erro na coleta (39)

| Ticker | Erro |
|---|---|
| МҮРКЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'МҮРКЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'МҮРКЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| NINJ3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'NINJ3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'NINJ3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ODPV3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ODPV3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ODPV3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| PAT13 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'PAT13' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'PAT13' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| PMSP11B | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'PMSP11B' não encontrado no Fundamentus: No tables found | YahooQuery: 'str' object has no attribute 'empty' | yfinance: Too Many Requests. Rate limited. Try after a while. |
| APT14 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'APT14' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'APT14' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| РОМОЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'РОМОЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'РОМОЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ARZZ3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ARZZ3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ARZZ3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| POS13 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'POS13' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'POS13' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ATMP3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ATMP3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ATMP3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ATOM3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ATOM3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ATOM3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| RAN13 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'RAN13' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'RAN13' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| AZUL11 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'AZUL11' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'AZUL11' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| RDN13 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'RDN13' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'RDN13' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ВАНІЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ВАНІЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ВАНІЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ROM13 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ROM13' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ROM13' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| RRRP3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'RRRP3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'RRRP3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| SHUL3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'SHUL3' não encontrado no Fundamentus: No tables found | YahooQuery: can't multiply sequence by non-int of type 'float' | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ΒΡΑΝ4 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ΒΡΑΝ4' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ΒΡΑΝ4' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| BSL13 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'BSL13' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'BSL13' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ТЕКАЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ТЕКАЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ТЕКАЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| СВЕЕЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'СВЕЕЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'СВЕЕЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| TF655 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'TF655' não encontrado no Fundamentus: No tables found | YahooQuery: 'str' object has no attribute 'empty' | yfinance: Too Many Requests. Rate limited. Try after a while. |
| CCRO3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'CCRO3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'CCRO3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| TKNO3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'TKNO3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'TKNO3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| COCEЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'COCEЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'COCEЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| СТКАЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'СТКАЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'СТКАЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| YBRA4 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'YBRA4' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'YBRA4' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ELET3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ELET3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ELET3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| ЕМАЕЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'ЕМАЕЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'ЕМАЕЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| FIE13 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'FIE13' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'FIE13' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| GFSA11 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'GFSA11' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'GFSA11' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| GUAR3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'GUAR3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'GUAR3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| НЕТАЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'НЕТАЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'НЕТАЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| НҮРЕЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'НҮРЕЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'НҮРЕЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| IFCM12 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'IFCM12' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'IFCM12' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| JОРАЗ | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'JОРАЗ' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'JОРАЗ' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| LVTC3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'LVTC3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'LVTC3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
| MBLY3 | HTTPException: 502: Erro ao buscar dados: Todas as fontes falharam: Fundamentus: Ticker 'MBLY3' não encontrado no Fundamentus: No tables found | YahooQuery: Ticker 'MBLY3' não encontrado no YahooQuery | yfinance: Too Many Requests. Rate limited. Try after a while. |
