"""
test_dcf_wiring.py
Teste de paridade (mesmo padrão AST das tarefas anteriores — test_capm_wiring.py,
test_concessao_wiring.py) confirmando que os DOIS call sites de calcular_dcf()
passam `divida_liquida`, pra não repetir o padrão já visto duas vezes nesta
investigação: uma correção feita só em main.py e esquecida em
scanner/trabalhador.py (bug do CAPM size premium) ou vice-versa (spread
cambial do Kd, implementado só em main.py por decisão explícita — mas aqui
o pedido é que os DOIS sejam corrigidos, então o teste cobre os dois).

Ver CONTEXT.md: calcular_dcf() entregava Enterprise Value por ação (nunca
subtraía a dívida líquida), sendo comparado com preço de mercado (equity)
como se fosse "valor intrínseco" — bug estrutural corrigido com o novo
parâmetro `divida_liquida`.
"""

import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent

ARQUIVOS_COM_CALL_SITES = [
    BACKEND_DIR / "main.py",
    BACKEND_DIR / "scanner" / "trabalhador.py",
]


def _encontrar_chamadas_calcular_dcf(caminho: Path) -> list:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    chamadas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "calcular_dcf":
            chamadas.append(no)
    return chamadas


def _passa_divida_liquida(chamada: ast.Call) -> bool:
    # calcular_dcf(fluxo_caixa_atual, taxa_crescimento, taxa_desconto,
    # anos_projecao, taxa_crescimento_perpetuidade, num_acoes, preco_atual,
    # divida_liquida) -> índice posicional 7 (0-indexed), mas os dois call
    # sites conhecidos sempre passam tudo por keyword — checa as duas formas.
    if any(kw.arg == "divida_liquida" for kw in chamada.keywords):
        return True
    return len(chamada.args) > 7


class TestCalcularDcfSempreRecebeDividaLiquida:

    def test_arquivos_de_producao_tem_pelo_menos_uma_chamada(self):
        total = 0
        for caminho in ARQUIVOS_COM_CALL_SITES:
            assert caminho.exists(), f"Arquivo esperado não encontrado: {caminho}"
            total += len(_encontrar_chamadas_calcular_dcf(caminho))
        assert total > 0, "Nenhuma chamada a calcular_dcf() encontrada nos arquivos de produção — teste não protege nada."

    def test_todas_as_chamadas_de_producao_passam_divida_liquida(self):
        falhas = []
        for caminho in ARQUIVOS_COM_CALL_SITES:
            for chamada in _encontrar_chamadas_calcular_dcf(caminho):
                if not _passa_divida_liquida(chamada):
                    falhas.append(f"{caminho.relative_to(BACKEND_DIR)}:{chamada.lineno}")

        assert not falhas, (
            "calcular_dcf() chamada sem 'divida_liquida' em: " + ", ".join(falhas) + " — "
            "sem esse argumento, o DCF entrega Enterprise Value por ação (não subtrai a "
            "dívida), inflando o valor justo proporcionalmente à alavancagem de cada empresa."
        )
