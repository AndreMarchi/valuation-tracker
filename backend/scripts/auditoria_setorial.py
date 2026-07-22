"""
auditoria_setorial.py
Auditoria sistemática de mismatch de setor/parâmetro contra TODOS os
tickers cobertos pela ferramenta — mesma classe de bug que já corrigimos
manualmente ação por ação nesta investigação (BEEF3, MGLU3, CSNA3, bancos),
agora rodada de uma vez só contra toda a base.

FERRAMENTA DE DIAGNÓSTICO — não altera main.py, scanner/trabalhador.py nem
nenhum módulo de valuation/. Só lê e chama funções já existentes.

Uso:
    cd backend
    python3 scripts/auditoria_setorial.py [--refresh] [--limit N]

    --refresh   ignora o cache do dia e busca os dados brutos de novo pra
                todos os tickers (útil se as fontes externas mudaram desde
                a última execução no mesmo dia)
    --limit N   audita só os N primeiros tickers (pra teste rápido)

Correções em relação ao que foi descrito na tarefa (confirmado no estado
ATUAL do repo antes de escrever qualquer linha, não presumido):
  - Não existe descoberta de tickers via brapi.dev neste projeto —
    dados/brapi.py está desconectado da cascata ativa (nunca importado por
    provider.py/main.py/scanner/trabalhador.py, achado de investigação
    anterior, ver CONTEXT.md). A descoberta real é
    scanner/trabalhador.py::_carregar_tickers_representativos(), que lê
    dados/setores_b3.json (1 ticker por empresa) — reaproveitada aqui tal
    qual.
  - Não existe asyncio.Semaphore no projeto hoje — scanner/trabalhador.py
    usa ThreadPoolExecutor(max_workers=6) porque seu pipeline
    (avaliar_ticker) é síncrono. Este script precisa do pipeline COMPLETO
    de main.py::valuation() (DCF Duas Fases, FCFE, CAGR de lucro via CVM —
    nenhum desses é calculado por avaliar_ticker(), que é uma versão
    enxuta), que é `async def`. Uso asyncio.Semaphore(6) — MESMO limite
    numérico já calibrado pro Scanner, mecanismo adaptado pro contexto
    async, não um valor novo inventado.
  - Não existe cache diário em JSON pra dados de mercado — só um cache em
    memória de 10 minutos em dados/provider.py. Criado um cache PRÓPRIO
    deste script (.auditoria_cache/), mas guardando o RESULTADO COMPLETO
    de valuation() por ticker junto com um fingerprint (mtime máximo dos
    arquivos de código relevantes). Se qualquer arquivo de
    main.py/valuation/*.py/dados/*.py mudar depois do cache ter sido
    escrito, o cache é tratado como stale automaticamente e os dados são
    buscados de novo — corrige o próprio propósito de "rodar de novo
    depois de uma correção" sem precisar de --refresh manual pra esse
    caso (--refresh força mesmo sem mudança de código, ex: dado de
    mercado mudou intraday).

Achado incidental durante a implementação (não é um bug dos 4 tipos
pedidos, mas vale registrar): valuation.wacc.calcular_wacc() lê
`dados.get("selic", 0.145)` — um fallback hardcoded. main.py NUNCA injeta
"selic" no dict `dados` antes de chamar calcular_wacc() (só
scanner/trabalhador.py faz isso, via `dados_wacc["selic"] = selic_val`),
então o WACC usado pelo DCF principal em main.py sempre usa o Selic
hardcoded (14,5%), nunca o Selic real buscado via buscar_selic_atual() —
mesmo essa função já tendo sido chamada e usada corretamente pro CAPM/Ke
umas linhas antes. Reportado no resumo executivo, não corrigido aqui.
"""

import argparse
import ast
import asyncio
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)  # main.py/scanner/trabalhador.py usam paths relativos ("dados/...")

CACHE_DIR = BACKEND_DIR / ".auditoria_cache"
CACHE_DIR.mkdir(exist_ok=True)

RELATORIO_PATH = BACKEND_DIR / "scripts" / "auditoria_setorial_relatorio.md"

CONCORRENCIA = 6  # mesmo MAX_WORKERS já calibrado em scanner/trabalhador.py


# ─────────────────────────────────────────────────────────────────────────
# 1. Descoberta de tickers e fetch em lote (reaproveita scanner/trabalhador.py
#    e main.py::valuation() — nenhum mecanismo de fetch novo)
# ─────────────────────────────────────────────────────────────────────────

def _arquivos_de_codigo_relevantes() -> list:
    """Arquivos cujo conteúdo, se mudar, invalida o cache — main.py, tudo
    em valuation/dados/scanner (qualquer correção de bug relevante mora
    aqui), e este próprio script (a extração de campos também é lógica
    que pode mudar e precisa re-rodar)."""
    arquivos = [BACKEND_DIR / "main.py", Path(__file__)]
    for pasta in ("valuation", "dados", "scanner"):
        arquivos.extend((BACKEND_DIR / pasta).glob("*.py"))
    return [a for a in arquivos if a.exists()]


