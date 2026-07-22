"""
atualizar_cvm.py
Baixa dados trimestrais da CVM usando curl (contorna bloqueio de User-Agent)
e extrai apenas os CSVs necessários para o Valuation Tracker.

Uso:
    cd backend
    python3 scripts/atualizar_cvm.py

Rodar 1x por trimestre ou quando quiser atualizar.
"""

import io
import os
import sys
import time
import zipfile
import subprocess
import pandas as pd
from pathlib import Path
from datetime import datetime

# ─── configuração ─────────────────────────────────────────────────────────────

DADOS_DIR = Path(__file__).parent.parent / "dados_cvm"
DADOS_DIR.mkdir(exist_ok=True)

ANO_ATUAL = datetime.now().year
ANOS = [ANO_ATUAL - 2, ANO_ATUAL - 1, ANO_ATUAL]

URL_CADASTRO = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"

# CSVs que queremos extrair de cada ZIP. BPA_con (Ativo) adicionado pra
# viabilizar o Valor de Liquidação (haircuts por classe de ativo — caixa,
# contas a receber, estoques, imobilizado, intangível) — antes só o BPP
# (Passivo+PL) era extraído, apesar do ZIP da CVM já conter o BPA_con
# (só não estava sendo lido). Ver CONTEXT.md.
CSVS_NECESSARIOS = {
    "DRE_con": "dre",
    "DFC_MI_con": "dfc",
    "BPP_con": "bpp",
    "BPA_con": "bpa",
}

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ─── helpers ──────────────────────────────────────────────────────────────────

def curl_download(url: str, destino: Path) -> bool:
    """Baixa um arquivo via curl. Retorna True se sucesso."""
    print(f"  Baixando {destino.name}...", end=" ", flush=True)
    try:
        result = subprocess.run(
            ["curl", "-L", "-s", "-o", str(destino),
             "-H", f"User-Agent: {USER_AGENT}",
             "--max-time", "120",
             "--write-out", "%{http_code}",
             url],
            capture_output=True, text=True, timeout=130
        )
        http_code = result.stdout.strip()
        if http_code == "200" and destino.exists() and destino.stat().st_size > 1000:
            size_kb = destino.stat().st_size / 1024
            print(f"OK ({size_kb:.0f} KB)")
            return True
        else:
            print(f"falhou (HTTP {http_code})")
            if destino.exists():
                destino.unlink()
            return False
    except Exception as e:
        print(f"ERRO: {e}")
        return False


def extrair_csvs_do_zip(zip_path: Path, tipo: str, ano: int) -> int:
    """
    Extrai os CSVs necessários do ZIP e salva em dados_cvm/.
    Retorna número de arquivos extraídos.
    """
    extraidos = 0
    try:
        with zipfile.ZipFile(zip_path) as z:
            for sufixo_csv, chave in CSVS_NECESSARIOS.items():
                # nome esperado dentro do zip
                nome_csv = f"{tipo}_cia_aberta_{sufixo_csv}_{ano}.csv"
                if nome_csv not in z.namelist():
                    continue
                destino = DADOS_DIR / f"{tipo}_{chave}_{ano}.csv"
                with z.open(nome_csv) as f_in:
                    df = pd.read_csv(f_in, sep=";", encoding="latin-1", dtype=str)
                    df.to_csv(destino, sep=";", index=False, encoding="utf-8")
                    print(f"  Extraído: {destino.name} ({len(df):,} linhas)")
                    extraidos += 1
    except Exception as e:
        print(f"  Erro ao extrair {zip_path.name}: {e}")
    return extraidos


def arquivo_recente(path: Path, dias: int = 7) -> bool:
    if not path.exists():
        return False
    idade_dias = (time.time() - path.stat().st_mtime) / 86400
    return idade_dias < dias

# ─── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Atualizador de dados CVM — Valuation Tracker")
    print(f"Destino: {DADOS_DIR}")
    print(f"Anos: {ANOS}")
    print("=" * 60)

    # 1. Cadastro
    print("\n[1/2] Cadastro de empresas abertas")
    cad_path = DADOS_DIR / "cad_cia_aberta.csv"
    if arquivo_recente(cad_path, dias=1):
        print(f"  Já atualizado hoje, pulando.")
    else:
        tmp = DADOS_DIR / "_cad_tmp.csv"
        if curl_download(URL_CADASTRO, tmp):
            df = pd.read_csv(tmp, sep=";", encoding="latin-1", dtype=str)
            df = df[df["SIT"] == "ATIVO"].copy()
            df.to_csv(cad_path, sep=";", index=False, encoding="utf-8")
            tmp.unlink()
            print(f"  Salvo: {cad_path.name} ({len(df):,} empresas ativas)")

    # 2. Demonstrações financeiras
    print("\n[2/2] Demonstrações financeiras")
    baixados = 0
    pulados = 0

    for ano in ANOS:
        print(f"\n  Ano {ano}:")
        for tipo in ["itr", "dfp"]:
            url = f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{tipo.upper()}/DADOS/{tipo}_cia_aberta_{ano}.zip"
            zip_path = DADOS_DIR / f"_{tipo}_{ano}.zip"

            # Verifica se TODOS os CSVs esperados deste ano já existem e
            # estão recentes — checar por chave exata (não um glob genérico
            # "{tipo}_*_{ano}.csv"), senão adicionar um novo tipo em
            # CSVS_NECESSARIOS (ex: BPA_con) nunca dispararia um novo
            # download pra anos que já tinham DRE/DFC/BPP extraídos
            # (o glob batia neles e "pulava" mesmo faltando o BPA).
            csvs_esperados = [DADOS_DIR / f"{tipo}_{chave}_{ano}.csv" for chave in CSVS_NECESSARIOS.values()]
            if all(arquivo_recente(f, dias=7) for f in csvs_esperados):
                print(f"  {tipo.upper()} {ano}: já extraído ({len(csvs_esperados)} arquivos), pulando")
                pulados += len(csvs_esperados)
                continue

            if curl_download(url, zip_path):
                n = extrair_csvs_do_zip(zip_path, tipo, ano)
                baixados += n
                zip_path.unlink()  # remove ZIP após extração
            else:
                if zip_path.exists():
                    zip_path.unlink()

    print("\n" + "=" * 60)
    print(f"Concluído: {baixados} CSVs extraídos, {pulados} já atualizados")

    if baixados > 0:
        data_hoje = datetime.now().strftime("%Y-%m-%d")
        print(f"\nPróximo passo:")
        print(f"  git add backend/dados_cvm/")
        print(f"  git commit -m 'data: atualiza dados CVM {data_hoje}'")
        print(f"  git push")


if __name__ == "__main__":
    main()