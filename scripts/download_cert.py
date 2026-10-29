#!/usr/bin/env python3
"""Baixa e extrai o CERT Insider Threat Test Dataset (release r4.2) do KiltHub/CMU.

Este script obtem os dados reais sobre os quais os exercicios do laboratorio
rodam. Ele:

- exibe a referencia da fonte primaria e os termos de uso antes de baixar;
- baixa o dataset r4.2 (~4,8 GB) e o gabarito oficial (answers) para data/;
- confere a integridade (MD5) de cada arquivo;
- com --extract, descompacta para data/r4.2/ e data/answers/.

Usa apenas a biblioteca padrao para o download (urllib). A extracao usa o `tar`
do sistema (lida com arquivos .tar.bz2 multi-stream, ao contrario do modulo
tarfile da stdlib).

Uso:
    python scripts/download_cert.py --dry-run     # so mostra fonte/termos/destino
    python scripts/download_cert.py               # baixa r4.2 + answers
    python scripts/download_cert.py --extract      # baixa (se preciso) e extrai
    python scripts/download_cert.py --help
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

KILTHUB_ARTICLE_URL = (
    "https://kilthub.cmu.edu/articles/dataset/Insider_Threat_Test_Dataset/12841247"
)
KILTHUB_DOI = "https://doi.org/10.1184/R1/12841247"

# Arquivos oficiais no figshare (resolvidos da API do artigo 12841247).
ARQUIVOS = {
    "r4.2.tar.bz2": {
        "url": "https://ndownloader.figshare.com/files/24856766",
        "md5": "cf64caa378acb77cd0c608a5576d998c",
        "size_gb": 4.8,
    },
    "answers.tar.bz2": {
        "url": "https://ndownloader.figshare.com/files/24857828",
        "md5": "c0c96eaa06915e417504f932756f58d8",
        "size_gb": 0.001,
    },
}

_USER_AGENT = "threat-hunting-lab/1.0 (+https://github.com/nilsonsangy/threat-hunting)"
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA = _REPO_ROOT / "data"
_CHUNK = 1024 * 1024


def _print_referencia_e_termos(destino: Path) -> None:
    print("=" * 72)
    print("CERT Insider Threat Test Dataset — release r4.2")
    print("=" * 72)
    print()
    print("FONTE / REFERENCIA (cite ao usar os dados):")
    print("  Lindauer, B. (2020). Insider Threat Test Dataset. Carnegie Mellon")
    print("  University (CERT Division). DOI 10.1184/R1/12841247.")
    print(f"  {KILTHUB_ARTICLE_URL}")
    print("  Glasser, J.; Lindauer, B. (2013). Bridging the Gap: A Pragmatic")
    print("  Approach to Generating Insider Threat Data. IEEE S&P Workshops.")
    print()
    print("TERMOS DE USO:")
    print("  - Dados sinteticos gerados pela ExactData, LLC (c) 2011 sob acordo")
    print("    com a CMU/SEI; veja a licenca inclusa no proprio dataset")
    print("    (r4.2/license.txt). Uso para pesquisa/educacao; nao redistribua os")
    print("    arquivos de teste. Credito obrigatorio a Glasser & Lindauer (2013).")
    print()
    print(f"Destino do download/extracao: {destino}")
    print("=" * 72)
    print()


def _erro(msg: str, code: int = 1) -> int:
    print(f"ERRO: {msg}", file=sys.stderr)
    return code


def _md5(caminho: Path) -> str:
    h = hashlib.md5()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(_CHUNK), b""):
            h.update(bloco)
    return h.hexdigest()


def _baixar_um(nome: str, info: dict, destino: Path) -> int:
    alvo = destino / nome
    if alvo.exists() and _md5(alvo) == info["md5"]:
        print(f"{nome}: ja presente e integro (pulando download).")
        return 0

    url = info["url"]
    parcial = alvo.with_suffix(alvo.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    print(f"Baixando {nome} (~{info['size_gb']} GB)...")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, parcial.open("wb") as out:
            total = resp.headers.get("Content-Length")
            total_int = int(total) if total and total.isdigit() else None
            baixado = 0
            while True:
                bloco = resp.read(_CHUNK)
                if not bloco:
                    break
                out.write(bloco)
                baixado += len(bloco)
                mb = baixado / (1024 * 1024)
                if total_int:
                    pct = 100.0 * baixado / total_int
                    print(f"\r  {mb:8.1f} MiB ({pct:5.1f}%)", end="", flush=True)
                else:
                    print(f"\r  {mb:8.1f} MiB", end="", flush=True)
            print()
    except urllib.error.HTTPError as exc:
        _limpar(parcial)
        return _erro(f"falha HTTP ao baixar {nome}: {exc.code} {exc.reason}.")
    except urllib.error.URLError as exc:
        _limpar(parcial)
        return _erro(f"falha de rede ao baixar {nome}: {exc.reason}.")
    except TimeoutError:
        _limpar(parcial)
        return _erro(f"tempo esgotado ao baixar {nome}.")
    except OSError as exc:
        _limpar(parcial)
        return _erro(f"falha de I/O ao gravar {parcial}: {exc}.")

    digest = _md5(parcial)
    if digest != info["md5"]:
        _limpar(parcial)
        return _erro(f"MD5 de {nome} divergente ({digest} != {info['md5']}).")
    parcial.replace(alvo)
    print(f"{nome}: OK (MD5 {digest}).")
    return 0


def _limpar(parcial: Path) -> None:
    try:
        parcial.unlink()
    except OSError:
        pass


def _extrair(nome: str, destino: Path) -> int:
    alvo = destino / nome
    if not alvo.exists():
        return _erro(f"{nome} nao encontrado em {destino}. Baixe primeiro.")
    print(f"Extraindo {nome} (pode levar varios minutos)...")
    try:
        subprocess.run(["tar", "-xjf", str(alvo)], cwd=destino, check=True)
    except FileNotFoundError:
        return _erro("comando 'tar' nao encontrado no sistema.")
    except subprocess.CalledProcessError as exc:
        return _erro(f"falha ao extrair {nome}: codigo {exc.returncode}.")
    print(f"{nome}: extraido em {destino}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="download_cert.py",
        description="Baixa e extrai o CERT Insider Threat Test Dataset (r4.2).",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="So mostra a fonte, os termos e o destino.")
    parser.add_argument("--extract", action="store_true",
                        help="Extrai os arquivos apos o download (tar do sistema).")
    args = parser.parse_args(argv)

    _DATA.mkdir(parents=True, exist_ok=True)
    _print_referencia_e_termos(_DATA)

    if args.dry_run:
        print("[--dry-run] Nenhum download realizado.")
        return 0

    for nome, info in ARQUIVOS.items():
        rc = _baixar_um(nome, info, _DATA)
        if rc != 0:
            return rc

    if args.extract:
        for nome in ARQUIVOS:
            rc = _extrair(nome, _DATA)
            if rc != 0:
                return rc
        print()
        print("Pronto. Dados em data/r4.2/ e gabarito em data/answers/.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