def _fingerprint_codigo() -> float:
    return max(a.stat().st_mtime for a in _arquivos_de_codigo_relevantes())


def _caminho_cache_hoje() -> Path:
    return CACHE_DIR / f"resultados_{date.today().isoformat()}.json"


def _carregar_cache_valido() -> Optional[dict]:
    caminho = _caminho_cache_hoje()
    if not caminho.exists():
        return None
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if payload.get("fingerprint_codigo") != _fingerprint_codigo():
        print("Cache do dia existe mas o código mudou desde então — ignorando cache.")
        return None
    return payload.get("resultados", {})


def _salvar_cache(resultados: dict):
    payload = {
        "fingerprint_codigo": _fingerprint_codigo(),
        "gerado_em": datetime.now().isoformat(),
        "resultados": resultados,
    }
    with open(_caminho_cache_hoje(), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


async def _avaliar_um(ticker: str, semaforo: asyncio.Semaphore, main_module) -> tuple:
    async with semaforo:
        try:
            resultado = await main_module.valuation(ticker)
            # extrair_campos() faz uma 2ª chamada síncrona a buscar_dados()
            # (pro recálculo de WACC) — rodada aqui, logo em seguida, pra
            # garantir que bate no cache em memória de 10min de
            # dados/provider.py (se rodasse só depois, no fim do lote
            # inteiro de ~450 tickers, o cache já teria expirado pros
            # primeiros tickers processados). asyncio.to_thread evita
            # bloquear o event loop enquanto isso roda.
            campos = await asyncio.to_thread(extrair_campos, ticker, resultado)
            return ticker, {"ok": True, "dados": resultado, "campos": campos}
        except Exception as e:
            return ticker, {"ok": False, "erro": f"{type(e).__name__}: {e}"}


async def _buscar_todos(tickers: list) -> dict:
    import main as main_module  # import tardio: precisa do sys.path/chdir já ajustados

    semaforo = asyncio.Semaphore(CONCORRENCIA)
    tarefas = [_avaliar_um(t, semaforo, main_module) for t in tickers]
    resultados = {}
    concluidos = 0
    total = len(tarefas)
    for coro in asyncio.as_completed(tarefas):
        ticker, resultado = await coro
        resultados[ticker] = resultado
        concluidos += 1
        if concluidos % 25 == 0 or concluidos == total:
            print(f"  {concluidos}/{total} tickers processados...")
    return resultados


def coletar_dados(limite: Optional[int], forcar_refresh: bool) -> dict:
    from scanner.trabalhador import _carregar_tickers_representativos

    tickers = _carregar_tickers_representativos()
    if limite:
        tickers = tickers[:limite]
    print(f"{len(tickers)} tickers descobertos via setores_b3.json (1 por empresa).")

    if not forcar_refresh:
        cache = _carregar_cache_valido()
        if cache is not None:
            faltando = [t for t in tickers if t not in cache]
            if not faltando:
                print(f"Cache do dia válido e completo ({len(cache)} tickers) — reaproveitando, sem rede.")
                return cache
            print(f"Cache do dia válido mas incompleto — buscando {len(faltando)} tickers faltantes.")
            novos = asyncio.run(_buscar_todos(faltando))
            cache.update(novos)
            _salvar_cache(cache)
            return cache

    print(f"Buscando dados ao vivo pra {len(tickers)} tickers (concorrência={CONCORRENCIA})...")
    resultados = asyncio.run(_buscar_todos(tickers))
    _salvar_cache(resultados)
    return resultados


# ─────────────────────────────────────────────────────────────────────────
# 2. Extração de dicionários setoriais via AST (pros que são locais/não
#    importáveis diretamente — SETORES_CICLICOS de main.py) e via import
#    direto (pros module-level). Nenhum valor duplicado à mão.
# ─────────────────────────────────────────────────────────────────────────

def _extrair_set_literal_por_ast(caminho: Path, nome_variavel: str) -> set:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == nome_variavel for t in no.targets
        ):
            return set(ast.literal_eval(no.value))
    raise AssertionError(f"{nome_variavel} não encontrado em {caminho}")


