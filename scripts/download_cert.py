#!/usr/bin/env python3
"""Baixa e extrai o CERT Insider Threat Test Dataset (release r4.2) do KiltHub/CMU.

Obtem os dados reais sobre os quais os exercicios rodam. O script:

- exibe a referencia da fonte e os termos de uso antes de baixar;
- baixa r4.2 (~4,8 GB) e o gabarito (answers) para data/, conferindo o MD5;
- com --extract, descompacta de forma INCREMENTAL: verifica o que ja foi extraido
  e extrai apenas os membros que faltam (ex.: so o http.csv), sem refazer o resto.

Download inteligente: se o .tar.bz2 ja existe e o MD5 confere, nao baixa de novo.
Se o tarball nao estiver presente e for preciso extrair algo que falta, o script
baixa o tarball automaticamente.

Usa a stdlib (urllib) para o download. A extracao usa o `tar` do sistema (lida
com .tar.bz2 multi-stream).

Uso:
    python scripts/download_cert.py --dry-run     # so mostra fonte/termos/destino
    python scripts/download_cert.py               # baixa r4.2 + answers (se faltarem)
    python scripts/download_cert.py --extract      # garante tudo extraido (incremental)
    python scripts/download_cert.py --extract --force-extract  # re-extrai tudo
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

# Membros esperados apos a extracao, por tarball. Cada entrada mapeia o caminho
# do membro dentro do tar -> caminho relativo verificado em data/.
# A extracao e feita por membro, extraindo so o que falta.
MEMBROS = {
    "r4.2.tar.bz2": [
        "r4.2/logon.csv",
        "r4.2/device.csv",
        "r4.2/file.csv",
        "r4.2/email.csv",
        "r4.2/http.csv",
        "r4.2/LDAP",          # diretorio (snapshots mensais)
        "r4.2/license.txt",
    ],
    "answers.tar.bz2": [
        "answers/insiders.csv",
    ],
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
    print("    com a CMU/SEI; veja a licenca inclusa no dataset (r4.2/license.txt).")
    print("    Uso para pesquisa/educacao; nao redistribua os arquivos de teste.")
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


def _membro_presente(membro: str, destino: Path) -> bool:
    """True se o membro ja foi extraido (arquivo nao-vazio ou diretorio populado)."""
    alvo = destino / membro
    if alvo.is_dir():
        return any(alvo.iterdir())
    return alvo.is_file() and alvo.stat().st_size > 0


def _faltantes(tarball: str, destino: Path) -> list[str]:
    """Lista os membros esperados daquele tarball que ainda nao foram extraidos."""
    return [m for m in MEMBROS[tarball] if not _membro_presente(m, destino)]


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
                    print(f"\r  {mb:8.1f} MiB ({100.0*baixado/total_int:5.1f}%)", end="", flush=True)
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


def _extrair_membros(tarball: str, membros: list[str], destino: Path) -> int:
    """Extrai apenas os membros indicados do tarball (tar do sistema)."""
    alvo = destino / tarball
    if not alvo.exists():
        return _erro(f"{tarball} ausente para extrair {membros}. Baixe primeiro.")
    print(f"Extraindo de {tarball}: {', '.join(membros)} (pode levar varios minutos)...")
    try:
        subprocess.run(["tar", "-xjf", str(alvo), *membros], cwd=destino, check=True)
    except FileNotFoundError:
        return _erro("comando 'tar' nao encontrado no sistema.")
    except subprocess.CalledProcessError as exc:
        return _erro(f"falha ao extrair de {tarball}: codigo {exc.returncode}.")
    return 0


def _garantir_extracao(destino: Path, *, force: bool) -> int:
    """Extracao incremental: extrai so os membros que faltam de cada tarball."""
    for tarball, info in ARQUIVOS.items():
        faltam = MEMBROS[tarball] if force else _faltantes(tarball, destino)
        if not faltam:
            print(f"{tarball}: tudo ja extraido (nada a fazer).")
            continue
        # precisa do tarball em disco para extrair os faltantes
        if not (destino / tarball).exists():
            print(f"{tarball}: ausente no disco; baixando para extrair os faltantes...")
            rc = _baixar_um(tarball, info, destino)
            if rc != 0:
                return rc
        rc = _extrair_membros(tarball, faltam, destino)
        if rc != 0:
            return rc
        ainda = _faltantes(tarball, destino)
        if ainda:
            return _erro(f"apos extrair, ainda faltam membros de {tarball}: {ainda}")
        print(f"{tarball}: extracao completa.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="download_cert.py",
        description="Baixa e extrai (incremental) o CERT Insider Threat Test Dataset r4.2.",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="So mostra a fonte, os termos e o estado atual.")
    p.add_argument("--extract", action="store_true",
                   help="Garante tudo extraido, baixando/extraindo so o que falta.")
    p.add_argument("--force-extract", action="store_true",
                   help="Re-extrai todos os membros, mesmo os ja presentes.")
    args = p.parse_args(argv)

    _DATA.mkdir(parents=True, exist_ok=True)
    _print_referencia_e_termos(_DATA)

    # Mostra o estado atual da extracao (util para o usuario saber o que falta).
    for tarball in ARQUIVOS:
        faltam = _faltantes(tarball, _DATA)
        if faltam:
            print(f"{tarball}: faltam {len(faltam)} membro(s): {', '.join(faltam)}")
        else:
            print(f"{tarball}: todos os membros ja extraidos.")
    print()

    if args.dry_run:
        print("[--dry-run] Nenhum download/extracao realizado.")
        return 0

    if args.extract or args.force_extract:
        return _garantir_extracao(_DATA, force=args.force_extract)

    # Sem --extract: apenas garante os tarballs baixados.
    for nome, info in ARQUIVOS.items():
        rc = _baixar_um(nome, info, _DATA)
        if rc != 0:
            return rc
    print()
    print("Tarballs prontos. Rode com --extract para descompactar (incremental).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
