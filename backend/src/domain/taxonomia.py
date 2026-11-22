"""Entidades e objetos de valor de Taxonomia Curricular (Taxonomia, Disciplina, Tópico)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from domain.exceptions import ErroValidacaoDominio

MAX_CHARS_TOPICO = 32
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def normalizar_topico(raw: str) -> str:
    """Normaliza texto livre para slug ASCII kebab-case de até 32 caracteres sem cortar palavras.

    Se o próprio primeiro token contínuo exceder 32 caracteres, retorna string vazia para
    evitar corte no meio da palavra.
    """
    if not isinstance(raw, str):
        return ""

    ascii_text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii").lower().strip()
    slug = _NON_ALNUM_PATTERN.sub("-", ascii_text).strip("-")
    if not slug:
        return ""

    tokens = [token for token in slug.split("-") if token]
    if not tokens or len(tokens[0]) > MAX_CHARS_TOPICO:
        return ""

    selecionados: list[str] = []
    comprimento = 0
    for token in tokens:
        adicional = len(token) if not selecionados else len(token) + 1
        if comprimento + adicional > MAX_CHARS_TOPICO:
            break
        selecionados.append(token)
        comprimento += adicional

    return "-".join(selecionados)


@dataclass(frozen=True, slots=True)
class Topico:
    """Rótulo granular livre em kebab-case ASCII (máx. 32 chars, sem corte de palavras)."""

    valor: str

    def __post_init__(self) -> None:
        normalizado = normalizar_topico(self.valor)
        if not normalizado:
            raise ErroValidacaoDominio(
                f"Tópico inválido ou maior que {MAX_CHARS_TOPICO} caracteres em token único: {self.valor!r}."
            )
        object.__setattr__(self, "valor", normalizado)

    @classmethod
    def criar(cls, raw: str) -> Topico:
        return cls(valor=raw)

    def __str__(self) -> str:
        return self.valor


@dataclass(slots=True)
class Disciplina:
    """Unidade curricular pertencente a uma Taxonomia."""

    codigo: str
    nome: str
    ementa: str = ""
    ativa: bool = True
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.codigo = self.codigo.strip()
        self.nome = self.nome.strip()
        self.ementa = self.ementa.strip()
        if not self.codigo:
            raise ErroValidacaoDominio("'codigo' da Disciplina não pode ser vazio.")
        if not self.nome:
            raise ErroValidacaoDominio("'nome' da Disciplina não pode ser vazio.")

    def arquivar(self) -> None:
        self.ativa = False

    def reativar(self) -> None:
        self.ativa = True


@dataclass(slots=True)
class Taxonomia:
    """Catálogo nomeado e editável de Disciplinas usado para classificação."""

    codigo: str
    nome: str
    curso_referencia: str = ""
    disciplinas: list[Disciplina] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.codigo = self.codigo.strip()
        self.nome = self.nome.strip()
        self.curso_referencia = self.curso_referencia.strip()
        if not self.codigo:
            raise ErroValidacaoDominio("'codigo' da Taxonomia não pode ser vazio.")
        if not self.nome:
            raise ErroValidacaoDominio("'nome' da Taxonomia não pode ser vazio.")

        if isinstance(self.disciplinas, str | bytes | bytearray | memoryview | Mapping) or not isinstance(
            self.disciplinas, Iterable
        ):
            raise ErroValidacaoDominio(
                "'disciplinas' da Taxonomia deve ser uma coleção iterável de Disciplina (não str/bytes/Mapping)."
            )
        self.disciplinas = list(self.disciplinas)

        codigos: set[str] = set()
        for disciplina in self.disciplinas:
            if not isinstance(disciplina, Disciplina):
                raise ErroValidacaoDominio(
                    f"Item de 'disciplinas' da Taxonomia deve ser Disciplina; recebido: {disciplina!r}."
                )
            if disciplina.codigo in codigos:
                raise ErroValidacaoDominio(f"Disciplina duplicada na Taxonomia '{self.codigo}': '{disciplina.codigo}'.")
            codigos.add(disciplina.codigo)

    def ativas(self) -> list[Disciplina]:
        return [d for d in self.disciplinas if d.ativa]

    def mapa_ativas(self) -> dict[str, Disciplina]:
        return {d.codigo: d for d in self.disciplinas if d.ativa}

    def mapa_todas(self) -> dict[str, Disciplina]:
        return {d.codigo: d for d in self.disciplinas}

    def snapshot_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "codigo": self.codigo,
            "nome": self.nome,
            "curso_referencia": self.curso_referencia,
            "disciplinas": [
                {
                    "id": str(d.id),
                    "codigo": d.codigo,
                    "nome": d.nome,
                    "ementa": d.ementa,
                    "ativa": d.ativa,
                }
                for d in self.ativas()
            ],
        }

    @classmethod
    def de_snapshot(cls, snapshot: Mapping[str, Any]) -> Taxonomia:
        if not isinstance(snapshot, Mapping):
            raise ErroValidacaoDominio("'snapshot_taxonomia' deve ser um mapeamento.")

        codigo = snapshot.get("codigo")
        nome = snapshot.get("nome")
        curso_referencia = snapshot.get("curso_referencia", "")
        if not isinstance(codigo, str):
            raise ErroValidacaoDominio("'codigo' no snapshot de Taxonomia deve ser string.")
        if not isinstance(nome, str):
            raise ErroValidacaoDominio("'nome' no snapshot de Taxonomia deve ser string.")
        if curso_referencia is None:
            curso_referencia = ""
        if not isinstance(curso_referencia, str):
            raise ErroValidacaoDominio("'curso_referencia' no snapshot de Taxonomia deve ser string.")

        raw_id = snapshot.get("id")
        if raw_id is None:
            taxonomia_id = uuid4()
        elif isinstance(raw_id, UUID):
            taxonomia_id = raw_id
        else:
            try:
                taxonomia_id = UUID(str(raw_id))
            except (ValueError, TypeError, AttributeError) as err:
                raise ErroValidacaoDominio(f"'id' inválido no snapshot de Taxonomia: {raw_id!r}.") from err

        raw_disciplinas = snapshot.get("disciplinas")
        if (
            raw_disciplinas is None
            or isinstance(raw_disciplinas, str | bytes | bytearray | memoryview | Mapping)
            or not isinstance(raw_disciplinas, Iterable)
        ):
            raise ErroValidacaoDominio("'disciplinas' no snapshot de Taxonomia deve ser uma coleção de mapeamentos.")

        disciplinas: list[Disciplina] = []
        for item in raw_disciplinas:
            if not isinstance(item, Mapping):
                raise ErroValidacaoDominio(
                    f"Item de 'disciplinas' no snapshot deve ser mapeamento; recebido: {item!r}."
                )
            disc_codigo = item.get("codigo")
            disc_nome = item.get("nome")
            disc_ementa = item.get("ementa", "")
            disc_ativa = item.get("ativa", True)
            if not isinstance(disc_codigo, str) or not isinstance(disc_nome, str):
                raise ErroValidacaoDominio("Disciplina no snapshot exige 'codigo' e 'nome' textuais.")
            if disc_ementa is None:
                disc_ementa = ""
            if not isinstance(disc_ementa, str):
                raise ErroValidacaoDominio("'ementa' da Disciplina no snapshot deve ser string.")
            if not isinstance(disc_ativa, bool):
                raise ErroValidacaoDominio("'ativa' da Disciplina no snapshot deve ser booleano.")

            raw_disc_id = item.get("id")
            if raw_disc_id is None:
                disc_id = uuid4()
            elif isinstance(raw_disc_id, UUID):
                disc_id = raw_disc_id
            else:
                try:
                    disc_id = UUID(str(raw_disc_id))
                except (ValueError, TypeError, AttributeError) as err:
                    raise ErroValidacaoDominio(f"'id' inválido de Disciplina no snapshot: {raw_disc_id!r}.") from err

            disciplinas.append(
                Disciplina(
                    id=disc_id,
                    codigo=disc_codigo,
                    nome=disc_nome,
                    ementa=disc_ementa,
                    ativa=disc_ativa,
                )
            )

        return cls(
            id=taxonomia_id,
            codigo=codigo,
            nome=nome,
            curso_referencia=curso_referencia,
            disciplinas=disciplinas,
        )
