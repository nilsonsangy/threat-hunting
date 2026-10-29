"""Exercício 4 — Cópia de arquivos vs. baseline do grupo (ATT&CK T1052).

Compara o volume de cópias de cada usuário contra a baseline do próprio usuário e
a do peer-group (papel no LDAP). Sinaliza quem supera a baseline do grupo. O
desvio contra os pares, não o valor absoluto, é o que acusa o outlier.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import pandas as pd

from thlab import loaders as _loaders
from thlab.baseline import baseline_individual, baseline_peer_group

__all__ = ["CopiaFlag", "run", "main"]


@dataclass(frozen=True)
class CopiaFlag:
    user: str
    role: str
    copias_dia_media: float
    baseline_peer_group: float
    fator: float


def run(sources: dict[str, pd.DataFrame], *, fator_min: float = 1.0) -> list[CopiaFlag]:
    file_df = sources["file"]
    ldap_df = sources["ldap"]
    ind = baseline_individual(file_df)
    peer = baseline_peer_group(file_df, ldap_df)
    if ind.empty:
        return []
    role = (ldap_df[["user_id", "role"]].drop_duplicates("user_id")
            .set_index("user_id")["role"].to_dict())
    flags: list[CopiaFlag] = []
    for user, media in ind.items():
        rl = role.get(user)
        if rl is None or rl not in peer.index:
            continue
        bp = float(peer.loc[rl])
        if bp <= 0:
            continue
        if float(media) > bp * fator_min and float(media) > bp:
            flags.append(CopiaFlag(str(user), str(rl), float(media), bp, float(media) / bp))
    flags.sort(key=lambda f: (-f.fator, -f.copias_dia_media, f.user))
    return flags


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m exercises.ex04_copia_arquivos",
                                description="Exercício 4 (T1052): cópia vs. baseline do grupo.")
    p.add_argument("--limite", type=int, default=None)
    p.add_argument("--fator", type=float, default=3.0,
                   help="Fator mínimo acima da baseline do grupo para sinalizar (padrão 3x).")
    p.add_argument("--top", type=int, default=30)
    args = p.parse_args(argv)

    sources = _loaders.load_sources(nrows=args.limite)
    flags = run(sources, fator_min=args.fator)

    print("Exercício 4 — Cópia de arquivos vs. baseline do grupo (T1052)")
    print("=" * 64)
    print(f"Usuários acima de {args.fator:g}x a baseline do papel: {len(flags)}")
    print(f"{'user':<10} {'papel':<20} {'copias/dia':>10} {'base_papel':>10} {'fator':>7}")
    print("-" * 64)
    for f in flags[: args.top]:
        print(f"{f.user:<10} {f.role:<20} {f.copias_dia_media:>10.1f} {f.baseline_peer_group:>10.1f} {f.fator:>6.1f}x")


if __name__ == "__main__":
    main()
