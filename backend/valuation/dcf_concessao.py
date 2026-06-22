
from dataclasses import dataclass, field
from typing import Optional
from datetime import date


# ---------------------------------------------------------------------------
# Parâmetros de concessão — adicionar ao payload de /analisar ou como
# campo extra em DadosEmpresa / inputs do frontend
# ---------------------------------------------------------------------------

@dataclass
class ParametrosConcessao:
    """
    Parâmetros que descrevem a estrutura de concessão da empresa.

    Exemplo para GEPA4:
        ano_vencimento_principal = 2029   (6 usinas do Contrato 76/99)
        ano_vencimento_secundario = 2033  (Canoas I e II)
        percentual_receita_principal = 0.75  (estimativa: 75% da receita está no bloco 2029)
        probabilidade_renovacao = 0.60
        desconto_pos_renovacao = 0.15    (tarifa tende a cair 15% numa renovação negociada)
        taxa_recuperacao_ativos = 0.30   (valor residual dos ativos fixos se não renovar)
    """

    ano_vencimento_principal: int            # Ano do primeiro (maior) vencimento
    percentual_receita_principal: float      # Fração da receita que se vai junto com o bloco principal
    probabilidade_renovacao: float = 0.60    # 0.0 = certeza de não renovar, 1.0 = certeza de renovar
    desconto_pos_renovacao: float = 0.15     # Queda esperada de FCF após renovação (regulatório)
    taxa_recuperacao_ativos: float = 0.30    # % do ativo imobilizado recuperável se não renovar
    ano_vencimento_secundario: Optional[int] = None   # Bloco menor (ex: 2033 para Canoas)
    percentual_receita_secundario: float = 0.0        # Fração da receita do bloco secundário
    crescimento_pre_cliff: float = 0.0       # Taxa de crescimento do FCF antes do vencimento
    crescimento_pos_renovacao: float = 0.0   # Taxa de crescimento do FCF pós-renovação
    wacc: float = 0.12                       # Taxa de desconto


