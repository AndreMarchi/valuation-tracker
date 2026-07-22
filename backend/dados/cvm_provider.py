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
from typing import Optional

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

# ─── BPA (Ativo) — usado pelo Valor de Liquidação (valor_liquidacao.py) ────
# `atualizar_cvm.py` passou a baixar/extrair BPA_con a partir desta tarefa
# (antes só o BPP era extraído do ZIP, embora o BPA já estivesse lá dentro —
# ver CONTEXT.md). Contas confirmadas com ST_CONTA_FIXA="S" (padronizadas,
# mesma confiabilidade já estabelecida no projeto pras contas de BPP como
# CONTA_DIVIDA_CIRCULANTE/CONTA_PATRIMONIO_LIQUIDO acima) — validado contra
# o BPA real da Minerva/BEEF3 (CD_CVM 020931, ITR 2026T1) antes de fixar os
# códigos.
CONTA_ATIVO_TOTAL                        = "1"
CONTA_CAIXA_EQUIVALENTES                 = "1.01.01"
CONTA_APLICACOES_FINANCEIRAS_CIRCULANTE  = "1.01.02"
CONTA_CONTAS_A_RECEBER_CIRCULANTE        = "1.01.03"
CONTA_ESTOQUES                           = "1.01.04"
CONTA_IMOBILIZADO                        = "1.02.03"
CONTA_INTANGIVEL                         = "1.02.04"

# Passivo TOTAL exigível (todas as obrigações — fornecedores, tributos,
# provisões, dívida financeira etc. — não só a Dívida Bruta financeira já
# usada em CONTA_DIVIDA_CIRCULANTE/CONTA_DIVIDA_NAO_CIRCULANTE acima).
# Passivo Circulante + Passivo Não Circulante == Passivo Total ("2") menos
# o Patrimônio Líquido ("2.03") — identidade contábil confirmada contra a
# Minerva (2 == 2.01+2.02+2.03 == 1, Ativo Total, no mesmo período).
CONTA_PASSIVO_CIRCULANTE     = "2.01"
CONTA_PASSIVO_NAO_CIRCULANTE = "2.02"

# A CVM não disponibiliza a composição cambial da RECEITA em taxonomia
# estruturada (só em notas explicativas de texto livre). Assume-se 0% em
# moeda estrangeira por padrão; popule aqui manualmente por ticker apenas
# quando houver dado publicamente confiável (ex: release de resultados).
OVERRIDE_PCT_RECEITA_MOEDA_ESTRANGEIRA: dict = {}

# Patrimônio Líquido Consolidado — parte do próprio arquivo BPP (a CVM
# combina Passivo + PL no mesmo arquivo "Balanço Patrimonial Passivo", só o
# lado do Ativo/BPA que não é baixado — ver CONTA_DIVIDA_CIRCULANTE acima).
# Usado junto com a Dívida Bruta como proxy de "capital investido" quando
# não há Ativo Imobilizado disponível — ver buscar_capital_investido_proxy_cvm().
CONTA_PATRIMONIO_LIQUIDO = "2.03"

# "Variações nos Ativos e Passivos" — segundo dos 3 sub-blocos padronizados
# da reconciliação de Caixa Líquido das Atividades Operacionais (junto com
# 6.01.01 "Caixa Gerado nas Operações" e 6.01.03 "Outros"). Confirmado
# ST_CONTA_FIXA="S" (padronizada) e presente em 100% das ~450 empresas em
# itr_dfc_2024/2025/2026 e dfp_dfc_2024/2025 — ao contrário das contas de
# CAPEX/financiamento (6.02.XX/6.03.XX), essa conta já vem como total
# consolidado, sem precisar somar sub-linhas não padronizadas. É o dado de
# ΔCCL usado em FCFE (ver buscar_inputs_fcfe_cvm) — mas na convenção de
# IMPACTO EM CAIXA da CVM, não na convenção acadêmica (ver
# _delta_ccl_convencao_academica).
CONTA_VARIACAO_ATIVOS_PASSIVOS = "6.01.02"

# ─── CAPEX e financiamento (via extrair_por_texto — ver CONTEXT.md) ─────────
# Grupos 6.02 (Investimento) e 6.03 (Financiamento): só o TOTAL de cada
# grupo é padronizado (ST_CONTA_FIXA="S"); as sub-linhas variam de nome E
# de posição por empresa — inclusive dentro da MESMA empresa entre filings
# diferentes (confirmado na Minerva: "Aquisição de imobilizado" ocupou
# 6.02.03 num filing e 6.02.04 noutro). Casamento por texto é a única
# forma confiável.

CAPEX_PREFIXO = "6.02"
# CAPEX bruto (só aquisições, sem netting contra vendas de ativo — é a
# definição padrão usada em DCF/FCFE). "venda"/"alienac" excluídos porque
# a mesma palavra "imobiliz"/"intangiv" aparece tanto em linhas de
# aquisição quanto de baixa/venda de ativo.
PADRAO_CAPEX_INCLUIR = ["imobiliz", "intangiv"]
PADRAO_CAPEX_EXCLUIR = ["venda", "alienac"]

FINANCIAMENTO_PREFIXO = "6.03"
# Capta empréstimos/financiamentos/debêntures — lookahead pra exigir as
# duas partes na mesma linha independente da ordem do texto. "emiss" cobre
# "Emissão de debêntures" (fraseado real e comum — confirmado em TAEE3 —
# alternativo a "captação"/"tomada"); seguro incluir porque a segunda
# lookahead ainda exige emprest/financiament/debentur na mesma linha, o
# que já barra "Emissão de ações" (equity, não dívida) sozinho.
PADRAO_CAPTACAO_INCLUIR = [r"(?=.*(?:captac|tomad|emiss))(?=.*(?:emprest|financiament|debentur))"]
# "Custo de Captação de Debêntures" é despesa de transação, não o
# principal captado — confirmado em B3SA3, onde sem essa exclusão o
# valor de captação vinha de uma linha de custo, não da linha de
# principal. Exclui só quando "custo(s)" está no INÍCIO da descrição (não
# blocklist geral: "...líquido dos custos de captação", como reportado
# pela RENT3, é a linha certa de captação, só descrita líquida de custos
# — excluir "custo" em qualquer posição derrubaria essa linha também).
PADRAO_CAPTACAO_EXCLUIR = [r"^CUSTO"]

