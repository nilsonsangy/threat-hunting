"""thlab.timewin — utilidades de Expediente (janela de horário) e sessões de logon.

Módulo puro e determinístico: não faz I/O de rede nem de disco. Opera sobre
``pandas.Timestamp`` e ``pandas.DataFrame`` já carregados pelos loaders.

Convenções-chave
-----------------
- **Expediente** é a janela de trabalho ``(hora_inicio, hora_fim)``, padrão ``(7, 19)``,
  interpretada como o intervalo **semiaberto** ``[hora_inicio, hora_fim)`` em horas do dia.
- **Fora de hora** (``is_fora_hora``) é, portanto, ``hora < hora_inicio`` **ou**
  ``hora >= hora_fim``. Com o padrão ``(7, 19)``: 06:59 é fora de hora, 07:00 é dentro,
  18:59 é dentro, 19:00 é fora. Um evento às 20:11 é fora de hora.
- **Sessão** é o par sequencial Logon→Logoff do mesmo ``(user, pc)``, representado pelo
  intervalo **fechado** ``[inicio, fim]`` (ambos os extremos pertencem à sessão), coerente
  com ``dentro_de_sessao`` usando ``inicio <= evento_ts <= fim``.
"""

from __future__ import annotations

import pandas as pd

Expediente = tuple[int, int]  # (hora_inicio, hora_fim), padrão (7, 19)

EXPEDIENTE_PADRAO: Expediente = (7, 19)


def is_fora_hora(ts: pd.Timestamp, expediente: Expediente = EXPEDIENTE_PADRAO) -> bool:
    """Retorna ``True`` se o horário de ``ts`` cair **fora** do Expediente.

    O Expediente é o intervalo semiaberto ``[hora_inicio, hora_fim)`` em horas do dia.
    Logo, fora de hora é definido como ``hora < hora_inicio`` ou ``hora >= hora_fim``.
    A comparação usa a hora cheia do ``timestamp`` (minutos/segundos não alteram a
    classificação, pois os limites são horas inteiras).

    Parameters
    ----------
    ts:
        Instante do evento (``pandas.Timestamp`` ou qualquer valor aceito por
        ``pd.Timestamp``). ``NaT``/nulo levanta ``ValueError``.
    expediente:
        Tupla ``(hora_inicio, hora_fim)``; padrão ``(7, 19)``.

    Returns
    -------
    bool
        ``True`` se o evento está fora do expediente.
    """
    inicio, fim = expediente
    ts = pd.Timestamp(ts)
    if ts is pd.NaT or pd.isna(ts):
        raise ValueError("is_fora_hora recebeu um timestamp nulo (NaT).")
    hora = ts.hour
    return hora < inicio or hora >= fim


def sessoes_logon(logon: pd.DataFrame) -> pd.DataFrame:
    """Reduz pares Logon/Logoff em sessões ``[inicio, fim]`` por ``(user, pc)``.

    Para cada ``(user, pc)``, os eventos são ordenados por ``date`` e pareados de forma
    sequencial: cada ``Logon`` abre uma sessão e o próximo ``Logoff`` a fecha. Pares
    Logon→Logon ou Logoff sem Logon aberto são ignorados de forma defensiva (um ``Logon``
    seguido de outro ``Logon`` mantém o primeiro em aberto até surgir o ``Logoff``; um
    ``Logoff`` sem sessão aberta é descartado).

    Parameters
    ----------
    logon:
        DataFrame com as colunas ``user``, ``pc``, ``date`` (datetime) e ``activity``
        (valores ``Logon``/``Logoff``).

    Returns
    -------
    pandas.DataFrame
        Colunas ``user``, ``pc``, ``inicio``, ``fim`` (datetime), uma linha por sessão,
        ordenada por ``user``, ``pc``, ``inicio``.
    """
    colunas = ["user", "pc", "inicio", "fim"]
    obrigatorias = {"user", "pc", "date", "activity"}
    faltando = obrigatorias - set(logon.columns)
    if faltando:
        raise ValueError(
            f"sessoes_logon: colunas ausentes no DataFrame de logon: {sorted(faltando)}."
        )

    if logon.empty:
        return pd.DataFrame(columns=colunas)

    df = logon.loc[:, ["user", "pc", "date", "activity"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["user", "pc", "date"], kind="stable")

    sessoes: list[dict[str, object]] = []
    for (user, pc), grupo in df.groupby(["user", "pc"], sort=True):
        inicio_aberto: pd.Timestamp | None = None
        for _, linha in grupo.iterrows():
            atividade = str(linha["activity"]).strip().lower()
            ts = linha["date"]
            if atividade == "logon":
                # Abre uma sessão. Se já houver uma aberta, mantém a primeira (defensivo).
                if inicio_aberto is None:
                    inicio_aberto = ts
            elif atividade == "logoff":
                # Fecha a sessão aberta, se houver.
                if inicio_aberto is not None:
                    sessoes.append(
                        {"user": user, "pc": pc, "inicio": inicio_aberto, "fim": ts}
                    )
                    inicio_aberto = None
            # Qualquer outra atividade é ignorada.

    resultado = pd.DataFrame(sessoes, columns=colunas)
    if not resultado.empty:
        resultado = resultado.sort_values(
            ["user", "pc", "inicio"], kind="stable"
        ).reset_index(drop=True)
    return resultado


def dentro_de_sessao(
    evento_ts: pd.Timestamp,
    user: str,
    pc: str,
    sessoes: pd.DataFrame,
) -> bool:
    """Retorna ``True`` se ``evento_ts`` cai dentro de alguma sessão do mesmo user/pc.

    A pertinência usa o intervalo **fechado** da sessão: existe sessão tal que
    ``inicio <= evento_ts <= fim`` para o mesmo ``user`` e ``pc``.

    Parameters
    ----------
    evento_ts:
        Instante do evento a verificar.
    user, pc:
        Chaves que identificam o usuário e a máquina da sessão.
    sessoes:
        DataFrame no formato produzido por :func:`sessoes_logon`
        (colunas ``user``, ``pc``, ``inicio``, ``fim``).

    Returns
    -------
    bool
        ``True`` se o evento está contido em ao menos uma sessão correspondente.
    """
    if sessoes is None or sessoes.empty:
        return False

    evento_ts = pd.Timestamp(evento_ts)
    if evento_ts is pd.NaT or pd.isna(evento_ts):
        raise ValueError("dentro_de_sessao recebeu um evento_ts nulo (NaT).")

    candidatas = sessoes[(sessoes["user"] == user) & (sessoes["pc"] == pc)]
    if candidatas.empty:
        return False

    inicio = pd.to_datetime(candidatas["inicio"])
    fim = pd.to_datetime(candidatas["fim"])
    contidas = (inicio <= evento_ts) & (evento_ts <= fim)
    return bool(contidas.any())
