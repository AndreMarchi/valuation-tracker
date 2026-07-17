"""
cvm_provider.py
Otimizado: Cache em RAM para cadastro e demonstrações para máxima performance.
"""

import io
import os
import re
import logging
import requests
import pandas as pd
import unicodedata
from pathlib import Path

# Configuração de Logger
logger = logging.getLogger(__name__)
DADOS_DIR = Path(__file__).parent.parent / "dados_cvm"

# Contas IFRS
CONTA_RECEITA_LIQUIDA = "3.01"
CONTA_LUCRO_LIQUIDO   = "3.11"
CONTA_FCO             = "6.01"
CONTA_EBIT            = "3.05"  # Resultado Antes do Resultado Financeiro e dos Tributos

# Depreciação/amortização — primeira linha de reconciliação do FCO (padrão
# CPC 03/IAS 7: "Resultado do período" seguido por "Depreciações e
# amortizações"). Não inclui depreciação de direito de uso (leasing IFRS16)
# quando reportada em linha separada — subestima levemente o EBITDA em
# empresas com muito leasing, o que é o lado conservador do erro (nunca
# esconde alavancagem, no máximo superestima).
CONTA_DEPRECIACAO_AMORTIZACAO = "6.01.01.02"

# Empréstimos e Financiamentos + Debêntures + Leasing, circulante e não
# circulante — usado como Dívida BRUTA (não líquida: a CVM não baixa o BPA,
# lado do Ativo onde ficariam Caixa/Aplicações Financeiras — ver CONTEXT.md).
CONTA_DIVIDA_CIRCULANTE     = "2.01.04"
CONTA_DIVIDA_NAO_CIRCULANTE = "2.02.01"

# Quebra por moeda da sub-linha "Empréstimos e Financiamentos" (exclui
# Debêntures, que nesta taxonomia não vêm quebradas por moeda — no Brasil
# debêntures são quase sempre em reais, então a omissão é razoável).
CONTA_EMPRESTIMOS_MOEDA_NACIONAL_CIRC     = "2.01.04.01.01"
CONTA_EMPRESTIMOS_MOEDA_ESTRANGEIRA_CIRC  = "2.01.04.01.02"
CONTA_EMPRESTIMOS_MOEDA_NACIONAL_NCIRC    = "2.02.01.01.01"
CONTA_EMPRESTIMOS_MOEDA_ESTRANGEIRA_NCIRC = "2.02.01.01.02"

# A CVM não disponibiliza a composição cambial da RECEITA em taxonomia
# estruturada (só em notas explicativas de texto livre). Assume-se 0% em
# moeda estrangeira por padrão; popule aqui manualmente por ticker apenas
# quando houver dado publicamente confiável (ex: release de resultados).
OVERRIDE_PCT_RECEITA_MOEDA_ESTRANGEIRA: dict = {}

# ─── CACHE GLOBAL EM MEMÓRIA ────────────────────────────────────────────────
_CADASTRO_CACHE = None
_DEMO_CACHE = {} # Estrutura: { 'tipo_cdcvm': pd.DataFrame }

