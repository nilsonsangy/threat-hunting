"""thlab.loaders — carga das fontes do CERT Insider Threat Test Dataset (r4.2).

Carrega as fontes de atividade, os dados de LDAP e o gabarito oficial a partir de
``data/`` (onde o dataset real é baixado e extraido por
``scripts/download_cert.py``). Layout esperado apos a extracao:

    data/
      r4.2/
        logon.csv            id,date,user,pc,activity           (Logon|Logoff)
        device.csv           id,date,user,pc,activity           (Connect|Disconnect)
        file.csv             id,date,user,pc,filename,content
        http.csv             id,date,user,pc,url,content        (dezenas de GB)
        email.csv            id,date,user,pc,to,cc,bcc,from,size,attachments,content
        LDAP/
          YYYY-MM.csv        employee_name,user_id,email,role,...,supervisor
      answers/
        insiders.csv         dataset,scenario,details,user,start,end

O ``http.csv`` do r4.2 tem dezenas de GB; por isso ele NAO e carregado por
``load_sources``. Use ``iter_http`` / ``load_http_sample`` para processa-lo em
blocos (streaming), sem carregar tudo na memoria.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

# Formato de data do r4.2.
_DATE_FORMAT = "%m/%d/%Y %H:%M:%S"

# Release alvo (para filtrar o gabarito, que cobre todas as releases).
RELEASE = "4.2"

# Colunas esperadas por fonte (schema r4.2).
SCHEMAS: dict[str, tuple[str, ...]] = {
    "logon": ("id", "date", "user", "pc", "activity"),
    "device": ("id", "date", "user", "pc", "activity"),
    "file": ("id", "date", "user", "pc", "filename", "content"),
    "http": ("id", "date", "user", "pc", "url", "content"),
    "email": ("id", "date", "user", "pc", "to", "cc", "bcc", "from",
              "size", "attachments", "content"),
}


def _data_root(data_dir: str | Path | None) -> Path:
    """Raiz dos dados. Padrao: <repo>/data (ou env THLAB_DATA)."""
    if data_dir is not None:
        return Path(data_dir)
    env = os.environ.get("THLAB_DATA")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent / "data"


def _dataset_dir(root: Path) -> Path:
    """Diretorio dos CSVs de atividade (data/r4.2)."""
    d = root / f"r{RELEASE}"
    if not d.is_dir():
        raise FileNotFoundError(
            f"Dataset nao encontrado em {d}. Baixe e extraia com: "
            f"python scripts/download_cert.py --extract"
        )
    return d


def _ler_csv(nome: str, caminho: Path, *, parse_date: bool, nrows: int | None = None) -> pd.DataFrame:
    if not caminho.is_file():
        raise FileNotFoundError(f"Fonte '{nome}' ausente: {caminho}.")
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, nrows=nrows)
    esperadas = SCHEMAS[nome]
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        raise ValueError(
            f"Fonte '{nome}' ({caminho.name}) sem coluna(s): {', '.join(faltando)}. "
            f"Esperado: {', '.join(esperadas)}."
        )
    if parse_date:
        parsed = pd.to_datetime(df["date"], format=_DATE_FORMAT, errors="coerce")
        ruins = df["date"][parsed.isna() & df["date"].astype(bool)]
        if len(ruins) > 0:
            raise ValueError(
                f"Fonte '{nome}': 'date' fora do formato {_DATE_FORMAT} "
                f"(ex.: {ruins.iloc[0]!r})."
            )
        df["date"] = parsed
    return df


def load_ldap(data_dir: str | Path | None = None) -> pd.DataFrame:
    """Carrega o LDAP (pasta mensal) como um unico DataFrame por usuario.

    O r4.2 traz um snapshot por mes em ``LDAP/YYYY-MM.csv``. Consolidamos todos e
    ficamos com o registro mais recente de cada ``user_id`` (o papel/departamento
    vigente ao fim do periodo), suficiente para montar o peer-group por papel.
    """
    root = _data_root(data_dir)
    ldap_dir = _dataset_dir(root) / "LDAP"
    if not ldap_dir.is_dir():
        raise FileNotFoundError(
            f"Pasta LDAP ausente em {ldap_dir}. Extraia o dataset "
            f"(python scripts/download_cert.py --extract)."
        )
    arquivos = sorted(ldap_dir.glob("*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum CSV de LDAP em {ldap_dir}.")

    partes: list[pd.DataFrame] = []
    for i, arq in enumerate(arquivos):
        d = pd.read_csv(arq, dtype=str, keep_default_na=False)
        d["_mes"] = i  # ordem cronologica pela ordenacao dos nomes YYYY-MM
        partes.append(d)
    todos = pd.concat(partes, ignore_index=True)

    chave = "user_id" if "user_id" in todos.columns else todos.columns[1]
    if "role" not in todos.columns:
        raise ValueError(
            f"LDAP sem coluna 'role' (colunas: {list(todos.columns)})."
        )
    # registro mais recente por usuario
    todos = todos.sort_values("_mes").drop_duplicates(subset=chave, keep="last")
    todos = todos.drop(columns=["_mes"]).reset_index(drop=True)
    if chave != "user_id":
        todos = todos.rename(columns={chave: "user_id"})
    return todos


def load_answer_key(data_dir: str | Path | None = None) -> pd.DataFrame:
    """Carrega o gabarito oficial de insiders filtrado para a release r4.2.

    Le ``data/answers/insiders.csv`` (colunas dataset,scenario,details,user,
    start,end) e devolve apenas as linhas da release alvo, com a coluna ``user``.
    """
    root = _data_root(data_dir)
    caminho = root / "answers" / "insiders.csv"
    if not caminho.is_file():
        raise FileNotFoundError(
            f"Gabarito ausente: {caminho}. Baixe/extraia com "
            f"python scripts/download_cert.py --extract."
        )
    ak = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    if "dataset" not in ak.columns or "user" not in ak.columns:
        raise ValueError(f"insiders.csv com colunas inesperadas: {list(ak.columns)}.")
    ak = ak[ak["dataset"].str.strip() == RELEASE].reset_index(drop=True)
    return ak


def load_sources(
    data_dir: str | Path | None = None,
    *,
    nrows: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Carrega logon, device, file, email + LDAP + answer_key.

    O ``http`` NAO entra aqui (arquivo gigante); use :func:`iter_http` ou
    :func:`load_http_sample`. ``nrows`` limita a leitura das fontes de atividade
    (util para desenvolvimento sobre um recorte).
    """
    root = _data_root(data_dir)
    d = _dataset_dir(root)
    fontes: dict[str, pd.DataFrame] = {}
    for nome in ("logon", "device", "file", "email"):
        fontes[nome] = _ler_csv(nome, d / f"{nome}.csv", parse_date=True, nrows=nrows)
    fontes["ldap"] = load_ldap(data_dir)
    fontes["answer_key"] = load_answer_key(data_dir)
    return fontes