def carregar_dicionarios_setoriais() -> dict:
    """Carrega (sem duplicar valores à mão) todos os dicionários/sets
    indexados por setor encontrados na varredura. Ver Parte 1 do
    relatório pra lista completa e o mecanismo de match de cada um."""
    from valuation.capm import BETA_POR_SETOR
    from valuation.ev_ebitda import EV_EBITDA_MEDIO_SETOR
    from valuation.crescimento import PSR_MEDIO_SETOR, PSR_MEDIO_PADRAO
    from valuation.risco import SETORES_REGULADOS
    from scanner.trabalhador import SETORES_CICLICOS as SETORES_CICLICOS_TRABALHADOR

    setores_ciclicos_main = _extrair_set_literal_por_ast(BACKEND_DIR / "main.py", "SETORES_CICLICOS")

    return {
        "BETA_POR_SETOR": BETA_POR_SETOR,
        "EV_EBITDA_MEDIO_SETOR": EV_EBITDA_MEDIO_SETOR,
        "PSR_MEDIO_SETOR": PSR_MEDIO_SETOR,
        "SETORES_REGULADOS": SETORES_REGULADOS,
        "SETORES_CICLICOS_main.py": setores_ciclicos_main,
        "SETORES_CICLICOS_trabalhador.py": SETORES_CICLICOS_TRABALHADOR,
    }


def _config_setor_py(setor: str) -> tuple:
    """Reproduz o roteamento de get_configuracao_setor() (valuation/setor.py)
    SÓ pra classificar qual branch bateu — chama a função real pro
    resultado, replica apenas a checagem de qual branch foi usado (a
    função não expõe isso). Se valuation/setor.py mudar o mecanismo de
    match, esta réplica pode dessincronizar — sinal de que este bloco
    precisa ser revisado junto."""
    from valuation.setor import CONFIGURACAO_SETORES

    setor_limpo = str(setor).lower().strip()
    if setor_limpo:
        for chave in CONFIGURACAO_SETORES:
            if chave.lower() in setor_limpo or setor_limpo in chave.lower():
                return "bate", chave
        if "tecnologia" in setor_limpo:
            return "fallback_dinamico", "tecnologia"
        if "petróleo" in setor_limpo or "gas" in setor_limpo or "gás" in setor_limpo:
            return "fallback_dinamico", "petróleo/gás"
    return "fallback_padrao", "CONFIGURACAO_PADRAO"


def _pesos_setoriais_subsetor(subsetor: str) -> tuple:
    from valuation.setor import obter_pesos_setoriais, PESOS_PADRAO

    pesos = obter_pesos_setoriais(subsetor)
    if pesos is PESOS_PADRAO or pesos == PESOS_PADRAO:
        return "fallback_padrao", None
    return "bate", pesos


def _cosif_susep(setor: str) -> bool:
    from valuation.fcfe_valuation import eh_setor_bancario_ou_segurador

    return eh_setor_bancario_ou_segurador(setor)


def _nopat_fator(setor: str) -> tuple:
    """FATOR_CONVERSAO_NOPAT é local a calcular_fcl_via_nopat() — não dá
    pra importar. Back-deriva o fator de verdade chamando a função real
    com um EBIT de referência, sem duplicar os valores do dicionário."""
    from valuation.nopat import calcular_fcl_via_nopat

    ebit_referencia = 1_000_000.0
    fcl = calcular_fcl_via_nopat({"ebit_12m": ebit_referencia, "setor": setor})
    fator = fcl / (ebit_referencia * (1 - 0.34) / 1_000_000) if fcl else 0.0
    fator = round(fator, 4)
    return ("fallback_padrao" if abs(fator - 0.65) < 1e-6 else "bate"), fator


# ─────────────────────────────────────────────────────────────────────────
# Parte 1 — matriz de cobertura setor × dicionário
# ─────────────────────────────────────────────────────────────────────────

def parte1_matriz_cobertura(tickers_ok: list, dicionarios: dict) -> dict:
    por_setor = {}
    for t in tickers_ok:
        setor = t["setor"]
        por_setor.setdefault(setor, {"tickers": []})["tickers"].append(t["ticker"])

    for setor, info in por_setor.items():
        colunas = {}

        for nome_dic, dic in dicionarios.items():
            if setor in dic:
                colunas[nome_dic] = "bate"
            else:
                colunas[nome_dic] = "fallback"

        colunas["setor.py (substring)"], detalhe_setor_py = _config_setor_py(setor)
        colunas["_setor_py_detalhe"] = detalhe_setor_py

        status_nopat, fator_nopat = _nopat_fator(setor)
        colunas["nopat.py (FATOR_CONVERSAO_NOPAT)"] = status_nopat
        colunas["_nopat_fator"] = fator_nopat

        colunas["fcfe_valuation.py (COSIF/SUSEP)"] = "bancário/segurador" if _cosif_susep(setor) else "n/a"

        n_fallback = sum(
            1 for k, v in colunas.items()
            if not k.startswith("_") and v in ("fallback", "fallback_dinamico", "fallback_padrao")
        )
        info["colunas"] = colunas
        info["n_fallback"] = n_fallback
        info["n_tickers"] = len(info["tickers"])

    return por_setor


