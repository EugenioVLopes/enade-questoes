"""Apoio compartilhado pelos testes de integração da API de Questões (dados montados via repositórios)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.classificacao import IdentidadeClassificador, ResultadoChamada
from domain.classificacao import Classificacao, DivergenciaReclassificacao, ExecucaoClassificacao, PerfilClassificacao
from domain.enums import (
    CodigoAlertaExtracao,
    EscopoExecucao,
    LetraAlternativa,
    OrigemClassificacao,
    SituacaoGabarito,
    StatusClassificacao,
)
from domain.prova import AlertaExtracao, Alternativa, Gabarito, Prova, Questao
from domain.taxonomia import Disciplina, Taxonomia
from infrastructure.config import Settings
from infrastructure.persistence.repositorios import (
    RepositorioClassificacoesSqlAlchemy,
    RepositorioDivergenciasReclassificacaoSqlAlchemy,
    RepositorioExecucoesClassificacaoSqlAlchemy,
    RepositorioPerfisClassificacaoSqlAlchemy,
    RepositorioProvasSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)
from presentation.main import build_app

T0 = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


class ClassificadorProibido:
    """O classificador nunca deve ser chamado pelos endpoints desta tarefa."""

    @property
    def identidade(self) -> IdentidadeClassificador:
        return IdentidadeClassificador(provider="fake", model="fake-v1", base_url="http://fake.local")

    def classificar_estruturado(self, **_kwargs: object) -> ResultadoChamada:
        raise AssertionError("Classificador não deveria ser chamado nestes testes.")


@dataclass
class Repos:
    session_factory: sessionmaker[Session]
    provas: RepositorioProvasSqlAlchemy
    questoes: RepositorioQuestoesSqlAlchemy
    classificacoes: RepositorioClassificacoesSqlAlchemy
    taxonomias: RepositorioTaxonomiasSqlAlchemy
    divergencias: RepositorioDivergenciasReclassificacaoSqlAlchemy
    execucoes: RepositorioExecucoesClassificacaoSqlAlchemy
    perfis: RepositorioPerfisClassificacaoSqlAlchemy


def criar_repos(session_factory: sessionmaker[Session]) -> Repos:
    return Repos(
        session_factory=session_factory,
        provas=RepositorioProvasSqlAlchemy(session_factory),
        questoes=RepositorioQuestoesSqlAlchemy(session_factory),
        classificacoes=RepositorioClassificacoesSqlAlchemy(session_factory),
        taxonomias=RepositorioTaxonomiasSqlAlchemy(session_factory),
        divergencias=RepositorioDivergenciasReclassificacaoSqlAlchemy(session_factory),
        execucoes=RepositorioExecucoesClassificacaoSqlAlchemy(session_factory),
        perfis=RepositorioPerfisClassificacaoSqlAlchemy(session_factory),
    )


def criar_app(db_url: str, data_dir: Path, armazenamento: ArmazenamentoArquivos | None = None) -> FastAPI:
    return build_app(
        Settings(database_url=db_url, data_dir=data_dir),
        classificador=ClassificadorProibido(),
        armazenamento=armazenamento,
    )


def png_bytes(cor: tuple[int, int, int] = (20, 90, 180)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (40, 24), color=cor).save(buf, format="PNG")
    return buf.getvalue()


def jpeg_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (40, 24), color=(200, 40, 40)).save(buf, format="JPEG")
    return buf.getvalue()


def alternativas_completas(prefixo: str = "Alternativa") -> list[Alternativa]:
    return [
        Alternativa(letra=letra, texto=f"{prefixo} {letra.value} com texto suficiente.") for letra in LetraAlternativa
    ]


def criar_taxonomia(repos: Repos) -> Taxonomia:
    return repos.taxonomias.salvar(
        Taxonomia(
            codigo="enade-ec",
            nome="ENADE EC",
            curso_referencia="Engenharia de Computação",
            disciplinas=[
                Disciplina("redes", "Redes", "OSPF e TCP/IP"),
                Disciplina("algoritmos", "Algoritmos", "Complexidade e grafos"),
                Disciplina("sistemas-operacionais", "Sistemas Operacionais", "Escalonamento"),
                Disciplina("legada", "Disciplina arquivada", "Antiga", ativa=False),
            ],
        )
    )


def criar_execucao(repos: Repos, taxonomia: Taxonomia) -> ExecucaoClassificacao:
    perfil = repos.perfis.salvar(
        PerfilClassificacao(
            codigo="perfil-teste",
            versao="v1",
            diretrizes_gerais="Classifique com precisão.",
            guia_fronteiras="Redes x Algoritmos",
            template_prompt="Questão: {enunciado}",
        )
    )
    return repos.execucoes.salvar(
        ExecucaoClassificacao(
            taxonomia_id=taxonomia.id,
            perfil_id=perfil.id,
            snapshot_taxonomia=taxonomia.snapshot_dict(),
            snapshot_perfil=perfil.snapshot_dict(),
            escopo=EscopoExecucao.TODAS,
        )
    )


def criar_prova(repos: Repos, ano: int, curso: str = "Engenharia de Computação") -> Prova:
    return repos.provas.salvar(Prova(exame="ENADE", curso=curso, ano=ano))


def criar_questao(
    repos: Repos,
    prova: Prova,
    numero: int,
    enunciado: str,
    *,
    alternativas: list[Alternativa] | None = None,
    alertas: tuple[CodigoAlertaExtracao, ...] = (),
    gabarito: Gabarito | None = None,
) -> Questao:
    return repos.questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=numero,
            enunciado=enunciado,
            alternativas=alternativas if alternativas is not None else alternativas_completas(),
            alertas_extracao=[AlertaExtracao(codigo=c) for c in alertas],
            gabarito=gabarito or Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A),
        )
    )


def classificar(
    repos: Repos,
    questao: Questao,
    taxonomia: Taxonomia,
    principal: str,
    *,
    secundarias: tuple[str, ...] = (),
    topicos: tuple[str, ...] = ("topico-base",),
    confianca: float = 0.9,
    status: StatusClassificacao = StatusClassificacao.PENDENTE_REVISAO,
    origem: OrigemClassificacao = OrigemClassificacao.AUTOMATICA,
    prioritaria: bool = False,
    execucao_id: object | None = None,
) -> Classificacao:
    return repos.classificacoes.salvar(
        Classificacao(
            questao_id=questao.id,
            taxonomia_id=taxonomia.id,
            disciplina_principal=principal,
            disciplinas_secundarias=secundarias,
            topicos=topicos,
            justificativa="Justificativa original da IA.",
            confianca=confianca,
            origem=origem,
            status=status,
            vigente=True,
            revisao_prioritaria=prioritaria,
            execucao_id=execucao_id,  # type: ignore[arg-type]
            criada_em=T0,
            revisada_em=T0 if status == StatusClassificacao.APROVADA else None,
        )
    )


def abrir_divergencia(
    repos: Repos,
    questao: Questao,
    taxonomia: Taxonomia,
    execucao: ExecucaoClassificacao,
    vigente: Classificacao,
    candidata: str = "redes",
) -> DivergenciaReclassificacao:
    return repos.divergencias.salvar(
        DivergenciaReclassificacao(
            questao_id=questao.id,
            taxonomia_id=taxonomia.id,
            execucao_id=execucao.id,
            classificacao_vigente_id=vigente.id,
            disciplina_principal_candidata=candidata,
            topicos_candidatos=("roteamento-ospf",),
            justificativa_candidata="Candidata da reexecução.",
            confianca_candidata=0.9,
            criada_em=T0,
        )
    )


def contar(repos: Repos, modelo: type) -> int:
    """Conta linhas de um modelo ORM (ex.: ClassificacaoModel, ExecucaoClassificacaoModel)."""
    with repos.session_factory() as session:
        return int(session.scalar(select(func.count()).select_from(modelo)) or 0)


ENUNCIADO_BOM = "Considere o protocolo de roteamento dinâmico OSPF aplicado em redes corporativas."


class RepoComGancho:
    """Delega ao repositório real e executa um gancho logo após a leitura (simula escrita concorrente)."""

    def __init__(self, real: Any, metodo: str, gancho: Any) -> None:
        self._real = real
        self._metodo = metodo
        self._gancho = gancho
        self._disparado = False

    def __getattr__(self, nome: str) -> Any:
        atributo = getattr(self._real, nome)
        if nome != self._metodo:
            return atributo

        def envolvido(*args: Any, **kwargs: Any) -> Any:
            resultado = atributo(*args, **kwargs)
            if not self._disparado:
                self._disparado = True
                self._gancho()
            return resultado

        return envolvido
