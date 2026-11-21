from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from application.seed import (
    CODIGO_PERFIL_PADRAO,
    CODIGO_TAXONOMIA_PADRAO,
    CURSO_REFERENCIA_PADRAO,
    DISCIPLINAS_PADRAO,
    VERSAO_PERFIL_PADRAO,
)
from domain.travas_classificacao import CONFIANCA_MINIMA_REVISAO
from infrastructure.persistence import (
    RepositorioPerfisClassificacaoSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)
from infrastructure.persistence.models import (
    DisciplinaModel,
    PerfilClassificacaoModel,
    TaxonomiaModel,
)
from infrastructure.persistence.seed import seed_banco_dados


def test_seed_executado_duas_vezes_e_100_por_cento_idempotente(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
) -> None:
    primeiro = seed_banco_dados(database_url=db_teste_url)
    segundo = seed_banco_dados(database_url=db_teste_url)

    assert primeiro.taxonomia_criada is True
    assert primeiro.perfil_criado is True
    assert segundo.taxonomia_criada is False
    assert segundo.perfil_criado is False

    # Mesmos registros e UUIDs preservados
    assert segundo.taxonomia.id == primeiro.taxonomia.id
    assert [d.id for d in segundo.taxonomia.disciplinas] == [d.id for d in primeiro.taxonomia.disciplinas]
    assert segundo.perfil.id == primeiro.perfil.id

    with session_factory_teste() as session:
        total_taxonomias = session.scalar(select(func.count(TaxonomiaModel.id)))
        total_disciplinas = session.scalar(select(func.count(DisciplinaModel.id)))
        total_disciplinas_ativas = session.scalar(
            select(func.count(DisciplinaModel.id)).where(DisciplinaModel.ativa.is_(True))
        )
        total_perfis = session.scalar(select(func.count(PerfilClassificacaoModel.id)))

        assert total_taxonomias == 1
        assert total_disciplinas == 18
        assert total_disciplinas_ativas == 18
        assert total_perfis == 1

    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory_teste)
    taxonomia = repo_tax.buscar_por_codigo(CODIGO_TAXONOMIA_PADRAO)
    assert taxonomia is not None
    assert taxonomia.curso_referencia == CURSO_REFERENCIA_PADRAO
    assert len(taxonomia.ativas()) == 18
    assert [(d.codigo, d.nome, d.ementa) for d in taxonomia.disciplinas] == list(DISCIPLINAS_PADRAO)

    repo_perfis = RepositorioPerfisClassificacaoSqlAlchemy(session_factory_teste)
    perfil = repo_perfis.buscar_por_codigo_e_versao(CODIGO_PERFIL_PADRAO, VERSAO_PERFIL_PADRAO)
    assert perfil is not None
    assert perfil.diretrizes_gerais
    assert f"{CONFIANCA_MINIMA_REVISAO:.2f}" in perfil.diretrizes_gerais
    assert perfil.template_prompt
    for numero in range(1, 16):
        assert f"\n{numero}." in perfil.guia_fronteiras
    assert "Regra anti-distrator" in perfil.guia_fronteiras
