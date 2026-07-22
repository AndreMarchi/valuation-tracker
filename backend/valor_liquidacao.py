# backend/valor_liquidacao.py
"""
Valor de Liquidação — piso conservador de valor calculado a partir do
balanço patrimonial (Ativo por classe via CVM/BPA, ver
dados/cvm_provider.py::buscar_ativos_para_liquidacao_cvm()).

Unidades: todos os valores monetários (ativos, passivo_total,
contingências) precisam vir na MESMA escala entre si, e `num_acoes` no
número real de ações (não pré-dividido) — o resultado por ação sai
automaticamente na mesma escala monetária usada nos ativos/passivo. Os
valores retornados por buscar_ativos_para_liquidacao_cvm() já vêm em R$
absolutos (mesma convenção do resto de cvm_provider.py), então o uso mais
simples é passar tudo em R$ absolutos direto.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class HaircutsAtivos:
    """
    Percentual do valor contábil que se espera recuperar numa liquidação
    forçada, por classe de ativo. Defaults seguem a convenção clássica de
    "liquidation value" / net-net working capital (Benjamin Graham) usada
    em análise de crédito e valuation defensivo: ativos líquidos/fungíveis
    têm haircut baixo; ativos específicos da operação (intangível) valem
    pouco ou nada fora do contexto da empresa em funcionamento normal:

      - caixa_equivalentes (100%):     já é caixa — nada a liquidar.
      - aplicacoes_financeiras (90%):  líquido, mas com deságio de
                                       marcação a mercado forçada/pressa.
      - contas_a_receber (80%):       parcela não será recebida
                                       (inadimplência, desconto para
                                       antecipar o recebimento).
      - estoques (70%):               deságio típico de venda forçada
                                       (leilão/liquidação), não preço de
                                       varejo normal.
      - imobilizado (50%):            ativo especializado — mercado
                                       secundário limitado, custo de
                                       desmontagem/transporte/tempo de
                                       venda.
      - intangivel (0%):              marca, ágio, contratos, software —
                                       tipicamente sem valor de revenda
                                       fora da empresa em funcionamento.

    Parametrizável — cada campo pode ser sobrescrito pelo chamador, nunca
    hardcoded sem opção de override.
    """
    caixa_equivalentes: float = 1.00
    aplicacoes_financeiras: float = 0.90
    contas_a_receber: float = 0.80
    estoques: float = 0.70
    imobilizado: float = 0.50
    intangivel: float = 0.00


def calcular_valor_liquidacao(
    caixa_equivalentes: float,
    aplicacoes_financeiras: float,
    contas_a_receber: float,
    estoques: float,
    imobilizado: float,
    intangivel: float,
    passivo_total: float,
    num_acoes: float,
    contingencias: Optional[float] = None,
    haircuts: Optional[HaircutsAtivos] = None,
) -> dict:
    """
    Valor de Liquidação = Σ(ativo_da_classe × haircut_da_classe) −
    passivo_total − contingências.

    `contingencias`: a CVM não disponibiliza uma estimativa estruturada de
    contingências (só em notas explicativas de texto livre — mesma
    limitação já documentada pra composição cambial da receita, ver
    dados/cvm_provider.py). Por isso é um input MANUAL opcional: `None`
    (default) aplica 0 e marca `contingencias_informadas=False` no
    retorno, pra deixar explícito que nenhuma contingência foi
    contabilizada — nunca estimamos um valor arbitrário no lugar de um
    dado ausente.

    Só as 6 classes de ativo citadas no pedido original entram no cálculo
    — deliberadamente NÃO é o Ativo Total (ver docstring de
    buscar_ativos_para_liquidacao_cvm(): outras classes como Investimentos
    ou Ativos Biológicos não têm uma convenção de haircut de liquidação
    definida, incluí-las exigiria inventar um percentual sem base). Isso
    torna o piso de liquidação MAIS conservador, nunca menos.

    `valor_liquidacao_total`/`valor_liquidacao_por_acao` podem sair
    negativos quando o passivo supera os ativos ajustados — não é
    clampado em zero: o número negativo é informação real (a empresa
    estaria com patrimônio líquido negativo numa liquidação forçada, ver
    `patrimonio_liquido_negativo_em_liquidacao` no retorno), mesmo padrão
    já usado no DCF Concessão para preço justo ≤ 0 (não esconder o número,
    só sinalizar explicitamente).
    """
    haircuts = haircuts or HaircutsAtivos()
    contingencias_informadas = contingencias is not None
    contingencias_aplicadas = contingencias if contingencias_informadas else 0.0

    ativos_ajustados = {
        "caixa_equivalentes": caixa_equivalentes * haircuts.caixa_equivalentes,
        "aplicacoes_financeiras": aplicacoes_financeiras * haircuts.aplicacoes_financeiras,
        "contas_a_receber": contas_a_receber * haircuts.contas_a_receber,
        "estoques": estoques * haircuts.estoques,
        "imobilizado": imobilizado * haircuts.imobilizado,
        "intangivel": intangivel * haircuts.intangivel,
    }
    total_ativos_ajustados = sum(ativos_ajustados.values())

    valor_liquidacao_total = total_ativos_ajustados - passivo_total - contingencias_aplicadas
    valor_liquidacao_por_acao = (
        valor_liquidacao_total / num_acoes if num_acoes and num_acoes > 0 else None
    )

    return {
        "ativos_ajustados": {chave: round(valor, 2) for chave, valor in ativos_ajustados.items()},
        "total_ativos_ajustados": round(total_ativos_ajustados, 2),
        "passivo_total": round(passivo_total, 2),
        "contingencias": round(contingencias_aplicadas, 2),
        "contingencias_informadas": contingencias_informadas,
        "valor_liquidacao_total": round(valor_liquidacao_total, 2),
        "valor_liquidacao_por_acao": (
            round(valor_liquidacao_por_acao, 2) if valor_liquidacao_por_acao is not None else None
        ),
        "patrimonio_liquido_negativo_em_liquidacao": valor_liquidacao_total < 0,
        "haircuts_aplicados": {
            "caixa_equivalentes": haircuts.caixa_equivalentes,
            "aplicacoes_financeiras": haircuts.aplicacoes_financeiras,
            "contas_a_receber": haircuts.contas_a_receber,
            "estoques": haircuts.estoques,
            "imobilizado": haircuts.imobilizado,
            "intangivel": haircuts.intangivel,
        },
    }