def parte1_para_markdown(por_setor: dict) -> str:
    linhas_ordenadas = sorted(
        por_setor.items(),
        key=lambda kv: (-kv[1]["n_fallback"], -kv[1]["n_tickers"]),
    )

    colunas_nomes = None
    for _, info in linhas_ordenadas:
        colunas_nomes = [k for k in info["colunas"] if not k.startswith("_")]
        break

    md = ["## Parte 1 — Matriz de cobertura setor × dicionário\n"]
    md.append(
        "Ordenado por nº de colunas em fallback (desc), depois por nº de tickers afetados (desc) — "
        "setores no topo são os candidatos mais prováveis a bug ainda não descoberto.\n"
    )
    header = "| Setor | Tickers | Nº fallback | " + " | ".join(colunas_nomes) + " |"
    sep = "|---|---|---|" + "---|" * len(colunas_nomes)
    md.append(header)
    md.append(sep)
    for setor, info in linhas_ordenadas:
        celulas = [info["colunas"][c] for c in colunas_nomes]
        md.append(
            f"| {setor} | {info['n_tickers']} | {info['n_fallback']} | " + " | ".join(celulas) + " |"
        )

    md.append("\n**Detalhe do fallback dinâmico/nopat por setor** (colunas com mecanismo não-óbvio):\n")
    md.append("| Setor | setor.py: branch usado | nopat.py: fator observado |")
    md.append("|---|---|---|")
    for setor, info in linhas_ordenadas:
        md.append(f"| {setor} | {info['colunas']['_setor_py_detalhe']} | {info['colunas']['_nopat_fator']} |")

    return "\n".join(md) + "\n"


# ─────────────────────────────────────────────────────────────────────────
# Parte 2 — divergência entre métodos de fluxo de caixa
# ─────────────────────────────────────────────────────────────────────────

def parte2_divergencia_fluxo_caixa(tickers_ok: list) -> list:
    linhas = []
    for t in tickers_ok:
        margens = {
            "dcf_principal": t.get("dcf_margem_pct"),
            "dcf_duas_fases": t.get("dcf_duas_fases_margem_pct"),
            "fcfe": t.get("fcfe_margem_pct"),
        }
        validas = {k: v for k, v in margens.items() if v is not None}
        if len(validas) < 3:
            continue  # pula se algum dos 3 for "Não aplicável"/indisponível

        amplitude = max(validas.values()) - min(validas.values())
        linhas.append({
            "ticker": t["ticker"],
            "setor": t["setor"],
            "amplitude": round(amplitude, 1),
            **{f"margem_{k}": round(v, 1) for k, v in validas.items()},
        })

    linhas.sort(key=lambda l: -l["amplitude"])
    return linhas


def parte2_para_markdown(linhas: list) -> str:
    md = ["## Parte 2 — Divergência entre DCF principal / DCF Duas Fases / FCFE\n"]
    md.append(
        "Amplitude = maior margem de segurança menos menor margem, entre os 3 métodos "
        "(só tickers onde os 3 rodaram). Ordenado decrescente — topo é o candidato mais "
        "provável a reproduzir a mesma inconsistência já vista em BEEF3/VULC3.\n"
    )
    md.append("| Ticker | Setor | Amplitude (pp) | DCF principal | DCF Duas Fases | FCFE |")
    md.append("|---|---|---|---|---|---|")
    for l in linhas[:60]:
        md.append(
            f"| {l['ticker']} | {l['setor']} | {l['amplitude']} | "
            f"{l.get('margem_dcf_principal', '—')} | {l.get('margem_dcf_duas_fases', '—')} | {l.get('margem_fcfe', '—')} |"
        )
    if len(linhas) > 60:
        md.append(f"\n_(+{len(linhas) - 60} tickers adicionais, omitidos por brevidade — todos no CSV/JSON bruto se necessário)_")
    return "\n".join(md) + "\n"


# ─────────────────────────────────────────────────────────────────────────
# Parte 3 — CAGR Receita − CAGR Lucro
# ─────────────────────────────────────────────────────────────────────────

