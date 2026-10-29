"""Exercício 2 — Exfiltração por USB (ATT&CK T1052).

No r4.2 não há flag de "mídia removível": uma cópia de arquivo é tratada como
exfiltração por USB quando seu horário cai dentro de uma janela de conexão de USB
(Connect→Disconnect) do mesmo usuário/máquina. Cruza device.csv e file.csv.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import pandas as pd

from thlab import loaders as _loaders
from thlab import timewin as _timewin

__all__ = ["CopiaDuranteUSB", "ResultadoUSB", "run", "main"]


@dataclass(frozen=True)
class CopiaDuranteUSB:
    user: str
    pc: str
    ts_copia: object
    filename: str
    ts_connect: object
    fora_hora: bool


@dataclass(frozen=True)
class ResultadoUSB:
    conexoes_por_usuario: dict
    copias_durante_conexao: list
    usuarios_exfiltracao_usb: list


def _janelas(device, expediente):
    jan = []
    if device is None or device.empty:
        return jan
    df = device[["user", "pc", "date", "activity"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["user", "pc", "date"], kind="stable")
    for (user, pc), g in df.groupby(["user", "pc"], sort=True):
        aberto = None
        for r in g.itertuples(index=False):
            act = str(r.activity).strip().lower()
            if act == "connect":
                aberto = r.date
            elif act == "disconnect" and aberto is not None:
                jan.append((user, pc, aberto, r.date, _timewin.is_fora_hora(aberto, expediente)))
                aberto = None
        if aberto is not None:
            jan.append((user, pc, aberto, aberto + pd.Timedelta("30min"),
                        _timewin.is_fora_hora(aberto, expediente)))
    return jan


def run(sources: dict[str, pd.DataFrame], *, expediente=(7, 19)) -> ResultadoUSB:
    device = sources.get("device")
    file_df = sources.get("file")

    conex: dict[str, int] = {}
    if device is not None and not device.empty:
        conn = device[device["activity"].astype(str).str.strip().str.lower() == "connect"]
        for r in conn.itertuples(index=False):
            conex[r.user] = conex.get(r.user, 0) + 1

    janelas = _janelas(device, expediente)
    copias: list[CopiaDuranteUSB] = []
    if file_df is not None and not file_df.empty:
        f = file_df[["user", "pc", "date", "filename"]].copy()
        f["date"] = pd.to_datetime(f["date"])
        # index de janelas por (user,pc) para busca rápida
        from collections import defaultdict
        por_chave = defaultdict(list)
        for (u, pc, ini, fim, fh) in janelas:
            por_chave[(u, pc)].append((ini, fim, fh))
        for r in f.itertuples(index=False):
            for (ini, fim, fh) in por_chave.get((r.user, r.pc), ()):
                if ini <= r.date <= fim:
                    copias.append(CopiaDuranteUSB(r.user, r.pc, r.date, str(r.filename), ini, fh))
                    break
    copias.sort(key=lambda c: (c.user, c.ts_copia))
    usuarios = sorted({c.user for c in copias})
    return ResultadoUSB(dict(sorted(conex.items())), copias, usuarios)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m exercises.ex02_usb",
                                description="Exercício 2 (T1052): exfiltração por USB.")
    p.add_argument("--limite", type=int, default=None,
                   help="Máximo de linhas por fonte (recorte para desenvolvimento).")
    p.add_argument("--top", type=int, default=30)
    args = p.parse_args(argv)

    sources = _loaders.load_sources(nrows=args.limite)
    res = run(sources)

    print("Exercício 2 — Exfiltração por USB (T1052)")
    print("=" * 64)
    print(f"Usuários que copiaram arquivos durante uma conexão de USB: {len(res.usuarios_exfiltracao_usb)}")
    for c in res.copias_durante_conexao[: args.top]:
        selo = "FORA DE HORA" if c.fora_hora else "no expediente"
        print(f"  {c.user} @ {c.pc} | {c.ts_copia:%m/%d %H:%M} {c.filename} (conexão {c.ts_connect:%H:%M}, {selo})")
    if len(res.copias_durante_conexao) > args.top:
        print(f"  ... (+{len(res.copias_durante_conexao) - args.top} cópias)")


if __name__ == "__main__":
    main()
