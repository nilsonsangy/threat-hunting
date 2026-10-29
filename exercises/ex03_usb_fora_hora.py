"""Exercício 3 — USB fora de hora cruzado com logon (ATT&CK T1078 + T1052).

Conexões de USB fora do expediente que caem dentro de uma sessão de logon real do
mesmo usuário/máquina (sinal forte: foi o próprio usuário, logado). Cruza
device.csv e logon.csv.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import pandas as pd

from thlab import loaders as _loaders
from thlab import timewin as _timewin

__all__ = ["OcorrenciaUSBForaHora", "run", "main"]


@dataclass(frozen=True)
class OcorrenciaUSBForaHora:
    user: str
    pc: str
    ts_usb: object
    sessao_inicio: object
    sessao_fim: object
    forte: bool


def _parse_expediente(texto: str):
    partes = texto.split("-")
    if len(partes) != 2:
        raise argparse.ArgumentTypeError(f"--expediente formato HORA-HORA (ex.: 7-19); recebido {texto!r}.")
    try:
        a, b = int(partes[0]), int(partes[1])
    except ValueError:
        raise argparse.ArgumentTypeError(f"--expediente horas inteiras (ex.: 7-19); recebido {texto!r}.")
    return (a, b)


def run(sources: dict[str, pd.DataFrame], expediente=(7, 19)) -> list[OcorrenciaUSBForaHora]:
    from collections import defaultdict
    device = sources["device"]
    logon = sources["logon"]
    sess = _timewin.sessoes_logon(logon)

    # Indexa as sessões por (user, pc) uma única vez: lista de (inicio, fim).
    por_chave: dict = defaultdict(list)
    for sr in sess.itertuples(index=False):
        por_chave[(sr.user, sr.pc)].append((pd.Timestamp(sr.inicio), pd.Timestamp(sr.fim)))

    conn = device[device["activity"].astype(str).str.strip().str.lower() == "connect"]
    out: list[OcorrenciaUSBForaHora] = []
    for r in conn.itertuples(index=False):
        ts = pd.Timestamp(r.date)
        if not _timewin.is_fora_hora(ts, expediente):
            continue
        ini = fim = None
        for (si, sf) in por_chave.get((r.user, r.pc), ()):
            if si <= ts <= sf:
                ini, fim = si, sf
                break
        out.append(OcorrenciaUSBForaHora(r.user, r.pc, ts, ini, fim, ini is not None))
    out.sort(key=lambda o: (o.ts_usb, o.user, o.pc))
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m exercises.ex03_usb_fora_hora",
                                description="Exercício 3 (T1078+T1052): USB fora de hora x logon.")
    p.add_argument("--limite", type=int, default=None)
    p.add_argument("--expediente", type=_parse_expediente, default=(7, 19), metavar="INICIO-FIM")
    p.add_argument("--top", type=int, default=30)
    args = p.parse_args(argv)

    sources = _loaders.load_sources(nrows=args.limite)
    ocorr = run(sources, expediente=args.expediente)
    fortes = [o for o in ocorr if o.forte]

    print(f"Exercício 3 — USB fora de hora x logon (expediente {args.expediente[0]:02d}h-{args.expediente[1]:02d}h)")
    print("=" * 64)
    print(f"Conexões de USB fora de hora: {len(ocorr)} | sinais fortes (em sessão própria): {len(fortes)}")
    for o in fortes[: args.top]:
        s = f"{o.sessao_inicio:%m/%d %H:%M}-{o.sessao_fim:%H:%M}" if o.sessao_inicio is not None else "?"
        print(f"  FORTE  {o.user} @ {o.pc} — Connect {o.ts_usb:%m/%d %H:%M} (sessão {s})")
    if len(fortes) > args.top:
        print(f"  ... (+{len(fortes) - args.top} sinais fortes)")


if __name__ == "__main__":
    main()