def parte3_gap_receita_lucro(tickers_ok: list) -> list:
    linhas = []
    for t in tickers_ok:
        cagr_receita = t.get("crescimento_receita_5a_pct")
        cagr_lucro = t.get("crescimento_lucro_fase1_pct")
        # crescimento_lucro_fase1_pct vem do piso conservador (2.0) quando
        # a CVM não tem CAGR de lucro confiável — não é um CAGR de lucro de
        # verdade nesse caso, então tratamos como dado insuficiente (senão
        # todo ticker sem CAGR de lucro real apareceria com um gap enorme e
        # artificial de "receita - 2%", inflando o ranking por um motivo
        # errado: falta de dado, não o bug em si).
        cagr_lucro_e_piso = t.get("crescimento_lucro_e_piso_conservador")

        if cagr_receita is None or cagr_lucro is None or cagr_lucro_e_piso:
            linhas.append({
                "ticker": t["ticker"], "setor": t["setor"],
                "gap": None, "cagr_receita": cagr_receita, "cagr_lucro": None,
                "status": "dado insuficiente" if (cagr_receita is None or cagr_lucro is None) else "CVM sem CAGR de lucro confiável (piso 2%)",
            })
            continue

        gap = round(cagr_receita - cagr_lucro, 1)
        linhas.append({
            "ticker": t["ticker"], "setor": t["setor"],
            "gap": gap, "cagr_receita": round(cagr_receita, 1), "cagr_lucro": round(cagr_lucro, 1),
            "status": "ok",
        })

    linhas.sort(key=lambda l: (l["gap"] is None, -(l["gap"] or 0)))
    return linhas


def parte3_para_markdown(linhas: list) -> str:
    md = ["## Parte 3 — CAGR Receita 5a − CAGR Lucro 5a\n"]
    md.append(
        "Não prova o bug de crescimento-de-receita-pra-projetar-lucro sozinho, mas ordena "
        "por probabilidade do efeito ser relevante. \"Dado insuficiente\" ≠ 0 — não conta "
        "como gap zero.\n"
    )
    com_dado = [l for l in linhas if l["status"] == "ok"]
    sem_dado = [l for l in linhas if l["status"] != "ok"]
    md.append(f"**{len(com_dado)} tickers com os dois CAGRs disponíveis, {len(sem_dado)} com dado insuficiente/piso.**\n")
    md.append("| Ticker | Setor | Gap (pp) | CAGR Receita 5a | CAGR Lucro (CVM) |")
    md.append("|---|---|---|---|---|")
    for l in com_dado[:60]:
        md.append(f"| {l['ticker']} | {l['setor']} | {l['gap']} | {l['cagr_receita']}% | {l['cagr_lucro']}% |")
    if len(com_dado) > 60:
        md.append(f"\n_(+{len(com_dado) - 60} tickers adicionais, omitidos por brevidade)_")
    return "\n".join(md) + "\n"


# ─────────────────────────────────────────────────────────────────────────
# Parte 4 — sanity checks de parâmetro fora de faixa
# ─────────────────────────────────────────────────────────────────────────

TETOS_CRESCIMENTO = {
    0.08: "cíclico (8%, DCF principal)",
    0.15: "geral (15%, DCF principal)",
    0.30: "DCF Duas Fases / FCFE (30%)",
}


def parte4_sanity_checks(tickers_ok: list) -> dict:
    achados_beta = []
    achados_taxa = []
    achados_teto = {}
    achados_divida = []

    for t in tickers_ok:
        ticker, setor = t["ticker"], t["setor"]

        beta = t.get("beta")
        if beta is not None and (beta < 0.15 or beta > 2.5):
            achados_beta.append({"ticker": ticker, "setor": setor, "beta": beta})

        ke = t.get("ke_pct")
        wacc = t.get("wacc_pct")
        for nome, valor in (("Ke", ke), ("WACC", wacc)):
            if valor is not None and (valor < 8.0 or valor > 35.0):
                achados_taxa.append({"ticker": ticker, "setor": setor, "taxa": nome, "valor": valor})

        # Um ticker pode bater o teto de 30% em dcf_duas_fases E em fcfe ao
        # mesmo tempo (as duas premissas de crescimento são derivadas do
        # mesmo CAGR de receita/lucro, ver CONTEXT.md) — sem o `campos_batidos`
        # abaixo ele contaria 2x na mesma linha de setor, inflando "Nº
        # tickers no teto" artificialmente.
        campos_batidos = set()
        for campo, valor_pct in (
            ("dcf_duas_fases_crescimento_fase1_frac", t.get("crescimento_lucro_fase1_pct")),
            ("fcfe_taxa_crescimento_explicito_frac", t.get("fcfe_crescimento_explicito_pct")),
        ):
            if valor_pct is None:
                continue
            frac = round(valor_pct / 100, 4)
            for teto, rotulo in TETOS_CRESCIMENTO.items():
                if teto == 0.30 and abs(frac - teto) < 1e-6:
                    campos_batidos.add((rotulo, campo))
        for rotulo, campo in campos_batidos:
            ja_tem_ticker = any(a["ticker"] == ticker for a in achados_teto.get(rotulo, []))
            if not ja_tem_ticker:
                achados_teto.setdefault(rotulo, []).append({"ticker": ticker, "setor": setor, "campo": campo})

        div_ebit = t.get("endividamento_div_ebit")
        div_patrim = t.get("endividamento_div_patrim")
        if (div_ebit is not None and div_ebit < 0 and div_patrim is not None and div_patrim < 0) or \
           (div_patrim is not None and div_patrim < -5) or (div_ebit is not None and div_ebit < -10):
            achados_divida.append({
                "ticker": ticker, "setor": setor,
                "div_liquida_ebit": div_ebit, "div_liquida_patrim": div_patrim,
            })

    achados_beta.sort(key=lambda a: -abs(a["beta"] - 1.0))
    achados_taxa.sort(key=lambda a: min(a["valor"], abs(a["valor"] - 20)))

    # Padrão sistemático: setores onde MUITOS tickers batem exatamente no
    # mesmo teto (mais grave que um caso isolado).
    contagem_por_setor = {}
    for rotulo, itens in achados_teto.items():
        por_setor = {}
        for item in itens:
            por_setor.setdefault(item["setor"], []).append(item["ticker"])
        contagem_por_setor[rotulo] = sorted(por_setor.items(), key=lambda kv: -len(kv[1]))

    return {
        "beta_fora_da_faixa": achados_beta,
        "taxa_fora_da_faixa": achados_taxa,
        "teto_exato_por_setor": contagem_por_setor,
        "divida_estranha": achados_divida,
    }


