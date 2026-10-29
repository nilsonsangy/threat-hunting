"""thlab.baseline — baselines de atividade de cópia de arquivos (CERT r4.2).

No r4.2, ``file.csv`` registra copias de arquivo (``id,date,user,pc,filename,
content``) — nao ha coluna indicando midia removivel. A exfiltracao por USB e
inferida correlacionando a copia com uma conexao de USB ativa (ver
``thlab.usb``/exercicios). Aqui tratamos o volume de copias em si: por dia, por
usuario, e a baseline por papel (peer-group do LDAP).

Todas as funcoes sao puras e deterministicas (sem I/O de rede).
"""

from __future__ import annotations

import pandas as pd

__all__ = ["copias_por_dia", "baseline_individual", "baseline_peer_group"]


def copias_por_dia(file_df: pd.DataFrame) -> pd.DataFrame:
    """Conta copias de arquivo por ``(user, dia)``.

    Cada linha de ``file.csv`` e uma copia. Retorna colunas ``user``, ``dia``
    (date) e ``copias`` (int), ordenado por user/dia.
    """
    _exigir(file_df, ["date", "user"], origem="file_df")
    date = pd.to_datetime(file_df["date"])
    base = pd.DataFrame({"user": file_df["user"].to_numpy(), "dia": date.dt.date.to_numpy()})
    if base.empty:
        return pd.DataFrame({"user": pd.Series(dtype=object),
                             "dia": pd.Series(dtype=object),
                             "copias": pd.Series(dtype="int64")})
    agg = base.groupby(["user", "dia"], sort=True).size().reset_index(name="copias")
    agg["copias"] = agg["copias"].astype("int64")
    return agg.sort_values(["user", "dia"]).reset_index(drop=True)


def baseline_individual(file_df: pd.DataFrame) -> pd.Series:
    """Media diaria de copias por usuario (sobre os dias em que houve copia)."""
    por_dia = copias_por_dia(file_df)
    if por_dia.empty:
        return pd.Series(dtype="float64", name="baseline_individual",
                         index=pd.Index([], name="user"))
    media = por_dia.groupby("user", sort=True)["copias"].mean()
    media.name = "baseline_individual"
    media.index.name = "user"
    return media


def baseline_peer_group(file_df: pd.DataFrame, ldap_df: pd.DataFrame) -> pd.Series:
    """Baseline de copias/dia por papel (``role`` do LDAP), robusta a outliers.

    Parte das medias diarias individuais e aplica a mediana por papel. A mediana
    e naturalmente robusta aos poucos insiders que copiam em volume muito acima
    dos pares, entregando uma referencia de normalidade do papel.
    """
    _exigir(ldap_df, ["user_id", "role"], origem="ldap_df")
    ind = baseline_individual(file_df)
    if ind.empty:
        return pd.Series(dtype="float64", name="baseline_peer_group",
                         index=pd.Index([], name="role"))
    papel = (ldap_df[["user_id", "role"]].drop_duplicates("user_id")
             .set_index("user_id")["role"])
    m = ind.rename_axis("user").reset_index(name="media")
    m["role"] = m["user"].map(papel)
    m = m.dropna(subset=["role"])
    if m.empty:
        return pd.Series(dtype="float64", name="baseline_peer_group",
                         index=pd.Index([], name="role"))
    base = m.groupby("role", sort=True)["media"].median()
    base.name = "baseline_peer_group"
    base.index.name = "role"
    return base


def _exigir(df: pd.DataFrame, cols: list[str], *, origem: str) -> None:
    faltando = [c for c in cols if c not in df.columns]
    if faltando:
        raise ValueError(f"{origem}: coluna(s) ausente(s) {faltando}; exigidas {cols}.")
