"""Testes unitários das funções puras do núcleo (sem depender do dataset baixado).

Constroem DataFrames pequenos em memória, no schema do r4.2, para exercitar a
lógica de timewin, baseline e score de forma determinística e rápida. Rodam em
qualquer máquina, mesmo sem o dataset do CERT presente.
"""

from __future__ import annotations

import pandas as pd

from thlab import baseline, domains, score, timewin


def _dt(s: str) -> pd.Timestamp:
    return pd.Timestamp(s)


def test_is_fora_hora_expediente_padrao():
    assert timewin.is_fora_hora(_dt("2010-01-01 20:11:00")) is True
    assert timewin.is_fora_hora(_dt("2010-01-01 09:00:00")) is False
    assert timewin.is_fora_hora(_dt("2010-01-01 19:00:00")) is True   # 19h ja e fora
    assert timewin.is_fora_hora(_dt("2010-01-01 06:59:00")) is True


def test_sessoes_e_dentro_de_sessao():
    logon = pd.DataFrame({
        "user": ["U1", "U1"],
        "pc": ["PC1", "PC1"],
        "date": [_dt("2010-01-01 19:58:00"), _dt("2010-01-01 21:30:00")],
        "activity": ["Logon", "Logoff"],
    })
    sess = timewin.sessoes_logon(logon)
    assert len(sess) == 1
    assert timewin.dentro_de_sessao(_dt("2010-01-01 20:11:00"), "U1", "PC1", sess) is True
    assert timewin.dentro_de_sessao(_dt("2010-01-01 20:11:00"), "U1", "PC2", sess) is False


def test_domains_classifica():
    assert domains.eh_suspeita("https://www.indeed.com/jobs") is True
    assert domains.eh_suspeita("https://dropbox.com/upload") is True
    assert domains.eh_suspeita("https://intranet.dtaa.com/home") is False


def test_baseline_peer_group_mediana_robusta():
    # 3 usuarios do papel A copiando 2/dia e um outlier de 50/dia.
    rows = []
    for u, n in [("A1", 2), ("A2", 2), ("A3", 2), ("OUT", 50)]:
        for i in range(n):
            rows.append({"user": u, "date": _dt("2010-01-01 10:00:00") + pd.Timedelta(minutes=i)})
    file_df = pd.DataFrame(rows)
    ldap = pd.DataFrame({"user_id": ["A1", "A2", "A3", "OUT"],
                         "role": ["A", "A", "A", "A"]})
    peer = baseline.baseline_peer_group(file_df, ldap)
    # mediana de {2,2,2,50} = 2 (robusta ao outlier)
    assert abs(float(peer.loc["A"]) - 2.0) < 1e-9


def test_score_soma_sinais():
    # U1 dispara logon fora de hora (+1), USB fora de hora (+2) e web (+1) = 4
    logon = pd.DataFrame({"user": ["U1", "U1"], "pc": ["PC1", "PC1"],
                          "date": [_dt("2010-01-01 20:00:00"), _dt("2010-01-01 22:00:00")],
                          "activity": ["Logon", "Logoff"]})
    device = pd.DataFrame({"user": ["U1"], "pc": ["PC1"],
                           "date": [_dt("2010-01-01 20:30:00")], "activity": ["Connect"]})
    file_df = pd.DataFrame({"user": [], "date": []})
    ldap = pd.DataFrame({"user_id": ["U1"], "role": ["A"]})
    http = pd.DataFrame({"user": ["U1"], "url": ["https://indeed.com/jobs"],
                         "date": [_dt("2010-01-01 20:40:00")]})
    ranking = score.score_por_usuario(
        {"logon": logon, "device": device, "file": file_df, "ldap": ldap}, http=http)
    por = {s.user: s.score for s in ranking}
    assert por["U1"] == 4