def parte4_para_markdown(achados: dict) -> str:
    md = ["## Parte 4 — Sanity checks de parâmetro fora de faixa plausível\n"]

    md.append(f"### Beta fora de [0.15, 2.5] — {len(achados['beta_fora_da_faixa'])} tickers\n")
    if achados["beta_fora_da_faixa"]:
        md.append("| Ticker | Setor | Beta |")
        md.append("|---|---|---|")
        for a in achados["beta_fora_da_faixa"][:40]:
            md.append(f"| {a['ticker']} | {a['setor']} | {a['beta']} |")
    else:
        md.append("Nenhum.")

    md.append(f"\n### Ke ou WACC fora de [8%, 35%] — {len(achados['taxa_fora_da_faixa'])} ocorrências\n")
    if achados["taxa_fora_da_faixa"]:
        md.append("| Ticker | Setor | Taxa | Valor |")
        md.append("|---|---|---|---|")
        for a in achados["taxa_fora_da_faixa"][:40]:
            md.append(f"| {a['ticker']} | {a['setor']} | {a['taxa']} | {a['valor']}% |")
    else:
        md.append("Nenhum.")

    md.append("\n### Teto de crescimento batido EXATAMENTE (30% — DCF Duas Fases/FCFE)\n")
    md.append(
        "Cap ativo não é necessariamente erro — mas muitos tickers do MESMO setor batendo "
        "sempre no mesmo teto é padrão sistemático, não caso isolado.\n"
    )
    algum = False
    for rotulo, por_setor in achados["teto_exato_por_setor"].items():
        if not por_setor:
            continue
        algum = True
        md.append(f"**{rotulo}:**\n")
        md.append("| Setor | Nº tickers no teto | Tickers |")
        md.append("|---|---|---|")
        for setor, tks in por_setor[:20]:
            amostra = ", ".join(tks[:8]) + (f" (+{len(tks)-8})" if len(tks) > 8 else "")
            md.append(f"| {setor} | {len(tks)} | {amostra} |")
    if not algum:
        md.append("Nenhum ticker bateu exatamente no teto de 30%.")

    md.append(f"\n### Dívida líquida/patrimônio ou dívida/EBIT negativos de forma suspeita — {len(achados['divida_estranha'])} tickers\n")
    md.append("_(critério: as duas razões negativas ao mesmo tempo, ou uma delas extremamente negativa — "
               "caixa líquido moderado é normal, ex. WEGE3, e não entra aqui)_\n")
    if achados["divida_estranha"]:
        md.append("| Ticker | Setor | Dívida/EBIT | Dívida/Patrimônio |")
        md.append("|---|---|---|---|")
        for a in achados["divida_estranha"][:40]:
            md.append(f"| {a['ticker']} | {a['setor']} | {a['div_liquida_ebit']} | {a['div_liquida_patrim']} |")
    else:
        md.append("Nenhum.")

    return "\n".join(md) + "\n"


# ─────────────────────────────────────────────────────────────────────────
# Extração dos campos relevantes do retorno de main.py::valuation()
# ─────────────────────────────────────────────────────────────────────────