# "liquidad" cobre um fraseado real e comum que "pagamento"/"amortiza"
# sozinhos não pegam — confirmado na Minerva/BEEF3 (ticker âncora desta
# investigação): a linha real é "Empréstimos e financiamentos liquidados",
# sem "pagamento" nem "amortiza" no texto. Sem esse padrão, BEEF3
# retornava série vazia.
PADRAO_AMORTIZACAO_INCLUIR = [r"(?=.*(?:pagamento|amortiza|liquidad))(?=.*(?:emprest|financiament|debentur))"]
# Exclui dividendo/arrendamento (falso-positivo já documentado no
# levantamento anterior) E linhas de JUROS que não mencionam "principal"
# na mesma linha — juros de dívida já estão embutidos no lucro líquido
# (via resultado financeiro), então somar a linha de juros aqui dobraria
# a conta. Quando a empresa reporta principal e juros na MESMA linha
# (ex: CSED3: "Pagamento de principal e juros sobre empréstimos e
# financiamentos"), a presença de "principal" no texto preserva a linha.
# Nota: o "^" na frente é obrigatório — sem ele, re.search() encontra uma
# posição MAIS ADIANTE na string (depois de onde "principal" já apareceu)
# de onde a lookahead negativa "sem principal à frente" passa a valer,
# fazendo a exclusão disparar mesmo quando a linha tem as duas palavras.
# Bug real pego pelo próprio teste automatizado (test_extrair_por_texto.py).
PADRAO_AMORTIZACAO_EXCLUIR = ["dividendo", "arrendamento", r"^(?=.*juros)(?!.*principal)"]

# ─── Depreciação/Amortização (D&A) — via extrair_por_texto (ver CONTEXT.md) ─
# A posição fixa CONTA_DEPRECIACAO_AMORTIZACAO (6.01.01.02) não é confiável:
# confirmado por auditoria contra as ~450 empresas de itr_dre_2025/itr_dfc_2025
# que a MESMA posição representa contas completamente diferentes em empresas
# diferentes — BBSE3/CXSE3: "Resultado de investimentos em participações
# societárias"; PSSA3: "Ajustes de exercícios anteriores" — nada a ver com
# D&A, e o problema não é exclusivo de bancos/seguradoras (140/438 empresas
# divergem, incluindo Petrobras, Sabesp, Usiminas e dezenas de outras
# "normais"). Casamento por texto dentro do bloco 6.01.01.XX ("Caixa Gerado
# nas Operações") é a única forma confiável, mesmo padrão já usado pra
# CAPEX/financiamento acima.
DEPRECIACAO_PREFIXO = "6.01.01"
PADRAO_DEPRECIACAO_INCLUIR = ["deprecia", "amortiza", "exaust"]
# "amortiza" sozinho casa tanto D&A real (imobilizado/intangível/direito de
# uso/ágio/mais-valia/ativo biológico) quanto "Amortização de Custo de
# Captação de Debêntures" (custo de transação financeira — nada a ver com
# CAPEX/EBITDA). Achado ao auditar as ~5700 variações de DS_CONTA reais
# dentro do prefixo 6.01.01: exclui as combinações que indicam amortização
# de natureza financeira/tributária/receita, não de ativo:
#   - custo/captac/transacao/debentur/emissao/encargo/valor justo/desconto:
#     custo de captação/transação de dívida (mesma família de falso-positivo
#     já vista em PADRAO_CAPTACAO_EXCLUIR)
#   - juros: linha combinada juros+amortização de custo é despesa financeira,
#     já embutida no lucro líquido via resultado financeiro
#   - credito/tributo: créditos fiscais (PIS/COFINS) e amortização de
#     tributo diferido sobre mais-valia — ajuste fiscal, não D&A física
#   - despesas antecipadas: amortização de prepaid expense, não CAPEX
#   - receita: "Receitas Diferidas Amortizadas" — reconhecimento de receita,
#     não depreciação/amortização de ativo
PADRAO_DEPRECIACAO_EXCLUIR = [
    "custo", "captac", "transacao", "debentur", "emissao", "encargo",
    "valor justo", "desconto", "credito", "tributo", "juros",
    r"despesas? antecipad", "receita",
]

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

def _extrair_linhas(df: pd.DataFrame, codigo_conta: str) -> pd.DataFrame:
    """
    Filtra e deduplica as linhas de uma conta padronizada da CVM, mas — ao
    contrário de _extrair_serie() — preserva `DT_INI` por período em vez de
    colapsar direto num valor só. Usado por _ttm_a_partir_de_linhas(), que
    precisa saber se cada ponto é ACUMULADO desde 1º de janeiro (convenção
    do DFC no ITR — ver nota grande em _ttm_a_partir_de_linhas) ou já
    ISOLADO (convenção da DRE) pra tratar cada caso corretamente.

    Duas armadilhas dos dados brutos exigem tratamento, ou os valores saem
    inflados (às vezes dobrados):

    1. `CD_CONTA` é hierárquico (ex: "3.11" tem filhos "3.11.01"/"3.11.02"
       que somam o total do pai) — por isso usamos igualdade exata, nunca
       prefixo, para não somar pai + filhos.
    2. A DRE reporta o trimestre isolado E o acumulado no exercício com o
       mesmo DT_FIM_EXERC (ex: 2025-09-30 aparece como jul-set E como
       jan-set) — o DFC não tem essa duplicidade (só reporta acumulado, ver
       _ttm_a_partir_de_linhas), mas o filtro abaixo funciona pros dois
       casos: por período, fica só com a menor duração disponível (que,
       quando as duas variantes existem, é o trimestre isolado). Também
       remove duplicatas exatas de valor entre comparativos de anos
       adjacentes (ORDEM_EXERC="PENÚLTIMO" vs "ÚLTIMO").

    Returns:
        DataFrame com colunas DT_FIM, DT_INI, VL_NUM — no máximo 1 linha
        por DT_FIM (usa a média quando sobra mais de uma linha ambígua
        após o dedup, mesmo comportamento de segurança que _extrair_serie
        já tinha antes desta refatoração).
    """
    vazio = pd.DataFrame(columns=["DT_FIM", "DT_INI", "VL_NUM"])
    if df.empty: return vazio
    mask = df["CD_CONTA"] == codigo_conta
    sub = df[mask].copy()
    if sub.empty: return vazio
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
        sub["DT_INI"] = pd.NaT
        sub["_DIAS"] = 0

    dias_min = sub.groupby("DT_FIM")["_DIAS"].transform("min")
    sub = sub[sub["_DIAS"] == dias_min]
    sub = sub.drop_duplicates(subset=["DT_FIM", "VL_NUM"])

    return sub.groupby("DT_FIM", as_index=False).agg(DT_INI=("DT_INI", "first"), VL_NUM=("VL_NUM", "mean"))


def _extrair_serie(df: pd.DataFrame, codigo_conta: str) -> pd.Series:
    """Extrai a série trimestral de uma conta padronizada da CVM (ver _extrair_linhas)."""
    linhas = _extrair_linhas(df, codigo_conta)
    if linhas.empty: return pd.Series(dtype=float)
    return pd.Series(linhas["VL_NUM"].values, index=linhas["DT_FIM"]).sort_index()


def _rotular_periodo(dt) -> str:
    trimestre = (dt.month - 1) // 3 + 1
    return f"{dt.year}T{trimestre}"


