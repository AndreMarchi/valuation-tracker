"""
test_setor_bancario_wiring.py
Teste de regressão pro mismatch de string de setor especificamente pro
setor financeiro/bancário — mesma família de bug já corrigida 3x nesta
investigação (Alimentos/Alimentos Processados, Comércio/Varejo, typo de
Siderurgia), ver test_normalizacao_setor.py.

Diferente daquele arquivo (que não depende de rede, cobre só os mapeamentos
já confirmados em dados/normalizacao_setor.py), este teste chama
buscar_dados() de verdade contra tickers reais de banco — de propósito: um
teste unitário isolado de cada função com valor mockado é exatamente o que
NÃO pegou os outros 3 bugs de string anteriores, porque cada um mockava o
setor "certo" sem confirmar que era o que os providers realmente retornam.

Achado real (rodando buscar_dados() contra ITUB4/BBAS3/BBDC4/SANB11): o
setor retornado é "Intermediários Financeiros" — não "Bancos" (esse é o
valor de dados["industria"]/subsetor). Confirmado batendo em 3 dos 4 pontos
que dão tratamento especial ao setor financeiro:

  - valuation/setor.py::CONFIGURACAO_SETORES — bate (tem as duas chaves,
    além de usar correspondência por substring)
  - valuation/nopat.py::FATOR_CONVERSAO_NOPAT — bate (só tem
    "Intermediários Financeiros", que é exatamente o que buscar_dados()
    retorna — a hipótese de que faltaria essa chave não se confirmou)
  - valuation/risco.py::SETORES_REGULADOS — NÃO batia (só tinha "Bancos"),
    bug real corrigido nesta sessão: bancos não-estatais (ITUB4, BBDC4)
    nunca recebiam a penalização de risco regulatório de 1.0 ponto que o
    set já pretendia aplicar
  - valuation/capm.py::BETA_POR_SETOR — não é um bug de string porque o
    dict nem chega a ser consultado: calcular_capm() recebe beta_ativo já
    calculado (dados.get("beta")) e nunca faz lookup por setor. O dict
    tem as duas chaves mesmo assim (defensivo, caso alguém o wire no
    futuro), mas hoje é código morto pra esse propósito — documentado
    aqui pra não ser reintroduzido como um "bug" que na prática não afeta
    nada em produção.

ATUALIZAÇÃO (investigação seguinte): EV/EBITDA foi deliberadamente
adicionado a metodos_invalidos pra banco/seguradora (mesma razão
metodológica de Graham/DCF — Enterprise Value pressupõe separar dívida
financeira de operação, o que não existe pra esse tipo de negócio) — ver
CONTEXT.md. O teste abaixo foi atualizado pra refletir isso.

Requer rede (Fundamentus/CVM) — mesma limitação de qualquer chamada real a
buscar_dados() no projeto.
"""

import pytest

from dados.provider import buscar_dados
from valuation.setor import CONFIGURACAO_SETORES, aplicar_restricoes_setor
from valuation.nopat import calcular_fcl_via_nopat
from valuation.risco import SETORES_REGULADOS, analisar_risco
from valuation.capm import BETA_POR_SETOR

TICKERS_BANCOS = ["ITUB4", "BBAS3", "BBDC4", "SANB11"]


@pytest.fixture(scope="module")
def setores_reais():
    """Um buscar_dados() real por ticker, reaproveitado entre os testes do
    módulo — evita bater na rede repetidas vezes pro mesmo dado."""
    resultado = {}
    for ticker in TICKERS_BANCOS:
        try:
            dados = buscar_dados(ticker)
        except Exception as e:
            pytest.skip(f"buscar_dados({ticker}) falhou (provavelmente rede/rate limit): {e}")
        resultado[ticker] = dados.get("setor")
    return resultado


