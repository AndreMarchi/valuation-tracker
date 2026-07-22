import pytest

from cenarios_sensibilidade import (
    DeltasCenario,
    WaccInvalidoError,
    gerar_cenarios,
    gerar_matriz_sensibilidade,
    gerar_matrizes_padrao,
    gerar_analise_completa,
)
from valuation.dcf import calcular_dcf

# Dados base reutilizados nos testes — mesmo padrão de test_dcf.py
DADOS_BASE = dict(
    fluxo_caixa_atual=1000.0,
    taxa_crescimento=0.10,
    taxa_desconto=0.12,
    anos_projecao=5,
    taxa_crescimento_perpetuidade=0.03,
    num_acoes=500.0,
    preco_atual=30.0,
    margem_ebitda_atual=0.20,
)


# ─── gerar_cenarios(): cada cenário isoladamente ────────────────────────────

def test_cenario_base_bate_com_calcular_dcf_direto():
    """Sem deltas, o cenário base tem que ser idêntico a chamar calcular_dcf()
    direto com os mesmos inputs — gerar_cenarios() não pode alterar o motor."""
    resultado = gerar_cenarios(**DADOS_BASE)
    esperado = calcular_dcf(
        fluxo_caixa_atual=DADOS_BASE["fluxo_caixa_atual"],
        taxa_crescimento=DADOS_BASE["taxa_crescimento"],
        taxa_desconto=DADOS_BASE["taxa_desconto"],
        anos_projecao=DADOS_BASE["anos_projecao"],
        taxa_crescimento_perpetuidade=DADOS_BASE["taxa_crescimento_perpetuidade"],
        num_acoes=DADOS_BASE["num_acoes"],
        preco_atual=DADOS_BASE["preco_atual"],
    )
    assert resultado["cenarios"]["base"] == esperado["valor_intrinseco"]


def test_cenario_pessimista_menor_que_base_e_otimista_maior():
    resultado = gerar_cenarios(**DADOS_BASE)
    assert resultado["cenarios"]["pessimista"] < resultado["cenarios"]["base"]
    assert resultado["cenarios"]["otimista"] > resultado["cenarios"]["base"]


def test_faixa_bate_com_min_max_dos_tres_cenarios():
    resultado = gerar_cenarios(**DADOS_BASE)
    valores = resultado["cenarios"].values()
    assert resultado["faixa"]["minimo"] == min(valores)
    assert resultado["faixa"]["maximo"] == max(valores)


def test_deltas_customizados_sao_respeitados_nao_hardcoded():
    """Deltas maiores -> faixa pessimista/otimista mais larga. Prova que os
    deltas são parâmetros reais, não uma constante interna ignorando o argumento."""
    deltas_pequenos = DeltasCenario(wacc_pp=0.005, g_perpetuo_pp=0.002, margem_ebitda_pp=0.005, crescimento_receita_pp=0.01)
    deltas_grandes = DeltasCenario(wacc_pp=0.03, g_perpetuo_pp=0.02, margem_ebitda_pp=0.05, crescimento_receita_pp=0.06)

    resultado_pequeno = gerar_cenarios(**DADOS_BASE, deltas=deltas_pequenos)
    resultado_grande = gerar_cenarios(**DADOS_BASE, deltas=deltas_grandes)

    largura_pequena = resultado_pequeno["faixa"]["maximo"] - resultado_pequeno["faixa"]["minimo"]
    largura_grande = resultado_grande["faixa"]["maximo"] - resultado_grande["faixa"]["minimo"]
    assert largura_grande > largura_pequena

    # o cenário base não muda com os deltas (só pessimista/otimista)
    assert resultado_pequeno["cenarios"]["base"] == resultado_grande["cenarios"]["base"]


def test_margem_ebitda_afeta_fluxo_proporcionalmente():
    """Cenário com margem EBITDA base = 0 (dado ausente/zero) não pode
    quebrar por divisão por zero — fator_margem cai pro default 1.0."""
    dados = dict(DADOS_BASE)
    dados["margem_ebitda_atual"] = 0.0
    resultado = gerar_cenarios(**dados)
    # sem margem base, os 3 cenários ainda têm que ser calculáveis e ordenados
    assert resultado["cenarios"]["pessimista"] < resultado["cenarios"]["base"] < resultado["cenarios"]["otimista"]


