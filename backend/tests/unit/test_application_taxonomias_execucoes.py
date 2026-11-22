from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from application.classificacao import ClassificarQuestaoService
from application.exceptions import (
    ConflitoRecursoError,
    ErroClassificadorLLMError,
    RecursoNaoEncontradoError,
)
from application.execucoes_classificacao import (
    CriarExecucaoClassificacaoUseCase,
    DetalharExecucaoClassificacaoUseCase,
    ExecutarLoteClassificacaoService,
    HookClassificacaoEncadeada,
    ListarExecucoesClassificacaoUseCase,
    RetomarExecucaoClassificacaoUseCase,
)
from application.ports.classificacao import IdentidadeClassificador, ResultadoChamada
from application.ports.extracao import (
    ResultadoExtracaoGabarito,
    ResultadoExtracaoProva,
)
from application.provas import CriarProvaUseCase
from application.seed import CODIGO_PERFIL_PADRAO, VERSAO_PERFIL_PADRAO
from application.taxonomias import (
    AdicionarDisciplinaUseCase,
    AtualizarDisciplinaUseCase,
    AtualizarTaxonomiaUseCase,
    CriarPerfilClassificacaoUseCase,
    CriarTaxonomiaUseCase,
    DetalharTaxonomiaUseCase,
    DisciplinaInput,
    ListarPerfisClassificacaoUseCase,
    ListarTaxonomiasUseCase,
)
from application.worker import WorkerLocal
from domain.classificacao import (
    Classificacao,
    DivergenciaReclassificacao,
    ExecucaoClassificacao,
    PerfilClassificacao,
)
from domain.enums import (
    EscopoExecucao,
    OrigemClassificacao,
    StatusClassificacao,
    StatusDivergencia,
    StatusExecucaoClassificacao,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.prova import FaixaQuestoes, Ingestao, Prova, Questao
from domain.taxonomia import Disciplina, Taxonomia


class _MemRepoProvas:
    def __init__(self) -> None:
        self.itens: dict[UUID, Prova] = {}

    def salvar(self, prova: Prova) -> Prova:
        self.itens[prova.id] = prova
        return prova

    def buscar_por_id(self, prova_id: UUID) -> Prova | None:
        return self.itens.get(prova_id)

    def buscar_por_chave_natural(self, exame: str, curso: str, ano: int) -> Prova | None:
        for p in self.itens.values():
            if p.exame == exame.strip().upper() and p.curso == curso.strip() and p.ano == ano:
                return p
        return None

    def listar(self) -> list[Prova]:
        return list(self.itens.values())


class _MemRepoIngestoes:
    def __init__(self) -> None:
        self.itens: dict[UUID, Ingestao] = {}

    def salvar(self, ingestao: Ingestao) -> Ingestao:
        self.itens[ingestao.id] = ingestao
        return ingestao

    def buscar_por_id(self, ingestao_id: UUID) -> Ingestao | None:
        return self.itens.get(ingestao_id)

    def buscar_ultima_por_prova(self, prova_id: UUID) -> Ingestao | None:
        return None

    def listar_por_prova(self, prova_id: UUID) -> list[Ingestao]:
        return [i for i in self.itens.values() if i.prova_id == prova_id]

    def marcar_em_processamento_como_interrompidas(self, agora: datetime, motivo: str) -> int:
        return 0


class _MemRepoQuestoes:
    def __init__(self, repo_classificacoes: _MemRepoClassificacoes, repo_taxonomias: _MemRepoTaxonomias) -> None:
        self.itens: dict[UUID, Questao] = {}
        self._repo_class = repo_classificacoes
        self._repo_tax = repo_taxonomias

    def salvar(self, questao: Questao) -> Questao:
        self.itens[questao.id] = questao
        return questao

    def salvar_lote(self, questoes: Sequence[Questao]) -> list[Questao]:
        for q in questoes:
            self.itens[q.id] = q
        return list(questoes)

    def salvar_lote_do_sistema(self, questoes: Sequence[Questao], *, sobrescrever_alteradas: bool) -> list[Questao]:
        return self.salvar_lote(questoes)

    def buscar_por_id(self, questao_id: UUID) -> Questao | None:
        return self.itens.get(questao_id)

    def buscar_por_prova_e_numero(self, prova_id: UUID, numero: int) -> Questao | None:
        for q in self.itens.values():
            if q.prova_id == prova_id and q.numero == numero:
                return q
        return None

    def listar_por_prova(self, prova_id: UUID) -> list[Questao]:
        return sorted([q for q in self.itens.values() if q.prova_id == prova_id], key=lambda q: q.numero)

    def listar_todas(self) -> list[Questao]:
        return list(self.itens.values())

    def listar_pendentes_classificacao(self, taxonomia_id: UUID) -> list[Questao]:
        res: list[Questao] = []
        for q in self.itens.values():
            vig = self._repo_class.buscar_vigente(q.id, taxonomia_id)
            if vig is None or vig.status != StatusClassificacao.APROVADA:
                res.append(q)
        return res

    def listar_com_disciplina_arquivada(self, taxonomia_id: UUID) -> list[Questao]:
        tax = self._repo_tax.buscar_por_id(taxonomia_id)
        if tax is None:
            return []
        arquivadas = {d.codigo for d in tax.disciplinas if not d.ativa}
        res: list[Questao] = []
        for q in self.itens.values():
            vig = self._repo_class.buscar_vigente(q.id, taxonomia_id)
            if vig is None:
                continue
            codigos = {vig.disciplina_principal, *vig.disciplinas_secundarias}
            if codigos & arquivadas:
                res.append(q)
        return res

    def listar_por_ids(self, questao_ids: Sequence[UUID]) -> list[Questao]:
        alvo = set(questao_ids)
        return [q for q in self.itens.values() if q.id in alvo]


class _MemRepoTaxonomias:
    def __init__(self, repo_classificacoes: _MemRepoClassificacoes) -> None:
        self.itens: dict[UUID, Taxonomia] = {}
        self._repo_class = repo_classificacoes

    def salvar(self, taxonomia: Taxonomia) -> Taxonomia:
        for existente in self.itens.values():
            if existente.codigo == taxonomia.codigo and existente.id != taxonomia.id:
                raise RuntimeError("duplicate key value violates unique constraint")
        self.itens[taxonomia.id] = taxonomia
        return taxonomia

    def buscar_por_id(self, taxonomia_id: UUID) -> Taxonomia | None:
        return self.itens.get(taxonomia_id)

    def buscar_por_codigo(self, codigo: str) -> Taxonomia | None:
        norm = codigo.strip()
        for t in self.itens.values():
            if t.codigo == norm:
                return t
        return None

    def listar(self) -> list[Taxonomia]:
        return sorted(self.itens.values(), key=lambda t: t.codigo)

    def buscar_disciplina_por_id(self, disciplina_id: UUID) -> tuple[UUID, Disciplina] | None:
        for t in self.itens.values():
            for d in t.disciplinas:
                if d.id == disciplina_id:
                    return (
                        t.id,
                        Disciplina(id=d.id, codigo=d.codigo, nome=d.nome, ementa=d.ementa, ativa=d.ativa),
                    )
        return None

    def adicionar_disciplina(
        self,
        taxonomia_id: UUID,
        disciplina: Disciplina,
        *,
        ordem: int | None = None,
    ) -> Disciplina:
        tax = self.itens[taxonomia_id]
        if disciplina.codigo in tax.mapa_todas():
            raise RuntimeError("duplicate discipline codigo")
        tax.disciplinas.append(disciplina)
        return disciplina

    def salvar_disciplina(
        self,
        taxonomia_id: UUID,
        disciplina: Disciplina,
        *,
        ordem: int | None = None,
    ) -> Disciplina:
        tax = self.itens[taxonomia_id]
        for idx, d in enumerate(tax.disciplinas):
            if d.id == disciplina.id:
                tax.disciplinas[idx] = disciplina
                return disciplina
        raise ErroInvarianteDominio("Disciplina não encontrada")

    def contar_classificacoes_vigentes_por_disciplina(
        self,
        taxonomia_id: UUID,
        disciplina_codigo: str,
    ) -> int:
        return self.contar_classificacoes_vigentes_por_disciplinas(taxonomia_id).get(disciplina_codigo, 0)

    def contar_classificacoes_vigentes_por_disciplinas(self, taxonomia_id: UUID) -> dict[str, int]:
        return self.contar_classificacoes_vigentes_por_taxonomias([taxonomia_id]).get(taxonomia_id, {})

    def contar_classificacoes_vigentes_por_taxonomias(
        self,
        taxonomia_ids: Sequence[UUID],
    ) -> dict[UUID, dict[str, int]]:
        resultado: dict[UUID, dict[str, int]] = {tid: {} for tid in taxonomia_ids}
        for c in self._repo_class.itens.values():
            if not c.vigente or c.taxonomia_id not in resultado:
                continue
            codigos = {c.disciplina_principal, *c.disciplinas_secundarias}
            for cod in codigos:
                resultado[c.taxonomia_id][cod] = resultado[c.taxonomia_id].get(cod, 0) + 1
        return resultado


class _MemRepoPerfis:
    def __init__(self) -> None:
        self.itens: dict[UUID, PerfilClassificacao] = {}

    def salvar(self, perfil: PerfilClassificacao) -> PerfilClassificacao:
        for p in self.itens.values():
            if p.codigo == perfil.codigo and p.versao == perfil.versao and p.id != perfil.id:
                raise RuntimeError("duplicate perfil")
        self.itens[perfil.id] = perfil
        return perfil

    def buscar_por_id(self, perfil_id: UUID) -> PerfilClassificacao | None:
        return self.itens.get(perfil_id)

    def buscar_por_codigo_e_versao(self, codigo: str, versao: str) -> PerfilClassificacao | None:
        for p in self.itens.values():
            if p.codigo == codigo.strip() and p.versao == versao.strip():
                return p
        return None

    def listar(self) -> list[PerfilClassificacao]:
        return sorted(self.itens.values(), key=lambda p: (p.codigo, p.versao))


class _MemRepoExecucoes:
    def __init__(self) -> None:
        self.itens: dict[UUID, ExecucaoClassificacao] = {}

    def salvar(self, execucao: ExecucaoClassificacao) -> ExecucaoClassificacao:
        self.itens[execucao.id] = execucao
        return execucao

    def buscar_por_id(self, execucao_id: UUID) -> ExecucaoClassificacao | None:
        return self.itens.get(execucao_id)

    def listar(self, *, taxonomia_id: UUID | None = None) -> list[ExecucaoClassificacao]:
        valores = list(self.itens.values())
        if taxonomia_id is not None:
            valores = [e for e in valores if e.taxonomia_id == taxonomia_id]
        return valores

    def marcar_em_processamento_como_interrompidas(self, agora: datetime) -> int:
        return 0


class _MemRepoClassificacoes:
    def __init__(self) -> None:
        self.itens: dict[UUID, Classificacao] = {}

    def salvar(self, classificacao: Classificacao) -> Classificacao:
        self.itens[classificacao.id] = classificacao
        return classificacao

    def registrar_substituicao(self, anterior: Classificacao, nova: Classificacao) -> Classificacao:
        self.itens[anterior.id].vigente = False
        self.itens[nova.id] = nova
        return nova

    def buscar_por_id(self, classificacao_id: UUID) -> Classificacao | None:
        return self.itens.get(classificacao_id)

    def buscar_vigente(self, questao_id: UUID, taxonomia_id: UUID) -> Classificacao | None:
        for c in self.itens.values():
            if c.questao_id == questao_id and c.taxonomia_id == taxonomia_id and c.vigente:
                return c
        return None

    def listar_historico(self, questao_id: UUID, taxonomia_id: UUID) -> list[Classificacao]:
        return [c for c in self.itens.values() if c.questao_id == questao_id and c.taxonomia_id == taxonomia_id]

    def listar_vigentes_por_questao(self, questao_id: UUID) -> list[Classificacao]:
        return [c for c in self.itens.values() if c.questao_id == questao_id and c.vigente]

    def listar_fila_revisao(
        self,
        taxonomia_id: UUID,
        *,
        status: StatusClassificacao | None = None,
        apenas_revisao_prioritaria: bool = False,
    ) -> list[Classificacao]:
        return []


class _MemRepoDivergencias:
    def __init__(self) -> None:
        self.itens: dict[UUID, DivergenciaReclassificacao] = {}

    def salvar(self, divergencia: DivergenciaReclassificacao) -> DivergenciaReclassificacao:
        self.itens[divergencia.id] = divergencia
        return divergencia

    def buscar_por_id(self, divergencia_id: UUID) -> DivergenciaReclassificacao | None:
        return self.itens.get(divergencia_id)

    def listar(
        self,
        *,
        taxonomia_id: UUID | None = None,
        status: StatusDivergencia | None = None,
    ) -> list[DivergenciaReclassificacao]:
        return list(self.itens.values())

    def resolver_atomicamente(
        self,
        divergencia_id: UUID,
        resolucao: Any,
        agora: datetime,
        nova_classificacao: Classificacao | None = None,
    ) -> DivergenciaReclassificacao:
        return self.itens[divergencia_id]


class _MemArmazenamento:
    def __init__(self) -> None:
        self.arquivos: dict[str, bytes] = {}

    def salvar(self, chave: str, conteudo: bytes) -> str:
        self.arquivos[chave] = conteudo
        return chave

    def ler(self, chave: str) -> bytes:
        return self.arquivos[chave]

    def remover(self, chave: str) -> None:
        self.arquivos.pop(chave, None)

    def existe(self, chave: str) -> bool:
        return chave in self.arquivos

    def resolver_caminho(self, chave: str) -> Path:
        return Path(chave)


class _DummyExtratorProva:
    def extrair(self, caminho_pdf: Path, faixa_ce: FaixaQuestoes) -> ResultadoExtracaoProva:
        raise NotImplementedError


class _DummyExtratorGab:
    def extrair(self, caminho_pdf: Path) -> ResultadoExtracaoGabarito:
        raise NotImplementedError


class _FakeClassificador:
    def __init__(self, comportamento_por_numero: dict[int, dict[str, Any] | Exception] | None = None) -> None:
        self.chamadas: list[str] = []
        self._comportamento = comportamento_por_numero or {}

    @property
    def identidade(self) -> IdentidadeClassificador:
        return IdentidadeClassificador(provider="fake", model="fake-v1", base_url="http://fake")

    def classificar_estruturado(
        self,
        *,
        system: str,
        user: str,
        imagens_png: Sequence[bytes],
        schema: Mapping[str, Any],
        nome_schema: str,
        max_tokens: int = 4096,
        usar_cache: bool = True,
    ) -> ResultadoChamada:
        self.chamadas.append(user)
        for num, acao in self._comportamento.items():
            if f"Q{num:02d}" in user or f"QUESTÃO {num:02d}" in user or f"Questão {num}" in user:
                if isinstance(acao, Exception):
                    raise acao
                return ResultadoChamada(
                    dados_brutos=acao,
                    prompt_tokens=100,
                    completion_tokens=20,
                    latencia_ms=5.0,
                    from_cache=False,
                    cache_key=f"k-{num}",
                )
        return ResultadoChamada(
            dados_brutos={
                "disciplina_principal": "algoritmos",
                "disciplinas_secundarias": [],
                "topicos": ["grafos"],
                "justificativa": "Justificativa padrão.",
                "confianca": 0.9,
            },
            prompt_tokens=80,
            completion_tokens=15,
            latencia_ms=3.0,
            from_cache=True,
            cache_key="k-default",
        )


def _criar_contexto() -> dict[str, Any]:
    repo_class = _MemRepoClassificacoes()
    repo_tax = _MemRepoTaxonomias(repo_class)
    repo_perfis = _MemRepoPerfis()
    repo_provas = _MemRepoProvas()
    repo_ing = _MemRepoIngestoes()
    repo_questoes = _MemRepoQuestoes(repo_class, repo_tax)
    repo_exec = _MemRepoExecucoes()
    repo_div = _MemRepoDivergencias()
    armazenamento = _MemArmazenamento()
    worker = WorkerLocal(
        repo_provas=repo_provas,
        repo_ingestoes=repo_ing,
        repo_questoes=repo_questoes,
        repo_execucoes=repo_exec,
        armazenamento=armazenamento,
        extrator_prova=_DummyExtratorProva(),
        extrator_gabarito=_DummyExtratorGab(),
    )
    return {
        "repo_class": repo_class,
        "repo_tax": repo_tax,
        "repo_perfis": repo_perfis,
        "repo_provas": repo_provas,
        "repo_ing": repo_ing,
        "repo_questoes": repo_questoes,
        "repo_exec": repo_exec,
        "repo_div": repo_div,
        "armazenamento": armazenamento,
        "worker": worker,
    }


def test_casos_de_uso_taxonomias_disciplinas_e_perfis() -> None:
    ctx = _criar_contexto()
    repo_tax: _MemRepoTaxonomias = ctx["repo_tax"]
    repo_perfis: _MemRepoPerfis = ctx["repo_perfis"]
    repo_class: _MemRepoClassificacoes = ctx["repo_class"]

    criar_tax = CriarTaxonomiaUseCase(repo_tax)
    listar_tax = ListarTaxonomiasUseCase(repo_tax)
    detalhar_tax = DetalharTaxonomiaUseCase(repo_tax)
    atualizar_tax = AtualizarTaxonomiaUseCase(repo_tax)
    add_disc = AdicionarDisciplinaUseCase(repo_tax)
    upd_disc = AtualizarDisciplinaUseCase(repo_tax)

    dto = criar_tax.execute(
        codigo="enade-ec",
        nome="ENADE EC",
        curso_referencia="Engenharia de Computação",
        disciplinas=[DisciplinaInput(codigo="algoritmos", nome="Algoritmos", ementa="Complexidade")],
    )
    assert dto.taxonomia.codigo == "enade-ec"
    assert len(dto.disciplinas) == 1

    with pytest.raises(ConflitoRecursoError):
        criar_tax.execute(codigo="enade-ec", nome="Duplicada")

    atualizada = atualizar_tax.execute(dto.taxonomia.id, nome="ENADE EC Atualizada")
    assert atualizada.taxonomia.nome == "ENADE EC Atualizada"
    assert len(atualizada.disciplinas) == 1

    tax_id, disc_dto = add_disc.execute(
        dto.taxonomia.id,
        codigo="redes",
        nome="Redes de Computadores",
        ementa="TCP/IP",
    )
    assert tax_id == dto.taxonomia.id
    assert disc_dto.disciplina.codigo == "redes"

    with pytest.raises(ConflitoRecursoError):
        add_disc.execute(dto.taxonomia.id, codigo="redes", nome="Redes Dup")

    repo_class.salvar(
        Classificacao(
            questao_id=uuid4(),
            taxonomia_id=dto.taxonomia.id,
            disciplina_principal="redes",
            vigente=True,
        )
    )
    _, disc_arq = upd_disc.execute(disc_dto.disciplina.id, ativa=False, nome="Redes Arquivada")
    assert disc_arq.disciplina.ativa is False
    assert disc_arq.classificacoes_vigentes_impactadas == 1

    with pytest.raises(RecursoNaoEncontradoError):
        upd_disc.execute(uuid4(), ativa=False)

    lista = listar_tax.execute()
    assert len(lista) == 1
    det = detalhar_tax.execute(dto.taxonomia.id)
    assert {d.disciplina.codigo: d.classificacoes_vigentes_impactadas for d in det.disciplinas} == {
        "algoritmos": 0,
        "redes": 1,
    }

    # Perfis imutáveis + clonagem com perfil_base_id
    criar_perfil = CriarPerfilClassificacaoUseCase(repo_perfis)
    listar_perfis = ListarPerfisClassificacaoUseCase(repo_perfis)

    p1 = criar_perfil.execute(
        codigo="v2-fronteiras",
        versao="v1",
        diretrizes_gerais="Diretrizes v1",
        guia_fronteiras="Fronteiras v1",
        template_prompt="Prompt {enunciado}",
        descricao="Descrição v1",
    )
    p2 = criar_perfil.execute(versao="v2", perfil_base_id=p1.id)
    assert p2.codigo == "v2-fronteiras"
    assert p2.diretrizes_gerais == "Diretrizes v1"
    assert p2.descricao == "Descrição v1"

    with pytest.raises(ConflitoRecursoError):
        criar_perfil.execute(versao="v1", perfil_base_id=p1.id)
    with pytest.raises(RecursoNaoEncontradoError):
        criar_perfil.execute(versao="v3", perfil_base_id=uuid4())

    assert [p.versao for p in listar_perfis.execute()] == ["v1", "v2"]


def test_execucao_lote_incluir_revisadas_divergencia_e_retomada() -> None:
    ctx = _criar_contexto()
    repo_tax: _MemRepoTaxonomias = ctx["repo_tax"]
    repo_perfis: _MemRepoPerfis = ctx["repo_perfis"]
    repo_provas: _MemRepoProvas = ctx["repo_provas"]
    repo_questoes: _MemRepoQuestoes = ctx["repo_questoes"]
    repo_exec: _MemRepoExecucoes = ctx["repo_exec"]
    repo_class: _MemRepoClassificacoes = ctx["repo_class"]
    repo_div: _MemRepoDivergencias = ctx["repo_div"]
    worker: WorkerLocal = ctx["worker"]

    tax = repo_tax.salvar(
        Taxonomia(
            codigo="enade-ec",
            nome="ENADE EC",
            disciplinas=[
                Disciplina(codigo="algoritmos", nome="Algoritmos"),
                Disciplina(codigo="redes", nome="Redes"),
            ],
        )
    )
    perfil = repo_perfis.salvar(
        PerfilClassificacao(
            codigo=CODIGO_PERFIL_PADRAO,
            versao=VERSAO_PERFIL_PADRAO,
            diretrizes_gerais="Classifique.",
            guia_fronteiras="",
            template_prompt="[SYSTEM]\n{catalogo_disciplinas}\n[USER]\nQ{numero:02d}: {enunciado}",
        )
    )
    prova = repo_provas.salvar(Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023))
    q1 = repo_questoes.salvar(Questao(prova_id=prova.id, numero=10, enunciado="Questão 10 aprovada."))
    q2 = repo_questoes.salvar(Questao(prova_id=prova.id, numero=11, enunciado="Questão 11 falha temporária."))
    q3 = repo_questoes.salvar(Questao(prova_id=prova.id, numero=12, enunciado="Questão 12 pendente."))

    # q1 aprovada (automatica aprovada in-place)
    vig_q1 = repo_class.salvar(
        Classificacao(
            questao_id=q1.id,
            taxonomia_id=tax.id,
            disciplina_principal="algoritmos",
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.APROVADA,
            vigente=True,
        )
    )
    # q3 pendente_revisao
    vig_q3 = repo_class.salvar(
        Classificacao(
            questao_id=q3.id,
            taxonomia_id=tax.id,
            disciplina_principal="algoritmos",
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
        )
    )

    comportamento: dict[int, dict[str, Any] | Exception] = {
        11: ErroClassificadorLLMError("Timeout LLM simulado"),
        12: {
            "disciplina_principal": "redes",
            "disciplinas_secundarias": [],
            "topicos": ["roteamento"],
            "justificativa": "OSPF.",
            "confianca": 0.91,
        },
    }
    fake_llm = _FakeClassificador(comportamento)
    service = ExecutarLoteClassificacaoService(
        repo_execucoes=repo_exec,
        repo_questoes=repo_questoes,
        repo_provas=repo_provas,
        repo_classificacoes=repo_class,
        repo_divergencias=repo_div,
        classificar_questao=ClassificarQuestaoService(fake_llm),
    )

    criar_exec = CriarExecucaoClassificacaoUseCase(repo_tax, repo_perfis, repo_provas, repo_questoes, repo_exec, worker)
    retomar_exec = RetomarExecucaoClassificacaoUseCase(repo_exec, repo_provas, worker)

    # 1. incluir_revisadas=False: pula q1 sem chamar LLM, falha q2, substitui q3 (PENDENTE_REVISAO)
    exec1 = criar_exec.execute(
        taxonomia_id=tax.id,
        perfil_id=perfil.id,
        escopo=EscopoExecucao.PROVA_ID,
        incluir_revisadas=False,
        prova_id=prova.id,
    )
    progresso_eventos: list[tuple[int, int]] = []
    service(exec1.id, lambda p, t: progresso_eventos.append((p, t)))

    e1_apos = repo_exec.buscar_por_id(exec1.id)
    assert e1_apos is not None
    assert e1_apos.status == StatusExecucaoClassificacao.CONCLUIDA_COM_ERROS
    assert e1_apos.processadas == 3
    assert e1_apos.total_itens == 3
    assert str(q2.id) in e1_apos.erros_por_questao
    assert set(e1_apos.questao_ids_concluidas) == {q1.id, q3.id}
    assert len(fake_llm.chamadas) == 2  # q1 NÃO chamou LLM
    assert repo_class.buscar_vigente(q3.id, tax.id).disciplina_principal == "redes"  # type: ignore[union-attr]
    assert repo_class.buscar_por_id(vig_q3.id).vigente is False  # type: ignore[union-attr]
    assert progresso_eventos[0] == (0, 3)
    assert progresso_eventos[-1] == (3, 3)

    # 2. Retomar exec1: reprocessa APENAS q2 após corrigir erro
    comportamento[11] = {
        "disciplina_principal": "algoritmos",
        "disciplinas_secundarias": [],
        "topicos": ["grafos"],
        "justificativa": "Dijkstra.",
        "confianca": 0.88,
    }
    fake_llm.chamadas.clear()
    retomada = retomar_exec.execute(exec1.id)
    assert retomada.status == StatusExecucaoClassificacao.PENDENTE
    assert retomada.processadas == 2
    service(retomada.id)

    e1_final = repo_exec.buscar_por_id(exec1.id)
    assert e1_final is not None
    assert e1_final.status == StatusExecucaoClassificacao.CONCLUIDA
    assert e1_final.processadas == 3
    assert len(fake_llm.chamadas) == 1  # só q2!

    with pytest.raises(ErroInvarianteDominio):
        retomar_exec.execute(exec1.id)

    # 3. incluir_revisadas=True: mantém humana vigente de q1, abre divergência apenas quando muda disciplina
    comportamento[10] = {
        "disciplina_principal": "redes",
        "disciplinas_secundarias": [],
        "topicos": ["tcp"],
        "justificativa": "Mudou para redes.",
        "confianca": 0.95,
    }
    exec2 = criar_exec.execute(
        taxonomia_id=tax.id,
        perfil_id=perfil.id,
        escopo=EscopoExecucao.QUESTAO_IDS,
        incluir_revisadas=True,
        questao_ids=[q1.id],
    )
    service(exec2.id)

    e2_apos = repo_exec.buscar_por_id(exec2.id)
    assert e2_apos is not None
    assert e2_apos.divergencias_abertas == 1
    assert repo_class.buscar_vigente(q1.id, tax.id).id == vig_q1.id  # type: ignore[union-attr]
    divs = repo_div.listar()
    assert len(divs) == 1
    assert divs[0].classificacao_candidata_id is not None
    assert divs[0].disciplina_principal_candidata == "redes"

    # Concordante (mesma disciplina_principal, tópicos diferentes): salva histórico, NÃO abre divergência
    comportamento[10] = {
        "disciplina_principal": "algoritmos",
        "disciplinas_secundarias": [],
        "topicos": ["ordenacao"],
        "justificativa": "Concordante.",
        "confianca": 0.99,
    }
    exec3 = criar_exec.execute(
        taxonomia_id=tax.id,
        perfil_id=perfil.id,
        escopo=EscopoExecucao.QUESTAO_IDS,
        incluir_revisadas=True,
        questao_ids=[q1.id],
    )
    service(exec3.id)
    assert repo_exec.buscar_por_id(exec3.id).divergencias_abertas == 0  # type: ignore[union-attr]
    assert len(repo_div.listar()) == 1


