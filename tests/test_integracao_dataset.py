"""Testes de integração sobre o dataset real do CERT r4.2.

Só rodam se o dataset tiver sido baixado e extraído (data/r4.2 presente); caso
contrário são pulados (skip), já que o dataset não é versionado no repositório.
Validam o schema real carregado pelos loaders e que os exercícios executam sobre
um recorte, produzindo resultados coerentes (sem travar valores, que variam com o
recorte).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thlab import loaders

_DATA = Path(__file__).resolve().parent.parent / "data"
_TEM_DATASET = (_DATA / "r4.2" / "logon.csv").is_file()

pytestmark = pytest.mark.skipif(
    not _TEM_DATASET,
    reason="dataset r4.2 ausente (baixe com scripts/download_cert.py --extract)",
)


def test_load_sources_schema_real():
    s = loaders.load_sources(nrows=50_000)
    assert set(s) == {"logon", "device", "file", "email", "ldap", "answer_key"}
    assert list(s["logon"].columns) == ["id", "date", "user", "pc", "activity"]
    assert list(s["file"].columns) == ["id", "date", "user", "pc", "filename", "content"]
    assert "user_id" in s["ldap"].columns and "role" in s["ldap"].columns


def test_answer_key_r42_tem_insiders():
    ak = loaders.load_answer_key()
    assert ak.shape[0] > 0
    assert (ak["dataset"].astype(str) == "4.2").all()


def test_exercicios_executam_sobre_recorte():
    from exercises import (ex02_usb, ex03_usb_fora_hora, ex04_copia_arquivos,
                           ex05_correlacao, ex06_validacao)
    s = loaders.load_sources(nrows=50_000)
    assert isinstance(ex02_usb.run(s).usuarios_exfiltracao_usb, list)
    assert isinstance(ex03_usb_fora_hora.run(s), list)
    assert isinstance(ex04_copia_arquivos.run(s), list)
    ranking = ex05_correlacao.run(s, http=None)
    vereditos = ex06_validacao.run(ranking, s["answer_key"])
    assert isinstance(vereditos, list)
