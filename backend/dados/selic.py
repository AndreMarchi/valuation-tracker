import httpx
import time

_cache_selic = {"valor": None, "timestamp": 0}
CACHE_SELIC_SEGUNDOS = 86400  # 24 horas


def buscar_selic_atual() -> float:
    """
    Busca a taxa Selic atual via API do Banco Central.
    Cache de 24 horas — a Selic não muda com frequência.

    Returns:
        Taxa Selic anual em decimal (ex: 0.1475 para 14.75%)
    """

    # Retorna do cache se ainda válido
    if (_cache_selic["valor"] is not None and
            time.time() - _cache_selic["timestamp"] < CACHE_SELIC_SEGUNDOS):
        print(f"Selic cache: {_cache_selic['valor'] * 100:.2f}%")
        return _cache_selic["valor"]

    try:
        # API do BACEN — série 432 = Taxa Selic acumulada no mês anualizada
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        dados = response.json()

        # Retorna em percentual ao ano — ex: "14.75"
        selic_pct = float(dados[0]["valor"].replace(",", "."))
        selic_decimal = selic_pct / 100

        # Salva no cache
        _cache_selic["valor"]     = selic_decimal
        _cache_selic["timestamp"] = time.time()

        print(f"Selic atualizada via BACEN: {selic_pct}%")
        return selic_decimal

    except Exception as e:
        print(f"Erro ao buscar Selic do BACEN: {e} — usando valor padrão")
        return 0.145  # fallback