def _ttm_a_partir_de_series(linhas_itr: pd.DataFrame, linhas_dfp: pd.DataFrame) -> dict:
    """
    Núcleo comum do TTM corrigido — recebe as linhas trimestrais (ITR) e
    anuais (DFP) já extraídas com DT_INI preservado (via _extrair_linhas ou
    _extrair_linhas_por_texto) e faz a derivação de Q4 + soma dos 4
    trimestres mais recentes. Ver calcular_ttm_correto() e
    calcular_ttm_por_texto() para as duas formas de chegar até aqui.

    BUG CORRIGIDO (achado durante a investigação do D&A por texto, ver
    CONTEXT.md): a DRE reporta cada trimestre ISOLADO no ITR (DT_INI_EXERC
    = início do próprio trimestre a partir do Q2) — mas o DFC **nunca**
    reporta trimestre isolado, só ACUMULADO desde 1º de janeiro do ano
    fiscal (DT_INI_EXERC é sempre 1º/jan, mesmo pro "trimestre" de
    setembro, que na prática é 9 meses acumulados). Confirmado
    sistematicamente: 441 de 451 empresas têm essa característica na conta
    FCO (6.01). A versão anterior desta função tratava toda série ITR como
    se fosse sempre isolada — certo pra DRE (lucro líquido, EBIT, receita:
    validado exatamente contra o lucro anual oficial do BEEF3), mas errado
    pra qualquer conta de DFC (FCO, D&A, ΔCCL, CAPEX, financiamento):
    somava valores acumulados como se fossem isolados, inflando o TTM.

    Detecção e correção: por trimestre, se `DT_INI` da linha ITR for
    exatamente 1º/jan do ano em questão (e não for o próprio Q1, onde
    acumulado-até-Q1 É o Q1 isolado) o valor é tratado como ACUMULADO e
    isolado por diferença contra o acumulado-até-o-trimestre-anterior
    (mesma ideia de derivar Q4: anual − acumulado-até-Q3). Se `DT_INI` for
    o início do próprio trimestre, o valor já é isolado — usado direto,
    sem alteração (mesmo comportamento de antes). Os dois casos convergem
    naturalmente pra mesma fórmula de Q4 = anual − (Q1+Q2+Q3) quando tudo é
    isolado (a soma acumulada-por-diferença degenera na soma direta) — por
    isso os testes com DRE (sempre isolada) continuam batendo igual.

    Só deriva/isola um trimestre quando os trimestres anteriores do mesmo
    ano estão TODOS presentes — nunca estima a partir de dado parcial.
    """
    def _mapa(linhas: pd.DataFrame) -> dict:
        if linhas.empty: return {}
        return {row.DT_FIM: (row.DT_INI, float(row.VL_NUM)) for row in linhas.itertuples()}

    mapa_itr = _mapa(linhas_itr)
    mapa_dfp = _mapa(linhas_dfp)

    if not mapa_itr and not mapa_dfp:
        return {"valor": None, "trimestres_usados": [], "quantidade_trimestres_reais": 0}

    pontos = {}
    anos = sorted({dt.year for dt in mapa_itr} | {dt.year for dt in mapa_dfp})

    for ano in anos:
        dt_q1 = pd.Timestamp(ano, 3, 31)
        dt_q2 = pd.Timestamp(ano, 6, 30)
        dt_q3 = pd.Timestamp(ano, 9, 30)
        dt_q4 = pd.Timestamp(ano, 12, 31)
        jan1 = pd.Timestamp(ano, 1, 1)

        cum = 0.0
        cum_valido = True  # acumulado-até-aqui íntegro (nenhum trimestre anterior faltando)

        cru_q1 = mapa_itr.get(dt_q1)
        if cru_q1 is not None:
            cum = cru_q1[1]  # Jan-Mar: acumulado-até-Q1 É o Q1 isolado, sempre
            pontos[dt_q1] = cum
        else:
            cum_valido = False

        for dt_q in (dt_q2, dt_q3):
            cru = mapa_itr.get(dt_q)
            if cru is None:
                cum_valido = False
                continue
            dt_ini, v = cru
            if dt_ini == jan1:
                # acumulado (convenção DFC) -> só isola se o acumulado-até-o-
                # trimestre-anterior for íntegro (nenhum trimestre anterior faltando)
                if not cum_valido:
                    continue
                pontos[dt_q] = v - cum
                cum = v
            else:
                # já isolado (convenção DRE, ou DFC no raro caso que reporta
                # isolado) -> inclui direto, mesmo que um trimestre anterior
                # esteja faltando (não depende do acumulado pra ser lido)
                pontos[dt_q] = v
                if cum_valido:
                    cum = cum + v

        cru_q4_itr = mapa_itr.get(dt_q4)
        if cru_q4_itr is not None:
            pontos[dt_q4] = cru_q4_itr[1]  # Q4 já reportado isolado no ITR (raro) — usa direto, não sobrescreve
        elif dt_q4 in mapa_dfp and cum_valido:
            pontos[dt_q4] = mapa_dfp[dt_q4][1] - cum  # deriva do anual DFP − acumulado-até-Q3
        # senão: falta trimestre necessário pra esse ano -> não deriva Q4, propositalmente

    if not pontos:
        return {"valor": None, "trimestres_usados": [], "quantidade_trimestres_reais": 0}

    serie_completa = pd.Series(pontos).sort_index()
    ultimos_4 = serie_completa.tail(4)
    rotulos = [_rotular_periodo(dt) for dt in ultimos_4.index]

    if len(ultimos_4) < 4:
        return {"valor": None, "trimestres_usados": rotulos, "quantidade_trimestres_reais": len(ultimos_4)}

    return {
        "valor": float(ultimos_4.sum()),
        "trimestres_usados": rotulos,
        "quantidade_trimestres_reais": 4,
    }


def calcular_ttm_correto(df_itr: pd.DataFrame, df_dfp: pd.DataFrame, codigo_conta: str) -> dict:
    """
    Soma os 4 trimestres mais recentes DE VERDADE — incluindo o 4º
    trimestre, que a CVM nunca reporta isolado via ITR (só via DFP, como
    total anual), e tratando corretamente contas de DFC (sempre reportadas
    acumuladas desde 1º/jan no ITR — ver _ttm_a_partir_de_series) vs contas
    de DRE (reportadas isoladas). Bug pré-existente (afetava
    `qualidade_lucro` e `divida_bruta_ebitda` em
    `buscar_saude_financeira_cvm()` antes desta correção), encontrado
    durante a investigação do FCFE. Ver CONTEXT.md.

    Args:
        df_itr: DataFrame bruto (ex: retorno de _carregar_demo("itr_dre", cd_cvm))
        df_dfp: DataFrame bruto (ex: retorno de _carregar_demo("dfp_dre", cd_cvm))
        codigo_conta: mesmo código usado em _extrair_serie (ex: CONTA_LUCRO_LIQUIDO)

    Returns:
        dict com:
        - "valor": soma dos 4 trimestres mais recentes, ou None se a série
          combinada (ITR + Q4 derivado) não tiver 4 trimestres reais.
        - "trimestres_usados": lista tipo ["2025T4", "2026T1", "2026T2", "2026T3"]
          na ordem cronológica somada — auditável, não escondido num comentário.
        - "quantidade_trimestres_reais": quantos entraram na soma (4 se "valor" não é None).
    """
    linhas_itr = _extrair_linhas(df_itr, codigo_conta)
    linhas_dfp = _extrair_linhas(df_dfp, codigo_conta)
    return _ttm_a_partir_de_series(linhas_itr, linhas_dfp)


