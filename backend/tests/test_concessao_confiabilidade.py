"""
test_concessao_confiabilidade.py
Teste da regra de exibição do DCF Concessão: preço justo <= 0 é
matematicamente válido (o cálculo rodou, não é indisponibilidade de dado),
mas é sinal forte de inconsistência nos inputs — achado real com GEPA4,
onde a CVM reporta balanço/DRE zerados desde 2024 (ver CONTEXT.md).
`enriquecer_com_concessao()` (main.py) deve marcar `confiabilidade_baixa:
True` e acrescentar uma nota explícita nesses casos, sem esconder o número
(é informação real de que algo está errado na fonte).

Usa GEPA4 (ticker real mapeado em CONCESSOES_CONHECIDAS) com inputs
artificialmente desbalanceados (dívida líquida muito acima do fluxo de
caixa) — determinístico, sem rede: não busca dados reais, só exercita
enriquecer_com_concessao() e calcular_dcf_concessao() diretamente.
"""

from main import enriquecer_com_concessao


class TestConfiabilidadeBaixaQuandoPrecoJustoNegativo:

    def test_preco_justo_negativo_marca_confiabilidade_baixa(self):
        # Dívida líquida muito maior que o FCF projetado -> equity/preço
        # justo negativo, garantido independente de premissas de WACC/g.
        resultado = enriquecer_com_concessao(
            ticker="GEPA4",
            fcf_base=1.0,        # R$ 1 mi — praticamente nulo
            ativo_imob=10.0,     # R$ 10 mi
            divida_liq=50_000.0, # R$ 50 bi — desbalanceado de propósito
            num_acoes=94_433_000.0,
            wacc=0.15,
            resultado={},
        )

        concessao = resultado["concessao"]
        assert concessao["aplicavel"] is True
        assert concessao["preco_justo"] <= 0
        assert concessao["confiabilidade_baixa"] is True
        assert any("não deve ser usado como referência de valor" in nota for nota in concessao["notas"])

    def test_preco_justo_positivo_nao_marca_confiabilidade_baixa(self):
        # Mesmo ticker, dados equilibrados -> preço justo positivo, sem a
        # flag (garante que a regra não dispara em falso-positivo).
        resultado = enriquecer_com_concessao(
            ticker="GEPA4",
            fcf_base=500.0,      # R$ 500 mi
            ativo_imob=3000.0,   # R$ 3 bi
            divida_liq=1000.0,   # R$ 1 bi — bem menor que o valor projetado
            num_acoes=94_433_000.0,
            wacc=0.12,
            resultado={},
        )

        concessao = resultado["concessao"]
        assert concessao["aplicavel"] is True
        assert concessao["preco_justo"] > 0
        assert "confiabilidade_baixa" not in concessao

    def test_ticker_sem_concessao_nao_afetado(self):
        # Não deve nem chegar perto da lógica de confiabilidade — early
        # return por não ser uma concessionária mapeada.
        resultado = enriquecer_com_concessao(
            ticker="BEEF3",
            fcf_base=100.0,
            ativo_imob=100.0,
            divida_liq=100.0,
            num_acoes=1_000_000.0,
            wacc=0.15,
            resultado={},
        )
        assert resultado["concessao"] is None