def test_hook_encadeado_escopo_vazio_e_guarda_taxonomia_sem_ativas() -> None:
    ctx = _criar_contexto()
    repo_tax: _MemRepoTaxonomias = ctx["repo_tax"]
    repo_perfis: _MemRepoPerfis = ctx["repo_perfis"]
    repo_provas: _MemRepoProvas = ctx["repo_provas"]
    repo_ing: _MemRepoIngestoes = ctx["repo_ing"]
    repo_questoes: _MemRepoQuestoes = ctx["repo_questoes"]
    repo_exec: _MemRepoExecucoes = ctx["repo_exec"]
    armazenamento: _MemArmazenamento = ctx["armazenamento"]
    worker: WorkerLocal = ctx["worker"]

    tax_vazia = repo_tax.salvar(
        Taxonomia(
            codigo="tax-vazia",
            nome="Taxonomia Sem Ativas",
            disciplinas=[Disciplina(codigo="old", nome="Antiga", ativa=False)],
        )
    )
    criar_prova = CriarProvaUseCase(
        repo_provas=repo_provas,
        repo_ingestoes=repo_ing,
        repo_taxonomias=repo_tax,
        repo_perfis=repo_perfis,
        armazenamento=armazenamento,
        worker=worker,
    )
    with pytest.raises(ErroValidacaoDominio):
        criar_prova.execute(
            exame="ENADE",
            curso="Engenharia de Computação",
            ano=2023,
            conteudo_prova_pdf=b"%PDF-1.4 ok",
            taxonomia_id=tax_vazia.id,
        )

    tax_ok = repo_tax.salvar(
        Taxonomia(
            codigo="enade-ec",
            nome="ENADE EC",
            disciplinas=[Disciplina(codigo="algoritmos", nome="Algoritmos", ativa=True)],
        )
    )
    perfil = repo_perfis.salvar(
        PerfilClassificacao(
            codigo=CODIGO_PERFIL_PADRAO,
            versao=VERSAO_PERFIL_PADRAO,
            diretrizes_gerais="D",
            guia_fronteiras="",
            template_prompt="T",
        )
    )
    prova = repo_provas.salvar(Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023))

    criar_exec = CriarExecucaoClassificacaoUseCase(repo_tax, repo_perfis, repo_provas, repo_questoes, repo_exec, worker)
    hook = HookClassificacaoEncadeada(repo_perfis=repo_perfis, criar_execucao=criar_exec)
    exec_id = hook(prova_id=prova.id, taxonomia_id=tax_ok.id, perfil_id=None)
    exec_criada = DetalharExecucaoClassificacaoUseCase(repo_exec).execute(exec_id)
    assert exec_criada.perfil_id == perfil.id
    assert exec_criada.escopo == EscopoExecucao.PROVA_ID
    assert exec_criada.escopo_prova_id == prova.id
    assert exec_criada.total_itens == 0
    assert len(ListarExecucoesClassificacaoUseCase(repo_exec).execute(taxonomia_id=tax_ok.id)) == 1

    service = ExecutarLoteClassificacaoService(
        repo_execucoes=repo_exec,
        repo_questoes=repo_questoes,
        repo_provas=repo_provas,
        repo_classificacoes=ctx["repo_class"],
        repo_divergencias=ctx["repo_div"],
        classificar_questao=ClassificarQuestaoService(_FakeClassificador()),
    )
    service(exec_criada.id)
    exec_final = repo_exec.buscar_por_id(exec_criada.id)
    assert exec_final is not None
    assert exec_final.status == StatusExecucaoClassificacao.CONCLUIDA
    assert exec_final.processadas == 0
    assert exec_final.total_itens == 0

    worker.configurar_classificacao(hook=hook, executor=service)
    assert worker._classificacao_hook is hook
    assert worker._classificacao_executor is service
