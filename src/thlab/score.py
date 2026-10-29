"""thlab.score — Score_Risco aditivo por tipo de sinal (CERT r4.2).

Soma, por usuario, pesos por PRESENCA de cada tipo de sinal numa janela:

    logon fora de hora ............. +1
    USB fora de hora ............... +2
    copia acima da baseline do papel +3
    web de emprego/nuvem ........... +1

No r4.2 o ``http.csv`` e enorme; por isso o sinal web e calculado a partir de um
DataFrame de http passado explicitamente (um recorte/stream), e nao de dentro de
``sources``. As demais fontes (logon/device/file/ldap) vem de
``thlab.loaders.load_sources``.

Modulo puro e deterministico. Depende de ``thlab.timewin``, ``thlab.baseline`` e
``thlab.domains``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from thlab import baseline as _baseline
from thlab import domains as _domains
from thlab import timewin as _timewin

__all__ = ["PESOS", "SuspeitoScore", "score_por_usuario"]

PESOS: dict[str, int] = {
    "logon_fora_hora": 1,
    "usb_fora_hora": 2,
    "copia_acima_baseline": 3,
    "web_suspeita": 1,
}


@dataclass(frozen=True)
class SuspeitoScore:
    user: str
    score: int
    sinais: dict[str, int] = field(default_factory=dict)


def _logon_fora_hora(logon, expediente) -> set[str]:
    if logon is None or logon.empty:
        return set()
    sess = _timewin.sessoes_logon(logon)
    if sess.empty:
        return set()
    users: set[str] = set()
    for r in sess.itertuples(index=False):
        if _timewin.is_fora_hora(r.inicio, expediente) or _timewin.is_fora_hora(r.fim, expediente):
            users.add(r.user)
    return users


def _usb_fora_hora(device, logon, expediente) -> set[str]:
    if device is None or device.empty:
        return set()
    conn = device[device["activity"].astype(str).str.strip().str.lower() == "connect"]
    if conn.empty:
        return set()
    sess = _timewin.sessoes_logon(logon) if logon is not None and not logon.empty else None
    users: set[str] = set()
    for r in conn.itertuples(index=False):
        if not _timewin.is_fora_hora(r.date, expediente):
            continue
        if sess is not None and not sess.empty:
            if _timewin.dentro_de_sessao(r.date, r.user, r.pc, sess):
                users.add(r.user)
        else:
            users.add(r.user)
    return users


def _copia_acima_baseline(file_df, ldap_df) -> set[str]:
    if file_df is None or file_df.empty or ldap_df is None or ldap_df.empty:
        return set()
    por_dia = _baseline.copias_por_dia(file_df)
    if por_dia.empty:
        return set()
    peer = _baseline.baseline_peer_group(file_df, ldap_df)
    role = (ldap_df[["user_id", "role"]].drop_duplicates("user_id")
            .set_index("user_id")["role"].to_dict())

    def base_do(user: str) -> float:
        rl = role.get(user)
        if rl is None or rl not in peer.index:
            return float("inf")
        return float(peer.loc[rl])

    users: set[str] = set()
    for r in por_dia.itertuples(index=False):
        if float(r.copias) > base_do(r.user):
            users.add(r.user)
    return users


def _web_suspeita(http) -> set[str]:
    if http is None or http.empty or "url" not in http.columns:
        return set()
    users: set[str] = set()
    for r in http.itertuples(index=False):
        if _domains.eh_suspeita(getattr(r, "url")):
            users.add(getattr(r, "user"))
    return users


def score_por_usuario(
    sources: dict[str, pd.DataFrame],
    *,
    http: pd.DataFrame | None = None,
    expediente: tuple[int, int] = (7, 19),
) -> list[SuspeitoScore]:
    """Calcula o Score_Risco por usuario (presenca de sinal x peso).

    ``sources`` traz logon/device/file/ldap (de ``load_sources``). ``http`` e o
    recorte de navegacao (DataFrame) usado para o sinal web; se ``None``, o sinal
    web nao e contado.
    """
    presencas = {
        "logon_fora_hora": _logon_fora_hora(sources.get("logon"), expediente),
        "usb_fora_hora": _usb_fora_hora(sources.get("device"), sources.get("logon"), expediente),
        "copia_acima_baseline": _copia_acima_baseline(sources.get("file"), sources.get("ldap")),
        "web_suspeita": _web_suspeita(http),
    }
    users: set[str] = set()
    for c in presencas.values():
        users |= c
    out: list[SuspeitoScore] = []
    for u in users:
        sinais = {t: PESOS[t] for t, c in presencas.items() if u in c}
        out.append(SuspeitoScore(user=u, score=sum(sinais.values()), sinais=sinais))
    out.sort(key=lambda s: (-s.score, s.user))
    return out
