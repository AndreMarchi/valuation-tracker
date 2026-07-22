"""
test_capm_wiring.py
Teste de regressão pro bug de "wiring": calcular_capm() tem um parâmetro
opcional `valor_mercado` (Size Premium Dinâmico — CAPM/WACC/DCF ficam
incorretos pra TODA ação se ele não for passado, caindo sempre no fallback
fixo de 1.5%, mesmo pra small/micro caps que deveriam ter até 3.5%) — mas os
call sites de produção (main.py, scanner/trabalhador.py) esqueciam de
repassar esse dado, que já vem pronto em buscar_dados()["valor_mercado"].

Diferente de test_capm.py (que testa calcular_capm() isolada, sempre
passando valor_mercado manualmente nos casos de teste — nunca vê esse tipo
de bug), este teste analisa o CÓDIGO-FONTE via `ast` — não regex, não
importação/execução — dos módulos que chamam calcular_capm() em produção, e
falha se algum call site não passar `valor_mercado` (nem como keyword nem
na posição correspondente). Pega esse bug de novo se alguém remover o
argumento no futuro, em qualquer um dos dois call sites (ou um novo que
venha a existir).
"""

import ast
import inspect
from pathlib import Path

from valuation.capm import calcular_capm

BACKEND_DIR = Path(__file__).parent.parent

# Módulos com call sites de produção de calcular_capm() — se um novo
# consumidor for criado, adicione o caminho aqui também.
ARQUIVOS_COM_CALL_SITES = [
    BACKEND_DIR / "main.py",
    BACKEND_DIR / "scanner" / "trabalhador.py",
]


def _indice_posicional(nome_parametro: str) -> int:
    """Posição (0-indexed) de `nome_parametro` na assinatura real de
    calcular_capm() — usa inspect em vez de um índice hardcoded, pra o
    teste continuar correto se a assinatura ganhar/perder parâmetros antes
    dele."""
    parametros = list(inspect.signature(calcular_capm).parameters)
    assert nome_parametro in parametros, (
        f"'{nome_parametro}' não existe mais em calcular_capm() — "
        "atualize este teste (ou o bug que ele protege já não existe)."
    )
    return parametros.index(nome_parametro)


def _encontrar_chamadas_calcular_capm(caminho: Path) -> list:
    """Retorna os nós ast.Call de todas as chamadas a `calcular_capm(...)`
    (chamada direta, ex: `from valuation.capm import calcular_capm`) num
    arquivo-fonte."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    chamadas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "calcular_capm":
            chamadas.append(no)
    return chamadas


def _passa_argumento(chamada: ast.Call, nome: str, indice_posicional: int) -> bool:
    passou_por_keyword = any(kw.arg == nome for kw in chamada.keywords)
    passou_por_posicao = len(chamada.args) > indice_posicional
    return passou_por_keyword or passou_por_posicao


class TestCalcularCapmSempreRecebeValorMercado:

    def test_arquivos_de_producao_existem_e_tem_pelo_menos_uma_chamada(self):
        # Canário: se ninguém mais chamar calcular_capm() nesses arquivos
        # (refactor, remoção), o teste abaixo passaria vazio e silencioso
        # — garante que o teste está realmente checando alguma coisa.
        total_chamadas = 0
        for caminho in ARQUIVOS_COM_CALL_SITES:
            assert caminho.exists(), f"Arquivo esperado não encontrado: {caminho}"
            total_chamadas += len(_encontrar_chamadas_calcular_capm(caminho))
        assert total_chamadas > 0, (
            "Nenhuma chamada a calcular_capm() encontrada nos arquivos de produção "
            f"({[str(p) for p in ARQUIVOS_COM_CALL_SITES]}) — o teste não está protegendo nada."
        )

    def test_todas_as_chamadas_de_producao_passam_valor_mercado(self):
        indice = _indice_posicional("valor_mercado")
        falhas = []

        for caminho in ARQUIVOS_COM_CALL_SITES:
            for chamada in _encontrar_chamadas_calcular_capm(caminho):
                if not _passa_argumento(chamada, "valor_mercado", indice):
                    falhas.append(f"{caminho.relative_to(BACKEND_DIR)}:{chamada.lineno}")

        assert not falhas, (
            "calcular_capm() chamada sem 'valor_mercado' em: " + ", ".join(falhas) + " — "
            "sem esse argumento, o Size Premium Dinâmico do CAPM cai sempre no fallback "
            "fixo de 1.5% (ver valuation/capm.py), distorcendo a taxa de desconto do "
            "DCF/WACC pra toda ação, mais visível em small/micro caps."
        )


# ─── beta_ativo passa por resolver_beta(), não por dados.get("beta", 1.0) ──
# Achado real (investigação seguinte): BETA_POR_SETOR estava calibrado mas
# nunca era consultado — os dois call sites usavam dados.get("beta", 1.0)
# direto, um fallback fixo indistinguível de "beta real é 1.0". Corrigido
# com resolver_beta(beta_bruto, setor) em valuation/capm.py, usado nos dois
# call sites — mesmo padrão de teste de paridade AST já usado nesta suíte
# (test_dcf_wiring.py, test_endividamento_wiring.py etc), pra não repetir o
# erro de corrigir um call site e esquecer o outro.

class TestBetaAtivoUsaResolverBeta:

    def test_nenhuma_chamada_usa_dados_get_beta_direto(self):
        # Regressão específica: dados.get("beta", 1.0) ou dados.get("beta")
        # passado direto pra beta_ativo reintroduziria o bug (1.0 genérico
        # em vez do fallback setorial quando o dado está genuinamente
        # ausente).
        falhas = []
        for caminho in ARQUIVOS_COM_CALL_SITES:
            for chamada in _encontrar_chamadas_calcular_capm(caminho):
                for kw in chamada.keywords:
                    if kw.arg != "beta_ativo":
                        continue
                    nomes_usados = {n.id for n in ast.walk(kw.value) if isinstance(n, ast.Name)}
                    if "resolver_beta" not in nomes_usados:
                        falhas.append(f"{caminho.relative_to(BACKEND_DIR)}:{chamada.lineno}")

        assert not falhas, (
            "calcular_capm() chamada com beta_ativo que não passa por resolver_beta() em: "
            + ", ".join(falhas) + " — sem isso, beta ausente cai num 1.0 genérico em vez do "
            "fallback setorial (BETA_POR_SETOR), e não há como diferenciar 'dado ausente' de "
            "'beta real é 1.0' (ver CONTEXT.md)."
        )