class TestSetorBancarioBateNosPontosRelevantes:

    def test_setor_real_e_intermediarios_financeiros_nao_bancos(self, setores_reais):
        # Confirma a premissa da investigação: o valor de dados["setor"]
        # pra banco é "Intermediários Financeiros", não "Bancos" — esse é
        # o valor de industria/subsetor, um campo diferente.
        for ticker, setor in setores_reais.items():
            assert setor == "Intermediários Financeiros", (
                f"{ticker}: setor mudou pra {setor!r} — se isso for uma mudança "
                "real do provedor, os 4 pontos abaixo (setor.py/nopat.py/"
                "risco.py/capm.py) precisam ser revisados de novo."
            )

    def test_setor_py_bate(self, setores_reais):
        for ticker, setor in setores_reais.items():
            assert setor in CONFIGURACAO_SETORES, f"{ticker}: {setor!r} não bate em CONFIGURACAO_SETORES"

    def test_setor_py_desabilita_graham_dcf_e_ev_ebitda(self, setores_reais):
        # EV/EBITDA passou a ser desabilitado pra banco (mesma família de
        # Graham/DCF) — decisão tomada e implementada numa investigação
        # posterior à que criou este teste, ver CONTEXT.md.
        for ticker, setor in setores_reais.items():
            graham, bazin, multiplos, dcf, ev_ebitda, config = aplicar_restricoes_setor(
                setor=setor,
                graham={"classificacao": "Descontada"},
                bazin={"classificacao": "Descontada"},
                multiplos={"pl": {"classificacao": "Descontada"}, "pvp": {"classificacao": "Descontada"}},
                dcf={"classificacao": "Descontada", "valor_intrinseco": 99.0},
                ev_ebitda={"classificacao": "Descontada", "preco_justo": 42.0},
                ticker=ticker,
            )
            assert dcf["classificacao"] == "Não aplicável"
            assert dcf["valor_intrinseco"] is None
            assert ev_ebitda["classificacao"] == "Não aplicável"
            assert ev_ebitda["preco_justo"] is None
            assert "graham" in config["metodos_invalidos"]
            assert "dcf" in config["metodos_invalidos"]
            assert "ev_ebitda" in config["metodos_invalidos"]

    def test_nopat_py_zera_fluxo_de_caixa_pra_banco(self, setores_reais):
        for ticker, setor in setores_reais.items():
            fcl = calcular_fcl_via_nopat({"ebit_12m": 1_000_000_000, "setor": setor})
            assert fcl == 0.0, f"{ticker}: fator de conversão do NOPAT não zerou pro setor {setor!r}"

    def test_risco_py_marca_como_regulado(self, setores_reais):
        # Regressão do bug real: SETORES_REGULADOS só tinha "Bancos", nunca
        # batia com "Intermediários Financeiros" (o setor real).
        for ticker, setor in setores_reais.items():
            assert setor in SETORES_REGULADOS, f"{ticker}: {setor!r} não bate em SETORES_REGULADOS"
            resultado = analisar_risco(ticker, setor, score_atual=7.0)
            assert resultado["is_regulado"] is True

    def test_risco_py_penaliza_banco_nao_estatal(self, setores_reais):
        # ITUB4/BBDC4 não são estatais — a penalização regulatória de 1.0
        # ponto precisa aparecer nos dois (BBAS3/SANB11 já são penalizados
        # como estatais, então o alerta "regulatorio" não duplica pra eles,
        # ver valuation/risco.py::analisar_risco()).
        for ticker in ("ITUB4", "BBDC4"):
            setor = setores_reais[ticker]
            resultado = analisar_risco(ticker, setor, score_atual=7.0)
            assert "regulatorio" in [a["tipo"] for a in resultado["alertas"]]
            assert resultado["penalizacao"] >= 1.0

    def test_capm_py_beta_por_setor_e_codigo_morto_documentado(self, setores_reais):
        # Não é um bug de string: calcular_capm() usa beta_ativo (vindo de
        # dados.get("beta"), o beta real do ticker), nunca consulta
        # BETA_POR_SETOR por setor. O dict tem as chaves certas mesmo assim
        # (defensivo), mas documentamos aqui que hoje ele não é lido em
        # nenhum lugar de produção — se isso mudar (alguém decidir usar
        # BETA_POR_SETOR de verdade), este teste precisa ser revisado.
        import ast
        from pathlib import Path

        capm_py = Path(__file__).parent.parent / "valuation" / "capm.py"
        arvore = ast.parse(capm_py.read_text(encoding="utf-8"), filename=str(capm_py))
        nomes_usados_na_funcao = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.FunctionDef) and no.name == "calcular_capm":
                nomes_usados_na_funcao = {n.id for n in ast.walk(no) if isinstance(n, ast.Name)}
        assert "BETA_POR_SETOR" not in nomes_usados_na_funcao, (
            "BETA_POR_SETOR passou a ser usado dentro de calcular_capm() — "
            "se isso é intencional, revise se a correspondência é exata ou "
            "por substring, e se o setor real ('Intermediários Financeiros') "
            "bate corretamente antes de confiar nesse teste."
        )
        for ticker, setor in setores_reais.items():
            assert setor in BETA_POR_SETOR


