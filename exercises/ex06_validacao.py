"""Exercício 6 — Validação contra o gabarito oficial de insiders do r4.2.

Cruza o ranking de Score_Risco (exercício 5) com o answer key oficial do CERT
(data/answers/insiders.csv, filtrado para a release 4.2). Classifica cada
suspeito do topo como verdadeiro positivo (está no gabarito) ou falso positivo.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import pandas as pd

from exercises import ex05_correlacao
from thlab import loaders as _loaders
from thlab.score import SuspeitoScore

__all__ = ["Veredito", "run", "main"]


@dataclass(frozen=True)
class Veredito:
    user: str
    score: int
    no_answer_key: bool
    classificacao: str


VERDADEIRO_POSITIVO = "verdadeiro positivo"
FALSO_POSITIVO = "falso positivo"


def run(ranking: list[SuspeitoScore], answer_key: pd.DataFrame, *, score_min: int = 1) -> list[Veredito]:
    insiders = set()
    if answer_key is not None and not answer_key.empty and "user" in answer_key.columns:
        insiders = {str(u).strip() for u in answer_key["user"] if str(u).strip()}
    out: list[Veredito] = []
    for s in ranking:
        if s.score < score_min:
            continue
        vp = s.user in insiders
        out.append(Veredito(s.user, s.score, vp, VERDADEIRO_POSITIVO if vp else FALSO_POSITIVO))
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m exercises.ex06_validacao",
                                description="Exercício 6: validação contra o gabarito oficial.")
    p.add_argument("--limite", type=int, default=None)
    p.add_argument("--http-amostra", type=int, default=2_000_000)
    p.add_argument("--top", type=int, default=30)
    args = p.parse_args(argv)

    sources = _loaders.load_sources(nrows=args.limite)
    try:
        http = _loaders.load_http_sample(nrows=args.http_amostra)
    except FileNotFoundError:
        http = None
    ranking = ex05_correlacao.run(sources, http=http)
    vereditos = run(ranking, sources["answer_key"])

    vp = [v for v in vereditos if v.no_answer_key]
    print("Exercício 6 — Validação contra o gabarito oficial (r4.2)")
    print("=" * 64)
    print(f"Insiders no gabarito r4.2: {len(set(sources['answer_key']['user']))}")
    print(f"Suspeitos avaliados (score>0): {len(vereditos)} | verdadeiros positivos no topo: {len(vp)}")
    print(f"{'user':<10} {'score':>5}  veredito")
    print("-" * 40)
    for v in vereditos[: args.top]:
        marca = "[VP]" if v.no_answer_key else "[FP]"
        print(f"{marca} {v.user:<8} {v.score:>5}  {v.classificacao}")


if __name__ == "__main__":
    main()