def _extrair_linhas_por_texto(df: pd.DataFrame, prefixo: str, incluir_padroes: list, excluir_padroes: list = None) -> pd.DataFrame:
    """
    Soma, por período, as linhas-folha da CVM cujo CD_CONTA comece com
    `prefixo` (ex: "6.02", "6.03") e cujo DS_CONTA bata em pelo menos um
    padrão de `incluir_padroes` e em NENHUM padrão de `excluir_padroes`.

    Usado pra contas não padronizadas (ST_CONTA_FIXA="N" — nome, posição e
    composição variam por empresa; ver CONTEXT.md) onde não existe um
    CD_CONTA fixo confiável: CAPEX (6.02.XX) e fluxos de financiamento
    (6.03.XX). Diferente de _extrair_serie() (que casa 1 CD_CONTA exato),
    aqui pode haver várias linhas por período que precisam ser somadas
    (ex: "Aquisição de imobilizado" + "Aquisição de intangível" na mesma
    empresa).

    "Linha-folha" = CD_CONTA com 3+ segmentos dentro do prefixo (ex:
    "6.02.03", não o total "6.02" do grupo, que é padronizado mas
    inclui M&A/aplicações financeiras junto — não serve como CAPEX isolado).

    Casamento de texto: sem acento, case-insensitive. Para exigir duas
    palavras na MESMA linha independente da ordem (ex: um verbo de
    pagamento E um substantivo de dívida), use lookahead no próprio
    padrão: `r"(?=.*captac)(?=.*emprest)"` bate tanto "Captação de
    Empréstimos" quanto (hipoteticamente) "Empréstimos captados".

    Aplica o MESMO dedup de _extrair_linhas() (trimestre isolado vs
    acumulado, duplicata exata de valor) ao conjunto já filtrado por
    texto — reaproveita a mesma lógica já corrigida, não reintroduz o bug
    de trimestre/acumulado documentado no CONTEXT.md. Preserva `DT_INI`
    por período (não colapsa em Series) pelo mesmo motivo de
    _extrair_linhas(): quem consome isso pra TTM (calcular_ttm_por_texto)
    precisa saber se cada ponto é acumulado (convenção do DFC) ou isolado.

    IMPORTANTE — não usa _extrair_serie(df, cd_conta) direto: confirmado
    que a mesma posição de CD_CONTA pode representar contas DIFERENTES
    entre filings da mesma empresa (ex: TAEE3, "6.03.03" é "Emissão de
    debêntures" — captação — num filing e "Pagamento de Debêntures -
    Principal" — amortização, sinal oposto — noutro). Reconsultar o
    dataframe inteiro por CD_CONTA depois de já ter identificado a linha
    certa pelo texto misturaria as duas. O dedup abaixo roda só sobre as
    linhas que já passaram no filtro de DS_CONTA, agrupando por
    (CD_CONTA, DT_FIM) — nunca herda linhas de outro período que só
    coincidem no código.

    Args:
        df: DataFrame bruto (ex: retorno de _carregar_demo("itr_dfc", cd_cvm))
        prefixo: prefixo de CD_CONTA (ex: "6.02")
        incluir_padroes: lista de regex (str, sem acento) — combinadas com OR
        excluir_padroes: lista de regex (str, sem acento) — se QUALQUER uma
            bater na linha, ela é descartada mesmo que bata em incluir_padroes

    Returns:
        DataFrame com colunas DT_FIM, DT_INI, VL_NUM — soma das linhas-folha
        que passaram no filtro, por período (no máximo 1 linha por DT_FIM).
        Vazio se nada bateu (nunca um valor "zero" enganoso).
    """
    vazio = pd.DataFrame(columns=["DT_FIM", "DT_INI", "VL_NUM"])
    if df.empty or "CD_CONTA" not in df.columns:
        return vazio

    def _normalizar_texto(s) -> str:
        s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
        return s.upper()

    mask_folha = df["CD_CONTA"].str.startswith(prefixo) & (df["CD_CONTA"].str.count(r"\.") >= 2)
    candidatas = df[mask_folha].copy()
    if candidatas.empty:
        return vazio

    ds_norm = candidatas["DS_CONTA"].apply(_normalizar_texto)

    incluir_regex = [re.compile(_normalizar_texto(p), re.IGNORECASE) for p in incluir_padroes]
    excluir_regex = [re.compile(_normalizar_texto(p), re.IGNORECASE) for p in (excluir_padroes or [])]

    bate_incluir = ds_norm.apply(lambda t: any(r.search(t) for r in incluir_regex))
    if excluir_regex:
        bate_excluir = ds_norm.apply(lambda t: any(r.search(t) for r in excluir_regex))
    else:
        bate_excluir = pd.Series(False, index=ds_norm.index)

    candidatas = candidatas[bate_incluir & ~bate_excluir]
    if candidatas.empty:
        return vazio

    candidatas["VL_NUM"] = pd.to_numeric(candidatas["VL_CONTA"], errors="coerce")
    candidatas["_FATOR"] = candidatas["ESCALA_MOEDA"].apply(lambda e: 1000.0 if str(e).strip().upper() == "MIL" else 1.0)
    candidatas["VL_NUM"] = candidatas["VL_NUM"] * candidatas["_FATOR"]
    candidatas["DT_FIM"] = pd.to_datetime(candidatas["DT_FIM_EXERC"], errors="coerce")

    if "DT_INI_EXERC" in candidatas.columns:
        candidatas["DT_INI"] = pd.to_datetime(candidatas["DT_INI_EXERC"], errors="coerce")
        candidatas["_DIAS"] = (candidatas["DT_FIM"] - candidatas["DT_INI"]).dt.days
    else:
        candidatas["DT_INI"] = pd.NaT
        candidatas["_DIAS"] = 0

    # menor duração de período por (conta, período) — trimestre isolado
    # em vez do acumulado no exercício, mesma ideia de _extrair_linhas().
    dias_min = candidatas.groupby(["CD_CONTA", "DT_FIM"])["_DIAS"].transform("min")
    candidatas = candidatas[candidatas["_DIAS"] == dias_min]
    # duplicata exata (ÚLTIMO vs PENÚLTIMO comparativo) por (conta, período, valor)
    candidatas = candidatas.drop_duplicates(subset=["CD_CONTA", "DT_FIM", "VL_NUM"])

    # soma entre as diferentes contas casadas, por período.
    return candidatas.groupby("DT_FIM", as_index=False).agg(DT_INI=("DT_INI", "first"), VL_NUM=("VL_NUM", "sum"))