def iter_http(data_dir: str | Path | None = None, *, chunksize: int = 500_000):
    """Itera o ``http.csv`` em blocos (streaming), com 'date' parseada.

    Permite processar o arquivo gigante sem carrega-lo inteiro na memoria.
    """
    d = _dataset_dir(_data_root(data_dir))
    caminho = d / "http.csv"
    if not caminho.is_file():
        amostra = d / "http.csv.sample"
        if amostra.is_file():
            caminho = amostra
        else:
            raise FileNotFoundError(f"http.csv ausente: {caminho}.")
    for chunk in pd.read_csv(
        caminho, dtype=str, keep_default_na=False, chunksize=chunksize
    ):
        faltando = [c for c in SCHEMAS["http"] if c not in chunk.columns]
        if faltando:
            raise ValueError(f"http.csv sem coluna(s): {', '.join(faltando)}.")
        chunk["date"] = pd.to_datetime(chunk["date"], format=_DATE_FORMAT, errors="coerce")
        yield chunk


def load_http_sample(
    data_dir: str | Path | None = None, *, nrows: int = 1_000_000
) -> pd.DataFrame:
    """Carrega apenas as primeiras ``nrows`` linhas do http (recorte).

    Usa ``http.csv`` se existir; senao, cai para ``http.csv.sample`` (um recorte
    do http gerado durante a extracao, util para desenvolvimento/validacao).
    """
    d = _dataset_dir(_data_root(data_dir))
    caminho = d / "http.csv"
    if not caminho.is_file():
        amostra = d / "http.csv.sample"
        if amostra.is_file():
            caminho = amostra
    return _ler_csv("http", caminho, parse_date=True, nrows=nrows)
