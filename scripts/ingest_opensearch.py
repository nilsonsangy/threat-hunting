#!/usr/bin/env python3
"""Ingest opcional das fontes do CERT r4.2 no OpenSearch (caminho exploratorio).

Le as fontes reais via thlab.loaders e indexa cada uma num indice proprio
(th-logon, th-device, th-file, th-email, th-http) via API _bulk. Opcional: nada
em exercises/ ou tests/ depende disso. Usa so a stdlib (urllib).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from thlab import loaders  # noqa: E402

_INDEX_PREFIX = "th-"
_DEFAULT = "localhost:9200"
_TIMEOUT = 60


def _json_default(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def _norm(h: str) -> str:
    h = h.strip()
    if not h.startswith(("http://", "https://")):
        h = "http://" + h
    return h.rstrip("/")


def _req(method, url, *, data=None, content_type=None):
    r = urllib.request.Request(url, data=data, method=method)
    if content_type:
        r.add_header("Content-Type", content_type)
    with urllib.request.urlopen(r, timeout=_TIMEOUT) as resp:
        return resp.status, resp.read()


def _criar(base, indice):
    try:
        _req("PUT", base + "/" + indice)
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise


def _bulk(indice, registros):
    linhas = []
    for doc in registros:
        linhas.append(json.dumps({"index": {"_index": indice}}))
        linhas.append(json.dumps(doc, default=_json_default, ensure_ascii=False))
    return ("\n".join(linhas) + "\n").encode("utf-8")


def _indexar(base, nome, df, lote=5000):
    indice = _INDEX_PREFIX + nome
    _criar(base, indice)
    registros = df.to_dict(orient="records")
    total = 0
    for i in range(0, len(registros), lote):
        parte = registros[i:i + lote]
        _req("POST", base + "/_bulk", data=_bulk(indice, parte),
             content_type="application/x-ndjson")
        total += len(parte)
    return total


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ingest_opensearch.py",
                                description="Ingest opcional das fontes do r4.2.")
    p.add_argument("--host", default=os.environ.get("OPENSEARCH_HOST", _DEFAULT))
    p.add_argument("--limite", type=int, default=200_000)
    p.add_argument("--http-amostra", type=int, default=200_000)
    args = p.parse_args(argv)

    base = _norm(args.host)
    try:
        _req("GET", base + "/")
    except urllib.error.URLError as e:
        print("ERRO: nao conectou ao OpenSearch em " + base + ": "
              + str(getattr(e, "reason", e)) + ". Suba com "
              + "'docker compose --profile opensearch up -d'.", file=sys.stderr)
        return 1

    try:
        s = loaders.load_sources(nrows=args.limite)
    except (FileNotFoundError, ValueError) as e:
        print("ERRO ao carregar os dados: " + str(e), file=sys.stderr)
        return 2

    print("Conectado a " + base + ". Ingerindo...")
    total = 0
    for nome in ("logon", "device", "file", "email"):
        n = _indexar(base, nome, s[nome])
        total += n
        print("  " + _INDEX_PREFIX + nome + ": " + str(n) + " docs")
    try:
        http = loaders.load_http_sample(nrows=args.http_amostra)
        n = _indexar(base, "http", http)
        total += n
        print("  " + _INDEX_PREFIX + "http: " + str(n) + " docs")
    except FileNotFoundError:
        print("  (http nao ingerido: sem http.csv/.sample)")

    print("Ingest concluido: " + str(total) + " docs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
