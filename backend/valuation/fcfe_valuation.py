"""
fcfe_valuation.py — orquestra o valuation de equity via FCFE ponta a ponta.

Liga: dados.cvm_provider.buscar_inputs_fcfe_cvm() (coleta de inputs, TTM
já corrigido — ver CONTEXT.md) -> valuation.fcfe.calcular_fcfe() (FCFE do
ano base) -> valuation.fcfe.valuation_fcfe_dois_estagios() (projeção e
valor justo por ação).

Premissas de Ke e crescimento são recebidas de fora (não recalculadas aqui)
— main.py já computa `taxa_capm` (Ke via calcular_capm()) e a taxa de
crescimento/g_perpetuo do DCF Duas Fases (valuation/crescimento.py::
calcular_dcf_duas_fases()) pra cada ticker; o FCFE reaproveita exatamente
os mesmos valores, pra a comparação lado a lado com o FCFF/DCF fazer
sentido (decisão explícita: os dois valuations só são comparáveis se
partirem da mesma premissa de crescimento).

Sector-aware: bancos e seguradoras usam taxonomia COSIF/SUSEP na CVM, onde
as contas fixas de cvm_provider.py (calibradas pra IFRS industrial) não
têm o mesmo significado — retorna indisponibilidade explícita nesses
casos, sem tentar calcular um número que seria enganoso.
"""

from dataclasses import asdict

from dados.cvm_provider import buscar_inputs_fcfe_cvm
from valuation.fcfe import calcular_fcfe, valuation_fcfe_dois_estagios


# Mesmas 3 categorias de valuation/setor.py::CONFIGURACAO_SETORES que já
# invalidam DCF clássico por taxonomia financeira — reaproveita o mesmo
# critério de correspondência parcial usado por get_configuracao_setor().
_SETORES_COSIF_SUSEP = ("bancos", "seguradoras", "intermediários financeiros", "intermediarios financeiros")


def eh_setor_bancario_ou_segurador(setor: str) -> bool:
    setor_limpo = str(setor).lower().strip()
    if not setor_limpo:
        return False  # string vazia é substring de qualquer "chave in setor_limpo" abaixo — não é um match real
    return any(chave in setor_limpo or setor_limpo in chave for chave in _SETORES_COSIF_SUSEP)


def calcular_valuation_fcfe(
    ticker: str,
    nome_empresa: str,
    setor: str,
    ke: float,
    taxa_crescimento_explicito: float,
    g_perpetuo: float,
    anos_explicitos: int,
    num_acoes: float,
) -> dict:
    """
    Args:
        ke: custo de capital próprio já calculado (calcular_capm()['taxa_desconto']
            de main.py) — NÃO recalculado aqui. FCFE desconta a Ke, não a WACC
            (diferente do FCFF/DCF): o fluxo já é líquido dos efeitos de dívida.
        taxa_crescimento_explicito / g_perpetuo / anos_explicitos: mesma premissa
            do DCF Duas Fases já existente (valuation/crescimento.py), pra a
            comparação lado a lado ser consistente.
        num_acoes: quantidade RAW de ações (não em milhões) — os valores de
            cvm_provider.py já vêm em R$ absolutos (ESCALA_MOEDA tratada),
            então a divisão precisa ser feita na mesma unidade.

    Returns:
        dict com "disponivel". Se True: "cd_cvm", "fcfe_ano_base" (dict de
        ResultadoFCFE), "projecao" (dict de ValuationFCFEResultado ou None
        se número de ações inválido) e "premissas". Se False: "erro" e,
        quando aplicável, "inputs_parciais" com os campos que já batiam.
    """
    if eh_setor_bancario_ou_segurador(setor):
        return {
            "disponivel": False,
            "erro": "FCFE indisponível — taxonomia COSIF/SUSEP não suportada",
        }

    inputs = buscar_inputs_fcfe_cvm(ticker, nome_empresa)

    if not inputs.get("disponivel"):
        return {"disponivel": False, "erro": inputs.get("erro", "Dados CVM indisponíveis")}

    if not inputs.get("fcfe_completo_disponivel"):
        return {
            "disponivel": False,
            "cd_cvm": inputs.get("cd_cvm"),
            "erro": "Dados de FCFE incompletos via CVM — pelo menos um dos 6 campos não foi encontrado",
            "inputs_parciais": {
                campo: inputs.get(campo)
                for campo in (
                    "lucro_liquido", "depreciacao", "delta_ccl",
                    "capex", "novas_dividas_emitidas", "amortizacao_dividas",
                )
            },
        }

    resultado_ano_base = calcular_fcfe(
        lucro_liquido=inputs["lucro_liquido"],
        capex=inputs["capex"],
        depreciacao=inputs["depreciacao"],
        delta_ccl=inputs["delta_ccl"],
        novas_dividas_emitidas=inputs["novas_dividas_emitidas"],
        amortizacao_dividas=inputs["amortizacao_dividas"],
    )

    if num_acoes is None or num_acoes <= 0:
        return {
            "disponivel": True,
            "cd_cvm": inputs.get("cd_cvm"),
            "fcfe_ano_base": asdict(resultado_ano_base),
            "projecao": None,
            "erro": "Número de ações inválido — impossível projetar valor justo por ação.",
        }

    projecao = valuation_fcfe_dois_estagios(
        fcfe_ano_base=resultado_ano_base.fcfe,
        taxa_crescimento_explicito=taxa_crescimento_explicito,
        anos_explicitos=anos_explicitos,
        ke=ke,
        g_perpetuo=g_perpetuo,
        numero_acoes=num_acoes,
    )

    return {
        "disponivel": True,
        "cd_cvm": inputs.get("cd_cvm"),
        "fcfe_ano_base": asdict(resultado_ano_base),
        "projecao": asdict(projecao),
        "premissas": {
            "ke": ke,
            "taxa_crescimento_explicito": taxa_crescimento_explicito,
            "g_perpetuo": g_perpetuo,
            "anos_explicitos": anos_explicitos,
        },
    }
