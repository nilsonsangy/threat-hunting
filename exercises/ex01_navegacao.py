"""Exercício 1 — Navegação web suspeita (ATT&CK T1567).

Usuários que acessam sites de emprego/recolocação ou fazem upload para nuvem
pessoal. Fonte: http.csv (id,date,user,pc,url,content) do CERT r4.2.

Como o http.csv é enorme, o exercício processa a navegação em blocos (streaming)
por padrão; use --limite para restringir o número de linhas lidas.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from thlab import domains as _domains
from thlab import loaders as _loaders

__all__ = ["NavegacaoSuspeita", "run", "run_streaming", "main"]


@dataclass(frozen=True)
class NavegacaoSuspeita:
    user: str
    contagem: int
    data_primeiro_acesso: object


def run(http: pd.DataFrame) -> list[NavegacaoSuspeita]:
    """Identifica navegação suspeita num DataFrame de http já carregado."""
    if http is None or http.empty or "url" not in http.columns:
        return []
    susp = http[http["url"].apply(_domains.eh_suspeita)]
    if susp.empty:
        return []
    out: list[NavegacaoSuspeita] = []
    for user, g in susp.groupby("user", sort=False):
        out.append(NavegacaoSuspeita(str(user), int(len(g)), g["date"].min()))
    out.sort(key=lambda r: (-r.contagem, r.user))
    return out


def run_streaming(data_dir=None, *, chunksize: int = 500_000, max_linhas: int | None = None):
    """Versão em streaming para o http.csv inteiro (acumula por usuário)."""
    cont: dict[str, int] = defaultdict(int)
    primeiro: dict[str, object] = {}
    lidas = 0
    for chunk in _loaders.iter_http(data_dir, chunksize=chunksize):
        susp = chunk[chunk["url"].apply(_domains.eh_suspeita)]
        for r in susp.itertuples(index=False):
            cont[r.user] += 1
            if r.user not in primeiro or r.date < primeiro[r.user]:
                primeiro[r.user] = r.date
        lidas += len(chunk)
        if max_linhas and lidas >= max_linhas:
            break
    out = [NavegacaoSuspeita(u, c, primeiro.get(u)) for u, c in cont.items()]
    out.sort(key=lambda r: (-r.contagem, r.user))
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m exercises.ex01_navegacao",
                                description="Exercício 1 (T1567): navegação web suspeita.")
    p.add_argument("--amostra", action="store_true",
                   help="Usa data/r4.2/http.csv.sample em vez do http.csv completo.")
    p.add_argument("--limite", type=int, default=None,
                   help="Máximo de linhas de http a ler (streaming).")
    p.add_argument("--top", type=int, default=20, help="Quantos usuários exibir.")
    args = p.parse_args(argv)

    if args.amostra:
        http = _loaders.load_http_sample(nrows=args.limite or 2_000_000)
        suspeitos = run(http)
    else:
        suspeitos = run_streaming(max_linhas=args.limite)

    print("Exercício 1 — Navegação web suspeita (emprego/nuvem pessoal)")
    print("=" * 64)
    if not suspeitos:
        print("Nenhum usuário com navegação suspeita encontrado.")
        return
    print(f"{'Usuário':<12} {'Acessos':>8}  {'Primeiro acesso':<19}")
    print("-" * 64)
    for item in suspeitos[: args.top]:
        pf = item.data_primeiro_acesso
        pf = pf.strftime("%Y-%m-%d %H:%M:%S") if hasattr(pf, "strftime") else str(pf)
        print(f"{item.user:<12} {item.contagem:>8}  {pf:<19}")
    print(f"\nTotal de usuários com navegação suspeita: {len(suspeitos)}")


if __name__ == "__main__":
    main()
