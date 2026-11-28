"""Perfil de classificação."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from domain.exceptions import ErroValidacaoDominio


@dataclass(frozen=True, slots=True)
class PerfilClassificacao:
    """Conjunto versionado e imutável de diretrizes, guia de fronteiras e prompt."""

    codigo: str
    versao: str
    diretrizes_gerais: str
    guia_fronteiras: str
    template_prompt: str
    descricao: str = ""
    criado_em: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        codigo = self.codigo.strip()
        versao = self.versao.strip()
        diretrizes = self.diretrizes_gerais.strip()
        template = self.template_prompt.strip()
        if not codigo:
            raise ErroValidacaoDominio("'codigo' do PerfilClassificacao não pode ser vazio.")
        if not versao:
            raise ErroValidacaoDominio("'versao' do PerfilClassificacao não pode ser vazia.")
        if not diretrizes:
            raise ErroValidacaoDominio("'diretrizes_gerais' do PerfilClassificacao não podem ser vazias.")
        if not template:
            raise ErroValidacaoDominio("'template_prompt' do PerfilClassificacao não pode ser vazio.")
        object.__setattr__(self, "codigo", codigo)
        object.__setattr__(self, "versao", versao)
        object.__setattr__(self, "diretrizes_gerais", diretrizes)
        object.__setattr__(self, "guia_fronteiras", self.guia_fronteiras.strip())
        object.__setattr__(self, "template_prompt", template)
        object.__setattr__(self, "descricao", self.descricao.strip())

    def snapshot_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "codigo": self.codigo,
            "versao": self.versao,
            "diretrizes_gerais": self.diretrizes_gerais,
            "guia_fronteiras": self.guia_fronteiras,
            "template_prompt": self.template_prompt,
            "descricao": self.descricao,
        }

    @classmethod
    def de_snapshot(cls, snapshot: Mapping[str, Any]) -> PerfilClassificacao:
        if not isinstance(snapshot, Mapping):
            raise ErroValidacaoDominio("'snapshot_perfil' deve ser um mapeamento.")

        codigo = snapshot.get("codigo")
        versao = snapshot.get("versao")
        diretrizes_gerais = snapshot.get("diretrizes_gerais")
        guia_fronteiras = snapshot.get("guia_fronteiras", "")
        template_prompt = snapshot.get("template_prompt")
        descricao = snapshot.get("descricao", "")

        for nome_campo, valor in (
            ("codigo", codigo),
            ("versao", versao),
            ("diretrizes_gerais", diretrizes_gerais),
            ("template_prompt", template_prompt),
        ):
            if not isinstance(valor, str):
                raise ErroValidacaoDominio(f"'{nome_campo}' no snapshot de PerfilClassificacao deve ser string.")

        if guia_fronteiras is None:
            guia_fronteiras = ""
        if not isinstance(guia_fronteiras, str):
            raise ErroValidacaoDominio("'guia_fronteiras' no snapshot de PerfilClassificacao deve ser string.")
        if descricao is None:
            descricao = ""
        if not isinstance(descricao, str):
            raise ErroValidacaoDominio("'descricao' no snapshot de PerfilClassificacao deve ser string.")

        raw_id = snapshot.get("id")
        if raw_id is None:
            perfil_id = uuid4()
        elif isinstance(raw_id, UUID):
            perfil_id = raw_id
        else:
            try:
                perfil_id = UUID(str(raw_id))
            except (ValueError, TypeError, AttributeError) as err:
                raise ErroValidacaoDominio(f"'id' inválido no snapshot de PerfilClassificacao: {raw_id!r}.") from err

        criado_em = snapshot.get("criado_em")
        if criado_em is not None and not isinstance(criado_em, datetime):
            criado_em = None

        return cls(
            id=perfil_id,
            codigo=codigo,
            versao=versao,
            diretrizes_gerais=diretrizes_gerais,
            guia_fronteiras=guia_fronteiras,
            template_prompt=template_prompt,
            descricao=descricao,
            criado_em=criado_em,
        )
