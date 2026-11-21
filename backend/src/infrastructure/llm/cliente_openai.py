"""Adaptador OpenAI-compatível com degradação de schema, resiliência e cache em disco."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from application.exceptions import ErroClassificadorLLMError
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.classificacao import IdentidadeClassificador, ResultadoChamada
from infrastructure.config import PISO_MAX_TOKENS_LLM, Settings
from infrastructure.llm.perfis import PerfilProvedorLLM, resolver_perfil_provedor
from infrastructure.storage.local import ArmazenamentoArquivosLocal

logger = logging.getLogger(__name__)

_STATUS_DEGRADACAO_SCHEMA = frozenset({400, 404, 422})
_STATUS_RETRY_TRANSIENTE = frozenset({429, 500, 502, 503, 504})
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", flags=re.IGNORECASE | re.DOTALL)
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)


class _RespostaVaziaOuInvalidaError(ValueError):
    """Sinaliza resposta vazia (ex.: consumo por thinking oculto) ou não estruturada."""


class SaidaBrutaLLMSchema(BaseModel):
    """Validação estrutural local da resposta JSON do LLM.

    Não restringe cardinalidade de `disciplinas_secundarias`/`topicos` nem faixa de
    `confianca` para que `domain.travas_classificacao.validar_e_normalizar_classificacao`
    possa executar o saneamento determinístico e registrar revisão prioritária.
    """

    model_config = ConfigDict(extra="ignore")

    disciplina_principal: str
    disciplinas_secundarias: list[str] = Field(default_factory=list)
    topicos: list[str] = Field(default_factory=list)
    justificativa: str
    confianca: float

    @field_validator("disciplinas_secundarias", "topicos", mode="before")
    @classmethod
    def _coagir_none_para_lista(cls, valor: Any) -> Any:
        return [] if valor is None else valor

    @field_validator("confianca", mode="before")
    @classmethod
    def _validar_confianca_finita(cls, valor: Any) -> float:
        if isinstance(valor, bool):
            raise ValueError("'confianca' não pode ser booleano.")
        numero = float(valor)
        if not math.isfinite(numero):
            raise ValueError("'confianca' deve ser número finito.")
        return numero


def _normalizar_para_json(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return {str(k): _normalizar_para_json(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_normalizar_para_json(v) for v in valor]
    return valor


def _extrair_e_validar_json(raw_text: str | None) -> dict[str, Any]:
    texto = _THINK_BLOCK_RE.sub("", raw_text or "").strip()
    if not texto:
        raise _RespostaVaziaOuInvalidaError("Resposta vazia do modelo (possível consumo total em thinking oculto).")

    if texto.startswith("```"):
        texto = _FENCE_RE.sub("", texto).strip()

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc_direto:
        decoder = json.JSONDecoder()
        ultimo_erro_validacao: ValidationError | None = None
        pos = 0
        while True:
            idx = texto.find("{", pos)
            if idx == -1:
                break
            try:
                candidato, fim = decoder.raw_decode(texto, idx)
            except json.JSONDecodeError:
                pos = idx + 1
                continue
            if isinstance(candidato, dict):
                try:
                    return SaidaBrutaLLMSchema.model_validate(candidato).model_dump()
                except ValidationError as exc_val:
                    ultimo_erro_validacao = exc_val
            pos = fim

        if ultimo_erro_validacao is not None:
            raise ultimo_erro_validacao from exc_direto
        raise exc_direto

    if not isinstance(dados, dict):
        raise _RespostaVaziaOuInvalidaError("JSON retornado pelo modelo não é um objeto.")

    validado = SaidaBrutaLLMSchema.model_validate(dados)
    return validado.model_dump()


class ClienteOpenAICompativel:
    """Adaptador único OpenAI-compatível implementando ``ClassificadorMultimodal``."""

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        max_rpm: int = 10,
        timeout_s: float = 60.0,
        max_tokens: int = PISO_MAX_TOKENS_LLM,
        armazenamento: ArmazenamentoArquivos | None = None,
        cache_dir: Path | None = None,
        client: Any | None = None,
        client_factory: Callable[..., Any] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
        perf_counter_fn: Callable[[], float] = time.perf_counter,
        max_tentativas: int = 5,
        backoff_base_s: float = 1.0,
        backoff_max_s: float = 30.0,
    ) -> None:
        self._identidade = IdentidadeClassificador(
            provider=provider.strip(),
            model=model.strip(),
            base_url=base_url.strip(),
        )
        self._perfil: PerfilProvedorLLM = resolver_perfil_provedor(
            self._identidade.provider,
            self._identidade.model,
        )
        self._max_rpm = int(max_rpm)
        self._min_interval_s = (60.0 / self._max_rpm) if self._max_rpm > 0 else 0.0
        self._max_tokens = max(PISO_MAX_TOKENS_LLM, int(max_tokens))
        self._armazenamento = armazenamento
        self._cache_dir = Path(cache_dir).resolve() if cache_dir is not None else None
        self._sleep_fn = sleep_fn
        self._monotonic_fn = monotonic_fn
        self._perf_counter_fn = perf_counter_fn
        self._max_tentativas = max(1, int(max_tentativas))
        self._backoff_base_s = max(0.0, float(backoff_base_s))
        self._backoff_max_s = max(self._backoff_base_s, float(backoff_max_s))

        self._rate_lock = threading.Lock()
        self._last_call_ts: float | None = None

        if client is not None:
            self._client = client
        elif client_factory is not None:
            self._client = client_factory(
                base_url=self._identidade.base_url,
                api_key=api_key,
                timeout=timeout_s,
            )
        else:
            openai_kwargs: dict[str, Any] = {
                "base_url": self._identidade.base_url,
                "api_key": api_key or "EMPTY",
                "timeout": timeout_s,
                "max_retries": 0,
            }
            if self._perfil.default_headers:
                openai_kwargs["default_headers"] = dict(self._perfil.default_headers)
            self._client = OpenAI(**openai_kwargs)

    @property
    def identidade(self) -> IdentidadeClassificador:
        return self._identidade

    @property
    def perfil(self) -> PerfilProvedorLLM:
        return self._perfil

    def _calcular_chave_cache(
        self,
        *,
        system: str,
        user: str,
        imagens_png: Sequence[bytes],
        schema: Mapping[str, Any],
        nome_schema: str,
    ) -> str:
        envelope = {
            "identidade": {
                "provider": self._identidade.provider,
                "model": self._identidade.model,
                "base_url": self._identidade.base_url,
            },
            "nome_schema": nome_schema,
            "system": system,
            "user": user,
            "schema": _normalizar_para_json(schema),
            "imagens_sha256": [hashlib.sha256(img).hexdigest() for img in imagens_png],
        }
        serializado = json.dumps(envelope, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(serializado.encode("utf-8")).hexdigest()

    def _ler_cache(self, cache_key: str) -> dict[str, Any] | None:
        chave_arquivo = f"cache/llm/{cache_key}.json"
        if self._armazenamento is not None:
            if not self._armazenamento.existe(chave_arquivo):
                return None
            bruto = self._armazenamento.ler(chave_arquivo).decode("utf-8")
            dados = json.loads(bruto)
            return dados if isinstance(dados, dict) else None

        if self._cache_dir is not None:
            arquivo = self._cache_dir / f"{cache_key}.json"
            if not arquivo.is_file():
                return None
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            return dados if isinstance(dados, dict) else None

        return None

    def _gravar_cache(self, cache_key: str, payload: Mapping[str, Any]) -> None:
        conteudo_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        if self._armazenamento is not None:
            self._armazenamento.salvar(f"cache/llm/{cache_key}.json", conteudo_bytes)
            return

        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            destino = self._cache_dir / f"{cache_key}.json"
            fd, caminho_tmp = tempfile.mkstemp(prefix=".tmp-", dir=self._cache_dir)
            try:
                with os.fdopen(fd, "wb") as arquivo_tmp:
                    arquivo_tmp.write(conteudo_bytes)
                    arquivo_tmp.flush()
                    os.fsync(arquivo_tmp.fileno())
                os.replace(caminho_tmp, destino)
            except Exception:
                Path(caminho_tmp).unlink(missing_ok=True)
                raise

    def _aguardar_rate_limit(self) -> None:
        if self._min_interval_s <= 0.0:
            return
        with self._rate_lock:
            agora = self._monotonic_fn()
            if self._last_call_ts is not None:
                espera = self._min_interval_s - (agora - self._last_call_ts)
                if espera > 0.0:
                    self._sleep_fn(espera)
            self._last_call_ts = self._monotonic_fn()

    def _calcular_backoff(self, indice_erro: int) -> float:
        return min(self._backoff_max_s, self._backoff_base_s * (2 ** max(0, indice_erro - 1)))

    def _montar_kwargs_chamada(
        self,
        *,
        system: str,
        user_content: list[dict[str, Any]],
        schema: Mapping[str, Any],
        nome_schema: str,
        max_tokens: int,
        modo_schema: str,
    ) -> dict[str, Any]:
        schema_dict = _normalizar_para_json(schema)
        system_conteudo = system
        if modo_schema in {"json_object", "prompt_json"}:
            system_conteudo = (
                f"{system}\n\nRETORNE EXCLUSIVAMENTE UM OBJETO JSON VÁLIDO SEGUINDO O SCHEMA:\n"
                f"{json.dumps(schema_dict, ensure_ascii=False)}"
            )

        kwargs: dict[str, Any] = {
            "model": self._identidade.model,
            "messages": [
                {"role": "system", "content": system_conteudo},
                {"role": "user", "content": copy.deepcopy(user_content)},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
        }

        if modo_schema == "json_schema":
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": nome_schema,
                    "schema": schema_dict,
                    "strict": True,
                },
            }
        elif modo_schema == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        if self._perfil.extra_body is not None:
            kwargs["extra_body"] = copy.deepcopy(dict(self._perfil.extra_body))

        return kwargs

    def classificar_estruturado(
        self,
        *,
        system: str,
        user: str,
        imagens_png: Sequence[bytes],
        schema: Mapping[str, Any],
        nome_schema: str,
        max_tokens: int = PISO_MAX_TOKENS_LLM,
        usar_cache: bool = True,
    ) -> ResultadoChamada:
        cache_key = self._calcular_chave_cache(
            system=system,
            user=user,
            imagens_png=imagens_png,
            schema=schema,
            nome_schema=nome_schema,
        )

        if usar_cache:
            cached = self._ler_cache(cache_key)
            if cached is not None and isinstance(cached.get("dados_brutos"), Mapping):
                return ResultadoChamada(
                    dados_brutos=dict(cached["dados_brutos"]),
                    prompt_tokens=int(cached.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(cached.get("completion_tokens", 0) or 0),
                    latencia_ms=float(cached.get("latencia_ms", 0.0) or 0.0),
                    from_cache=True,
                    cache_key=cache_key,
                    tentativas=1,
                    modelo_efetivo=str(cached.get("modelo_efetivo") or self._identidade.model),
                    modo_schema=str(cached.get("modo_schema") or "json_schema"),
                )

        user_content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        for img_bytes in imagens_png:
            b64 = base64.b64encode(img_bytes).decode("ascii")
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )

        max_tokens_efetivo = max(int(max_tokens), self._max_tokens, PISO_MAX_TOKENS_LLM)
        modo_schema = "json_schema"
        tentativas = 0
        erros_transientes = 0
        ultimo_erro: Exception | None = None
        limite_total_tentativas = self._max_tentativas + 2
        t0_chamada = self._perf_counter_fn()

        while tentativas < limite_total_tentativas:
            tentativas += 1
            self._aguardar_rate_limit()
            kwargs = self._montar_kwargs_chamada(
                system=system,
                user_content=user_content,
                schema=schema,
                nome_schema=nome_schema,
                max_tokens=max_tokens_efetivo,
                modo_schema=modo_schema,
            )

            try:
                resp = self._client.chat.completions.create(**kwargs)
                raw_text = resp.choices[0].message.content
                dados = _extrair_e_validar_json(raw_text)
                latencia_ms = round(max(0.0, (self._perf_counter_fn() - t0_chamada) * 1000.0), 2)

                usage = getattr(resp, "usage", None)
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                modelo_efetivo = str(getattr(resp, "model", None) or self._identidade.model)

                if usar_cache:
                    payload_cache = {
                        "identidade": {
                            "provider": self._identidade.provider,
                            "model": self._identidade.model,
                            "base_url": self._identidade.base_url,
                        },
                        "cache_key": cache_key,
                        "modelo_efetivo": modelo_efetivo,
                        "modo_schema": modo_schema,
                        "dados_brutos": dados,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "latencia_ms": latencia_ms,
                        "tentativas": tentativas,
                    }
                    self._gravar_cache(cache_key, payload_cache)

                return ResultadoChamada(
                    dados_brutos=dados,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latencia_ms=latencia_ms,
                    from_cache=False,
                    cache_key=cache_key,
                    tentativas=tentativas,
                    modelo_efetivo=modelo_efetivo,
                    modo_schema=modo_schema,
                )

            except APIStatusError as exc:
                ultimo_erro = exc
                status = exc.status_code
                if status in _STATUS_DEGRADACAO_SCHEMA:
                    if modo_schema == "json_schema":
                        logger.warning(
                            "Endpoint rejeitou json_schema (HTTP %s); degradando para json_object.",
                            status,
                        )
                        modo_schema = "json_object"
                        continue
                    if modo_schema == "json_object":
                        logger.warning(
                            "Endpoint rejeitou json_object (HTTP %s); degradando para prompt_json.",
                            status,
                        )
                        modo_schema = "prompt_json"
                        continue
                    raise ErroClassificadorLLMError(
                        f"Endpoint rejeitou chamada mesmo em modo prompt_json (HTTP {status}): {exc}"
                    ) from exc

                if status in _STATUS_RETRY_TRANSIENTE or status >= 500:
                    erros_transientes += 1
                    if erros_transientes >= self._max_tentativas:
                        break
                    backoff = self._calcular_backoff(erros_transientes)
                    logger.warning(
                        "Erro transitório HTTP %s no provedor '%s' (tentativa %d/%d); aguardando %.2fs.",
                        status,
                        self._identidade.provider,
                        erros_transientes,
                        self._max_tentativas,
                        backoff,
                    )
                    self._sleep_fn(backoff)
                    continue

                raise ErroClassificadorLLMError(
                    f"Erro HTTP não recuperável ({status}) no provedor '{self._identidade.provider}': {exc}"
                ) from exc

            except (APITimeoutError, APIConnectionError, TimeoutError, ConnectionError) as exc:
                ultimo_erro = exc
                erros_transientes += 1
                if erros_transientes >= self._max_tentativas:
                    break
                backoff = self._calcular_backoff(erros_transientes)
                logger.warning(
                    "Falha de conexão/timeout no provedor '%s' (tentativa %d/%d); aguardando %.2fs.",
                    self._identidade.provider,
                    erros_transientes,
                    self._max_tentativas,
                    backoff,
                )
                self._sleep_fn(backoff)

            except (
                json.JSONDecodeError,
                ValidationError,
                _RespostaVaziaOuInvalidaError,
                IndexError,
                AttributeError,
            ) as exc:
                ultimo_erro = exc
                erros_transientes += 1
                if erros_transientes >= self._max_tentativas:
                    break
                backoff = self._calcular_backoff(erros_transientes)
                logger.warning(
                    "Resposta inválida do provedor '%s' (%s) (tentativa %d/%d); aguardando %.2fs.",
                    self._identidade.provider,
                    type(exc).__name__,
                    erros_transientes,
                    self._max_tentativas,
                    backoff,
                )
                self._sleep_fn(backoff)

        raise ErroClassificadorLLMError(
            f"Falha após {tentativas} tentativa(s) no provedor '{self._identidade.provider}': {ultimo_erro}"
        ) from ultimo_erro


def criar_classificador_multimodal(
    settings: Settings,
    armazenamento: ArmazenamentoArquivos | None = None,
    *,
    client: Any | None = None,
) -> ClienteOpenAICompativel:
    """Fábrica padrão do adaptador ``ClienteOpenAICompativel`` a partir de ``Settings``."""
    armazenamento_efetivo = armazenamento or ArmazenamentoArquivosLocal(settings.resolved_data_dir)
    return ClienteOpenAICompativel(
        provider=settings.llm_provider,
        base_url=settings.llm_base_url,
        api_key=settings.effective_llm_api_key,
        model=settings.llm_model,
        max_rpm=settings.llm_max_rpm,
        timeout_s=float(settings.llm_timeout_s),
        max_tokens=settings.llm_max_tokens,
        armazenamento=armazenamento_efetivo,
        client=client,
    )