def test_premissas_base_e_deltas_aplicados_presentes():
    resultado = gerar_cenarios(**DADOS_BASE)
    assert resultado["premissas_base"]["wacc"] == pytest.approx(0.12)
    assert resultado["premissas_base"]["g_perpetuo"] == pytest.approx(0.03)
    assert resultado["premissas_base"]["margem_ebitda"] == pytest.approx(0.20)
    assert resultado["deltas_aplicados"]["wacc_pp"] == pytest.approx(DeltasCenario().wacc_pp)


# ─── caso limite: WACC <= g perpétuo ────────────────────────────────────────

def test_wacc_igual_a_g_perpetuo_levanta_erro_tratado():
    """Bug comum em DCF: quando WACC <= g, o valor terminal diverge — não
    pode silenciosamente virar um número (0.0 ou negativo) sem avisar."""
    dados = dict(DADOS_BASE)
    dados["taxa_crescimento_perpetuidade"] = dados["taxa_desconto"]  # g == WACC
    with pytest.raises(WaccInvalidoError):
        gerar_cenarios(**dados)


def test_wacc_menor_que_g_perpetuo_levanta_erro_tratado():
    dados = dict(DADOS_BASE)
    dados["taxa_crescimento_perpetuidade"] = dados["taxa_desconto"] + 0.05  # g > WACC
    with pytest.raises(WaccInvalidoError):
        gerar_cenarios(**dados)


def test_delta_que_empurra_otimista_para_wacc_invalido_tambem_levanta_erro():
    """Mesmo que o cenário BASE seja válido, o cenário OTIMISTA reduz o WACC
    e aumenta o g perpétuo (as duas direções que aproximam WACC de g) — se
    o gap base for pequeno o bastante, o delta pode empurrar essa
    combinação específica pra WACC<=g. Tem que estourar erro tratado, não
    devolver um número incorreto só pro cenário otimista."""
    dados = dict(DADOS_BASE)
    dados["taxa_desconto"] = 0.05                    # base válido: WACC (5%) > g (3%)
    dados["taxa_crescimento_perpetuidade"] = 0.03
    # deltas default: otimista vira WACC=0.05-0.015=0.035, g=0.03+0.01=0.04 -> WACC <= g
    with pytest.raises(WaccInvalidoError):
        gerar_cenarios(**dados)


# ─── gerar_matriz_sensibilidade(): valores calculados à mão ─────────────────

def test_matriz_dimensoes_e_eixos():
    resultado = gerar_matriz_sensibilidade(
        "wacc", "g_perpetuo", **DADOS_BASE, passo_x=0.02, passo_y=0.01, pontos=1
    )
    assert resultado["eixo_x"] == [0.10, 0.12, 0.14]
    assert resultado["eixo_y"] == [0.02, 0.03, 0.04]
    assert len(resultado["matriz"]) == 3
    assert all(len(linha) == 3 for linha in resultado["matriz"])


def test_matriz_celula_central_bate_com_cenario_base():
    """A célula central da matriz (delta 0 nos dois eixos) tem que ser
    idêntica ao valor_intrinseco calculado direto por calcular_dcf()."""
    resultado = gerar_matriz_sensibilidade(
        "wacc", "g_perpetuo", **DADOS_BASE, passo_x=0.02, passo_y=0.01, pontos=1
    )
    celula_central = resultado["matriz"][1][1]  # eixo_y[1]=0.03 (base), eixo_x[1]=0.12 (base)
    esperado = calcular_dcf(
        fluxo_caixa_atual=DADOS_BASE["fluxo_caixa_atual"],
        taxa_crescimento=DADOS_BASE["taxa_crescimento"],
        taxa_desconto=0.12,
        anos_projecao=DADOS_BASE["anos_projecao"],
        taxa_crescimento_perpetuidade=0.03,
        num_acoes=DADOS_BASE["num_acoes"],
        preco_atual=DADOS_BASE["preco_atual"],
    )["valor_intrinseco"]
    assert celula_central == esperado


