#!/usr/bin/env python3
"""Ingest das fontes do CERT r4.2 no OpenSearch (caminho exploratorio opcional).

Por PADRAO ingere o dataset INTEIRO. As fontes de atividade (logon, device, file,
email) e o http.csv sao lidas em STREAMING (blocos), indexando bloco a bloco via
API _bulk, para nao carregar os arquivos grandes (http ~14 GB) na memoria.

Limites sao OPCIONAIS: passe --limite N (fontes de atividade) e/ou --http-limite N
para restringir; sem eles, vai tudo.

Cria um indice por fonte: th-logon, th-device, th-file, th-email, th-http.
Usa so a stdlib (urllib) para o transporte HTTP.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime
import urllib.error
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA = _REPO_ROOT / "data" / "r4.2"
_INDEX_PREFIX = "th-"
_DEFAULT = "localhost:9200"
_TIMEOUT = 120

# Fontes a ingerir e suas colunas (schema r4.2).
FONTES = {
    "logon": ["id", "date", "user", "pc", "activity"],
    "device": ["id", "date", "user", "pc", "activity"],
    "file": ["id", "date", "user", "pc", "filename", "content"],
    "email": ["id", "date", "user", "pc", "to", "cc", "bcc", "from", "size", "attachments", "content"],
    "http": ["id", "date", "user", "pc", "url", "content"],
}
# Colunas de texto longo que NAO vamos indexar (economiza espaco/tempo): o corpo
# sintetico de file/email/http e irrelevante para a exploracao dos sinais.
DESCARTAR = {"content"}


def _data_iso(valor: str) -> str | None:
    """Converte 'MM/DD/YYYY HH:MM:SS' do CERT para ISO-8601; None se vazio/invalido."""
    valor = (valor or "").strip()
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%m/%d/%Y %H:%M:%S").isoformat()
    except ValueError:
        return None


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


def _criar_indice(base, indice, colunas):
    # Mapping explicito: `date` como tipo date (ISO-8601); demais campos como
    # keyword (bom para filtros exatos por user/pc/activity/url/filename).
    props = {}
    for c in colunas:
        if c in DESCARTAR:
            continue
        if c == "date":
            props[c] = {"type": "date"}
        else:
            props[c] = {"type": "keyword"}
    corpo = json.dumps({
        "settings": {"number_of_replicas": 0, "refresh_interval": "-1"},
        "mappings": {"properties": props},
    }).encode("utf-8")
    try:
        _req("PUT", base + "/" + indice, data=corpo, content_type="application/json")
    except urllib.error.HTTPError as e:
        if e.code != 400:  # 400 = index ja existe
            raise


def _finalizar_indice(base, indice):
    # Religa o refresh e forca um flush para deixar os docs pesquisaveis.
    corpo = json.dumps({"index": {"refresh_interval": "1s"}}).encode("utf-8")
    try:
        _req("PUT", base + "/" + indice + "/_settings", data=corpo, content_type="application/json")
        _req("POST", base + "/" + indice + "/_refresh")
    except urllib.error.URLError:
        pass


def _enviar_bulk(base, indice, linhas_ndjson):
    corpo = ("".join(linhas_ndjson)).encode("utf-8")
    status, resp = _req("POST", base + "/_bulk", data=corpo,
                        content_type="application/x-ndjson")
    payload = json.loads(resp)
    if payload.get("errors"):
        for item in payload.get("items", []):
            acao = next(iter(item.values()))
            if acao.get("error"):
                raise RuntimeError(f"OpenSearch rejeitou doc em '{indice}': {acao['error']}")
    return


def _indexar_streaming(base, nome, colunas, caminho, *, limite=None, lote=10000):
    indice = _INDEX_PREFIX + nome
    _criar_indice(base, indice, colunas)
    manter = [c for c in colunas if c not in DESCARTAR]
    action = json.dumps({"index": {"_index": indice}}) + "\n"

    total = 0
    buffer: list[str] = []
    with open(caminho, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            doc = {c: row.get(c, "") for c in manter}
            if "date" in doc:
                iso = _data_iso(doc["date"])
                if iso is not None:
                    doc["date"] = iso
                else:
                    doc.pop("date", None)
            # _id deterministico = id unico da linha do CERT. Torna a ingestao
            # IDEMPOTENTE: re-indexar a mesma linha sobrescreve (nao duplica), o
            # que deixa a carga retomavel apos qualquer interrupcao.
            doc_id = row.get("id") or None
            if doc_id:
                meta = json.dumps({"index": {"_index": indice, "_id": doc_id}}) + "\n"
            else:
                meta = action
            buffer.append(meta)
            buffer.append(json.dumps(doc, ensure_ascii=False) + "\n")
            total += 1
            if len(buffer) >= lote * 2:
                _enviar_bulk(base, indice, buffer)
                buffer.clear()
                if total % 100000 == 0:
                    print(f"    {nome}: {total} docs...", flush=True)
            if limite and total >= limite:
                break
    if buffer:
        _enviar_bulk(base, indice, buffer)
    _finalizar_indice(base, indice)
    return total


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ingest_opensearch.py",
                                description="Ingere as fontes do r4.2 no OpenSearch (tudo por padrao).")
    p.add_argument("--host", default=os.environ.get("OPENSEARCH_HOST", _DEFAULT))
    p.add_argument("--limite", type=int, default=None,
                   help="Opcional: max. de linhas por fonte de atividade (logon/device/file/email).")
    p.add_argument("--http-limite", type=int, default=None,
                   help="Opcional: max. de linhas do http.csv. Sem isso, ingere o http inteiro.")
    p.add_argument("--lote", type=int, default=10000, help="Tamanho do lote _bulk.")
    p.add_argument("--so", default=None,
                   help="Opcional: ingerir so uma fonte (ex.: --so http).")
    args = p.parse_args(argv)

    base = _norm(args.host)
    try:
        _req("GET", base + "/")
    except urllib.error.URLError as e:
        print("ERRO: nao conectou ao OpenSearch em " + base + ": "
              + str(getattr(e, "reason", e)) + ". Suba com "
              + "'docker compose --profile opensearch up -d'.", file=sys.stderr)
        return 1

    alvos = [args.so] if args.so else list(FONTES.keys())
    print("Conectado a " + base + ". Ingestao (tudo por padrao)...")
    grande_total = 0
    for nome in alvos:
        if nome not in FONTES:
            print("  fonte desconhecida: " + str(nome), file=sys.stderr)
            return 2
        caminho = _DATA / (nome + ".csv")
        if not caminho.is_file():
            print("  " + nome + ": arquivo ausente (" + str(caminho) + "), pulando.")
            continue
        lim = args.http_limite if nome == "http" else args.limite
        print("  " + _INDEX_PREFIX + nome + ": indexando" + (f" (limite {lim})" if lim else " TUDO") + "...")
        n = _indexar_streaming(base, nome, FONTES[nome], caminho, limite=lim, lote=args.lote)
        grande_total += n
        print("  " + _INDEX_PREFIX + nome + ": " + str(n) + " docs.")

    print("Ingestao concluida: " + str(grande_total) + " docs. Explore em http://localhost:5601")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
