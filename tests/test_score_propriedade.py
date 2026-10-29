"""Teste de propriedade (opcional) do Score_Risco — monotonicidade.

**Feature: threat-hunting-lab, Property 1: Score é monotônico no conjunto de sinais**

O Score_Risco é um modelo **aditivo por presença** de tipo de sinal: cada categoria
presente numa janela contribui, no máximo uma vez, com o peso declarado em
``thlab.score.PESOS`` (todos não-negativos). Portanto, para qualquer conjunto de
sinais, **adicionar** um sinal (ligar uma categoria antes ausente) nunca pode
**diminuir** o score — o score é monotônico não-decrescente no conjunto de sinais
presentes.

Escolha de modelagem (documentada): ``thlab.score.score_por_usuario`` opera sobre
DataFrames (I/O de dados determinístico), o que é custoso e pouco informativo para
PBT. A forma mais limpa e fiel de verificar este invariante é testá-lo diretamente
sobre o modelo aditivo de ``PESOS``, que é a própria **definição** do score: o score
de um conjunto de sinais é a soma dos pesos dos sinais presentes
(``sum(PESOS[t] for t in subconjunto)``). Isso NÃO reimplementa a lógica de detecção
de sinais (quem dispara o quê) — apenas a soma trivial dos pesos, exatamente como o
módulo faz em ``score = sum(sinais.values())``. Usamos os ``PESOS`` reais do módulo,
sem valores fabricados.

A propriedade roda com Hypothesis (≥100 exemplos), que gera subconjuntos de tipos de
sinal e um sinal extra, assegurando o invariante sobre todo o espaço de combinações.

Este teste é **opcional e complementar** — não substitui nenhum teste por exemplo
exigido por R11.

**Validates: Requirements 8.1**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from thlab.score import PESOS

# Tipos de sinal reais declarados no módulo (ex.: logon_fora_hora, usb_fora_hora, ...).
TIPOS_DE_SINAL = sorted(PESOS.keys())


def _score_do_conjunto(sinais: frozenset[str]) -> int:
    """Score de um conjunto de sinais = soma dos pesos presentes (definição do módulo).

    Reproduz exatamente ``score = sum(sinais.values())`` de
    ``thlab.score.score_por_usuario``, usando os ``PESOS`` reais — sem reimplementar
    a detecção de sinais, apenas a soma trivial dos pesos já declarados.
    """
    return sum(PESOS[tipo] for tipo in sinais)


@settings(max_examples=200)
@given(
    subconjunto=st.sets(st.sampled_from(TIPOS_DE_SINAL)).map(frozenset),
    extra=st.sampled_from(TIPOS_DE_SINAL),
)
def test_adicionar_sinal_nunca_diminui_o_score(
    subconjunto: frozenset[str], extra: str
) -> None:
    """Adicionar um sinal a um conjunto nunca diminui o Score_Risco (R8.1).

    Feature: threat-hunting-lab, Property 1: Score é monotônico no conjunto de sinais.
    Como todos os pesos de ``PESOS`` são não-negativos, ``score(S ∪ {extra}) >=
    score(S)`` para qualquer conjunto de sinais ``S`` e qualquer sinal ``extra``.
    """
    # Pré-condição do modelo: os pesos são todos não-negativos (origem da monotonicidade).
    assert all(peso >= 0 for peso in PESOS.values()), (
        "O invariante de monotonicidade exige pesos não-negativos em PESOS; "
        f"PESOS={PESOS!r}"
    )

    score_base = _score_do_conjunto(subconjunto)
    score_ampliado = _score_do_conjunto(subconjunto | {extra})

    assert score_ampliado >= score_base, (
        "Adicionar um sinal diminuiu o score (viola a monotonicidade): "
        f"base={sorted(subconjunto)} (score={score_base}); "
        f"extra={extra!r}; ampliado score={score_ampliado}"
    )
