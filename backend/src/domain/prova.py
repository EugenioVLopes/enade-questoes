"""Entidades e objetos de valor de Conteúdo de Prova (desacoplados de classificação)."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from domain.enums import (
    CodigoAlertaExtracao,
    ComponenteProva,
    LetraAlternativa,
    OrigemAtivoVisual,
    SeveridadeAlerta,
    SituacaoGabarito,
    StatusAlerta,
    StatusIngestao,
    TipoQuestao,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio

SEVERIDADE_POR_CODIGO: dict[CodigoAlertaExtracao, SeveridadeAlerta] = {
    CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA: SeveridadeAlerta.CRITICO,
    CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS: SeveridadeAlerta.CRITICO,
    CodigoAlertaExtracao.PDF_VIA_OCR: SeveridadeAlerta.CRITICO,
    CodigoAlertaExtracao.ENUNCIADO_SUSPEITO: SeveridadeAlerta.CRITICO,
    CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA: SeveridadeAlerta.INFORMATIVO,
    CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA: SeveridadeAlerta.INFORMATIVO,
}

ALERTAS_ESTRUTURAIS: frozenset[CodigoAlertaExtracao] = frozenset(
    {
        CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA,
        CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS,
        CodigoAlertaExtracao.ENUNCIADO_SUSPEITO,
        CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA,
    }
)

ALERTAS_INSPECAO: frozenset[CodigoAlertaExtracao] = frozenset(
    {
        CodigoAlertaExtracao.PDF_VIA_OCR,
        CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA,
    }
)


def _validar_inteiro_positivo(valor: int, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise ErroValidacaoDominio(f"'{campo}' deve ser inteiro >= 1; recebido: {valor!r}.")
    return valor


def _validar_inteiro_nao_negativo(valor: int, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErroValidacaoDominio(f"'{campo}' deve ser inteiro >= 0; recebido: {valor!r}.")
    return valor


def _copiar_lista_validada(valor: Iterable[Any], campo: str) -> list[Any]:
    if isinstance(valor, str | bytes | bytearray | memoryview | Mapping) or not isinstance(valor, Iterable):
        raise ErroValidacaoDominio(
            f"'{campo}' deve ser uma sequência ou coleção iterável válida (não str/bytes/Mapping)."
        )
    return list(valor)


@dataclass(frozen=True, slots=True)
class FaixaQuestoes:
    """Faixa inclusiva de números oficiais de questões de uma Prova."""

    inicio: int
    fim: int

    def __post_init__(self) -> None:
        _validar_inteiro_positivo(self.inicio, "inicio")
        _validar_inteiro_positivo(self.fim, "fim")
        if self.fim < self.inicio:
            raise ErroValidacaoDominio(
                f"FaixaQuestoes inválida: 'fim' ({self.fim}) deve ser >= 'inicio' ({self.inicio})."
            )

    def contem(self, numero: int) -> bool:
        return self.inicio <= numero <= self.fim

    def numeros(self) -> range:
        return range(self.inicio, self.fim + 1)

    def __len__(self) -> int:
        return self.fim - self.inicio + 1


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Caixa delimitadora normalizada (x0 < x1, y0 < y1)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        for nome, val in (("x0", self.x0), ("y0", self.y0), ("x1", self.x1), ("y1", self.y1)):
            if isinstance(val, bool) or not isinstance(val, int | float) or not math.isfinite(val):
                raise ErroValidacaoDominio(f"Coordenada '{nome}' da BoundingBox deve ser finita; recebido: {val!r}.")
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            coords = f"({self.x0}, {self.y0}, {self.x1}, {self.y1})"
            raise ErroValidacaoDominio(f"BoundingBox degenerada: esperado x0 < x1 e y0 < y1; recebido {coords}.")


@dataclass(frozen=True, slots=True)
class Gabarito:
    """Registro oficial de resposta correta ou anulação de uma Questão."""

    situacao_gabarito: SituacaoGabarito = SituacaoGabarito.PENDENTE
    alternativa_correta: LetraAlternativa | None = None

    def __post_init__(self) -> None:
        try:
            situacao = SituacaoGabarito(self.situacao_gabarito)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Situação de gabarito inválida: {self.situacao_gabarito!r}.") from err
        object.__setattr__(self, "situacao_gabarito", situacao)

        if self.alternativa_correta is not None:
            try:
                letra = LetraAlternativa(self.alternativa_correta)
            except ValueError as err:
                raise ErroValidacaoDominio(
                    f"Alternativa correta inválida no gabarito: {self.alternativa_correta!r}."
                ) from err
            object.__setattr__(self, "alternativa_correta", letra)

        if situacao == SituacaoGabarito.VALIDA and self.alternativa_correta is None:
            raise ErroValidacaoDominio("Gabarito 'valida' exige alternativa_correta definida (A..E).")
        if situacao in {SituacaoGabarito.ANULADA, SituacaoGabarito.PENDENTE} and self.alternativa_correta is not None:
            raise ErroValidacaoDominio(f"Gabarito '{situacao.value}' não pode definir alternativa_correta.")


@dataclass(frozen=True, slots=True)
class MetadadosIngestao:
    """Telemetria agregada da etapa de extração de uma Ingestão."""

    total_questoes_extraidas: int = 0
    imagens_detectadas: int = 0
    imagens_filtradas_margem: int = 0
    formulas_recortadas: int = 0
    usou_ocr: bool = False
    paginas_fonte_symbol: tuple[int, ...] = ()
    gabarito_enviado: bool = False
    taxonomia_id_encadeada: UUID | None = None
    perfil_id_encadeada: UUID | None = None
    execucao_classificacao_id: UUID | None = None
    status_classificacao_encadeada: str | None = None

    def __post_init__(self) -> None:
        _validar_inteiro_nao_negativo(self.total_questoes_extraidas, "total_questoes_extraidas")
        _validar_inteiro_nao_negativo(self.imagens_detectadas, "imagens_detectadas")
        _validar_inteiro_nao_negativo(self.imagens_filtradas_margem, "imagens_filtradas_margem")
        _validar_inteiro_nao_negativo(self.formulas_recortadas, "formulas_recortadas")
        paginas = tuple(_validar_inteiro_positivo(p, "paginas_fonte_symbol") for p in self.paginas_fonte_symbol)
        object.__setattr__(self, "paginas_fonte_symbol", paginas)
        if self.status_classificacao_encadeada is not None:
            status_limpo = self.status_classificacao_encadeada.strip()
            object.__setattr__(self, "status_classificacao_encadeada", status_limpo or None)


@dataclass(frozen=True, slots=True)
class Alternativa:
    """Opção de resposta (A..E) pertencente a uma Questão objetiva."""

    letra: LetraAlternativa
    texto: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        try:
            letra = LetraAlternativa(self.letra)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Letra de alternativa inválida: {self.letra!r}.") from err
        object.__setattr__(self, "letra", letra)


@dataclass(slots=True)
class AtivoVisual:
    """Elemento gráfico extraído de uma Prova ou enviado manualmente na curadoria."""

    origem: OrigemAtivoVisual
    ordem: int = 0
    alternativa_letra: LetraAlternativa | None = None
    pagina: int | None = None
    bbox: BoundingBox | None = None
    chave_arquivo: str | None = None
    id: UUID = field(default_factory=uuid4)
    questao_id: UUID | None = None

    def __post_init__(self) -> None:
        try:
            self.origem = OrigemAtivoVisual(self.origem)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Origem de ativo visual inválida: {self.origem!r}.") from err

        _validar_inteiro_nao_negativo(self.ordem, "ordem")

        if self.alternativa_letra is not None:
            try:
                self.alternativa_letra = LetraAlternativa(self.alternativa_letra)
            except ValueError as err:
                raise ErroValidacaoDominio(
                    f"Letra de alternativa inválida no ativo visual: {self.alternativa_letra!r}."
                ) from err

        if self.pagina is not None:
            _validar_inteiro_positivo(self.pagina, "pagina")

        if (
            self.origem in {OrigemAtivoVisual.PICTURE_DOCLING, OrigemAtivoVisual.FORMULA_RECORTE}
            and self.pagina is None
        ):
            raise ErroValidacaoDominio(f"AtivoVisual com origem '{self.origem.value}' exige número de página válido.")


@dataclass(slots=True)
class AlertaExtracao:
    """Sinalização determinística de anomalia de extração em uma Questão."""

    SEVERIDADE_POR_CODIGO: ClassVar[dict[CodigoAlertaExtracao, SeveridadeAlerta]] = SEVERIDADE_POR_CODIGO
    ALERTAS_ESTRUTURAIS: ClassVar[frozenset[CodigoAlertaExtracao]] = ALERTAS_ESTRUTURAIS
    ALERTAS_INSPECAO: ClassVar[frozenset[CodigoAlertaExtracao]] = ALERTAS_INSPECAO

    codigo: CodigoAlertaExtracao
    severidade: SeveridadeAlerta | None = None
    status: StatusAlerta = StatusAlerta.ABERTO
    mensagem: str = ""
    resolvido_em: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        try:
            self.codigo = CodigoAlertaExtracao(self.codigo)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Código de alerta inválido: {self.codigo!r}.") from err

        severidade_esperada = SEVERIDADE_POR_CODIGO[self.codigo]
        if self.severidade is None:
            self.severidade = severidade_esperada
        else:
            try:
                self.severidade = SeveridadeAlerta(self.severidade)
            except ValueError as err:
                raise ErroValidacaoDominio(f"Severidade de alerta inválida: {self.severidade!r}.") from err
            if self.severidade != severidade_esperada:
                raise ErroValidacaoDominio(
                    f"Severidade '{self.severidade.value}' incompatível com alerta '{self.codigo.value}' "
                    f"(esperado '{severidade_esperada.value}')."
                )

        try:
            self.status = StatusAlerta(self.status)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Status de alerta inválido: {self.status!r}.") from err

        if self.resolvido_em is not None and not isinstance(self.resolvido_em, datetime):
            raise ErroValidacaoDominio(f"'resolvido_em' deve ser um datetime válido; recebido: {self.resolvido_em!r}.")
        if self.status == StatusAlerta.ABERTO and self.resolvido_em is not None:
            raise ErroInvarianteDominio("Alerta 'aberto' não pode possuir resolvido_em.")
        if self.status == StatusAlerta.RESOLVIDO and self.resolvido_em is None:
            raise ErroInvarianteDominio("Alerta 'resolvido' exige timestamp resolvido_em.")

    @property
    def is_critico(self) -> bool:
        return self.severidade == SeveridadeAlerta.CRITICO

    @property
    def is_aberto(self) -> bool:
        return self.status == StatusAlerta.ABERTO

    @property
    def is_estrutural(self) -> bool:
        return self.codigo in ALERTAS_ESTRUTURAIS

    @property
    def is_inspecao(self) -> bool:
        return self.codigo in ALERTAS_INSPECAO

    def resolver(self, agora: datetime) -> None:
        if not isinstance(agora, datetime):
            raise ErroValidacaoDominio(f"'agora' deve ser um datetime válido ao resolver alerta; recebido: {agora!r}.")
        self.status = StatusAlerta.RESOLVIDO
        self.resolvido_em = agora

    def reabrir(self, mensagem: str | None = None) -> None:
        self.status = StatusAlerta.ABERTO
        self.resolvido_em = None
        if mensagem is not None:
            self.mensagem = mensagem


@dataclass(slots=True)
class Questao:
    """Item individual extraído de uma Prova, desacoplado de classificações."""

    prova_id: UUID
    numero: int
    enunciado: str
    componente: ComponenteProva = ComponenteProva.COMPONENTE_ESPECIFICO
    tipo: TipoQuestao = TipoQuestao.OBJETIVA
    paginas: tuple[int, ...] = ()
    alternativas: list[Alternativa] = field(default_factory=list)
    ativos_visuais: list[AtivoVisual] = field(default_factory=list)
    gabarito: Gabarito = field(default_factory=Gabarito)
    alertas_extracao: list[AlertaExtracao] = field(default_factory=list)
    editada_manualmente: bool = False
    id: UUID = field(default_factory=uuid4)
    versao: int = 1

    def __post_init__(self) -> None:
        _validar_inteiro_positivo(self.numero, "numero")
        _validar_inteiro_positivo(self.versao, "versao")
        try:
            self.componente = ComponenteProva(self.componente)
            self.tipo = TipoQuestao(self.tipo)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Componente ou tipo de questão inválido: {err}") from err

        self.paginas = tuple(_validar_inteiro_positivo(p, "paginas") for p in self.paginas)
        self.alternativas = _copiar_lista_validada(self.alternativas, "alternativas")
        self.ativos_visuais = _copiar_lista_validada(self.ativos_visuais, "ativos_visuais")
        self.alertas_extracao = _copiar_lista_validada(self.alertas_extracao, "alertas_extracao")
        self._validar_alternativas(self.alternativas)
        self._validar_alertas(self.alertas_extracao)

    @staticmethod
    def _validar_alternativas(alternativas: list[Alternativa]) -> None:
        vistas: set[LetraAlternativa] = set()
        for alt in alternativas:
            if alt.letra in vistas:
                raise ErroValidacaoDominio(f"Alternativa duplicada para letra '{alt.letra.value}'.")
            vistas.add(alt.letra)

    @staticmethod
    def _validar_alertas(alertas: list[AlertaExtracao]) -> None:
        vistos: set[CodigoAlertaExtracao] = set()
        for alerta in alertas:
            if alerta.codigo in vistos:
                raise ErroValidacaoDominio(f"Alerta duplicado para código '{alerta.codigo.value}'.")
            vistos.add(alerta.codigo)

    @property
    def tem_alerta_critico_aberto(self) -> bool:
        return any(a.is_critico and a.is_aberto for a in self.alertas_extracao)

    @property
    def codigos_alertas_abertos(self) -> set[CodigoAlertaExtracao]:
        return {a.codigo for a in self.alertas_extracao if a.is_aberto}

    def editar_conteudo(
        self,
        *,
        enunciado: str | None = None,
        alternativas: list[Alternativa] | None = None,
        gabarito: Gabarito | None = None,
    ) -> None:
        if enunciado is not None and not enunciado.strip():
            raise ErroValidacaoDominio("O enunciado não pode ser vazio.")
        if alternativas is not None:
            copia_alternativas = _copiar_lista_validada(alternativas, "alternativas")
            self._validar_alternativas(copia_alternativas)
            if self.tipo == TipoQuestao.OBJETIVA and not copia_alternativas:
                raise ErroValidacaoDominio("Questão objetiva exige ao menos uma alternativa.")
            self.alternativas = copia_alternativas
        if enunciado is not None:
            self.enunciado = enunciado
        if gabarito is not None:
            self.gabarito = gabarito
        self.editada_manualmente = True

    def aplicar_gabarito_oficial(self, gabarito: Gabarito) -> None:
        """Atualiza o gabarito oficial sem marcar edição manual de conteúdo."""
        self.gabarito = gabarito


@dataclass(slots=True)
class Ingestao:
    """Processo registrado de carga, extração e estruturação de uma Prova."""

    prova_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: StatusIngestao = StatusIngestao.PENDENTE
    mensagem_erro: str | None = None
    metadados: MetadadosIngestao = field(default_factory=MetadadosIngestao)
    iniciada_em: datetime | None = None
    concluida_em: datetime | None = None
    criada_em: datetime | None = None

    def __post_init__(self) -> None:
        try:
            self.status = StatusIngestao(self.status)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Status de ingestão inválido: {self.status!r}.") from err

    def iniciar(self, agora: datetime) -> None:
        permitidos = {
            StatusIngestao.PENDENTE,
            StatusIngestao.ERRO,
            StatusIngestao.INTERROMPIDA,
            StatusIngestao.CONCLUIDA,
        }
        if self.status not in permitidos:
            raise ErroInvarianteDominio(f"Não é possível iniciar ingestão no estado '{self.status.value}'.")
        self.status = StatusIngestao.PROCESSANDO
        self.iniciada_em = agora
        self.mensagem_erro = None
        self.concluida_em = None

    def concluir(self, agora: datetime, metadados: MetadadosIngestao) -> None:
        if self.status != StatusIngestao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível concluir ingestão em 'processando'; estado atual: '{self.status.value}'."
            )
        self.status = StatusIngestao.CONCLUIDA
        self.concluida_em = agora
        self.metadados = metadados
        self.mensagem_erro = None

    def falhar(self, mensagem: str, agora: datetime) -> None:
        if self.status != StatusIngestao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível falhar ingestão em 'processando'; estado atual: '{self.status.value}'."
            )
        if not mensagem.strip():
            raise ErroValidacaoDominio("Mensagem de erro da ingestão não pode ser vazia.")
        self.status = StatusIngestao.ERRO
        self.mensagem_erro = mensagem.strip()
        self.concluida_em = agora

    def interromper(self, agora: datetime, motivo: str = "Processo interrompido durante execução.") -> None:
        if self.status != StatusIngestao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível interromper ingestão em 'processando'; estado atual: '{self.status.value}'."
            )
        self.status = StatusIngestao.INTERROMPIDA
        self.mensagem_erro = motivo.strip() or "Processo interrompido durante execução."
        self.concluida_em = agora


@dataclass(slots=True)
class Prova:
    """Caderno oficial de um exame acadêmico, único por (exame, curso, ano)."""

    exame: str
    curso: str
    ano: int
    faixa_ce: FaixaQuestoes | None = None
    id: UUID = field(default_factory=uuid4)
    caminho_pdf: str | None = None
    caminho_gabarito: str | None = None
    caminho_extracao_bruta: str | None = None
    criada_em: datetime | None = None
    atualizada_em: datetime | None = None

    def __post_init__(self) -> None:
        self.exame = self.exame.strip()
        self.curso = self.curso.strip()
        if not self.exame:
            raise ErroValidacaoDominio("'exame' da Prova não pode ser vazio.")
        if not self.curso:
            raise ErroValidacaoDominio("'curso' da Prova não pode ser vazio.")
        if isinstance(self.ano, bool) or not isinstance(self.ano, int) or self.ano < 1900:
            raise ErroValidacaoDominio(f"'ano' da Prova inválido: {self.ano!r}.")
        if self.faixa_ce is None:
            from domain.faixas_enade import resolver_faixa_componente_especifico

            self.faixa_ce = resolver_faixa_componente_especifico(self.ano)

    @property
    def chave_natural(self) -> tuple[str, str, int]:
        return (self.exame.upper(), self.curso, self.ano)