def extrair_campos(ticker: str, resultado: dict) -> dict:
    from dados.provider import buscar_dados
    from valuation.wacc import calcular_wacc

    setor_info = resultado.get("setor_info", {}) or {}
    capm = resultado.get("capm", {}) or {}
    dcf = resultado.get("dcf", {}) or {}
    crescimento = resultado.get("crescimento", {}) or {}
    dcf_duas_fases = crescimento.get("dcf_duas_fases", {}) or {}
    fcfe = resultado.get("fcfe", {}) or {}
    endividamento = resultado.get("endividamento", {}) or {}
    ev_receita = crescimento.get("ev_receita", {}) or {}

    preco = resultado.get("preco_atual")
    fcfe_valor_justo = (fcfe.get("projecao") or {}).get("valor_justo_por_acao") if fcfe.get("disponivel") else None
    fcfe_margem_pct = None
    if fcfe_valor_justo is not None and preco:
        fcfe_margem_pct = (fcfe_valor_justo - preco) / preco * 100

    fcfe_crescimento_explicito = (fcfe.get("premissas") or {}).get("taxa_crescimento_explicito")

    # WACC não é exposto na resposta — recalculado com os MESMOS inputs que
    # main.py já usou (dados brutos, Ke), chamando a função real (não
    # duplicando a fórmula). Mesma limitação de main.py replicada de
    # propósito: NÃO injeta "selic" em `dados` (main.py também não injeta —
    # ver achado incidental no topo do arquivo), pra refletir o
    # comportamento real de produção, bug incluído.
    wacc_pct = None
    try:
        dados_brutos = buscar_dados(ticker)
        taxa_capm_frac = capm.get("taxa_desconto")
        if taxa_capm_frac is not None:
            wacc_frac = calcular_wacc(dados_brutos, taxa_capm_frac, pct_divida_moeda_estrangeira=None)
            wacc_pct = round(wacc_frac * 100, 2)
    except Exception:
        pass

    crescimento_lucro_fase1_pct = dcf_duas_fases.get("crescimento_fase1")
    # heurística: o piso conservador é exatamente 2.0 — mas 2.0 também
    # pode ser um CAGR real coincidentemente igual a 2%. Não temos como
    # diferenciar só pelo valor devolvido (buscar_crescimento_lucro_anual_cvm
    # não expõe "disponivel" na resposta de main.py) — tratamos == 2.0 como
    # sinal de piso pra fins de Parte 3 (evita inflar o ranking com o
    # próprio piso conservador), documentado como heurística no relatório.
    crescimento_lucro_e_piso_conservador = crescimento_lucro_fase1_pct == 2.0

    return {
        "ticker": ticker,
        "nome": resultado.get("nome"),
        "setor": setor_info.get("setor", "Geral"),
        "subsetor": setor_info.get("industria", "Geral"),
        "beta": capm.get("beta"),
        "ke_pct": capm.get("taxa_desconto_pct"),
        "wacc_pct": wacc_pct,
        "size_premium_pct": capm.get("size_premium"),
        "crescimento_receita_5a_pct": crescimento.get("crescimento_5a"),
        "crescimento_lucro_fase1_pct": crescimento_lucro_fase1_pct,
        "crescimento_lucro_e_piso_conservador": crescimento_lucro_e_piso_conservador,
        "fcfe_crescimento_explicito_pct": (fcfe_crescimento_explicito * 100) if fcfe_crescimento_explicito is not None else None,
        "dcf_margem_pct": dcf.get("margem_seguranca"),
        "dcf_duas_fases_margem_pct": dcf_duas_fases.get("margem_seguranca"),
        "fcfe_margem_pct": fcfe_margem_pct,
        "psr_medio_setor": ev_receita.get("psr_medio_setor"),
        "endividamento_div_ebit": endividamento.get("div_liquida_ebit"),
        "endividamento_div_patrim": endividamento.get("div_liquida_patrim"),
        "endividamento_classificacao": endividamento.get("classificacao"),
        "score_final": (resultado.get("score") or {}).get("score"),
    }