class TestMatrizDeConsensoParaBancos:
    """Achado real (investigação de EV/EBITDA pra bancos): desabilitar
    EV/EBITDA além de Graham/DCF deixa 2 dos 3 pilares da Matriz de
    Consenso (main.py) como "Não aplicável" pra banco — cenário nunca
    testado antes (só DCF ficava nulo). Ao investigar, achamos um SEGUNDO
    bug pré-existente e não relacionado: calcular_multiplos() nunca
    retornava uma chave "classificacao" agregada, então o pilar
    "patrimonial_multiplos" já estava sempre "Não aplicável" pra QUALQUER
    ticker — corrigido junto (ver valuation/multiplos.py e CONTEXT.md)."""

    def test_endpoint_real_ev_ebitda_nao_aplicavel_e_multiplos_ativo(self):
        import asyncio
        from main import valuation

        for ticker in ("ITUB4", "BBAS3"):
            try:
                r = asyncio.run(valuation(ticker))
            except Exception as e:
                pytest.skip(f"valuation({ticker}) falhou (provavelmente rede/rate limit): {e}")

            assert r["dcf"]["classificacao"] == "Não aplicável"
            assert r["ev_ebitda"]["classificacao"] == "Não aplicável"
            # patrimonial_multiplos continua ativo — P/L e P/VP não são
            # restritos pra banco, e a classificação agregada existe agora
            assert r["multiplos"]["classificacao"] in ("Descontada", "Neutra", "Cara")

            consenso = r["consenso"]
            assert consenso["pilares_status"]["operacional_ebitda"] == "Não aplicável"
            assert consenso["pilares_status"]["fluxo_de_caixa"] == "Não aplicável"
            assert consenso["pilares_status"]["patrimonial_multiplos"] != "Não aplicável"
            # "X/1", não "X/3" (só 1 pilar é de fato aplicável) nem "0/0"
            # (que aconteceria se o bug do multiplos.classificacao não
            # tivesse sido corrigido junto)
            assert consenso["grau_concordancia"].endswith("/1 pilares descontados"), (
                f"{ticker}: grau_concordancia={consenso['grau_concordancia']!r} — "
                "esperado 'X/1 pilares descontados'"
            )

    def test_score_nao_quebra_e_nao_fica_nao_aplicavel(self):
        # Trava de segurança: mesmo com 2/3 pilares nulos, calcular_score()
        # ainda tem P/L, P/VP e Bazin válidos pra banco — não deve cair no
        # fallback "Não foi possível aplicar nenhum método válido".
        import asyncio
        from main import valuation

        for ticker in ("ITUB4", "BBAS3"):
            try:
                r = asyncio.run(valuation(ticker))
            except Exception as e:
                pytest.skip(f"valuation({ticker}) falhou (provavelmente rede/rate limit): {e}")

            assert r["score"]["classificacao"] != "Não aplicável"
            assert r["score"]["metodos_aplicados"] >= 1


class TestEndividamentoNaoAplicavelParaBancos:
    """Achado real (investigação seguinte): analisar_endividamento() recebia
    ebit_12m=0 pra banco (EBIT operacional não é conceito limpo pra esse
    tipo de negócio, mesma razão de Graham/DCF/EV-EBITDA) e caía no ramo
    "else: div_ebit=0" — mostrava "0,0x · sem alertas" como se fosse
    ausência real de dívida, quando na verdade a métrica não se aplica.
    Corrigido em setor.py (CONFIGURACAO_SETORES) + main.py/trabalhador.py
    (pula analisar_endividamento() pro grupo financeiro, preservando o
    score de entrada intacto). Ver CONTEXT.md.

    Também confirma o achado de que endividamento.score_ajustado é
    puramente informativo no endpoint principal — nunca compõe o "Score de
    Atratividade" (dados_finais["score"], vindo de calcular_score(),
    computado ANTES de analisar_endividamento() e nunca atualizado depois)."""

    def test_endividamento_nao_aplicavel_e_score_final_preservado(self):
        import asyncio
        from main import valuation

        for ticker in ("ITUB4", "BBAS3"):
            try:
                r = asyncio.run(valuation(ticker))
            except Exception as e:
                pytest.skip(f"valuation({ticker}) falhou (provavelmente rede/rate limit): {e}")

            e = r["endividamento"]
            assert e["classificacao"] == "Não aplicável"
            assert e["div_liquida_ebit"] is None
            assert e["div_liquida_patrim"] is None
            assert e["alertas"] == []
            assert e["penalizacao"] == 0.0
            assert e["erro"]
            # o ponto crítico: score_ajustado sai EXATAMENTE igual ao score
            # de entrada — nem crédito por "sem alerta", nem penalização
            assert e["score_ajustado"] == r["score"]["score"]

    def test_tickers_nao_financeiros_continuam_com_endividamento_real(self):
        # Guarda de regressão: essa é uma correção cirúrgica, só pro grupo
        # financeiro — confirma que BEEF3/WEGE3 continuam recebendo a
        # métrica de verdade, calculada por analisar_endividamento().
        import asyncio
        from main import valuation

        for ticker in ("BEEF3", "WEGE3"):
            try:
                r = asyncio.run(valuation(ticker))
            except Exception as e:
                pytest.skip(f"valuation({ticker}) falhou (provavelmente rede/rate limit): {e}")

            e = r["endividamento"]
            assert e["classificacao"] != "Não aplicável"
            assert e["div_liquida_ebit"] is not None
            assert e["div_liquida_patrim"] is not None
