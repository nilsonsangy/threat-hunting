"""Exercício 5 — Correlação de sinais e ranking de Score_Risco.

Soma, por usuário, um score aditivo pelos sinais presentes (logon fora de hora,
USB fora de hora, cópia acima da baseline, navegação suspeita), produzindo um
ranking dos usuários a investigar primeiro. Usa um recorte de http para o sinal
web (o http completo é gigante).
"""

from __future__ import annotations

import argparse

import pandas as pd

from thlab import loaders as _loaders
from thlab.score import SuspeitoScore, score_por_usuario

__all__ = ["run", "main"]


def run(sources, *, http=None, expediente=(7, 19)) -> list[SuspeitoScore]:
    return score_por_usuario(sources, http=http, expediente=expediente)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m exercises.ex05_correlacao",
                                description="Exercício 5: correlação e Score_Risco.")
    p.add_argument("--limite", type=int, default=None,
                   help="Máximo de linhas por fonte de atividade (recorte).")
    p.add_argument("--http-amostra", type=int, default=2_000_000,
                   help="Linhas do http.csv.sample a usar para o sinal web.")
    p.add_argument("--top", type=int, default=25)
    args = p.parse_args(argv)

    sources = _loaders.load_sources(nrows=args.limite)
    try:
        http = _loaders.load_http_sample(nrows=args.http_amostra)
    except FileNotFoundError:
        http = None

    ranking = run(sources, http=http)

    print("Exercício 5 — Correlação de sinais (ranking de Score_Risco)")
    print("=" * 64)
    if not ranking:
        print("Nenhum suspeito pontuou.")
        return
    for i, s in enumerate(ranking[: args.top], 1):
        sinais = ", ".join(f"{t}=+{p}" for t, p in sorted(s.sinais.items()))
        print(f"{i:>2}. {s.user:<10} score={s.score}  [{sinais}]")
    print(f"\nTotal de usuários com score > 0: {len(ranking)}")


if __name__ == "__main__":
    main()
