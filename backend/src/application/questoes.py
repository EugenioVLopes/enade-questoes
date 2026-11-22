"""Casos de uso de consulta, detalhe e edição curada de Questões, Alertas e Ativos Visuais."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from application.busca import buscar_taxonomia_ou_404
from application.exceptions import ConflitoRecursoError, RecursoNaoEncontradoError
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.consulta_questoes import (
    ConsultaQuestoes,
    ContadoresRevisao,
    FiltroConsultaQuestoes,
    OrdenacaoConsulta,
    PaginaConsultaQuestoes,
    StatusRevisao,
)
from application.ports.imagem import NormalizadorImagem
from application.ports.repositorios import (
    RepositorioAtivosVisuais,
    RepositorioClassificacoes,
    RepositorioProvas,
    RepositorioQuestoes,
    RepositorioTaxonomias,
)
from domain.alertas_extracao import marcar_alerta_verificado, reavaliar_alertas_estruturais
from domain.classificacao import Classificacao, DivergenciaReclassificacao
from domain.enums import LetraAlternativa, OrigemAtivoVisual, SituacaoGabarito, StatusClassificacao
from domain.exceptions import ErroValidacaoDominio
from domain.prova import AlertaExtracao, Alternativa, AtivoVisual, Gabarito, Prova, Questao
from domain.taxonomia import normalizar_topico
from domain.travas_classificacao import calcular_revisao_prioritaria

TAMANHO_MAXIMO_IMAGEM_BYTES = 10 * 1024 * 1024
ANO_MINIMO = 1900
ANO_MAXIMO = 2100
PAGINA_MAXIMA = 100_000


def _agora_utc() -> datetime:
    return datetime.now(UTC)


def _buscar_questao(repo_questoes: RepositorioQuestoes, questao_id: UUID) -> Questao:
    questao = repo_questoes.buscar_por_id(questao_id)
    if questao is None:
        raise RecursoNaoEncontradoError(f"Questão '{questao_id}' não encontrada.")
    return questao


def recalcular_revisao_prioritaria_pendentes(
    questao: Questao,
    repo_classificacoes: RepositorioClassificacoes,
) -> int:
    """Recalcula `revisao_prioritaria` das Classificações vigentes pendentes após edição (sem acionar LLM)."""
    alteradas = 0
    for classificacao in repo_classificacoes.listar_vigentes_por_questao(questao.id):
        if classificacao.status != StatusClassificacao.PENDENTE_REVISAO:
            continue
        nova_prioridade = calcular_revisao_prioritaria(
            confianca=classificacao.confianca,
            alertas_extracao=questao.alertas_extracao,
            alertas_saneamento=classificacao.alertas_validacao,
        )
        if nova_prioridade != classificacao.revisao_prioritaria and repo_classificacoes.atualizar_revisao_prioritaria(
            classificacao.id, nova_prioridade
        ):
            alteradas += 1
    return alteradas


# ---------------------------------------------------------------------------
# Consulta e fila de revisão
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParametrosConsultaQuestoes:
    q: str | None = None
    prova_id: UUID | None = None
    ano: int | None = None
    taxonomia_id: UUID | None = None
    disciplina_id: UUID | None = None
    incluir_secundarias: bool = True
    topico: str | None = None
    status_revisao: StatusRevisao | None = None
    revisao_prioritaria: bool | None = None
    com_divergencia: bool | None = None
    usa_disciplina_arquivada: bool | None = None
    situacao_gabarito: SituacaoGabarito | None = None
    com_alerta_extracao: bool | None = None
    ordenacao: OrdenacaoConsulta = OrdenacaoConsulta.CONSULTA
    pagina: int = 1
    tamanho_pagina: int = 50


@dataclass(frozen=True, slots=True)
class ResultadoConsultaQuestoes:
    pagina: PaginaConsultaQuestoes
    numero_pagina: int
    tamanho_pagina: int
    taxonomia_id: UUID | None
    contadores: ContadoresRevisao | None


class ConsultarQuestoesUseCase:
    TAMANHO_PAGINA_MAXIMO = 200

    def __init__(self, *, consulta: ConsultaQuestoes, repo_taxonomias: RepositorioTaxonomias) -> None:
        self._consulta = consulta
        self._repo_taxonomias = repo_taxonomias

    def execute(self, parametros: ParametrosConsultaQuestoes) -> ResultadoConsultaQuestoes:
        if not 1 <= parametros.pagina <= PAGINA_MAXIMA:
            raise ErroValidacaoDominio(f"'pagina' deve estar entre 1 e {PAGINA_MAXIMA}; recebido: {parametros.pagina}.")
        if parametros.ano is not None and not ANO_MINIMO <= parametros.ano <= ANO_MAXIMO:
            raise ErroValidacaoDominio(
                f"'ano' deve estar entre {ANO_MINIMO} e {ANO_MAXIMO}; recebido: {parametros.ano}."
            )
        if parametros.q is not None and "\x00" in parametros.q:
            raise ErroValidacaoDominio("'q' não pode conter o caractere NUL.")
        if parametros.topico is not None and "\x00" in parametros.topico:
            raise ErroValidacaoDominio("'topico' não pode conter o caractere NUL.")
        if not 1 <= parametros.tamanho_pagina <= self.TAMANHO_PAGINA_MAXIMO:
            raise ErroValidacaoDominio(
                f"'tamanho_pagina' deve estar entre 1 e {self.TAMANHO_PAGINA_MAXIMO}; "
                f"recebido: {parametros.tamanho_pagina}."
            )

        taxonomia_id = parametros.taxonomia_id
        disciplina_codigo: str | None = None
        if parametros.disciplina_id is not None:
            encontrada = self._repo_taxonomias.buscar_disciplina_por_id(parametros.disciplina_id)
            if encontrada is None:
                raise RecursoNaoEncontradoError(f"Disciplina '{parametros.disciplina_id}' não encontrada.")
            taxonomia_da_disciplina, disciplina = encontrada
            if taxonomia_id is not None and taxonomia_id != taxonomia_da_disciplina:
                raise ErroValidacaoDominio("'disciplina_id' não pertence à 'taxonomia_id' informada.")
            taxonomia_id = taxonomia_da_disciplina
            disciplina_codigo = disciplina.codigo

        if taxonomia_id is not None:
            buscar_taxonomia_ou_404(self._repo_taxonomias, taxonomia_id)
        else:
            exigem_taxonomia = {
                "topico": parametros.topico,
                "status_revisao": parametros.status_revisao,
                "revisao_prioritaria": parametros.revisao_prioritaria,
                "com_divergencia": parametros.com_divergencia,
                "usa_disciplina_arquivada": parametros.usa_disciplina_arquivada,
            }
            informados = [nome for nome, valor in exigem_taxonomia.items() if valor is not None]
            if parametros.ordenacao == OrdenacaoConsulta.FILA_REVISAO:
                informados.append("ordenacao=fila_revisao")
            if informados:
                raise ErroValidacaoDominio(f"Os filtros {', '.join(informados)} exigem 'taxonomia_id'.")

        topico: str | None = None
        if parametros.topico is not None and parametros.topico.strip():
            topico = normalizar_topico(parametros.topico)
            if not topico:
                raise ErroValidacaoDominio(f"Tópico inválido para filtro: {parametros.topico!r}.")

        filtro = FiltroConsultaQuestoes(
            termo=parametros.q.strip() if parametros.q and parametros.q.strip() else None,
            prova_id=parametros.prova_id,
            ano=parametros.ano,
            taxonomia_id=taxonomia_id,
            disciplina_codigo=disciplina_codigo,
            incluir_secundarias=parametros.incluir_secundarias,
            topico=topico,
            status_revisao=parametros.status_revisao,
            revisao_prioritaria=parametros.revisao_prioritaria,
            com_divergencia=parametros.com_divergencia,
            usa_disciplina_arquivada=parametros.usa_disciplina_arquivada,
            situacao_gabarito=parametros.situacao_gabarito,
            com_alerta_extracao=parametros.com_alerta_extracao,
            ordenacao=parametros.ordenacao,
            limite=parametros.tamanho_pagina,
            deslocamento=(parametros.pagina - 1) * parametros.tamanho_pagina,
        )
        pagina = self._consulta.consultar(filtro)
        contadores = self._consulta.contar_abas_revisao(taxonomia_id) if taxonomia_id is not None else None
        return ResultadoConsultaQuestoes(
            pagina=pagina,
            numero_pagina=parametros.pagina,
            tamanho_pagina=parametros.tamanho_pagina,
            taxonomia_id=taxonomia_id,
            contadores=contadores,
        )


# ---------------------------------------------------------------------------
# Detalhe
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClassificacaoOutraTaxonomia:
    classificacao: Classificacao
    taxonomia_codigo: str
    taxonomia_nome: str


@dataclass(frozen=True, slots=True)
class DetalheQuestao:
    questao: Questao
    prova: Prova
    taxonomia_id: UUID | None
    classificacao_vigente: Classificacao | None
    disciplinas_arquivadas_em_uso: tuple[str, ...]
    divergencia_aberta: DivergenciaReclassificacao | None
    historico: tuple[Classificacao, ...]
    outras_taxonomias: tuple[ClassificacaoOutraTaxonomia, ...]


class DetalharQuestaoUseCase:
    def __init__(
        self,
        *,
        repo_questoes: RepositorioQuestoes,
        repo_provas: RepositorioProvas,
        repo_taxonomias: RepositorioTaxonomias,
        repo_classificacoes: RepositorioClassificacoes,
        consulta: ConsultaQuestoes,
    ) -> None:
        self._repo_questoes = repo_questoes
        self._repo_provas = repo_provas
        self._repo_taxonomias = repo_taxonomias
        self._repo_classificacoes = repo_classificacoes
        self._consulta = consulta

    def execute(self, questao_id: UUID, *, taxonomia_id: UUID | None = None) -> DetalheQuestao:
        questao = _buscar_questao(self._repo_questoes, questao_id)
        prova = self._repo_provas.buscar_por_id(questao.prova_id)
        if prova is None:
            raise RecursoNaoEncontradoError(f"Prova '{questao.prova_id}' da questão não encontrada.")

        taxonomia = buscar_taxonomia_ou_404(self._repo_taxonomias, taxonomia_id) if taxonomia_id is not None else None
        vigentes = self._repo_classificacoes.listar_vigentes_por_questao(questao.id)
        taxonomias_por_id = {tax.id: tax for tax in self._repo_taxonomias.listar()}

        vigente: Classificacao | None = None
        arquivadas: tuple[str, ...] = ()
        divergencia: DivergenciaReclassificacao | None = None
        historico: tuple[Classificacao, ...] = ()
        if taxonomia is not None:
            vigente = next((c for c in vigentes if c.taxonomia_id == taxonomia.id), None)
            if vigente is not None:
                ativas = taxonomia.mapa_ativas()
                arquivadas = tuple(
                    codigo
                    for codigo in (vigente.disciplina_principal, *vigente.disciplinas_secundarias)
                    if codigo not in ativas
                )
            divergencia = next(
                (
                    d
                    for d in self._consulta.listar_divergencias_abertas_da_questao(questao.id)
                    if d.taxonomia_id == taxonomia.id
                ),
                None,
            )
            historico = tuple(self._repo_classificacoes.listar_historico(questao.id, taxonomia.id))

        outras = tuple(
            ClassificacaoOutraTaxonomia(
                classificacao=c,
                taxonomia_codigo=taxonomias_por_id[c.taxonomia_id].codigo,
                taxonomia_nome=taxonomias_por_id[c.taxonomia_id].nome,
            )
            for c in vigentes
            if c.taxonomia_id != taxonomia_id and c.taxonomia_id in taxonomias_por_id
        )
        return DetalheQuestao(
            questao=questao,
            prova=prova,
            taxonomia_id=taxonomia_id,
            classificacao_vigente=vigente,
            disciplinas_arquivadas_em_uso=arquivadas,
            divergencia_aberta=divergencia,
            historico=historico,
            outras_taxonomias=outras,
        )


# ---------------------------------------------------------------------------
# Edição curada de conteúdo e alertas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AlternativaEdicao:
    letra: LetraAlternativa
    texto: str


@dataclass(frozen=True, slots=True)
class GabaritoEdicao:
    situacao_gabarito: SituacaoGabarito
    alternativa_correta: LetraAlternativa | None = None


class EditarConteudoQuestaoUseCase:
    def __init__(
        self,
        *,
        repo_questoes: RepositorioQuestoes,
        repo_provas: RepositorioProvas,
        repo_classificacoes: RepositorioClassificacoes,
    ) -> None:
        self._repo_questoes = repo_questoes
        self._repo_provas = repo_provas
        self._repo_classificacoes = repo_classificacoes

    def execute(
        self,
        questao_id: UUID,
        *,
        enunciado: str | None = None,
        alternativas: Sequence[AlternativaEdicao] | None = None,
        gabarito: GabaritoEdicao | None = None,
        versao: int | None = None,
    ) -> None:
        if enunciado is None and alternativas is None and gabarito is None:
            raise ErroValidacaoDominio("Informe ao menos um campo para edição: enunciado, alternativas ou gabarito.")

        questao = _buscar_questao(self._repo_questoes, questao_id)
        if versao is not None and versao != questao.versao:
            raise ConflitoRecursoError(
                f"Questão '{questao_id}' está na versão {questao.versao}; o pedido foi feito sobre a versão {versao}."
            )
        prova = self._repo_provas.buscar_por_id(questao.prova_id)

        novas_alternativas: list[Alternativa] | None = None
        if alternativas is not None:
            ids_por_letra = {alt.letra: alt.id for alt in questao.alternativas}
            novas_alternativas = [
                Alternativa(
                    letra=item.letra, texto=item.texto, id=ids_por_letra.get(LetraAlternativa(item.letra), uuid4())
                )
                for item in sorted(alternativas, key=lambda alt: LetraAlternativa(alt.letra).value)
            ]

        novo_gabarito = (
            Gabarito(situacao_gabarito=gabarito.situacao_gabarito, alternativa_correta=gabarito.alternativa_correta)
            if gabarito is not None
            else None
        )

        questao.editar_conteudo(enunciado=enunciado, alternativas=novas_alternativas, gabarito=novo_gabarito)
        reavaliar_alertas_estruturais(
            questao,
            _agora_utc(),
            gabarito_enviado_na_prova=(prova.caminho_gabarito is not None) if prova is not None else None,
        )
        salva = self._repo_questoes.salvar(questao)
        recalcular_revisao_prioritaria_pendentes(salva, self._repo_classificacoes)


class ResolverAlertaExtracaoUseCase:
    def __init__(
        self,
        *,
        repo_questoes: RepositorioQuestoes,
        repo_classificacoes: RepositorioClassificacoes,
    ) -> None:
        self._repo_questoes = repo_questoes
        self._repo_classificacoes = repo_classificacoes

    def execute(self, questao_id: UUID, alerta_id: UUID) -> None:
        questao = _buscar_questao(self._repo_questoes, questao_id)
        alerta: AlertaExtracao | None = next((a for a in questao.alertas_extracao if a.id == alerta_id), None)
        if alerta is None:
            raise RecursoNaoEncontradoError(f"Alerta '{alerta_id}' não encontrado na questão '{questao_id}'.")
        if alerta.is_estrutural:
            raise ErroValidacaoDominio(
                f"Alerta estrutural '{alerta.codigo.value}' é resolvido automaticamente pela correção do conteúdo."
            )
        if not alerta.is_aberto:
            return

        marcar_alerta_verificado(questao, alerta_id, _agora_utc())
        salva = self._repo_questoes.salvar(questao)
        recalcular_revisao_prioritaria_pendentes(salva, self._repo_classificacoes)


# ---------------------------------------------------------------------------
# Gestão manual de Ativos Visuais
# ---------------------------------------------------------------------------


def _chave_ativo(prova_id: UUID, ativo_id: UUID, sufixo: str = "") -> str:
    return f"provas/{prova_id}/ativos/{ativo_id}{sufixo}.png"


def _validar_tamanho_imagem(conteudo: bytes) -> None:
    if len(conteudo) > TAMANHO_MAXIMO_IMAGEM_BYTES:
        raise ErroValidacaoDominio(f"Imagem excede o limite de {TAMANHO_MAXIMO_IMAGEM_BYTES // (1024 * 1024)} MB.")


class _GestaoAtivosBase:
    def __init__(
        self,
        *,
        repo_questoes: RepositorioQuestoes,
        repo_ativos: RepositorioAtivosVisuais,
        armazenamento: ArmazenamentoArquivos,
        normalizador: NormalizadorImagem,
    ) -> None:
        self._repo_questoes = repo_questoes
        self._repo_ativos = repo_ativos
        self._armazenamento = armazenamento
        self._normalizador = normalizador

    def _carregar_por_ativo(self, ativo_id: UUID) -> tuple[Questao, AtivoVisual]:
        ativo = self._repo_ativos.buscar_por_id(ativo_id)
        if ativo is None or ativo.questao_id is None:
            raise RecursoNaoEncontradoError(f"Ativo visual '{ativo_id}' não encontrado.")
        questao = _buscar_questao(self._repo_questoes, ativo.questao_id)
        alvo = next((a for a in questao.ativos_visuais if a.id == ativo_id), None)
        if alvo is None:
            raise RecursoNaoEncontradoError(f"Ativo visual '{ativo_id}' não encontrado.")
        return questao, alvo

    def _remover_arquivo_silencioso(self, chave: str | None) -> None:
        if not chave:
            return
        try:
            self._armazenamento.remover(chave)
        except (FileNotFoundError, ErroValidacaoDominio):
            pass


class AdicionarAtivoVisualUseCase(_GestaoAtivosBase):
    def execute(
        self,
        questao_id: UUID,
        conteudo: bytes,
        *,
        alternativa_letra: LetraAlternativa | None = None,
        ordem: int | None = None,
    ) -> AtivoVisual:
        questao = _buscar_questao(self._repo_questoes, questao_id)
        _validar_tamanho_imagem(conteudo)
        png = self._normalizador.normalizar_para_png(conteudo)

        if ordem is None:
            ordem = max((a.ordem for a in questao.ativos_visuais), default=-1) + 1
        ativo = AtivoVisual(
            origem=OrigemAtivoVisual.UPLOAD_MANUAL,
            ordem=ordem,
            alternativa_letra=alternativa_letra,
            questao_id=questao.id,
        )
        chave = _chave_ativo(questao.prova_id, ativo.id)
        ativo.chave_arquivo = chave
        self._armazenamento.salvar(chave, png)

        questao.ativos_visuais.append(ativo)
        questao.editada_manualmente = True
        try:
            salva = self._repo_questoes.salvar(questao)
        except Exception:
            self._remover_arquivo_silencioso(chave)
            raise
        return next(a for a in salva.ativos_visuais if a.id == ativo.id)


class AtualizarAtivoVisualUseCase(_GestaoAtivosBase):
    def execute(
        self,
        ativo_id: UUID,
        *,
        conteudo: bytes | None = None,
        ordem: int | None = None,
        alternativa_letra: LetraAlternativa | None = None,
        remover_alternativa_letra: bool = False,
    ) -> AtivoVisual:
        if alternativa_letra is not None and remover_alternativa_letra:
            raise ErroValidacaoDominio("Informe 'alternativa_letra' ou 'remover_alternativa_letra', não ambos.")
        alterar_alternativa = alternativa_letra is not None or remover_alternativa_letra
        if conteudo is None and ordem is None and not alterar_alternativa:
            raise ErroValidacaoDominio("Informe ao menos um campo: arquivo, ordem ou alternativa_letra.")

        questao, alvo = self._carregar_por_ativo(ativo_id)
        atualizado = replace(alvo)
        if ordem is not None:
            atualizado.ordem = ordem
        if alterar_alternativa:
            atualizado.alternativa_letra = alternativa_letra

        chave_antiga = alvo.chave_arquivo
        chave_nova: str | None = None
        if conteudo is not None:
            _validar_tamanho_imagem(conteudo)
            png = self._normalizador.normalizar_para_png(conteudo)
            chave_nova = _chave_ativo(questao.prova_id, alvo.id, f"-{uuid4().hex[:8]}")
            self._armazenamento.salvar(chave_nova, png)
            atualizado.chave_arquivo = chave_nova
            atualizado.origem = OrigemAtivoVisual.UPLOAD_MANUAL
            atualizado.bbox = None

        validado = AtivoVisual(
            origem=atualizado.origem,
            ordem=atualizado.ordem,
            alternativa_letra=atualizado.alternativa_letra,
            pagina=atualizado.pagina,
            bbox=atualizado.bbox,
            chave_arquivo=atualizado.chave_arquivo,
            id=atualizado.id,
            questao_id=questao.id,
        )
        questao.ativos_visuais = [validado if a.id == ativo_id else a for a in questao.ativos_visuais]
        questao.editada_manualmente = True
        try:
            salva = self._repo_questoes.salvar(questao)
        except Exception:
            self._remover_arquivo_silencioso(chave_nova)
            raise
        if chave_nova is not None and chave_antiga != chave_nova:
            self._remover_arquivo_silencioso(chave_antiga)
        return next(a for a in salva.ativos_visuais if a.id == ativo_id)


class RemoverAtivoVisualUseCase(_GestaoAtivosBase):
    def execute(self, ativo_id: UUID) -> None:
        questao, alvo = self._carregar_por_ativo(ativo_id)
        questao.ativos_visuais = [a for a in questao.ativos_visuais if a.id != ativo_id]
        questao.editada_manualmente = True
        self._repo_questoes.salvar(questao)
        self._remover_arquivo_silencioso(alvo.chave_arquivo)
