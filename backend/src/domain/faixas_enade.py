"""Regra determinística de faixas padrão do Componente Específico do ENADE."""

from __future__ import annotations

from domain.exceptions import ErroValidacaoDominio, FaixaQuestoesIndisponivelError
from domain.prova import FaixaQuestoes


def resolver_faixa_componente_especifico(
    ano: int,
    questao_inicio: int | None = None,
    questao_fim: int | None = None,
) -> FaixaQuestoes:
    """Resolve a faixa oficial de questões objetivas do Componente Específico por ano.

    Regras oficiais:
    - 2014–2019: 09–35
    - 2023: 10–38
    - 2026+: 16–45
    - Override explícito exige (questao_inicio, questao_fim) simultaneamente.
    - Anos fora dessas faixas sem override explícito levantam FaixaQuestoesIndisponivelError.
    """
    if isinstance(ano, bool) or not isinstance(ano, int) or ano < 1900:
        raise ErroValidacaoDominio(f"'ano' deve ser inteiro >= 1900; recebido: {ano!r}.")

    if (questao_inicio is None) != (questao_fim is None):
        raise ErroValidacaoDominio("Override explícito de faixa exige 'questao_inicio' e 'questao_fim' juntos.")

    if questao_inicio is not None and questao_fim is not None:
        return FaixaQuestoes(inicio=questao_inicio, fim=questao_fim)

    if 2014 <= ano <= 2019:
        return FaixaQuestoes(inicio=9, fim=35)
    if ano == 2023:
        return FaixaQuestoes(inicio=10, fim=38)
    if ano >= 2026:
        return FaixaQuestoes(inicio=16, fim=45)

    raise FaixaQuestoesIndisponivelError(
        f"Nenhuma faixa padrão de Componente Específico conhecida para o ano {ano}. "
        "Informe explicitamente 'questao_inicio' e 'questao_fim'."
    )
