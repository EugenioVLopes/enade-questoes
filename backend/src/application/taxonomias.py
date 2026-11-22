"""Casos de uso de Taxonomias, Disciplinas e Perfis de Classificação."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from application.exceptions import ConflitoRecursoError, RecursoNaoEncontradoError
from application.ports.repositorios import (
    RepositorioPerfisClassificacao,
    RepositorioTaxonomias,
)
from domain.classificacao import PerfilClassificacao
from domain.exceptions import ErroDominio, ErroValidacaoDominio
from domain.taxonomia import Disciplina, Taxonomia


@dataclass(frozen=True, slots=True)
class DisciplinaInput:
    codigo: str
    nome: str
    ementa: str = ""
    ativa: bool = True


@dataclass(frozen=True, slots=True)
class DisciplinaComImpactoDTO:
    disciplina: Disciplina
    classificacoes_vigentes_impactadas: int


@dataclass(frozen=True, slots=True)
class TaxonomiaComImpactoDTO:
    taxonomia: Taxonomia
    disciplinas: tuple[DisciplinaComImpactoDTO, ...]


def _montar_taxonomia_dto(
    taxonomia: Taxonomia,
    contagens: Mapping[str, int],
) -> TaxonomiaComImpactoDTO:
    itens = tuple(
        DisciplinaComImpactoDTO(
            disciplina=disc,
            classificacoes_vigentes_impactadas=int(contagens.get(disc.codigo, 0)),
        )
        for disc in taxonomia.disciplinas
    )
    return TaxonomiaComImpactoDTO(taxonomia=taxonomia, disciplinas=itens)


def _validar_ordem_opcional(ordem: int | None) -> None:
    if ordem is not None and (isinstance(ordem, bool) or not isinstance(ordem, int) or ordem < 0):
        raise ErroValidacaoDominio(f"'ordem' da Disciplina deve ser inteiro >= 0; recebido: {ordem!r}.")


class ListarTaxonomiasUseCase:
    def __init__(self, repo_taxonomias: RepositorioTaxonomias) -> None:
        self._repo_taxonomias = repo_taxonomias

    def execute(self) -> list[TaxonomiaComImpactoDTO]:
        taxonomias = self._repo_taxonomias.listar()
        if not taxonomias:
            return []
        contagens_por_taxonomia = self._repo_taxonomias.contar_classificacoes_vigentes_por_taxonomias(
            [tax.id for tax in taxonomias]
        )
        return [_montar_taxonomia_dto(tax, contagens_por_taxonomia.get(tax.id, {})) for tax in taxonomias]


class DetalharTaxonomiaUseCase:
    def __init__(self, repo_taxonomias: RepositorioTaxonomias) -> None:
        self._repo_taxonomias = repo_taxonomias

    def execute(self, taxonomia_id: UUID) -> TaxonomiaComImpactoDTO:
        taxonomia = self._repo_taxonomias.buscar_por_id(taxonomia_id)
        if taxonomia is None:
            raise RecursoNaoEncontradoError(f"Taxonomia '{taxonomia_id}' não encontrada.")
        contagens = self._repo_taxonomias.contar_classificacoes_vigentes_por_disciplinas(taxonomia.id)
        return _montar_taxonomia_dto(taxonomia, contagens)


class CriarTaxonomiaUseCase:
    def __init__(self, repo_taxonomias: RepositorioTaxonomias) -> None:
        self._repo_taxonomias = repo_taxonomias

    def execute(
        self,
        codigo: str,
        nome: str,
        curso_referencia: str = "",
        disciplinas: Sequence[DisciplinaInput] = (),
    ) -> TaxonomiaComImpactoDTO:
        if isinstance(disciplinas, str | bytes | bytearray | memoryview | Mapping) or not isinstance(
            disciplinas, Iterable
        ):
            raise ErroValidacaoDominio("'disciplinas' deve ser uma coleção de DisciplinaInput.")

        disciplinas_dominio: list[Disciplina] = []
        for item in disciplinas:
            if not isinstance(item, DisciplinaInput):
                raise ErroValidacaoDominio(f"Item de 'disciplinas' inválido: {item!r}.")
            if not isinstance(item.ativa, bool):
                raise ErroValidacaoDominio("'ativa' da Disciplina deve ser booleano.")
            disciplinas_dominio.append(
                Disciplina(
                    codigo=item.codigo,
                    nome=item.nome,
                    ementa=item.ementa,
                    ativa=item.ativa,
                )
            )

        taxonomia = Taxonomia(
            codigo=codigo,
            nome=nome,
            curso_referencia=curso_referencia,
            disciplinas=disciplinas_dominio,
        )

        if self._repo_taxonomias.buscar_por_codigo(taxonomia.codigo) is not None:
            raise ConflitoRecursoError(f"Já existe uma Taxonomia cadastrada com o código '{taxonomia.codigo}'.")

        try:
            salva = self._repo_taxonomias.salvar(taxonomia)
        except ErroDominio:
            raise
        except Exception:
            if self._repo_taxonomias.buscar_por_codigo(taxonomia.codigo) is not None:
                raise ConflitoRecursoError(
                    f"Já existe uma Taxonomia cadastrada com o código '{taxonomia.codigo}'."
                ) from None
            raise

        return _montar_taxonomia_dto(salva, {})


class AtualizarTaxonomiaUseCase:
    def __init__(self, repo_taxonomias: RepositorioTaxonomias) -> None:
        self._repo_taxonomias = repo_taxonomias

    def execute(
        self,
        taxonomia_id: UUID,
        *,
        nome: str | None = None,
        curso_referencia: str | None = None,
    ) -> TaxonomiaComImpactoDTO:
        taxonomia = self._repo_taxonomias.buscar_por_id(taxonomia_id)
        if taxonomia is None:
            raise RecursoNaoEncontradoError(f"Taxonomia '{taxonomia_id}' não encontrada.")

        if nome is not None:
            if not isinstance(nome, str) or not nome.strip():
                raise ErroValidacaoDominio("'nome' da Taxonomia não pode ser vazio.")
            taxonomia.nome = nome.strip()

        if curso_referencia is not None:
            if not isinstance(curso_referencia, str):
                raise ErroValidacaoDominio("'curso_referencia' da Taxonomia deve ser texto.")
            taxonomia.curso_referencia = curso_referencia.strip()

        salva = self._repo_taxonomias.salvar(taxonomia)
        contagens = self._repo_taxonomias.contar_classificacoes_vigentes_por_disciplinas(salva.id)
        return _montar_taxonomia_dto(salva, contagens)


class AdicionarDisciplinaUseCase:
    def __init__(self, repo_taxonomias: RepositorioTaxonomias) -> None:
        self._repo_taxonomias = repo_taxonomias

    def execute(
        self,
        taxonomia_id: UUID,
        *,
        codigo: str,
        nome: str,
        ementa: str = "",
        ativa: bool = True,
        ordem: int | None = None,
    ) -> tuple[UUID, DisciplinaComImpactoDTO]:
        taxonomia = self._repo_taxonomias.buscar_por_id(taxonomia_id)
        if taxonomia is None:
            raise RecursoNaoEncontradoError(f"Taxonomia '{taxonomia_id}' não encontrada.")

        _validar_ordem_opcional(ordem)
        if not isinstance(ativa, bool):
            raise ErroValidacaoDominio("'ativa' da Disciplina deve ser booleano.")

        nova = Disciplina(
            codigo=codigo,
            nome=nome,
            ementa=ementa,
            ativa=ativa,
        )

        if nova.codigo in taxonomia.mapa_todas():
            raise ConflitoRecursoError(
                f"Já existe uma Disciplina com código '{nova.codigo}' na Taxonomia '{taxonomia.codigo}'."
            )

        try:
            salva = self._repo_taxonomias.adicionar_disciplina(taxonomia.id, nova, ordem=ordem)
        except ErroDominio:
            raise
        except Exception:
            recarregada = self._repo_taxonomias.buscar_por_id(taxonomia.id)
            if recarregada is not None and nova.codigo in recarregada.mapa_todas():
                raise ConflitoRecursoError(
                    f"Já existe uma Disciplina com código '{nova.codigo}' na Taxonomia '{taxonomia.codigo}'."
                ) from None
            raise

        return (
            taxonomia.id,
            DisciplinaComImpactoDTO(
                disciplina=salva,
                classificacoes_vigentes_impactadas=0,
            ),
        )


class AtualizarDisciplinaUseCase:
    def __init__(self, repo_taxonomias: RepositorioTaxonomias) -> None:
        self._repo_taxonomias = repo_taxonomias

    def execute(
        self,
        disciplina_id: UUID,
        *,
        nome: str | None = None,
        ementa: str | None = None,
        ativa: bool | None = None,
        ordem: int | None = None,
    ) -> tuple[UUID, DisciplinaComImpactoDTO]:
        encontrada = self._repo_taxonomias.buscar_disciplina_por_id(disciplina_id)
        if encontrada is None:
            raise RecursoNaoEncontradoError(f"Disciplina '{disciplina_id}' não encontrada.")

        taxonomia_id, disciplina = encontrada
        _validar_ordem_opcional(ordem)

        if nome is not None:
            if not isinstance(nome, str) or not nome.strip():
                raise ErroValidacaoDominio("'nome' da Disciplina não pode ser vazio.")
            disciplina.nome = nome.strip()

        if ementa is not None:
            if not isinstance(ementa, str):
                raise ErroValidacaoDominio("'ementa' da Disciplina deve ser texto.")
            disciplina.ementa = ementa.strip()

        if ativa is not None:
            if not isinstance(ativa, bool):
                raise ErroValidacaoDominio("'ativa' da Disciplina deve ser booleano.")
            disciplina.ativa = ativa

        salva = self._repo_taxonomias.salvar_disciplina(taxonomia_id, disciplina, ordem=ordem)
        impactadas = self._repo_taxonomias.contar_classificacoes_vigentes_por_disciplina(taxonomia_id, salva.codigo)
        return (
            taxonomia_id,
            DisciplinaComImpactoDTO(
                disciplina=salva,
                classificacoes_vigentes_impactadas=impactadas,
            ),
        )


class ListarPerfisClassificacaoUseCase:
    def __init__(self, repo_perfis: RepositorioPerfisClassificacao) -> None:
        self._repo_perfis = repo_perfis

    def execute(self) -> list[PerfilClassificacao]:
        return self._repo_perfis.listar()


class CriarPerfilClassificacaoUseCase:
    def __init__(self, repo_perfis: RepositorioPerfisClassificacao) -> None:
        self._repo_perfis = repo_perfis

    def execute(
        self,
        *,
        versao: str,
        codigo: str | None = None,
        perfil_base_id: UUID | None = None,
        diretrizes_gerais: str | None = None,
        guia_fronteiras: str | None = None,
        template_prompt: str | None = None,
        descricao: str | None = None,
    ) -> PerfilClassificacao:
        if perfil_base_id is not None:
            base = self._repo_perfis.buscar_por_id(perfil_base_id)
            if base is None:
                raise RecursoNaoEncontradoError(f"Perfil base '{perfil_base_id}' não encontrado.")
            codigo_efetivo = base.codigo if codigo is None else codigo
            diretrizes_efetivas = base.diretrizes_gerais if diretrizes_gerais is None else diretrizes_gerais
            guia_efetivo = base.guia_fronteiras if guia_fronteiras is None else guia_fronteiras
            template_efetivo = base.template_prompt if template_prompt is None else template_prompt
            descricao_efetiva = base.descricao if descricao is None else descricao
        else:
            codigo_efetivo = "" if codigo is None else codigo
            diretrizes_efetivas = "" if diretrizes_gerais is None else diretrizes_gerais
            guia_efetivo = "" if guia_fronteiras is None else guia_fronteiras
            template_efetivo = "" if template_prompt is None else template_prompt
            descricao_efetiva = "" if descricao is None else descricao

        novo = PerfilClassificacao(
            codigo=codigo_efetivo,
            versao=versao,
            diretrizes_gerais=diretrizes_efetivas,
            guia_fronteiras=guia_efetivo,
            template_prompt=template_efetivo,
            descricao=descricao_efetiva,
        )

        if self._repo_perfis.buscar_por_codigo_e_versao(novo.codigo, novo.versao) is not None:
            raise ConflitoRecursoError(
                f"Já existe um PerfilClassificacao cadastrado para ({novo.codigo}, {novo.versao})."
            )

        try:
            return self._repo_perfis.salvar(novo)
        except ErroDominio:
            raise
        except Exception:
            if self._repo_perfis.buscar_por_codigo_e_versao(novo.codigo, novo.versao) is not None:
                raise ConflitoRecursoError(
                    f"Já existe um PerfilClassificacao cadastrado para ({novo.codigo}, {novo.versao})."
                ) from None
            raise