def extrair_por_texto(df: pd.DataFrame, prefixo: str, incluir_padroes: list, excluir_padroes: list = None) -> pd.Series:
    """Versão em Series de _extrair_linhas_por_texto() — mesmo formato de _extrair_serie()."""
    linhas = _extrair_linhas_por_texto(df, prefixo, incluir_padroes, excluir_padroes)
    if linhas.empty: return pd.Series(dtype=float)
    return pd.Series(linhas["VL_NUM"].values, index=linhas["DT_FIM"]).sort_index()


def calcular_ttm_por_texto(df_itr: pd.DataFrame, df_dfp: pd.DataFrame, prefixo: str, incluir_padroes: list, excluir_padroes: list = None) -> dict:
    """
    Mesma lógica de calcular_ttm_correto(), mas pra contas não padronizadas
    identificadas por texto via extrair_por_texto() (CAPEX, financiamento,
    D&A) em vez de um único CD_CONTA exato. Mesmo formato de retorno.
    """
    linhas_itr = _extrair_linhas_por_texto(df_itr, prefixo, incluir_padroes, excluir_padroes)
    linhas_dfp = _extrair_linhas_por_texto(df_dfp, prefixo, incluir_padroes, excluir_padroes)
    return _ttm_a_partir_de_series(linhas_itr, linhas_dfp)


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
    "SBSP3":  "CIA SANEAMENTO BASICO ESTADO SAO PAULO",
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

        dre_itr = _carregar_demo("itr_dre", cd_cvm)
        dfc_itr = _carregar_demo("itr_dfc", cd_cvm)
        dre_dfp = _carregar_demo("dfp_dre", cd_cvm)
        dfc_dfp = _carregar_demo("dfp_dfc", cd_cvm)

        # dre/dfc "preferido" (ITR quando disponível, senão DFP) — usado nos
        # gráficos trimestrais e na tendência de receita, sem mudança de
        # comportamento. Os totais TTM (qualidade_lucro, EBITDA) usam
        # dre_itr/dre_dfp e dfc_itr/dfc_dfp separadamente via
        # calcular_ttm_correto(), porque precisam dos dois ao mesmo tempo
        # pra derivar o 4º trimestre (ver CONTEXT.md).
        dre = dre_itr if not dre_itr.empty else dre_dfp
        dfc = dfc_itr if not dfc_itr.empty else dfc_dfp

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

        # TTM corrigido (ver calcular_ttm_correto) — soma os 4 trimestres
        # mais recentes DE VERDADE, incluindo o 4º trimestre derivado via
        # DFP. Substitui o antigo fco.tail(4).sum()/lucro.tail(4).sum(),
        # que pulava o Q4 e cobria ~15 meses em vez de 12.
        ttm_fco   = calcular_ttm_correto(dfc_itr, dfc_dfp, CONTA_FCO)
        ttm_lucro = calcular_ttm_correto(dre_itr, dre_dfp, CONTA_LUCRO_LIQUIDO)

        qualidade_lucro = None
        if ttm_fco["valor"] is not None and ttm_lucro["valor"]:
            qualidade_lucro = round(ttm_fco["valor"] / ttm_lucro["valor"], 2)

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

        # TTM corrigido (ver calcular_ttm_correto), mesmo motivo do
        # qualidade_lucro acima — substitui ebit.tail(4).sum()+d_e_a.tail(4).sum().
        # D&A por TEXTO (não pela posição fixa CONTA_DEPRECIACAO_AMORTIZACAO)
        # — auditoria contra ~450 empresas confirmou que a posição fixa
        # 6.01.01.02 representa contas completamente diferentes em 32% delas
        # (sem concentração setorial, ver CONTEXT.md). None explícito quando
        # nenhuma linha bate, nunca cai de volta pra posição fixa.
        ttm_ebit = calcular_ttm_correto(dre_itr, dre_dfp, CONTA_EBIT)
        ttm_d_e_a = calcular_ttm_por_texto(dfc_itr, dfc_dfp, DEPRECIACAO_PREFIXO, PADRAO_DEPRECIACAO_INCLUIR, PADRAO_DEPRECIACAO_EXCLUIR)

        ebitda_ttm = None
        if ttm_ebit["valor"] is not None and ttm_d_e_a["valor"] is not None:
            ebitda_ttm = ttm_ebit["valor"] + ttm_d_e_a["valor"]

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


def buscar_capital_investido_proxy_cvm(ticker: str, nome_empresa: str = "") -> dict:
    """
    Proxy de "Ativo Imobilizado líquido" via CVM, usado pelo DCF Concessão
    (valuation/dcf_concessao.py) — a CVM não baixa o BPA (lado do Ativo do
    balanço, onde ficaria o Imobilizado de verdade; só o BPP — Passivo +
    Patrimônio Líquido — é baixado, ver CONTA_DIVIDA_CIRCULANTE acima).

    Proxy: Capital Investido = Dívida Bruta + Patrimônio Líquido. Pela
    identidade contábil (Ativo Total = Passivo + PL), isso É o Ativo Total
    — não especificamente o Imobilizado, mas pra uma concessionária de
    energia/infraestrutura (o único tipo de empresa em CONCESSOES_CONHECIDAS
    hoje) o Imobilizado domina o Ativo (pouco estoque, caixa/recebíveis
    proporcionalmente pequenos) — é uma superestimativa leve, do lado
    otimista pro cenário de liquidação do DCF Concessão. Documentado como
    proxy explícito, não um valor de balanço real — quem consome isso deve
    marcar como estimativa.

    Retorna `disponivel: False` (não um valor de zero, enganoso) quando:
      - a empresa não é encontrada na CVM;
      - Dívida Bruta E Patrimônio Líquido vêm ambos zerados — confirmado
        que isso acontece por empresa reportar o BPP inteiro zerado em
        alguns casos reais (ex: GEPA4/Rio Paranapanema Energia SA, CD_CVM
        18368 — TODAS as ~520 linhas do BPP consolidado, ITR e DFP, desde
        2023, vêm com VL_CONTA=0; a DRE do mesmo ticker também zera a
        partir de 2024T1, sugerindo mudança na forma de reporte à CVM não
        relacionada a este código — ver CONTEXT.md).
    """
    ticker_busca = ticker.upper().strip()
    razao_social_exata = MAPA_NOMES_CVM.get(ticker_busca, nome_empresa or ticker_busca)

    try:
        if not DADOS_DIR.exists() or not any(DADOS_DIR.iterdir()):
            return {"disponivel": False, "erro": "Dados CVM não encontrados. Execute backend/scripts/atualizar_cvm.py"}

        cd_cvm = buscar_cd_cvm(razao_social_exata)
        if cd_cvm is None:
            return {"disponivel": False, "erro": f"Empresa não encontrada na CVM: {razao_social_exata}"}

        bpp = _carregar_demo("itr_bpp", cd_cvm)
        if bpp.empty:
            bpp = _carregar_demo("dfp_bpp", cd_cvm)
        if bpp.empty:
            return {"disponivel": False, "cd_cvm": cd_cvm, "erro": "BPP indisponível pra este ticker"}

        def _ultimo_valor(codigo: str) -> float:
            s = _extrair_serie(bpp, codigo)
            return float(s.iloc[-1]) if not s.empty else 0.0

        divida_bruta = _ultimo_valor(CONTA_DIVIDA_CIRCULANTE) + _ultimo_valor(CONTA_DIVIDA_NAO_CIRCULANTE)
        patrimonio_liquido = _ultimo_valor(CONTA_PATRIMONIO_LIQUIDO)
        capital_investido = divida_bruta + patrimonio_liquido

        if capital_investido <= 0:
            return {
                "disponivel": False,
                "cd_cvm": cd_cvm,
                "erro": "Dívida Bruta e Patrimônio Líquido vieram zerados no BPP — dado da CVM indisponível/inconsistente pra este ticker",
            }

        return {"disponivel": True, "cd_cvm": cd_cvm, "valor": capital_investido, "eh_proxy": True}

    except Exception as e:
        logger.error(f"Erro em buscar_capital_investido_proxy_cvm: {e}")
        return {"disponivel": False, "erro": str(e)}