def test_matriz_valor_calculado_a_mao():
    """Célula canto inferior-direito (WACC=0.14, g=0.02) calculada à mão via
    o mesmo Gordon Growth de 1 ano de projeção, pra validar a fórmula ponta
    a ponta (não só que 'bate com a própria função')."""
    dados = dict(
        fluxo_caixa_atual=100.0,
        taxa_crescimento=0.0,  # sem crescimento explícito, simplifica a conta manual
        taxa_desconto=0.10,
        anos_projecao=1,
        taxa_crescimento_perpetuidade=0.03,
        num_acoes=100.0,
        preco_atual=1.0,
        margem_ebitda_atual=0.20,
    )
    resultado = gerar_matriz_sensibilidade("wacc", "g_perpetuo", **dados, passo_x=0.02, passo_y=0.0, pontos=1)
    wacc_cenario = 0.12  # base 0.10 + passo 0.02
    g_cenario = 0.03      # passo_y=0, todas as linhas usam o g base

    # Cálculo manual: fluxo ano 1 = 100 (sem crescimento explícito),
    # VP do fluxo = 100 / 1.12; terminal = 100*(1.03) / (0.12-0.03); VP terminal = terminal / 1.12
    vp_fluxo = 100.0 / (1 + wacc_cenario)
    valor_terminal = (100.0 * (1 + g_cenario)) / (wacc_cenario - g_cenario)
    vp_terminal = valor_terminal / (1 + wacc_cenario)
    valor_esperado = round((vp_fluxo + vp_terminal) / 100.0, 2)  # dividido por num_acoes

    celula = resultado["matriz"][1][2]  # eixo_y=[0.03,0.03,0.03] (passo 0), eixo_x=[0.08,0.10,0.12]
    assert celula == pytest.approx(valor_esperado, abs=0.01)


def test_matriz_celula_com_wacc_menor_ou_igual_a_g_vira_none():
    """Bordas da matriz que caem em WACC<=g não podem levantar exceção pro
    heatmap inteiro — viram None, marcando a célula como fora do domínio."""
    dados = dict(DADOS_BASE)
    dados["taxa_desconto"] = 0.04
    dados["taxa_crescimento_perpetuidade"] = 0.03
    # passo_x=0.02, pontos=2 -> eixo_x = [0.00, 0.02, 0.04, 0.06, 0.08] -> as duas primeiras <= 0.03 (g)
    resultado = gerar_matriz_sensibilidade("wacc", "crescimento_receita", **dados, passo_x=0.02, passo_y=0.03, pontos=2)
    primeira_coluna = [linha[0] for linha in resultado["matriz"]]
    assert all(v is None for v in primeira_coluna)
    # células com WACC alto o suficiente continuam calculáveis (não-None)
    ultima_coluna = [linha[-1] for linha in resultado["matriz"]]
    assert all(v is not None for v in ultima_coluna)


def test_matriz_variavel_invalida_levanta_value_error():
    with pytest.raises(ValueError):
        gerar_matriz_sensibilidade("wacc", "inexistente", **DADOS_BASE)


def test_matriz_mesma_variavel_nos_dois_eixos_levanta_value_error():
    with pytest.raises(ValueError):
        gerar_matriz_sensibilidade("wacc", "wacc", **DADOS_BASE)


# ─── gerar_matrizes_padrao(): as 3 combinações pedidas ──────────────────────

def test_gerar_matrizes_padrao_retorna_as_tres_combinacoes():
    resultado = gerar_matrizes_padrao(**DADOS_BASE)
    assert set(resultado.keys()) == {
        "wacc_x_g_perpetuo",
        "wacc_x_margem_ebitda",
        "margem_ebitda_x_crescimento_receita",
    }
    assert resultado["wacc_x_g_perpetuo"]["variavel_x"] == "wacc"
    assert resultado["wacc_x_g_perpetuo"]["variavel_y"] == "g_perpetuo"
    assert resultado["wacc_x_margem_ebitda"]["variavel_y"] == "margem_ebitda"
    assert resultado["margem_ebitda_x_crescimento_receita"]["variavel_x"] == "margem_ebitda"


# ─── gerar_analise_completa(): endpoint-level ────────────────────────────────

def test_gerar_analise_completa_combina_cenarios_e_matrizes():
    resultado = gerar_analise_completa(**DADOS_BASE)
    assert "cenarios" in resultado
    assert "faixa" in resultado
    assert "matrizes_sensibilidade" in resultado
    assert set(resultado["matrizes_sensibilidade"].keys()) == {
        "wacc_x_g_perpetuo",
        "wacc_x_margem_ebitda",
        "margem_ebitda_x_crescimento_receita",
    }


def test_gerar_analise_completa_propaga_erro_wacc_invalido():
    dados = dict(DADOS_BASE)
    dados["taxa_crescimento_perpetuidade"] = dados["taxa_desconto"] + 0.05
    with pytest.raises(WaccInvalidoError):
        gerar_analise_completa(**dados)