def _normalizar_nome(nome: str) -> str:
    if not nome: return ""
    nome = "".join(c for c in unicodedata.normalize('NFD', nome) if unicodedata.category(c) != 'Mn')
    nome = nome.upper()
    # Nota: "S.A." e "CIA." usam lookahead (?=\s|$) em vez de \b no final —
    # \b não fecha depois de um ponto (não é caractere de palavra), então
    # "MINERVA S.A." ficava "MINERVA ." em vez de "MINERVA".
    sufixos = [r"\b(ON|PN|PNA|PNB|NM|N1|N2|N3|MB|MA|EJ|EB|DR3|PFD|PREFERENCIAL|ORDINARIA)\b", r"\bS\.?A\.?(?=\s|$)", r"\bS/A\b", r"\bCIA\.?(?=\s|$)", r"\bSA\b", r"\bLTDA\b"]
    for s in sufixos: nome = re.sub(s, "", nome, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", nome.replace("-", " ")).strip()

def _carregar_cadastro():
    global _CADASTRO_CACHE
    if _CADASTRO_CACHE is not None: return _CADASTRO_CACHE

    path = DADOS_DIR / "cad_cia_aberta.csv"
    if not path.exists():
        logger.error("Arquivo de cadastro não encontrado.")
        return pd.DataFrame()

    df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
    df["CD_CVM"] = pd.to_numeric(df["CD_CVM"], errors="coerce")
    df["_NOME_NORM"] = df["DENOM_SOCIAL"].fillna("").apply(_normalizar_nome)
    df["_COMERC_NORM"] = df["DENOM_COMERC"].fillna("").apply(_normalizar_nome)
    _CADASTRO_CACHE = df
    return _CADASTRO_CACHE

def buscar_cd_cvm(nome_fundamentus: str):
    cadastro = _carregar_cadastro()
    if cadastro.empty: return None
    nome_norm = _normalizar_nome(nome_fundamentus)
    
    for col in ["_NOME_NORM", "_COMERC_NORM"]:
        m = cadastro[cadastro[col] == nome_norm]
        if not m.empty: return int(m.iloc[0]["CD_CVM"])
    
    return None

def _carregar_demo(tipo: str, cd_cvm: int) -> pd.DataFrame:
    """Carrega apenas uma vez para o cache global."""
    chave = f"{tipo}_{cd_cvm}"
    if chave in _DEMO_CACHE: return _DEMO_CACHE[chave]

    frames = []
    # Nota: Carregamos apenas o arquivo necessário para este CD_CVM se ele ainda não estiver no cache
    for path in DADOS_DIR.glob(f"{tipo}_*.csv"):
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
        df_emp = df[df["CD_CVM"].astype(str).str.zfill(6) == str(cd_cvm).zfill(6)]
        if not df_emp.empty: frames.append(df_emp)
    
    _DEMO_CACHE[chave] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return _DEMO_CACHE[chave]

def _extrair_serie(df: pd.DataFrame, codigo_conta: str) -> pd.Series:
    """
    Extrai a série trimestral de uma conta padronizada da CVM.

    Duas armadilhas dos dados brutos exigem tratamento, ou os valores saem
    inflados (às vezes dobrados):

    1. `CD_CONTA` é hierárquico (ex: "3.11" tem filhos "3.11.01"/"3.11.02"
       que somam o total do pai) — por isso usamos igualdade exata, nunca
       prefixo, para não somar pai + filhos.
    2. Cada filing ITR reporta o trimestre isolado E o acumulado no
       exercício com o mesmo DT_FIM_EXERC (ex: 2025-09-30 aparece como
       jul-set E como jan-set), e comparativos de anos anteriores
       (ORDEM_EXERC="PENÚLTIMO") duplicam linhas já vistas no arquivo do
       ano anterior. Por período, ficamos só com a menor duração (o
       trimestre isolado, não o acumulado) e removemos duplicatas exatas
       de valor antes de agregar.
    """
    if df.empty: return pd.Series(dtype=float)
    mask = df["CD_CONTA"] == codigo_conta
    sub = df[mask].copy()
    if sub.empty: return pd.Series(dtype=float)
    sub["VL_NUM"] = pd.to_numeric(sub["VL_CONTA"], errors="coerce")
    sub["_FATOR"] = sub["ESCALA_MOEDA"].apply(lambda e: 1000.0 if str(e).strip().upper() == "MIL" else 1.0)
    sub["VL_NUM"] = sub["VL_NUM"] * sub["_FATOR"]
    sub["DT_FIM"] = pd.to_datetime(sub["DT_FIM_EXERC"], errors="coerce")

    if "DT_INI_EXERC" in sub.columns:
        sub["DT_INI"] = pd.to_datetime(sub["DT_INI_EXERC"], errors="coerce")
        sub["_DIAS"] = (sub["DT_FIM"] - sub["DT_INI"]).dt.days
    else:
        # Contas de balanço patrimonial (BPP) não têm DT_INI_EXERC — são
        # fotografias de um instante, não fluxos de um período.
        sub["_DIAS"] = 0

    dias_min = sub.groupby("DT_FIM")["_DIAS"].transform("min")
    sub = sub[sub["_DIAS"] == dias_min]
    sub = sub.drop_duplicates(subset=["DT_FIM", "VL_NUM"])

    return sub.groupby("DT_FIM")["VL_NUM"].mean().sort_index()
# ─── dicionário de tradução corporativa ───────────────────────────────────────

MAPA_NOMES_CVM = {
    # Âncoras de Blue Chips e casos complexos de strings
    "PETR4":  "PETROLEO BRASILEIRO S.A. - PETROBRAS",
    "PETR3":  "PETROLEO BRASILEIRO S.A. - PETROBRAS",
    
    # Casos Críticos e Rebrandings
    "WIZC3":  "WIZ CO PARTICIPAÇÕES E CORRETAGEM DE SEGUROS S.A.",
    "B3SA3":  "B3 S.A. - BRASIL, BOLSA, BALCÃO",
    "VIIA3":  "GRUPO CASAS BAHIA S.A.",
    "BHIA3":  "GRUPO CASAS BAHIA S.A.",
    "ALOS3":  "ALLOS S.A.", # Antiga Aliansce Sonae
    "PRIO3":  "PETRO RIO S.A.",
    
    # Energia e Saneamento (Nomes Longos)
    "TAEE3":  "TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S.A.",
    "TAEE4":  "TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S.A.",
    "TAEE11": "TRANSMISSORA ALIANCA DE ENERGIA ELETRICA S.A.",
    "SAPR3":  "CIA SANEAMENTO DO PARANA SANEPAR",
    "SAPR4":  "CIA SANEAMENTO DO PARANA SANEPAR",
    "SAPR11": "CIA SANEAMENTO DO PARANA SANEPAR",
    "SBSP3":  "CIA SANEAMENTO BASICO EST SAO PAULO",
    "CMIG3":  "CIA ENERGETICA DE MINAS GERAIS - CEMIG",
    "CMIG4":  "CIA ENERGETICA DE MINAS GERAIS - CEMIG",
    "CPLE3":  "CIA PARANAENSE DE ENERGIA - COPEL",
    "CPLE6":  "CIA PARANAENSE DE ENERGIA - COPEL",
    "EQTL3":  "EQUATORIAL ENERGIA S.A.",

    # Bancos e Seguros
    "BBAS3":  "BANCO DO BRASIL S.A.",
    "BBSE3":  "BB SEGURIDADE PARTICIPACOES S.A.",
    "CXSE3":  "CAIXA SEGURIDADE PARTICIPACOES S.A.",
    "ITUB3":  "ITAU UNIBANCO HOLDING S.A.",
    "ITUB4":  "ITAU UNIBANCO HOLDING S.A.",
    "ITSA3":  "ITAUSA S.A.",
    "ITSA4":  "ITAUSA S.A.",

    # Varejo, Alimentos e Outros
    "MGLU3":  "MAGAZINE LUIZA S.A.",
    "RENT3":  "LOCALIZA RENT A CAR S.A.",
    "RAIL3":  "RUMO S.A.",
    "RDOR3":  "REDE D OR SAO LUIZ S.A.",
    "ABEV3":  "AMBEV S.A.",
    "ASAI3":  "SENDAS DISTRIBUIDORA S.A.", # Assaí Atacadista
    "CRFB3":  "ATACADAO S.A.",            # Grupo Carrefour
    "JBSS3":  "JBS S.A.",
    "BEEF3":  "MINERVA S.A.",
    "MRFG3":  "MARFRIG GLOBAL FOODS S.A.",
    "CSED3":  "CRUZEIRO DO SUL EDUCACIONAL S.A.",
}

# ─── função principal ─────────────────────────────────────────────────────────

def buscar_saude_financeira_cvm(ticker: str, nome_empresa: str = "") -> dict:
    """Busca dados na CVM usando o mapeamento de ticker ou o nome oficial como fallback."""
    
    ticker_busca = ticker.upper().strip()
    
    # 1. VERIFICA O DICIONÁRIO PRIMEIRO
    if ticker_busca in MAPA_NOMES_CVM:
        razao_social_exata = MAPA_NOMES_CVM[ticker_busca]
        print(f"🔄 Traduzindo {ticker_busca} para a CVM: {razao_social_exata}")
    else:
        # Se não estiver no mapa das problemáticas, usa o nome real
        razao_social_exata = nome_empresa if nome_empresa else ticker_busca
        
    try:
        if not DADOS_DIR.exists() or not any(DADOS_DIR.iterdir()):
            return {
                "disponivel": False,
                "erro": "Dados CVM não encontrados. Execute backend/scripts/atualizar_cvm.py",
            }

        cd_cvm = buscar_cd_cvm(razao_social_exata)
        
        if cd_cvm is None:
            return {"disponivel": False, "erro": f"Empresa não encontrada na CVM: {razao_social_exata}"}

        logger.info(f"Carregando demonstrações CVM para CD_CVM={cd_cvm}")

        dre = _carregar_demo("itr_dre", cd_cvm)
        dfc = _carregar_demo("itr_dfc", cd_cvm)

        # complementa com DFP se ITR vazio
        if dre.empty:
            dre = _carregar_demo("dfp_dre", cd_cvm)
        if dfc.empty:
            dfc = _carregar_demo("dfp_dfc", cd_cvm)

        if dre.empty:
            return {"disponivel": False, "erro": "Demonstrações não disponíveis para este ticker", "cd_cvm": cd_cvm}

        receita = _extrair_serie(dre, CONTA_RECEITA_LIQUIDA)
        lucro   = _extrair_serie(dre, CONTA_LUCRO_LIQUIDO)
        fco     = _extrair_serie(dfc, CONTA_FCO)

        def serie_para_lista(s: pd.Series, n: int = 6) -> list:
            s = s.tail(n)
            result = []
            for dt, v in s.items():
                if pd.notna(v):
                    mes = dt.month
                    trimestre = (mes - 1) // 3 + 1
                    periodo = f"{dt.year}T{trimestre}"
                    result.append({"periodo": periodo, "valor": round(float(v) / 1_000_000, 1)})
            return result

        receita_lista = serie_para_lista(receita)
        lucro_lista   = serie_para_lista(lucro)
        fco_lista     = serie_para_lista(fco)

        margens = []
        r_vals = receita.tail(6).values
        l_vals = lucro.tail(6).values
        for r_v, l_v in zip(r_vals, l_vals):
            if r_v and r_v != 0:
                margens.append(round(float(l_v) / float(r_v) * 100, 1))

        tendencia_receita = "estável"
        if len(receita) >= 4:
            vals = receita.tail(4).values
            if float(vals[-1]) > float(vals[0]) * 1.05:
                tendencia_receita = "crescendo"
            elif float(vals[-1]) < float(vals[0]) * 0.95:
                tendencia_receita = "caindo"

        qualidade_lucro = None
        if not fco.empty and not lucro.empty and len(fco) >= 2 and len(lucro) >= 2:
            fco_sum   = float(fco.tail(4).sum())
            lucro_sum = float(lucro.tail(4).sum())
            if lucro_sum and lucro_sum != 0:
                qualidade_lucro = round(fco_sum / lucro_sum, 2)

        # ── Alavancagem (Dívida Bruta/EBITDA) e descasamento cambial ────────
        # Dívida BRUTA, não líquida: a CVM não baixa o BPA (lado do Ativo,
        # onde ficariam Caixa/Aplicações Financeiras) — ver CONTEXT.md.
        # Dívida bruta é sempre >= dívida líquida, então este é o lado
        # conservador do erro (nunca esconde alavancagem).
        bpp = _carregar_demo("itr_bpp", cd_cvm)
        if bpp.empty:
            bpp = _carregar_demo("dfp_bpp", cd_cvm)

        divida_bruta_ebitda = None
        pct_divida_moeda_estrangeira = None
        descasamento_cambial_pp = None

        ebit = _extrair_serie(dre, CONTA_EBIT)
        d_e_a = _extrair_serie(dfc, CONTA_DEPRECIACAO_AMORTIZACAO)

        ebitda_ttm = None
        if len(ebit) >= 4 and len(d_e_a) >= 4:
            ebitda_ttm = float(ebit.tail(4).sum()) + float(d_e_a.tail(4).sum())

        if not bpp.empty:
            div_circ  = _extrair_serie(bpp, CONTA_DIVIDA_CIRCULANTE)
            div_ncirc = _extrair_serie(bpp, CONTA_DIVIDA_NAO_CIRCULANTE)
            if not div_circ.empty or not div_ncirc.empty:
                divida_bruta = (
                    (float(div_circ.iloc[-1]) if not div_circ.empty else 0.0)
                    + (float(div_ncirc.iloc[-1]) if not div_ncirc.empty else 0.0)
                )
                if ebitda_ttm and ebitda_ttm > 0:
                    divida_bruta_ebitda = round(divida_bruta / ebitda_ttm, 2)

            def _ultimo_valor(codigo: str) -> float:
                s = _extrair_serie(bpp, codigo)
                return float(s.iloc[-1]) if not s.empty else 0.0

            moeda_nacional = (
                _ultimo_valor(CONTA_EMPRESTIMOS_MOEDA_NACIONAL_CIRC)
                + _ultimo_valor(CONTA_EMPRESTIMOS_MOEDA_NACIONAL_NCIRC)
            )
            moeda_estrangeira = (
                _ultimo_valor(CONTA_EMPRESTIMOS_MOEDA_ESTRANGEIRA_CIRC)
                + _ultimo_valor(CONTA_EMPRESTIMOS_MOEDA_ESTRANGEIRA_NCIRC)
            )
            total_com_quebra_cambial = moeda_nacional + moeda_estrangeira

            if total_com_quebra_cambial > 0:
                pct_divida_moeda_estrangeira = round(moeda_estrangeira / total_com_quebra_cambial * 100, 1)
                pct_receita_estrangeira = OVERRIDE_PCT_RECEITA_MOEDA_ESTRANGEIRA.get(ticker_busca, 0.0)
                descasamento_cambial_pp = round(pct_divida_moeda_estrangeira - pct_receita_estrangeira, 1)

        return {
            "disponivel": True,
            "cd_cvm": cd_cvm,
            "receita_trimestral": receita_lista,
            "lucro_trimestral": lucro_lista,
            "fco_trimestral": fco_lista,
            "margens_pct": margens,
            "tendencia_receita": tendencia_receita,
            "qualidade_lucro": qualidade_lucro,
            "divida_bruta_ebitda": divida_bruta_ebitda,
            "pct_divida_moeda_estrangeira": pct_divida_moeda_estrangeira,
            "descasamento_cambial_pp": descasamento_cambial_pp,
        }

    except Exception as e:
        logger.error(f"Erro em buscar_saude_financeira_cvm: {e}")
        return {"disponivel": False, "erro": str(e)}