def buscar_ativos_para_liquidacao_cvm(ticker: str, nome_empresa: str = "") -> dict:
    """
    Ativos (por classe) e Passivo Total via BPA/BPP da CVM, usado pelo
    Valor de Liquidação (valuation/valor_liquidacao.py). Ao contrário de
    buscar_capital_investido_proxy_cvm() (que usa um PROXY de Ativo Total
    porque o BPA não era baixado), esta função lê o BPA_con de verdade —
    `atualizar_cvm.py` passou a extraí-lo nesta tarefa (ver CONTEXT.md).

    Classes retornadas (todas em R$ absolutos, valor mais recente
    disponível) — só as 6 citadas no pedido original, cada uma com
    ST_CONTA_FIXA="S" (posição padronizada, validado contra o BPA real da
    Minerva/BEEF3 antes de fixar os códigos, mesmo nível de confiança já
    estabelecido pras contas de BPP como CONTA_DIVIDA_CIRCULANTE):
      - caixa_equivalentes        (1.01.01)
      - aplicacoes_financeiras    (1.01.02, só a parcela CIRCULANTE)
      - contas_a_receber          (1.01.03, só a parcela CIRCULANTE)
      - estoques                  (1.01.04)
      - imobilizado               (1.02.03)
      - intangivel                (1.02.04)

    Deliberadamente NÃO soma todo o Ativo Não Circulante (Investimentos,
    Ativo Realizável a Longo Prazo, Ativos Biológicos, Tributos
    Diferidos etc.) — essas classes não têm uma convenção de haircut de
    liquidação citada no pedido original, e incluí-las exigiria inventar
    um percentual sem base. Ficam de fora do "Ativo ajustado" (mesmo
    espírito do "net-net working capital" de Graham: só conta o que tem
    convenção de haircut definida) — o que torna o piso de liquidação
    MAIS conservador, nunca menos. `ativo_total_bpa` (conta "1", Ativo
    Total real) é retornado à parte só como referência de cobertura (ex:
    o frontend pode mostrar "X% do Ativo Total coberto pelas classes com
    haircut definido").

    `passivo_total` = Passivo Circulante (2.01) + Passivo Não Circulante
    (2.02) — TODAS as obrigações exigíveis (fornecedores, tributos,
    provisões, dívida financeira etc.), não só a Dívida Bruta financeira
    de CONTA_DIVIDA_CIRCULANTE/CONTA_DIVIDA_NAO_CIRCULANTE (usada em
    outras partes do projeto). É o número certo para subtrair do Ativo
    ajustado num cálculo de liquidação — o acionista só recebe o que
    sobra depois de TODOS os credores serem pagos, não só os financeiros.

    Retorna `disponivel: False` (nunca um valor de zero enganoso) quando a
    empresa não é encontrada, o BPA/BPP não existem pra ela, ou quando
    Ativo Total e Passivo Total vêm ambos zerados (mesmo sintoma real já
    documentado em buscar_capital_investido_proxy_cvm — ex: GEPA4).
    """
    ticker_busca = ticker.upper().strip()
    razao_social_exata = MAPA_NOMES_CVM.get(ticker_busca, nome_empresa or ticker_busca)

    try:
        if not DADOS_DIR.exists() or not any(DADOS_DIR.iterdir()):
            return {"disponivel": False, "erro": "Dados CVM não encontrados. Execute backend/scripts/atualizar_cvm.py"}

        cd_cvm = buscar_cd_cvm(razao_social_exata)
        if cd_cvm is None:
            return {"disponivel": False, "erro": f"Empresa não encontrada na CVM: {razao_social_exata}"}

        bpa = _carregar_demo("itr_bpa", cd_cvm)
        if bpa.empty:
            bpa = _carregar_demo("dfp_bpa", cd_cvm)
        if bpa.empty:
            return {
                "disponivel": False, "cd_cvm": cd_cvm,
                "erro": "BPA indisponível pra este ticker — rode backend/scripts/atualizar_cvm.py",
            }

        bpp = _carregar_demo("itr_bpp", cd_cvm)
        if bpp.empty:
            bpp = _carregar_demo("dfp_bpp", cd_cvm)
        if bpp.empty:
            return {"disponivel": False, "cd_cvm": cd_cvm, "erro": "BPP indisponível pra este ticker"}

        def _ultimo_valor(df: pd.DataFrame, codigo: str) -> float:
            s = _extrair_serie(df, codigo)
            return float(s.iloc[-1]) if not s.empty else 0.0

        ativo_total = _ultimo_valor(bpa, CONTA_ATIVO_TOTAL)
        passivo_total = _ultimo_valor(bpp, CONTA_PASSIVO_CIRCULANTE) + _ultimo_valor(bpp, CONTA_PASSIVO_NAO_CIRCULANTE)

        if ativo_total <= 0 and passivo_total <= 0:
            return {
                "disponivel": False, "cd_cvm": cd_cvm,
                "erro": "Ativo Total e Passivo Total vieram zerados no BPA/BPP — dado da CVM indisponível/inconsistente pra este ticker",
            }

        return {
            "disponivel": True,
            "cd_cvm": cd_cvm,
            "caixa_equivalentes": _ultimo_valor(bpa, CONTA_CAIXA_EQUIVALENTES),
            "aplicacoes_financeiras": _ultimo_valor(bpa, CONTA_APLICACOES_FINANCEIRAS_CIRCULANTE),
            "contas_a_receber": _ultimo_valor(bpa, CONTA_CONTAS_A_RECEBER_CIRCULANTE),
            "estoques": _ultimo_valor(bpa, CONTA_ESTOQUES),
            "imobilizado": _ultimo_valor(bpa, CONTA_IMOBILIZADO),
            "intangivel": _ultimo_valor(bpa, CONTA_INTANGIVEL),
            "ativo_total_bpa": ativo_total,
            "passivo_total": passivo_total,
        }

    except Exception as e:
        logger.error(f"Erro em buscar_ativos_para_liquidacao_cvm: {e}")
        return {"disponivel": False, "erro": str(e)}


