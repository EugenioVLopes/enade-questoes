"""Composition root isolado para a CLI ``enade-eval`` (sem importar ``presentation.main``)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from application.avaliacao import (
    AvaliarConjuntoOuroUseCase,
    CompararAvaliacoesUseCase,
    ConsultarHistoricoConcordanciaUseCase,
    ExportarConjuntoOuroUseCase,
)
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.classificacao import ClassificadorMultimodal
from infrastructure.config import Settings
from infrastructure.llm.cliente_openai import criar_classificador_multimodal
from infrastructure.persistence.avaliacao import (
    ConsultaAvaliacaoSqlAlchemy,
    RepositorioConjuntoOuroSqlAlchemy,
)
from infrastructure.persistence.database import (
    create_readonly_db_engine,
    create_readonly_session_factory,
)
from infrastructure.storage.local import ArmazenamentoArquivosLocal


def resolver_settings_eval(
    settings: Settings | None = None,
    *,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    provider: str | None = None,
) -> Settings:
    """Aplica overrides da CLI sobre ``Settings``, inferindo ``vllm_qwen`` quando aplicável."""
    eff = settings or Settings()
    updates: dict[str, Any] = {}

    base_url_override = base_url is not None and bool(base_url.strip())
    if base_url_override and base_url is not None:
        updates["llm_base_url"] = base_url.strip()

    eff_model = eff.llm_model
    if model is not None and model.strip():
        eff_model = model.strip()
        updates["llm_model"] = eff_model

    if api_key is not None and api_key.strip():
        updates["llm_api_key"] = api_key.strip()

    if provider is not None and provider.strip():
        updates["llm_provider"] = provider.strip()
    elif base_url_override and "qwen" in eff_model.lower():
        updates["llm_provider"] = "vllm_qwen"

    return eff.model_copy(update=updates) if updates else eff


class ProvedorDependenciasEval:
    """Provedor de casos de uso da CLI ``enade-eval`` com PostgreSQL estritamente somente-leitura."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: sessionmaker[Session] | None = None,
        classificador: ClassificadorMultimodal | None = None,
        armazenamento: ArmazenamentoArquivos | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._session_factory_externa = session_factory
        self._classificador_externo = classificador
        self._armazenamento_externo = armazenamento
        self._engine_propria: Engine | None = None
        self._session_factory_propria: sessionmaker[Session] | None = None

    def _obter_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory_externa is not None:
            return self._session_factory_externa
        if self._session_factory_propria is None:
            self._engine_propria = create_readonly_db_engine(self._settings.database_url)
            self._session_factory_propria = create_readonly_session_factory(self._engine_propria)
        return self._session_factory_propria

    def _obter_armazenamento(self) -> ArmazenamentoArquivos:
        if self._armazenamento_externo is not None:
            return self._armazenamento_externo
        return ArmazenamentoArquivosLocal(self._settings.resolved_data_dir)

    def criar_exportar_ouro(self) -> ExportarConjuntoOuroUseCase:
        repo_ouro = RepositorioConjuntoOuroSqlAlchemy(self._obter_session_factory())
        return ExportarConjuntoOuroUseCase(repo_ouro=repo_ouro)

    def criar_avaliar(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        provider: str | None = None,
    ) -> AvaliarConjuntoOuroUseCase:
        session_factory = self._obter_session_factory()
        armazenamento = self._obter_armazenamento()
        if self._classificador_externo is not None:
            classificador = self._classificador_externo
        else:
            settings_llm = resolver_settings_eval(
                self._settings,
                base_url=base_url,
                model=model,
                api_key=api_key,
                provider=provider,
            )
            classificador = criar_classificador_multimodal(settings_llm, armazenamento=armazenamento)
        return AvaliarConjuntoOuroUseCase(
            repo_ouro=RepositorioConjuntoOuroSqlAlchemy(session_factory),
            consulta=ConsultaAvaliacaoSqlAlchemy(session_factory),
            classificador=classificador,
            armazenamento=armazenamento,
        )

    def criar_comparar(self) -> CompararAvaliacoesUseCase:
        return CompararAvaliacoesUseCase()

    def criar_historico(self) -> ConsultarHistoricoConcordanciaUseCase:
        consulta = ConsultaAvaliacaoSqlAlchemy(self._obter_session_factory())
        return ConsultarHistoricoConcordanciaUseCase(consulta=consulta)

    def close(self) -> None:
        if self._engine_propria is not None:
            self._engine_propria.dispose()
            self._engine_propria = None
            self._session_factory_propria = None


def criar_provedor_eval(
    *,
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    classificador: ClassificadorMultimodal | None = None,
    armazenamento: ArmazenamentoArquivos | None = None,
) -> ProvedorDependenciasEval:
    return ProvedorDependenciasEval(
        settings=settings,
        session_factory=session_factory,
        classificador=classificador,
        armazenamento=armazenamento,
    )