@dataclass
class ResultadoDCFConcessao:
    """Resultado detalhado do DCF com concession cliff."""

    preco_justo: float
    valor_presente_fluxos: float          # Soma dos FCFs descontados até o cliff
    valor_terminal_esperado_pv: float     # E[VT] trazido a valor presente
    valor_terminal_renovacao: float       # VT se renovar (antes da probabilidade)
    valor_terminal_liquidacao: float      # VT se não renovar (antes da probabilidade)
    anos_ate_vencimento: int
    fluxos_projetados: list[dict]         # Detalhe ano a ano para exibir no frontend
    wacc_usado: float
    probabilidade_renovacao: float
    impacto_cliff: float                  # Diferença vs DCF perpétuo padrão (R$ por ação)
    notas: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def calcular_dcf_concessao(
    fcf_base: float,                    # FCF do último exercício (R$ milhões)
    ativo_imobilizado: float,           # Ativo imobilizado líquido (R$ milhões)
    divida_liquida: float,              # Dívida líquida (R$ milhões)
    numero_acoes: float,                # Total de ações (unidades)
    params: ParametrosConcessao,
    ano_atual: int = None,
) -> ResultadoDCFConcessao:
    """
    Calcula o preço justo por ação usando DCF com modelagem do cliff de concessão.

    Retorna ResultadoDCFConcessao com preço justo e breakdown detalhado.
    """

    if ano_atual is None:
        ano_atual = date.today().year

    anos_ate_vencimento = params.ano_vencimento_principal - ano_atual
    wacc = params.wacc
    g_pre = params.crescimento_pre_cliff
    g_pos = params.crescimento_pos_renovacao

    notas = []

    if anos_ate_vencimento <= 0:
        notas.append("⚠️ Concessão já vencida ou vence este ano. Análise inconclusiva.")
        anos_ate_vencimento = 1

    # ------------------------------------------------------------------
    # FASE 1 — Projeção dos FCFs até o vencimento da concessão principal
    # ------------------------------------------------------------------
    vp_fluxos = 0.0
    fluxos_projetados = []
    fcf_t = fcf_base

    for t in range(1, anos_ate_vencimento + 1):
        fcf_t = fcf_t * (1 + g_pre)
        desconto = (1 + wacc) ** t
        vp = fcf_t / desconto
        vp_fluxos += vp
        fluxos_projetados.append({
            "ano": ano_atual + t,
            "fcf": round(fcf_t, 2),
            "fator_desconto": round(desconto, 4),
            "vp": round(vp, 2),
            "fase": "pré-cliff" if t < anos_ate_vencimento else "cliff",
        })

    # ------------------------------------------------------------------
    # VALOR TERMINAL — Probabilístico no ano do vencimento
    # ------------------------------------------------------------------

    # Cenário A: Renovação — FCF cai pelo desconto regulatório e segue como perpetuidade
    fcf_pos_renovacao = fcf_t * (1 - params.desconto_pos_renovacao)

    # Se há bloco secundário (ex: 2033), parte do FCF ainda sobrevive após 2029
    if params.ano_vencimento_secundario and params.percentual_receita_secundario > 0:
        fcf_apenas_principal = fcf_t * params.percentual_receita_principal
        fcf_sobrevivente = fcf_t * params.percentual_receita_secundario
        fcf_pos_renovacao = (
            fcf_apenas_principal * (1 - params.desconto_pos_renovacao)
            + fcf_sobrevivente  # bloco secundário continua operando normalmente
        )
        notas.append(
            f"Bloco secundário ({params.ano_vencimento_secundario}): "
            f"{params.percentual_receita_secundario*100:.0f}% da receita continua após {params.ano_vencimento_principal}."
        )

    if wacc > g_pos:
        vt_renovacao = fcf_pos_renovacao * (1 + g_pos) / (wacc - g_pos)
    else:
        # WACC ≤ crescimento: perpetuidade explodiria — capeia em 20x FCF
        vt_renovacao = fcf_pos_renovacao * 20
        notas.append("⚠️ g ≥ WACC: valor terminal de renovação limitado a 20× FCF.")

    # Cenário B: Sem renovação — valor residual dos ativos
    vt_liquidacao = ativo_imobilizado * params.taxa_recuperacao_ativos

    # Valor terminal esperado (ponderado pela probabilidade)
    p = params.probabilidade_renovacao
    vt_esperado = (p * vt_renovacao) + ((1 - p) * vt_liquidacao)

    # Traz o VT esperado a valor presente (descontado pelos anos até o cliff)
    vt_esperado_pv = vt_esperado / (1 + wacc) ** anos_ate_vencimento

    # ------------------------------------------------------------------
    # VALOR DA EMPRESA (equity) → Preço por ação
    # ------------------------------------------------------------------
    valor_empresa = vp_fluxos + vt_esperado_pv
    equity_value = valor_empresa - divida_liquida
    preco_justo = (equity_value * 1_000_000) / numero_acoes  # converte R$ mi → R$

    # ------------------------------------------------------------------
    # IMPACTO DO CLIFF (comparação com perpetuidade ingênua)
    # ------------------------------------------------------------------
    if wacc > g_pre:
        vt_perpetuidade = fcf_base * (1 + g_pre) / (wacc - g_pre)
    else:
        vt_perpetuidade = fcf_base * 20

    equity_sem_cliff = (vp_fluxos + vt_perpetuidade / (1 + wacc) ** anos_ate_vencimento - divida_liquida) * 1_000_000
    preco_sem_cliff = equity_sem_cliff / numero_acoes
    impacto_cliff = preco_justo - preco_sem_cliff

    # Notas adicionais
    if anos_ate_vencimento <= 5:
        notas.append(f"🚨 Concessão principal vence em {params.ano_vencimento_principal} ({anos_ate_vencimento} anos). Risco alto.")
    elif anos_ate_vencimento <= 8:
        notas.append(f"⚠️ Concessão principal vence em {params.ano_vencimento_principal} ({anos_ate_vencimento} anos). Monitorar.")

    if params.probabilidade_renovacao < 0.5:
        notas.append("⚠️ Probabilidade de renovação abaixo de 50% — ativo especulativo.")

    return ResultadoDCFConcessao(
        preco_justo=round(preco_justo, 2),
        valor_presente_fluxos=round(vp_fluxos, 2),
        valor_terminal_esperado_pv=round(vt_esperado_pv, 2),
        valor_terminal_renovacao=round(vt_renovacao, 2),
        valor_terminal_liquidacao=round(vt_liquidacao, 2),
        anos_ate_vencimento=anos_ate_vencimento,
        fluxos_projetados=fluxos_projetados,
        wacc_usado=wacc,
        probabilidade_renovacao=p,
        impacto_cliff=round(impacto_cliff, 2),
        notas=notas,
    )


# ---------------------------------------------------------------------------
# Detecção automática de empresas concessionárias
# ---------------------------------------------------------------------------

# Mapa estático inicial — expandir conforme necessário
CONCESSOES_CONHECIDAS: dict[str, ParametrosConcessao] = {
    "GEPA4": ParametrosConcessao(
        ano_vencimento_principal=2029,
        percentual_receita_principal=0.75,
        probabilidade_renovacao=0.60,
        desconto_pos_renovacao=0.15,
        taxa_recuperacao_ativos=0.30,
        ano_vencimento_secundario=2033,
        percentual_receita_secundario=0.25,
        crescimento_pre_cliff=0.0,
        crescimento_pos_renovacao=0.0,
    ),
    "GEPA3": ParametrosConcessao(  # mesma empresa, ação ON
        ano_vencimento_principal=2029,
        percentual_receita_principal=0.75,
        probabilidade_renovacao=0.60,
        desconto_pos_renovacao=0.15,
        taxa_recuperacao_ativos=0.30,
        ano_vencimento_secundario=2033,
        percentual_receita_secundario=0.25,
    ),
    # Adicionar outras concessionárias aqui:
    # "TIET11": ParametrosConcessao(ano_vencimento_principal=2029, ...),
}


def detectar_concessao(ticker: str) -> Optional[ParametrosConcessao]:
    """
    Retorna os parâmetros de concessão para o ticker, se conhecido.
    Retorna None se não for uma empresa concessionária mapeada.
    """
    return CONCESSOES_CONHECIDAS.get(ticker.upper())


def empresa_tem_concessao(ticker: str) -> bool:
    return ticker.upper() in CONCESSOES_CONHECIDAS