def buscar_crescimento_lucro_anual_cvm(ticker: str, nome_empresa: str = "") -> dict:
    """
    CAGR de lucro líquido anual via CVM (DFP, exercícios completos) — usado
    pelo DCF Duas Fases (valuation/crescimento.py::calcular_dcf_duas_fases())
    como alternativa ao crescimento de RECEITA que era usado antes pra
    projetar o LPA (lucro por ação, um fluxo de lucro, não de receita — ver
    CONTEXT.md). Não existe um campo de crescimento de lucro pronto nem no
    pacote `fundamentus` (só `Cres_Rec_5a`, de receita) nem em
    `saude_financeira.py::extrair_crescimento_cvm()` (também de receita, e
    limitado a 6 trimestres — insuficiente pro comparativo YoY que essa
    função já faz).

    Retorna `disponivel: False` (nunca um número inventado) quando:
      - a empresa não é encontrada na CVM ou tem menos de 2 exercícios
        anuais completos de lucro líquido;
      - QUALQUER exercício do período disponível teve prejuízo (lucro <= 0)
        — CAGR entre um prejuízo e um lucro (ou vice-versa) não é
        matematicamente definido de forma útil (a base seria negativa) e
        um CAGR calculado só entre os dois extremos, ignorando um prejuízo
        no meio, pode subestimar dramaticamente a volatilidade real —
        confirmado com a própria BEEF3: FY2023 lucro R$396mi, FY2024
        PREJUÍZO de R$1,56bi, FY2025 lucro R$848mi — um CAGR ponta-a-ponta
        (2023->2025) dessa série daria ~+46% ao ano, escondendo o prejuízo
        no meio e superestimando o crescimento real de forma perigosa se
        usado numa projeção de 5 anos.

    Quando `disponivel: True`, o CAGR retornado já vem clampado numa faixa
    conservadora (-5% a 30%) — mesma ordem de grandeza dos limites já
    usados em outros lugares do pipeline de crescimento (main.py,
    valuation/crescimento.py).
    """
    ticker_busca = ticker.upper().strip()
    razao_social_exata = MAPA_NOMES_CVM.get(ticker_busca, nome_empresa or ticker_busca)

    try:
        if not DADOS_DIR.exists() or not any(DADOS_DIR.iterdir()):
            return {"disponivel": False, "erro": "Dados CVM não encontrados. Execute backend/scripts/atualizar_cvm.py"}

        cd_cvm = buscar_cd_cvm(razao_social_exata)
        if cd_cvm is None:
            return {"disponivel": False, "erro": f"Empresa não encontrada na CVM: {razao_social_exata}"}

        dfp_dre = _carregar_demo("dfp_dre", cd_cvm)
        if dfp_dre.empty:
            return {"disponivel": False, "cd_cvm": cd_cvm, "erro": "DFP (DRE anual) indisponível pra este ticker"}

        serie_lucro_anual = _extrair_serie(dfp_dre, CONTA_LUCRO_LIQUIDO)
        if len(serie_lucro_anual) < 2:
            return {
                "disponivel": False,
                "cd_cvm": cd_cvm,
                "erro": f"Só {len(serie_lucro_anual)} exercício(s) anual(is) de lucro líquido disponível — precisa de ao menos 2",
            }

        valores = [float(v) for v in serie_lucro_anual.values]
        if any(v <= 0 for v in valores):
            return {
                "disponivel": False,
                "cd_cvm": cd_cvm,
                "erro": "Prejuízo em pelo menos um exercício do período disponível — CAGR de lucro não é confiável nesse caso",
                "lucros_anuais": valores,
            }

        anos = [dt.year for dt in serie_lucro_anual.index]
        num_anos = anos[-1] - anos[0]
        if num_anos <= 0:
            return {"disponivel": False, "cd_cvm": cd_cvm, "erro": "Exercícios disponíveis não cobrem um intervalo de anos válido"}

        cagr = (valores[-1] / valores[0]) ** (1 / num_anos) - 1
        cagr_clampado = max(-0.05, min(cagr, 0.30))

        return {
            "disponivel": True,
            "cd_cvm": cd_cvm,
            "cagr": round(cagr_clampado, 4),
            "anos_considerados": anos,
            "lucros_anuais": valores,
        }

    except Exception as e:
        logger.error(f"Erro em buscar_crescimento_lucro_anual_cvm: {e}")
        return {"disponivel": False, "erro": str(e)}


# ─── FCFE — coleta de inputs via CVM ────────────────────────────────────────

def _delta_ccl_convencao_academica(variacao_ativos_passivos_cvm: float) -> float:
    """
    Converte a conta CVM 6.01.02 ("Variações nos Ativos e Passivos") da
    convenção de IMPACTO EM CAIXA (positivo = liberou caixa, capital de
    giro caiu; é a convenção que a própria CVM usa pra somar direto ao
    lucro líquido no cálculo do FCO) para a convenção ACADÊMICA de ΔCCL
    esperada por valuation.fcfe.calcular_fcfe() (positivo = aumento de
    capital de giro, ou seja, consumiu caixa).

    As duas convenções têm sinal invertido uma da outra — daí o -1. Função
    isolada (em vez de inline) de propósito: essa decisão de sinal já foi
    perdida uma vez num comentário antes, então agora ela é uma unidade só
    testável e auditável.
    """
    return -1.0 * variacao_ativos_passivos_cvm


def _magnitude_convencao_fcfe(soma_saida_cvm: Optional[float]) -> Optional[float]:
    """
    CAPEX e amortização de dívida são reportados pela CVM como SAÍDA de
    caixa (valor negativo — mesma convenção do DFC inteiro: entrada é
    positiva, saída é negativa). valuation.fcfe.calcular_fcfe() espera os
    dois como MAGNITUDE positiva (ver docstring de calcular_fcfe() e os
    testes em test_fcfe.py — `capex=400`, `amortizacao_dividas=300`, não
    negativos). Inverte o sinal. `None` continua `None` (dado indisponível
    não vira zero).
    """
    if soma_saida_cvm is None:
        return None
    return -1.0 * soma_saida_cvm