# ─────────────────────────────────────────────────────────────────────────
# Orquestração / relatório
# ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="ignora o cache do dia e busca tudo de novo")
    parser.add_argument("--limit", type=int, default=None, help="audita só os N primeiros tickers")
    args = parser.parse_args()

    bruto = coletar_dados(args.limit, args.refresh)

    tickers_ok = []
    tickers_com_erro = []
    for ticker, item in bruto.items():
        if item.get("ok"):
            # "campos" já vem extraído do fetch (ver _avaliar_um) — cache
            # de dias anteriores a essa mudança não teria essa chave;
            # extrai na hora como rede de segurança (mais lento, mas
            # correto) em vez de quebrar.
            campos = item.get("campos")
            if campos is None:
                try:
                    campos = extrair_campos(ticker, item["dados"])
                except Exception as e:
                    tickers_com_erro.append({"ticker": ticker, "erro": f"extracao: {e}"})
                    continue
            tickers_ok.append(campos)
        else:
            tickers_com_erro.append({"ticker": ticker, "erro": item.get("erro", "desconhecido")})

    print(f"\n{len(tickers_ok)} tickers processados com sucesso, {len(tickers_com_erro)} com erro.\n")

    print("Carregando dicionários setoriais...")
    dicionarios = carregar_dicionarios_setoriais()

    print("Rodando Parte 1 (matriz de cobertura)...")
    matriz = parte1_matriz_cobertura(tickers_ok, dicionarios)

    print("Rodando Parte 2 (divergência de fluxo de caixa)...")
    divergencia = parte2_divergencia_fluxo_caixa(tickers_ok)

    print("Rodando Parte 3 (gap receita/lucro)...")
    gap_receita_lucro = parte3_gap_receita_lucro(tickers_ok)

    print("Rodando Parte 4 (sanity checks)...")
    sanity = parte4_sanity_checks(tickers_ok)

    # ── Resumo executivo ────────────────────────────────────────────────
    setores_com_gap = [s for s, info in matriz.items() if info["n_fallback"] > 0]
    tickers_afetados_gap = sum(
        info["n_tickers"] for s, info in matriz.items() if info["n_fallback"] >= 2
    )

    candidatos = []
    for setor, info in sorted(matriz.items(), key=lambda kv: (-kv[1]["n_fallback"], -kv[1]["n_tickers"]))[:5]:
        if info["n_fallback"] > 0:
            candidatos.append(f"setor **{setor}** ({info['n_tickers']} tickers, {info['n_fallback']} colunas em fallback)")
    for l in divergencia[:3]:
        candidatos.append(f"ticker **{l['ticker']}** (amplitude de {l['amplitude']}pp entre DCF/DCF-2-fases/FCFE)")
    for l in [x for x in gap_receita_lucro if x["status"] == "ok"][:2]:
        candidatos.append(f"ticker **{l['ticker']}** (gap CAGR receita−lucro de {l['gap']}pp)")

    resumo = ["# Auditoria Setorial — Valuation Tracker\n"]
    resumo.append(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
                   f"{len(tickers_ok)} tickers cobertos, {len(tickers_com_erro)} com erro na coleta.\n")
    resumo.append("## Resumo executivo\n")
    resumo.append(f"- **{len(setores_com_gap)}** setores reais têm pelo menos 1 dicionário em fallback (de {len(matriz)} setores encontrados)")
    resumo.append(f"- **{tickers_afetados_gap}** tickers estão em setores com 2+ colunas em fallback (candidatos mais fortes a bug)")
    resumo.append(f"- **{len(divergencia)}** tickers têm os 3 métodos de fluxo de caixa aplicáveis simultaneamente (base da Parte 2)")
    resumo.append(f"- **{len([l for l in gap_receita_lucro if l['status']=='ok'])}** tickers têm CAGR de receita E de lucro disponíveis (base da Parte 3)")
    resumo.append(f"- **{len(sanity['beta_fora_da_faixa'])}** tickers com beta fora de [0.15, 2.5]; "
                   f"**{len(sanity['taxa_fora_da_faixa'])}** ocorrências de Ke/WACC fora de [8%, 35%]")
    resumo.append("\n**Achado incidental (fora dos 4 tipos pedidos, encontrado ao implementar a Parte 4):** "
                   "`valuation/wacc.py::calcular_wacc()` usa `dados.get(\"selic\", 0.145)` — "
                   "`main.py` nunca injeta o Selic real nesse dict antes de chamar a função "
                   "(só `scanner/trabalhador.py` faz isso), então o WACC do DCF principal em "
                   "produção sempre usa 14,5% hardcoded, não o Selic real buscado via "
                   "`buscar_selic_atual()` (que já é usado corretamente pro CAPM/Ke, umas linhas "
                   "antes). Não corrigido por este script — é uma ferramenta de diagnóstico.\n")
    resumo.append("### Candidatos pra checagem manual primeiro\n")
    for c in candidatos[:10]:
        resumo.append(f"1. {c}")
    resumo.append("")

    corpo = "\n".join(resumo) + "\n"
    corpo += parte1_para_markdown(matriz) + "\n"
    corpo += parte2_para_markdown(divergencia) + "\n"
    corpo += parte3_para_markdown(gap_receita_lucro) + "\n"
    corpo += parte4_para_markdown(sanity) + "\n"

    if tickers_com_erro:
        corpo += f"\n## Tickers com erro na coleta ({len(tickers_com_erro)})\n\n"
        corpo += "| Ticker | Erro |\n|---|---|\n"
        for e in tickers_com_erro[:40]:
            corpo += f"| {e['ticker']} | {e['erro']} |\n"
        if len(tickers_com_erro) > 40:
            corpo += f"\n_(+{len(tickers_com_erro) - 40} adicionais)_\n"

    RELATORIO_PATH.write_text(corpo, encoding="utf-8")
    print(f"\nRelatório salvo em {RELATORIO_PATH}")


if __name__ == "__main__":
    main()
