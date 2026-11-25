"""Casos de uso de Avaliação Offline: exportar Conjunto-Ouro, avaliar, comparar e histórico IA × Humano."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from application.classificacao import ClassificarQuestaoService
from application.exceptions import ErroClassificadorLLMError, RecursoNaoEncontradoError
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.avaliacao import ConsultaAvaliacao
from application.ports.classificacao import ClassificadorMultimodal
from application.ports.repositorios import RepositorioConjuntoOuro
from application.seed import TEMPLATE_PROMPT_PADRAO
from domain.avaliacao import (
    AvaliacaoClassificacao,
    ChaveQuestaoOuro,
    ConjuntoOuro,
    DivergenciaAvaliacao,
    MetricasCamada1,
    MetricasCamada2,
    MetricasCamada3,
    ParConfusao,
    PredicaoClassificacao,
    ResultadoGate,
    ResultadoItemAvaliacao,
)
from domain.classificacao import PerfilClassificacao
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.metricas_avaliacao import (
    ROTULO_PREDICAO_INVALIDA,
    avaliar_gate_regressao,
    calcular_avaliacao_classificacao,
)

VERSAO_RELATORIO_AVALIACAO = "1.0"
_SLUG_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _agora_utc() -> datetime:
    return datetime.now(UTC)


def _sanitizar_segmento(texto: str) -> str:
    limpo = _SLUG_SAFE_RE.sub("-", texto.strip()).strip("-.")
    return limpo or "item"


def _parse_datetime_iso(raw: Any, *, campo: str) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise ErroValidacaoDominio(f"Campo '{campo}' deve ser string ISO-8601 não vazia.")
    texto = raw.strip()
    if texto.endswith("Z"):
        texto = f"{texto[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(texto)
    except ValueError as err:
        raise ErroValidacaoDominio(f"Timestamp ISO inválido em '{campo}': {raw!r}.") from err
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


class PreflightConjuntoOuroError(ErroInvarianteDominio):
    """Falha na validação prévia (preflight) antes de qualquer chamada ao LLM."""

    def __init__(self, erros: list[str] | tuple[str, ...]) -> None:
        self.erros = tuple(erros)
        detalhes = "\n".join(f"- {erro}" for erro in self.erros)
        super().__init__(f"Preflight do Conjunto-Ouro falhou ({len(self.erros)} problema(s)):\n{detalhes}")


@dataclass(frozen=True, slots=True)
class ResultadoExportacaoOuro:
    conjunto: ConjuntoOuro
    caminho_saida: str


@dataclass(frozen=True, slots=True)
class ResultadoAvaliacaoOffline:
    avaliacao: AvaliacaoClassificacao
    chave_json: str
    chave_markdown: str
    caminho_json: Path
    caminho_markdown: Path


@dataclass(frozen=True, slots=True)
class ResultadoComparacaoAvaliacoes:
    baseline: AvaliacaoClassificacao
    candidato: AvaliacaoClassificacao
    gate: ResultadoGate


@dataclass(frozen=True, slots=True)
class GrupoHistoricoConcordancia:
    perfil_codigo: str
    perfil_versao: str
    modelo: str
    total_revisadas: int
    aprovacoes_diretas: int
    correcoes_principal: int
    correcoes_apenas_secundarias: int
    taxa_aprovacao_direta: float
    taxa_correcao_principal: float
    taxa_correcao_apenas_secundarias: float


@dataclass(frozen=True, slots=True)
class ResultadoHistoricoConcordancia:
    taxonomia_codigo: str | None
    total_registros: int
    grupos: tuple[GrupoHistoricoConcordancia, ...]


def carregar_perfil_avaliacao(perfil_spec: str, consulta: ConsultaAvaliacao) -> PerfilClassificacao:
    """Resolve ``codigo@versao`` no PostgreSQL ou rascunho local em arquivo YAML/JSON."""
    spec = perfil_spec.strip()
    if not spec:
        raise ErroValidacaoDominio("Especificação '--perfil' não pode ser vazia.")

    caminho = Path(spec)
    if caminho.is_file() or caminho.suffix.lower() in {".yaml", ".yml", ".json"}:
        if not caminho.is_file():
            raise RecursoNaoEncontradoError(f"Arquivo de perfil não encontrado: '{spec}'.")
        try:
            texto = caminho.read_text(encoding="utf-8")
            if caminho.suffix.lower() == ".json":
                bruto = json.loads(texto)
            else:
                bruto = yaml.safe_load(texto)
        except (OSError, json.JSONDecodeError, yaml.YAMLError) as err:
            raise ErroValidacaoDominio(f"Falha ao carregar arquivo de perfil '{spec}': {err}") from err

        if not isinstance(bruto, Mapping):
            raise ErroValidacaoDominio(f"Arquivo de perfil '{spec}' deve conter um objeto/mapeamento YAML ou JSON.")

        dados = dict(bruto)
        template_raw = dados.get("template_prompt")
        if template_raw is None or (isinstance(template_raw, str) and not template_raw.strip()):
            dados["template_prompt"] = TEMPLATE_PROMPT_PADRAO
        if dados.get("guia_fronteiras") is None:
            dados["guia_fronteiras"] = ""
        if dados.get("descricao") is None:
            dados["descricao"] = ""
        return PerfilClassificacao.de_snapshot(dados)

    if "@" not in spec:
        raise ErroValidacaoDominio(
            f"Especificação de perfil inválida: '{spec}'. Use '<codigo>@<versao>' ou caminho para YAML/JSON."
        )
    codigo, versao = spec.split("@", 1)
    codigo = codigo.strip()
    versao = versao.strip()
    if not codigo or not versao:
        raise ErroValidacaoDominio(
            f"Especificação de perfil inválida: '{spec}'. Informe '<codigo>@<versao>' não vazios."
        )

    perfil = consulta.buscar_perfil_por_codigo_versao(codigo, versao)
    if perfil is None:
        raise RecursoNaoEncontradoError(f"Perfil de classificação '{codigo}@{versao}' não encontrado no PostgreSQL.")
    return perfil


def avaliacao_para_dict(avaliacao: AvaliacaoClassificacao) -> dict[str, Any]:
    """Serializa ``AvaliacaoClassificacao`` em JSON estruturado completo para persistência e comparação."""
    return {
        "versao_schema": VERSAO_RELATORIO_AVALIACAO,
        "taxonomia_codigo": avaliacao.taxonomia_codigo,
        "conjunto_ouro_digest": avaliacao.conjunto_ouro_digest,
        "perfil_codigo": avaliacao.perfil_codigo,
        "perfil_versao": avaliacao.perfil_versao,
        "modelo_identidade": avaliacao.modelo_identidade,
        "executado_em": avaliacao.executado_em.isoformat(),
        "camada1": {
            "total_itens": avaliacao.camada1.total_itens,
            "acuracia_principal": avaliacao.camada1.acuracia_principal,
            "macro_f1_principal": avaliacao.camada1.macro_f1_principal,
            "jaccard_secundarias": avaliacao.camada1.jaccard_secundarias,
            "f1_secundarias": avaliacao.camada1.f1_secundarias,
            "exact_match": avaliacao.camada1.exact_match,
        },
        "camada2": {
            "matriz_confusao": {
                esperada: dict(preditas) for esperada, preditas in avaliacao.camada2.matriz_confusao.items()
            },
            "pares_confusao_ranqueados": [
                {
                    "esperada": par.esperada,
                    "predita": par.predita,
                    "contagem": par.contagem,
                }
                for par in avaliacao.camada2.pares_confusao_ranqueados
            ],
            "divergencias": [
                {
                    "exame": div.chave.exame,
                    "curso": div.chave.curso,
                    "ano": div.chave.ano,
                    "numero": div.chave.numero,
                    "esperada_principal": div.esperada_principal,
                    "esperadas_secundarias": list(div.esperadas_secundarias),
                    "predita_principal": div.predita_principal,
                    "preditas_secundarias": list(div.preditas_secundarias),
                    "confianca": div.confianca,
                    "revisao_prioritaria": div.revisao_prioritaria,
                    "trecho_justificativa": div.trecho_justificativa,
                }
                for div in avaliacao.camada2.divergencias
            ],
        },
        "camada3": {
            "conclusao_valida": avaliacao.camada3.conclusao_valida,
            "validade_primeira_tentativa": avaliacao.camada3.validade_primeira_tentativa,
            "taxa_revisao_prioritaria": avaliacao.camada3.taxa_revisao_prioritaria,
            "taxa_erro_alta_confianca": avaliacao.camada3.taxa_erro_alta_confianca,
            "total_alta_confianca": avaliacao.camada3.total_alta_confianca,
            "erros_alta_confianca": avaliacao.camada3.erros_alta_confianca,
            "prompt_tokens": avaliacao.camada3.prompt_tokens,
            "completion_tokens": avaliacao.camada3.completion_tokens,
            "cache_hits": avaliacao.camada3.cache_hits,
            "cache_hit_rate": avaliacao.camada3.cache_hit_rate,
            "latencia_media_ms": avaliacao.camada3.latencia_media_ms,
            "latencia_p95_ms": avaliacao.camada3.latencia_p95_ms,
            "estabilidade_multipass": avaliacao.camada3.estabilidade_multipass,
        },
        "itens": [
            {
                "exame": item.chave.exame,
                "curso": item.chave.curso,
                "ano": item.chave.ano,
                "numero": item.chave.numero,
                "esperada_principal": item.esperada_principal,
                "esperadas_secundarias": list(item.esperadas_secundarias),
                "predita_principal": item.predita_principal,
                "preditas_secundarias": list(item.preditas_secundarias),
                "conclusao_valida": item.conclusao_valida,
                "principal_correta": item.principal_correta,
                "jaccard_secundarias": item.jaccard_secundarias,
                "f1_secundarias": item.f1_secundarias,
                "exact_match": item.exact_match,
                "confianca": item.confianca,
                "revisao_prioritaria": item.revisao_prioritaria,
                "justificativa": item.justificativa,
            }
            for item in avaliacao.itens
        ],
    }


def _chave_de_mapping(raw: Mapping[str, Any], contexto: str) -> ChaveQuestaoOuro:
    try:
        return ChaveQuestaoOuro(
            exame=str(raw["exame"]),
            curso=str(raw["curso"]),
            ano=raw["ano"],
            numero=raw["numero"],
        )
    except (KeyError, TypeError, ValueError) as err:
        raise ErroValidacaoDominio(f"Chave de questão inválida em {contexto}: {err}.") from err


def avaliacao_de_dict(dados: Mapping[str, Any]) -> AvaliacaoClassificacao:
    """Reconstrói ``AvaliacaoClassificacao`` a partir de relatório JSON serializado."""
    if not isinstance(dados, Mapping):
        raise ErroValidacaoDominio("Relatório de avaliação deve ser um objeto JSON.")

    try:
        c1_raw = dados["camada1"]
        c2_raw = dados["camada2"]
        c3_raw = dados["camada3"]
        itens_raw = dados["itens"]
        if (
            not isinstance(c1_raw, Mapping)
            or not isinstance(c2_raw, Mapping)
            or not isinstance(c3_raw, Mapping)
            or not isinstance(itens_raw, list)
        ):
            raise ErroValidacaoDominio("Estrutura inválida em camada1/camada2/camada3/itens do relatório.")

        camada1 = MetricasCamada1(
            total_itens=int(c1_raw["total_itens"]),
            acuracia_principal=float(c1_raw["acuracia_principal"]),
            macro_f1_principal=float(c1_raw["macro_f1_principal"]),
            jaccard_secundarias=float(c1_raw["jaccard_secundarias"]),
            f1_secundarias=float(c1_raw["f1_secundarias"]),
            exact_match=float(c1_raw["exact_match"]),
        )

        matriz_raw = c2_raw.get("matriz_confusao", {})
        if not isinstance(matriz_raw, Mapping):
            raise ErroValidacaoDominio("'matriz_confusao' inválida no relatório.")
        matriz = {
            str(esp): {str(pred): int(cnt) for pred, cnt in pred_map.items()}
            for esp, pred_map in matriz_raw.items()
            if isinstance(pred_map, Mapping)
        }
        pares = tuple(
            ParConfusao(
                esperada=str(par["esperada"]),
                predita=str(par["predita"]),
                contagem=int(par["contagem"]),
            )
            for par in c2_raw.get("pares_confusao_ranqueados", ())
        )
        divergencias = tuple(
            DivergenciaAvaliacao(
                chave=_chave_de_mapping(div, "divergencias"),
                esperada_principal=str(div["esperada_principal"]),
                esperadas_secundarias=tuple(str(s) for s in div.get("esperadas_secundarias", ())),
                predita_principal=str(div["predita_principal"]) if div.get("predita_principal") is not None else None,
                preditas_secundarias=tuple(str(s) for s in div.get("preditas_secundarias", ())),
                confianca=float(div["confianca"]),
                revisao_prioritaria=bool(div["revisao_prioritaria"]),
                trecho_justificativa=str(div.get("trecho_justificativa", "")),
            )
            for div in c2_raw.get("divergencias", ())
        )
        camada2 = MetricasCamada2(
            matriz_confusao=matriz,
            pares_confusao_ranqueados=pares,
            divergencias=divergencias,
        )

        estab_raw = c3_raw.get("estabilidade_multipass")
        camada3 = MetricasCamada3(
            conclusao_valida=float(c3_raw["conclusao_valida"]),
            validade_primeira_tentativa=float(c3_raw["validade_primeira_tentativa"]),
            taxa_revisao_prioritaria=float(c3_raw["taxa_revisao_prioritaria"]),
            taxa_erro_alta_confianca=float(c3_raw["taxa_erro_alta_confianca"]),
            total_alta_confianca=int(c3_raw["total_alta_confianca"]),
            erros_alta_confianca=int(c3_raw["erros_alta_confianca"]),
            prompt_tokens=int(c3_raw["prompt_tokens"]),
            completion_tokens=int(c3_raw["completion_tokens"]),
            cache_hits=int(c3_raw["cache_hits"]),
            cache_hit_rate=float(c3_raw["cache_hit_rate"]),
            latencia_media_ms=float(c3_raw["latencia_media_ms"]),
            latencia_p95_ms=float(c3_raw["latencia_p95_ms"]),
            estabilidade_multipass=float(estab_raw) if estab_raw is not None else None,
        )

        itens = tuple(
            ResultadoItemAvaliacao(
                chave=_chave_de_mapping(item, "itens"),
                esperada_principal=str(item["esperada_principal"]),
                esperadas_secundarias=tuple(str(s) for s in item.get("esperadas_secundarias", ())),
                predita_principal=(
                    str(item["predita_principal"]) if item.get("predita_principal") is not None else None
                ),
                preditas_secundarias=tuple(str(s) for s in item.get("preditas_secundarias", ())),
                conclusao_valida=bool(item["conclusao_valida"]),
                principal_correta=bool(item["principal_correta"]),
                jaccard_secundarias=float(item["jaccard_secundarias"]),
                f1_secundarias=float(item["f1_secundarias"]),
                exact_match=bool(item["exact_match"]),
                confianca=float(item["confianca"]),
                revisao_prioritaria=bool(item["revisao_prioritaria"]),
                justificativa=str(item.get("justificativa", "")),
            )
            for item in itens_raw
        )

        return AvaliacaoClassificacao(
            taxonomia_codigo=str(dados["taxonomia_codigo"]),
            conjunto_ouro_digest=str(dados["conjunto_ouro_digest"]),
            perfil_codigo=str(dados["perfil_codigo"]),
            perfil_versao=str(dados["perfil_versao"]),
            modelo_identidade=str(dados["modelo_identidade"]),
            executado_em=_parse_datetime_iso(dados.get("executado_em"), campo="executado_em"),
            camada1=camada1,
            camada2=camada2,
            camada3=camada3,
            itens=itens,
        )
    except KeyError as err:
        raise ErroValidacaoDominio(f"Campo obrigatório ausente no relatório de avaliação: {err}.") from err
    except (TypeError, ValueError) as err:
        raise ErroValidacaoDominio(f"Relatório de avaliação inválido: {err}.") from err


def carregar_relatorio_avaliacao(caminho: str | Path) -> AvaliacaoClassificacao:
    alvo = Path(caminho)
    if not alvo.is_file():
        raise RecursoNaoEncontradoError(f"Arquivo de relatório não encontrado: '{caminho}'.")
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ErroValidacaoDominio(f"Falha ao ler JSON de avaliação '{caminho}': {err}") from err
    return avaliacao_de_dict(dados)


def renderizar_relatorio_markdown(avaliacao: AvaliacaoClassificacao) -> str:
    c1 = avaliacao.camada1
    c2 = avaliacao.camada2
    c3 = avaliacao.camada3

    linhas = [
        f"# Avaliação de Classificação — `{avaliacao.taxonomia_codigo}`",
        "",
        f"- **Perfil**: `{avaliacao.perfil_codigo}@{avaliacao.perfil_versao}`",
        f"- **Modelo**: `{avaliacao.modelo_identidade}`",
        f"- **Digest do Conjunto-Ouro**: `{avaliacao.conjunto_ouro_digest}`",
        f"- **Executado em**: `{avaliacao.executado_em.isoformat()}`",
        "",
        "## Camada 1 — Acurácia Curricular",
        "",
        "| Métrica | Valor |",
        "| --- | ---: |",
        f"| Total de itens | {c1.total_itens} |",
        f"| Acurácia principal | {c1.acuracia_principal * 100:.2f}% |",
        f"| Macro-F1 principal | {c1.macro_f1_principal * 100:.2f}% |",
        f"| Jaccard médio secundárias | {c1.jaccard_secundarias * 100:.2f}% |",
        f"| F1 médio secundárias | {c1.f1_secundarias * 100:.2f}% |",
        f"| Exact Match combinado | {c1.exact_match * 100:.2f}% |",
        "",
        "## Camada 2 — Diagnóstico de Fronteiras",
        "",
        "### Principais pares de confusão (esperada → predita)",
        "",
    ]
    if c2.pares_confusao_ranqueados:
        linhas.extend(["| Esperada | Predita | Ocorrências |", "| --- | --- | ---: |"])
        for par in c2.pares_confusao_ranqueados:
            linhas.append(f"| `{par.esperada}` | `{par.predita}` | {par.contagem} |")
    else:
        linhas.append("Nenhuma confusão na disciplina principal.")

    linhas.extend(["", "### Questões divergentes", ""])
    if c2.divergencias:
        linhas.extend(
            [
                "| Questão | Esperado | Predito | Confiança | Rev. Prior. | Justificativa |",
                "| --- | --- | --- | ---: | :---: | --- |",
            ]
        )
        for div in c2.divergencias:
            esp_sec = ", ".join(div.esperadas_secundarias) or "-"
            pred_sec = ", ".join(div.preditas_secundarias) or "-"
            pred_princ = div.predita_principal or ROTULO_PREDICAO_INVALIDA
            just = div.trecho_justificativa.replace("|", "\\|").replace("\n", " ")
            linhas.append(
                f"| {div.chave.exame} {div.chave.ano} Q{div.chave.numero:02d} "
                f"| `{div.esperada_principal}` [{esp_sec}] "
                f"| `{pred_princ}` [{pred_sec}] "
                f"| {div.confianca:.2f} "
                f"| {'sim' if div.revisao_prioritaria else 'não'} "
                f"| {just} |"
            )
    else:
        linhas.append("Nenhuma divergência registrada (100% Exact Match).")

    linhas.extend(
        [
            "",
            "## Camada 3 — Saúde Operacional e Calibração",
            "",
            "| Indicador | Valor |",
            "| --- | ---: |",
            f"| Conclusão válida | {c3.conclusao_valida * 100:.2f}% |",
            f"| Validade na 1ª tentativa | {c3.validade_primeira_tentativa * 100:.2f}% |",
            f"| Taxa de revisão prioritária | {c3.taxa_revisao_prioritaria * 100:.2f}% |",
            (
                f"| Erro em alta confiança (>= 0,85) | {c3.taxa_erro_alta_confianca * 100:.2f}% "
                f"({c3.erros_alta_confianca}/{c3.total_alta_confianca}) |"
            ),
            f"| Prompt tokens | {c3.prompt_tokens} |",
            f"| Completion tokens | {c3.completion_tokens} |",
            f"| Cache hits | {c3.cache_hits} ({c3.cache_hit_rate * 100:.2f}%) |",
            f"| Latência média (ms) | {c3.latencia_media_ms:.2f} |",
            f"| Latência p95 (ms) | {c3.latencia_p95_ms:.2f} |",
        ]
    )
    if c3.estabilidade_multipass is not None:
        linhas.append(f"| Estabilidade multipass | {c3.estabilidade_multipass * 100:.2f}% |")
    linhas.append("")
    return "\n".join(linhas)


class ExportarConjuntoOuroUseCase:
    def __init__(self, repo_ouro: RepositorioConjuntoOuro) -> None:
        self._repo_ouro = repo_ouro

    def execute(
        self,
        *,
        taxonomia_codigo: str,
        destino: str,
        agora: datetime | None = None,
    ) -> ResultadoExportacaoOuro:
        conjunto = self._repo_ouro.exportar_elegiveis(taxonomia_codigo, agora or _agora_utc())
        caminho_saida = self._repo_ouro.salvar_snapshot(conjunto, destino)
        return ResultadoExportacaoOuro(conjunto=conjunto, caminho_saida=caminho_saida)


class AvaliarConjuntoOuroUseCase:
    def __init__(
        self,
        *,
        repo_ouro: RepositorioConjuntoOuro,
        consulta: ConsultaAvaliacao,
        classificador: ClassificadorMultimodal,
        armazenamento: ArmazenamentoArquivos,
    ) -> None:
        self._repo_ouro = repo_ouro
        self._consulta = consulta
        self._classificador = classificador
        self._armazenamento = armazenamento

    def execute(
        self,
        *,
        caminho_ouro: str,
        perfil_spec: str,
        no_cache: bool = False,
        repeticoes: int = 1,
        max_tokens: int = 4096,
        agora: datetime | None = None,
    ) -> ResultadoAvaliacaoOffline:
        if isinstance(repeticoes, bool) or repeticoes < 1:
            raise ErroValidacaoDominio(f"'repeticoes' deve ser inteiro >= 1; recebido: {repeticoes!r}.")

        conjunto = self._repo_ouro.carregar_snapshot(caminho_ouro)
        if conjunto.total_itens == 0:
            raise ErroValidacaoDominio("Conjunto-Ouro vazio não pode ser avaliado.")

        taxonomia = self._consulta.buscar_taxonomia_por_codigo(conjunto.taxonomia_codigo)
        if taxonomia is None:
            raise RecursoNaoEncontradoError(
                f"Taxonomia '{conjunto.taxonomia_codigo}' do Conjunto-Ouro não encontrada no PostgreSQL."
            )

        perfil = carregar_perfil_avaliacao(perfil_spec, self._consulta)

        chaves = [item.chave for item in conjunto.itens]
        questoes_por_chave = self._consulta.carregar_questoes_por_chaves(chaves)
        alertas_por_chave = {chave: questao.alertas_extracao for chave, (_, questao) in questoes_por_chave.items()}

        erros_preflight = conjunto.validar_preflight(taxonomia, alertas_por_chave)
        if erros_preflight:
            raise PreflightConjuntoOuroError(erros_preflight)

        servico = ClassificarQuestaoService(self._classificador, self._armazenamento)
        predicoes: list[PredicaoClassificacao] = []
        modelo_efetivo_observado = ""

        for item in conjunto.itens:
            prova, questao = questoes_por_chave[item.chave]

            passes_tuplas: list[tuple[str, tuple[str, ...]]] = []
            primeiro_conclusao_valida = False
            primeiro_principal: str | None = None
            primeiro_secundarias: tuple[str, ...] = ()
            primeiro_confianca = 0.0
            primeiro_revisao = True
            primeiro_justificativa = ""
            primeiro_tentativas = 1
            primeiro_saneamento = False

            total_prompt_tokens = 0
            total_completion_tokens = 0
            todos_cache_hit = True
            latencias_passes: list[float] = []

            for indice_passe in range(repeticoes):
                try:
                    resultado = servico.classificar(
                        questao=questao,
                        taxonomia=taxonomia,
                        perfil=perfil,
                        prova=prova,
                        ignorar_cache=no_cache,
                        max_tokens=max_tokens,
                    )
                except ErroClassificadorLLMError as err:
                    passes_tuplas.append((ROTULO_PREDICAO_INVALIDA, ()))
                    todos_cache_hit = False
                    latencias_passes.append(0.0)
                    if indice_passe == 0:
                        primeiro_conclusao_valida = False
                        primeiro_justificativa = str(err).strip() or type(err).__name__
                    continue

                metricas = resultado.metricas
                if metricas.modelo_efetivo.strip():
                    modelo_efetivo_observado = metricas.modelo_efetivo.strip()

                total_prompt_tokens += metricas.prompt_tokens
                total_completion_tokens += metricas.completion_tokens
                todos_cache_hit = todos_cache_hit and metricas.cache_hit
                latencias_passes.append(metricas.latencia_ms)

                if resultado.sucesso and resultado.classificacao is not None:
                    clf = resultado.classificacao
                    passes_tuplas.append((clf.disciplina_principal, clf.disciplinas_secundarias))
                    if indice_passe == 0:
                        primeiro_conclusao_valida = True
                        primeiro_principal = clf.disciplina_principal
                        primeiro_secundarias = clf.disciplinas_secundarias
                        primeiro_confianca = clf.confianca
                        primeiro_revisao = clf.revisao_prioritaria
                        primeiro_justificativa = clf.justificativa
                        primeiro_tentativas = max(1, metricas.tentativas)
                        primeiro_saneamento = metricas.saneada
                else:
                    passes_tuplas.append((ROTULO_PREDICAO_INVALIDA, ()))
                    if indice_passe == 0:
                        primeiro_conclusao_valida = False
                        primeiro_justificativa = (
                            resultado.erro.mensagem if resultado.erro is not None else "Classificação inválida."
                        )
                        primeiro_tentativas = max(1, metricas.tentativas)
                        primeiro_saneamento = metricas.saneada

            latencia_media_item = (sum(latencias_passes) / len(latencias_passes)) if latencias_passes else 0.0
            predicoes.append(
                PredicaoClassificacao(
                    chave=item.chave,
                    conclusao_valida=primeiro_conclusao_valida,
                    disciplina_principal=primeiro_principal,
                    disciplinas_secundarias=primeiro_secundarias,
                    confianca=primeiro_confianca,
                    revisao_prioritaria=primeiro_revisao,
                    justificativa=primeiro_justificativa,
                    tentativas=primeiro_tentativas,
                    houve_saneamento=primeiro_saneamento,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    from_cache=todos_cache_hit,
                    latencia_ms=round(latencia_media_item, 2),
                    passes=tuple(passes_tuplas),
                )
            )

        instante = agora or _agora_utc()
        modelo_identidade = modelo_efetivo_observado or self._classificador.identidade.model
        avaliacao = calcular_avaliacao_classificacao(
            conjunto,
            predicoes,
            perfil_codigo=perfil.codigo,
            perfil_versao=perfil.versao,
            modelo_identidade=modelo_identidade,
            executado_em=instante,
        )

        timestamp_slug = instante.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        nome_base = (
            f"{timestamp_slug}_{_sanitizar_segmento(avaliacao.taxonomia_codigo)}_"
            f"{_sanitizar_segmento(perfil.codigo)}@{_sanitizar_segmento(perfil.versao)}_"
            f"{_sanitizar_segmento(modelo_identidade)}"
        )
        chave_json = f"evals/{nome_base}.json"
        chave_md = f"evals/{nome_base}.md"
        sufixo = 2
        while self._armazenamento.existe(chave_json) or self._armazenamento.existe(chave_md):
            chave_json = f"evals/{nome_base}_{sufixo}.json"
            chave_md = f"evals/{nome_base}_{sufixo}.md"
            sufixo += 1

        conteudo_json = json.dumps(avaliacao_para_dict(avaliacao), ensure_ascii=False, indent=2) + "\n"
        conteudo_md = renderizar_relatorio_markdown(avaliacao)

        chave_json_salva = self._armazenamento.salvar(chave_json, conteudo_json.encode("utf-8"))
        chave_md_salva = self._armazenamento.salvar(chave_md, conteudo_md.encode("utf-8"))

        return ResultadoAvaliacaoOffline(
            avaliacao=avaliacao,
            chave_json=chave_json_salva,
            chave_markdown=chave_md_salva,
            caminho_json=self._armazenamento.resolver_caminho(chave_json_salva),
            caminho_markdown=self._armazenamento.resolver_caminho(chave_md_salva),
        )


class CompararAvaliacoesUseCase:
    def execute(
        self,
        *,
        caminho_baseline: str | Path,
        caminho_candidato: str | Path,
        modo_migracao: bool = False,
    ) -> ResultadoComparacaoAvaliacoes:
        baseline = carregar_relatorio_avaliacao(caminho_baseline)
        candidato = carregar_relatorio_avaliacao(caminho_candidato)
        gate = avaliar_gate_regressao(baseline, candidato, modo_migracao=modo_migracao)
        return ResultadoComparacaoAvaliacoes(baseline=baseline, candidato=candidato, gate=gate)


class ConsultarHistoricoConcordanciaUseCase:
    def __init__(self, consulta: ConsultaAvaliacao) -> None:
        self._consulta = consulta

    def execute(self, *, taxonomia_codigo: str | None = None) -> ResultadoHistoricoConcordancia:
        registros = self._consulta.listar_registros_historico(taxonomia_codigo=taxonomia_codigo)

        contagens: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
        for reg in registros:
            chave = (reg.perfil_codigo, reg.perfil_versao, reg.modelo)
            bucket = contagens[chave]
            bucket[0] += 1
            if reg.final_disciplina_principal != reg.ia_disciplina_principal:
                bucket[2] += 1
            elif set(reg.final_disciplinas_secundarias) != set(reg.ia_disciplinas_secundarias):
                bucket[3] += 1
            else:
                bucket[1] += 1

        grupos: list[GrupoHistoricoConcordancia] = []
        for perfil_codigo, perfil_versao, modelo in sorted(contagens):
            total, diretas, principal, secundarias = contagens[(perfil_codigo, perfil_versao, modelo)]
            grupos.append(
                GrupoHistoricoConcordancia(
                    perfil_codigo=perfil_codigo,
                    perfil_versao=perfil_versao,
                    modelo=modelo,
                    total_revisadas=total,
                    aprovacoes_diretas=diretas,
                    correcoes_principal=principal,
                    correcoes_apenas_secundarias=secundarias,
                    taxa_aprovacao_direta=diretas / total,
                    taxa_correcao_principal=principal / total,
                    taxa_correcao_apenas_secundarias=secundarias / total,
                )
            )

        return ResultadoHistoricoConcordancia(
            taxonomia_codigo=taxonomia_codigo.strip() if taxonomia_codigo else None,
            total_registros=len(registros),
            grupos=tuple(grupos),
        )