def buscar_inputs_fcfe_cvm(ticker: str, nome_empresa: str = "") -> dict:
    """
    Coleta os inputs de FCFE disponíveis via CVM — lucro líquido,
    depreciação/amortização, ΔCCL, CAPEX, captação e amortização de
    dívida, todos TTM (soma dos 4 trimestres mais recentes de verdade via
    calcular_ttm_correto()/calcular_ttm_por_texto(), incluindo o 4º
    trimestre derivado via DFP — ver CONTEXT.md) para serem
    dimensionalmente consistentes entre si. As chaves do dict batem com
    os nomes de parâmetro de valuation.fcfe.calcular_fcfe(), prontas para
    uso direto via `calcular_fcfe(**inputs)` quando `fcfe_completo_disponivel`
    for True.

    CAPEX/captação/amortização vêm de contas não padronizadas do DFC
    (ST_CONTA_FIXA="N" — nome, posição e composição variam por empresa, e
    a MESMA empresa pode reordenar os códigos entre filings; ver
    CONTEXT.md) — identificadas por casamento de texto via
    extrair_por_texto(), validado manualmente contra 20 tickers de
    setores diferentes antes de ligar aqui. Continuam None (não zero)
    quando:
      - nenhuma linha bateu no filtro pra aquele ticker (dado
        genuinamente indisponível, não confundir com "a empresa não teve
        movimento" — isso já é coberto por um valor 0 real vindo da CVM);
      - o valor resultante veio com sinal invertido do esperado (ex:
        captação negativa, amortização/capex positivos) — sinal de que a
        heurística de texto pegou a linha errada pra esse ticker
        específico (confirmado em WIZC3/TAEE3 durante a validação: contas
        que mudam de posição entre filings podem, em casos raros,
        escapar do filtro). Preferimos declarar indisponível a expor um
        valor sabidamente errado.

    Sinal de delta_ccl: ver _delta_ccl_convencao_academica().
    Sinal de capex/amortizacao_dividas: ver _magnitude_convencao_fcfe().
    novas_dividas_emitidas não precisa de inversão — a CVM já reporta
    captação como entrada positiva, mesma convenção de calcular_fcfe().
    """
    ticker_busca = ticker.upper().strip()

    if ticker_busca in MAPA_NOMES_CVM:
        razao_social_exata = MAPA_NOMES_CVM[ticker_busca]
    else:
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

        dre_itr = _carregar_demo("itr_dre", cd_cvm)
        dfc_itr = _carregar_demo("itr_dfc", cd_cvm)
        dre_dfp = _carregar_demo("dfp_dre", cd_cvm)
        dfc_dfp = _carregar_demo("dfp_dfc", cd_cvm)

        dre = dre_itr if not dre_itr.empty else dre_dfp
        dfc = dfc_itr if not dfc_itr.empty else dfc_dfp

        if dre.empty or dfc.empty:
            return {"disponivel": False, "erro": "Demonstrações não disponíveis para este ticker", "cd_cvm": cd_cvm}

        # TTM corrigido (ver calcular_ttm_correto em cvm_provider.py) — soma
        # os 4 trimestres mais recentes DE VERDADE, incluindo o 4º trimestre
        # derivado via DFP. Substitui o antigo .tail(4).sum() direto sobre a
        # série só-ITR, que pulava o Q4 e cobria ~15 meses em vez de 12.
        ttm_lucro = calcular_ttm_correto(dre_itr, dre_dfp, CONTA_LUCRO_LIQUIDO)
        # D&A por texto (não pela posição fixa) — ver nota em buscar_saude_financeira_cvm()
        ttm_dep   = calcular_ttm_por_texto(dfc_itr, dfc_dfp, DEPRECIACAO_PREFIXO, PADRAO_DEPRECIACAO_INCLUIR, PADRAO_DEPRECIACAO_EXCLUIR)
        ttm_var   = calcular_ttm_correto(dfc_itr, dfc_dfp, CONTA_VARIACAO_ATIVOS_PASSIVOS)

        lucro_liquido = ttm_lucro["valor"]
        depreciacao   = ttm_dep["valor"]

        delta_ccl = None
        if ttm_var["valor"] is not None:
            delta_ccl = _delta_ccl_convencao_academica(ttm_var["valor"])

        # CAPEX/captação/amortização — casamento de texto (ver CONTEXT.md
        # e o levantamento de validação manual contra 20 tickers).
        ttm_capex = calcular_ttm_por_texto(dfc_itr, dfc_dfp, CAPEX_PREFIXO, PADRAO_CAPEX_INCLUIR, PADRAO_CAPEX_EXCLUIR)
        ttm_capt  = calcular_ttm_por_texto(dfc_itr, dfc_dfp, FINANCIAMENTO_PREFIXO, PADRAO_CAPTACAO_INCLUIR, PADRAO_CAPTACAO_EXCLUIR)
        ttm_amort = calcular_ttm_por_texto(dfc_itr, dfc_dfp, FINANCIAMENTO_PREFIXO, PADRAO_AMORTIZACAO_INCLUIR, PADRAO_AMORTIZACAO_EXCLUIR)

        capex = _magnitude_convencao_fcfe(ttm_capex["valor"])
        if capex is not None and capex < 0:
            # CVM trouxe a linha de CAPEX com saída positiva (sinal
            # invertido do esperado) — heurística de texto pegou algo
            # errado pra esse ticker. Não expõe valor sabidamente errado.
            capex = None

        novas_dividas_emitidas = ttm_capt["valor"]
        if novas_dividas_emitidas is not None and novas_dividas_emitidas < 0:
            # Captação nunca deveria ser negativa (confirmado em WIZC3
            # que isso acontece por inconsistência na própria empresa
            # nos dados brutos da CVM, não bug do filtro).
            novas_dividas_emitidas = None

        amortizacao_dividas = _magnitude_convencao_fcfe(ttm_amort["valor"])
        if amortizacao_dividas is not None and amortizacao_dividas < 0:
            amortizacao_dividas = None

        fcfe_completo_disponivel = all(
            v is not None
            for v in (lucro_liquido, capex, depreciacao, delta_ccl, novas_dividas_emitidas, amortizacao_dividas)
        )

        return {
            "disponivel": True,
            "cd_cvm": cd_cvm,
            "lucro_liquido": lucro_liquido,
            "depreciacao": depreciacao,
            "delta_ccl": delta_ccl,
            "capex": capex,
            "novas_dividas_emitidas": novas_dividas_emitidas,
            "amortizacao_dividas": amortizacao_dividas,
            "fcfe_completo_disponivel": fcfe_completo_disponivel,
        }

    except Exception as e:
        logger.error(f"Erro em buscar_inputs_fcfe_cvm: {e}")
        return {"disponivel": False, "erro": str(e)}