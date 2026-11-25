from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from application.avaliacao import (
    AvaliarConjuntoOuroUseCase,
    ConsultarHistoricoConcordanciaUseCase,
    PreflightConjuntoOuroError,
    avaliacao_de_dict,
    avaliacao_para_dict,
    carregar_perfil_avaliacao,
    renderizar_relatorio_markdown,
)
from application.exceptions import ErroClassificadorLLMError, RecursoNaoEncontradoError
from application.ports.avaliacao import RegistroHistoricoClassificacao
from application.ports.classificacao import IdentidadeClassificador, ResultadoChamada
from application.seed import TEMPLATE_PROMPT_PADRAO
from domain.avaliacao import ChaveQuestaoOuro, ConjuntoOuro, ItemConjuntoOuro, PredicaoClassificacao
from domain.classificacao import PerfilClassificacao
from domain.enums import ComponenteProva, LetraAlternativa, SituacaoGabarito, TipoQuestao
from domain.exceptions import ErroValidacaoDominio
from domain.metricas_avaliacao import ROTULO_PREDICAO_INVALIDA, calcular_avaliacao_classificacao
from domain.prova import Alternativa, FaixaQuestoes, Gabarito, Prova, Questao
from domain.taxonomia import Disciplina, Taxonomia
from infrastructure.config import Settings
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from presentation.cli.bootstrap import resolver_settings_eval
from presentation.cli.eval_cli import app


class _ConsultaFake:
    def __init__(
        self,
        *,
        taxonomia: Taxonomia | None = None,
        perfis: dict[tuple[str, str], PerfilClassificacao] | None = None,
        questoes: dict[ChaveQuestaoOuro, tuple[Prova, Questao]] | None = None,
        historico: Sequence[RegistroHistoricoClassificacao] = (),
    ) -> None:
        self.taxonomia = taxonomia
        self.perfis = perfis or {}
        self.questoes = questoes or {}
        self.historico = list(historico)

    def buscar_taxonomia_por_codigo(self, codigo: str) -> Taxonomia | None:
        if self.taxonomia is not None and self.taxonomia.codigo == codigo:
            return self.taxonomia
        return None

    def buscar_perfil_por_codigo_versao(self, codigo: str, versao: str) -> PerfilClassificacao | None:
        return self.perfis.get((codigo, versao))

    def carregar_questoes_por_chaves(
        self,
        chaves: Sequence[ChaveQuestaoOuro],
    ) -> dict[ChaveQuestaoOuro, tuple[Prova, Questao]]:
        return {c: self.questoes[c] for c in chaves if c in self.questoes}

    def listar_registros_historico(
        self,
        taxonomia_codigo: str | None = None,
    ) -> Sequence[RegistroHistoricoClassificacao]:
        if taxonomia_codigo is None:
            return list(self.historico)
        return [r for r in self.historico if r.taxonomia_codigo == taxonomia_codigo]


class _RepoOuroFake:
    def __init__(self, conjunto: ConjuntoOuro) -> None:
        self.conjunto = conjunto

    def exportar_elegiveis(self, taxonomia_codigo: str, agora: datetime) -> ConjuntoOuro:
        return self.conjunto

    def salvar_snapshot(self, conjunto: ConjuntoOuro, destino: str) -> str:
        return destino

    def carregar_snapshot(self, origem: str) -> ConjuntoOuro:
        return self.conjunto


class _ClassificadorSequencialFake:
    def __init__(self, respostas: dict[int, list[dict[str, Any] | Exception]]) -> None:
        self._respostas = {num: list(seq) for num, seq in respostas.items()}
        self.chamadas: list[dict[str, Any]] = []

    @property
    def identidade(self) -> IdentidadeClassificador:
        return IdentidadeClassificador(
            provider="vllm_qwen",
            model="Qwen/Qwen3-27B",
            base_url="http://localhost:8005/v1",
        )

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
        self.chamadas.append({"user": user, "usar_cache": usar_cache})
        for num, fila in self._respostas.items():
            if f"QUESTÃO {num:02d}" in user:
                proximo = fila.pop(0) if len(fila) > 1 else fila[0]
                if isinstance(proximo, Exception):
                    raise proximo
                return ResultadoChamada(
                    dados_brutos=proximo,
                    prompt_tokens=100,
                    completion_tokens=20,
                    latencia_ms=15.0,
                    from_cache=False,
                    cache_key=f"k-{num}",
                    modelo_efetivo="Qwen/Qwen3-27B",
                )
        raise AssertionError(f"Questão inesperada no prompt: {user}")


def _taxonomia_exemplo() -> Taxonomia:
    return Taxonomia(
        codigo="enade-ec",
        nome="ENADE EC",
        curso_referencia="Engenharia de Computação",
        disciplinas=[
            Disciplina(codigo="alg", nome="Algoritmos", ementa="Complexidade e grafos.", ativa=True),
            Disciplina(codigo="redes", nome="Redes", ementa="TCP/IP e roteamento.", ativa=True),
            Disciplina(codigo="so", nome="Sistemas Operacionais", ementa="Kernel e escalonamento.", ativa=True),
        ],
    )


def _questao_exemplo(prova_id: Any, numero: int) -> Questao:
    return Questao(
        prova_id=prova_id,
        numero=numero,
        enunciado=f"Enunciado da questão {numero}",
        componente=ComponenteProva.COMPONENTE_ESPECIFICO,
        tipo=TipoQuestao.OBJETIVA,
        alternativas=[Alternativa(letra=letra, texto=f"Alternativa {letra.value}") for letra in LetraAlternativa],
        gabarito=Gabarito(situacao_gabarito=SituacaoGabarito.VALIDA, alternativa_correta=LetraAlternativa.A),
    )


def test_carregar_perfil_avaliacao_yaml_e_json_e_banco(tmp_path: Path) -> None:
    yaml_path = tmp_path / "rascunho.yaml"
    yaml_path.write_text(
        "codigo: rascunho-qwen\nversao: v2\ndiretrizes_gerais: Classifique com rigor.\n",
        encoding="utf-8",
    )
    consulta = _ConsultaFake()

    perfil_yaml = carregar_perfil_avaliacao(str(yaml_path), consulta)
    assert perfil_yaml.codigo == "rascunho-qwen"
    assert perfil_yaml.versao == "v2"
    assert perfil_yaml.template_prompt == TEMPLATE_PROMPT_PADRAO
    assert perfil_yaml.guia_fronteiras == ""

    json_path = tmp_path / "rascunho.json"
    json_path.write_text(
        json.dumps(
            {
                "codigo": "rascunho-json",
                "versao": "v1",
                "diretrizes_gerais": "Diretriz customizada",
                "guia_fronteiras": "Fronteira 1",
                "template_prompt": "[SYSTEM]\n{diretrizes_gerais}\n[USER]\n{enunciado}",
            }
        ),
        encoding="utf-8",
    )
    perfil_json = carregar_perfil_avaliacao(str(json_path), consulta)
    assert perfil_json.guia_fronteiras == "Fronteira 1"
    assert "[USER]" in perfil_json.template_prompt

    with pytest.raises(ErroValidacaoDominio):
        carregar_perfil_avaliacao("sem-arroba", consulta)

    with pytest.raises(RecursoNaoEncontradoError):
        carregar_perfil_avaliacao("inexistente@v1", consulta)

    with pytest.raises(RecursoNaoEncontradoError):
        carregar_perfil_avaliacao(str(tmp_path / "nao-existe.yaml"), consulta)


def test_avaliacao_para_dict_e_de_dict_roundtrip_completo() -> None:
    agora = datetime(2026, 11, 25, 8, 0, tzinfo=UTC)
    c1 = ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2023, 1)
    c2 = ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2023, 2)
    ouro = ConjuntoOuro(
        "1.0",
        "enade-ec",
        agora,
        (
            ItemConjuntoOuro(chave=c1, disciplina_principal="alg", disciplinas_secundarias=("so",)),
            ItemConjuntoOuro(chave=c2, disciplina_principal="redes"),
        ),
    )
    preds = (
        PredicaoClassificacao(
            chave=c1,
            conclusao_valida=True,
            disciplina_principal="alg",
            disciplinas_secundarias=("so",),
            confianca=0.92,
            prompt_tokens=100,
            completion_tokens=20,
            from_cache=True,
            latencia_ms=10.0,
            passes=(("alg", ("so",)), ("alg", ("so",))),
        ),
        PredicaoClassificacao(
            chave=c2,
            conclusao_valida=True,
            disciplina_principal="alg",
            disciplinas_secundarias=(),
            confianca=0.88,
            revisao_prioritaria=False,
            justificativa="Focou no algoritmo.",
            tentativas=2,
            houve_saneamento=True,
            prompt_tokens=150,
            completion_tokens=30,
            from_cache=False,
            latencia_ms=40.0,
            passes=(("alg", ()), ("redes", ())),
        ),
    )
    avaliacao = calcular_avaliacao_classificacao(
        ouro,
        preds,
        perfil_codigo="v2",
        perfil_versao="v1",
        modelo_identidade="Qwen/Qwen3-27B",
        executado_em=agora,
    )

    payload = avaliacao_para_dict(avaliacao)
    reconstruida = avaliacao_de_dict(json.loads(json.dumps(payload)))

    assert reconstruida == avaliacao
    md = renderizar_relatorio_markdown(reconstruida)
    assert "Camada 1 — Acurácia Curricular" in md
    assert "Camada 2 — Diagnóstico de Fronteiras" in md
    assert "Camada 3 — Saúde Operacional e Calibração" in md
    assert "Estabilidade multipass" in md
    assert "`redes` | `alg` | 1" in md


def test_avaliar_use_case_multipass_com_erro_llm_e_sanitizacao_caminho(tmp_path: Path) -> None:
    agora = datetime(2026, 11, 25, 8, 5, tzinfo=UTC)
    tax = _taxonomia_exemplo()
    prova = Prova(
        exame="ENADE",
        curso="Engenharia de Computação",
        ano=2023,
        faixa_ce=FaixaQuestoes(1, 2),
    )
    q1 = _questao_exemplo(prova.id, 1)
    q2 = _questao_exemplo(prova.id, 2)
    c1 = ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2023, 1)
    c2 = ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2023, 2)
    ouro = ConjuntoOuro(
        "1.0",
        "enade-ec",
        agora,
        (
            ItemConjuntoOuro(chave=c1, disciplina_principal="alg"),
            ItemConjuntoOuro(chave=c2, disciplina_principal="redes"),
        ),
    )
    perfil = PerfilClassificacao(
        codigo="v2",
        versao="v1",
        diretrizes_gerais="Diretrizes",
        guia_fronteiras="Fronteiras",
        template_prompt=TEMPLATE_PROMPT_PADRAO,
    )
    consulta = _ConsultaFake(
        taxonomia=tax,
        perfis={("v2", "v1"): perfil},
        questoes={c1: (prova, q1), c2: (prova, q2)},
    )
    classificador = _ClassificadorSequencialFake(
        {
            1: [
                {
                    "disciplina_principal": "alg",
                    "disciplinas_secundarias": [],
                    "topicos": ["grafos"],
                    "justificativa": "Questão de grafos.",
                    "confianca": 0.95,
                },
                {
                    "disciplina_principal": "alg",
                    "disciplinas_secundarias": [],
                    "topicos": ["grafos"],
                    "justificativa": "Questão de grafos.",
                    "confianca": 0.95,
                },
            ],
            2: [
                {
                    "disciplina_principal": "redes",
                    "disciplinas_secundarias": [],
                    "topicos": ["tcp"],
                    "justificativa": "Questão de TCP.",
                    "confianca": 0.90,
                },
                ErroClassificadorLLMError("Timeout no segundo passe"),
            ],
        }
    )
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    use_case = AvaliarConjuntoOuroUseCase(
        repo_ouro=_RepoOuroFake(ouro),
        consulta=consulta,
        classificador=classificador,
        armazenamento=armazenamento,
    )

    resultado = use_case.execute(
        caminho_ouro="ignorado.json",
        perfil_spec="v2@v1",
        no_cache=True,
        repeticoes=2,
        agora=agora,
    )

    assert len(classificador.chamadas) == 4
    assert all(ch["usar_cache"] is False for ch in classificador.chamadas)
    assert resultado.avaliacao.camada1.acuracia_principal == pytest.approx(1.0)
    assert resultado.avaliacao.camada3.conclusao_valida == pytest.approx(1.0)
    # Q1 estável (2/2 iguais), Q2 instável (passe 2 falhou -> ROTULO_PREDICAO_INVALIDA)
    assert resultado.avaliacao.camada3.estabilidade_multipass == pytest.approx(0.5)
    assert resultado.caminho_json.is_file()
    assert resultado.caminho_markdown.is_file()
    assert resultado.chave_json.startswith("evals/")
    assert "Qwen-Qwen3-27B" in resultado.chave_json

    # Se falhar na primeira passada com ErroClassificadorLLMError, contabiliza conclusão inválida
    classificador_falha_p1 = _ClassificadorSequencialFake(
        {
            1: [ErroClassificadorLLMError("HTTP 500")],
            2: [
                {
                    "disciplina_principal": "redes",
                    "disciplinas_secundarias": [],
                    "topicos": ["tcp"],
                    "justificativa": "OK",
                    "confianca": 0.90,
                }
            ],
        }
    )
    use_case_falha = AvaliarConjuntoOuroUseCase(
        repo_ouro=_RepoOuroFake(ouro),
        consulta=consulta,
        classificador=classificador_falha_p1,
        armazenamento=armazenamento,
    )
    res_falha = use_case_falha.execute(caminho_ouro="ignorado.json", perfil_spec="v2@v1", agora=agora)
    assert res_falha.avaliacao.camada3.conclusao_valida == pytest.approx(0.5)
    assert res_falha.avaliacao.camada2.divergencias[0].predita_principal is None
    assert ROTULO_PREDICAO_INVALIDA in res_falha.avaliacao.camada2.matriz_confusao["alg"]

    # Preflight aborta antes de chamar LLM
    tax_arquivada = Taxonomia(
        codigo="enade-ec",
        nome="ENADE EC",
        curso_referencia="Engenharia de Computação",
        disciplinas=[
            Disciplina(codigo="alg", nome="Algoritmos", ementa="...", ativa=False),
            Disciplina(codigo="redes", nome="Redes", ementa="...", ativa=True),
        ],
    )
    classificador_nao_chamado = _ClassificadorSequencialFake({})
    use_case_preflight = AvaliarConjuntoOuroUseCase(
        repo_ouro=_RepoOuroFake(ouro),
        consulta=_ConsultaFake(
            taxonomia=tax_arquivada,
            perfis={("v2", "v1"): perfil},
            questoes={c1: (prova, q1), c2: (prova, q2)},
        ),
        classificador=classificador_nao_chamado,
        armazenamento=armazenamento,
    )
    with pytest.raises(PreflightConjuntoOuroError) as exc_info:
        use_case_preflight.execute(caminho_ouro="ignorado.json", perfil_spec="v2@v1", agora=agora)
    assert "alg" in str(exc_info.value)
    assert classificador_nao_chamado.chamadas == []


def test_consultar_historico_concordancia_agrupamento_e_taxas() -> None:
    registros = (
        RegistroHistoricoClassificacao(
            taxonomia_codigo="enade-ec",
            perfil_codigo="v2",
            perfil_versao="v1",
            modelo="gemini-2.5-flash-lite",
            ia_disciplina_principal="alg",
            ia_disciplinas_secundarias=("so",),
            final_disciplina_principal="alg",
            final_disciplinas_secundarias=("so",),
        ),
        RegistroHistoricoClassificacao(
            taxonomia_codigo="enade-ec",
            perfil_codigo="v2",
            perfil_versao="v1",
            modelo="gemini-2.5-flash-lite",
            ia_disciplina_principal="alg",
            ia_disciplinas_secundarias=("so", "redes"),
            final_disciplina_principal="alg",
            final_disciplinas_secundarias=("redes", "so"),  # Mesmas secundárias em ordem diferente
        ),
        RegistroHistoricoClassificacao(
            taxonomia_codigo="enade-ec",
            perfil_codigo="v2",
            perfil_versao="v1",
            modelo="gemini-2.5-flash-lite",
            ia_disciplina_principal="alg",
            ia_disciplinas_secundarias=("so",),
            final_disciplina_principal="redes",
            final_disciplinas_secundarias=("so",),
        ),
        RegistroHistoricoClassificacao(
            taxonomia_codigo="enade-ec",
            perfil_codigo="v2",
            perfil_versao="v1",
            modelo="gemini-2.5-flash-lite",
            ia_disciplina_principal="alg",
            ia_disciplinas_secundarias=(),
            final_disciplina_principal="alg",
            final_disciplinas_secundarias=("so",),
        ),
        RegistroHistoricoClassificacao(
            taxonomia_codigo="enade-ec",
            perfil_codigo="v3",
            perfil_versao="v1",
            modelo="Qwen/Qwen3-27B",
            ia_disciplina_principal="redes",
            ia_disciplinas_secundarias=(),
            final_disciplina_principal="redes",
            final_disciplinas_secundarias=(),
        ),
    )
    use_case = ConsultarHistoricoConcordanciaUseCase(_ConsultaFake(historico=registros))
    res = use_case.execute(taxonomia_codigo="enade-ec")

    assert res.total_registros == 5
    assert len(res.grupos) == 2

    g_v2 = res.grupos[0]
    assert g_v2.perfil_codigo == "v2"
    assert g_v2.modelo == "gemini-2.5-flash-lite"
    assert g_v2.total_revisadas == 4
    assert g_v2.aprovacoes_diretas == 2
    assert g_v2.correcoes_principal == 1
    assert g_v2.correcoes_apenas_secundarias == 1
    assert g_v2.taxa_aprovacao_direta == pytest.approx(0.5)
    assert g_v2.taxa_correcao_principal == pytest.approx(0.25)
    assert g_v2.taxa_correcao_apenas_secundarias == pytest.approx(0.25)

    g_v3 = res.grupos[1]
    assert g_v3.perfil_codigo == "v3"
    assert g_v3.taxa_aprovacao_direta == pytest.approx(1.0)


def test_resolver_settings_eval_infere_vllm_qwen_e_respeita_provider_explicito() -> None:
    base = Settings(llm_provider="gemini_openai", llm_model="gemini-2.5-flash-lite")

    qwen_inferido = resolver_settings_eval(
        base,
        base_url="http://localhost:8005/v1",
        model="Qwen/Qwen3-27B",
    )
    assert qwen_inferido.llm_provider == "vllm_qwen"
    assert qwen_inferido.llm_base_url == "http://localhost:8005/v1"
    assert qwen_inferido.llm_model == "Qwen/Qwen3-27B"

    provider_explicito = resolver_settings_eval(
        base,
        base_url="http://localhost:8005/v1",
        model="Qwen/Qwen3-27B",
        provider="openai",
    )
    assert provider_explicito.llm_provider == "openai"

    sem_base_url = resolver_settings_eval(base, model="Qwen/Qwen3-27B")
    assert sem_base_url.llm_provider == "gemini_openai"


def _gravar_relatorio_teste(
    caminho: Path,
    *,
    num_itens: int,
    acertos_principal: int,
    acertos_sec: int,
    digest_ouro: str = "digest-1",
    taxonomia: str = "enade-ec",
) -> None:
    agora = datetime(2026, 11, 25, 8, 10, tzinfo=UTC)
    itens = tuple(
        ItemConjuntoOuro(
            chave=ChaveQuestaoOuro("ENADE", "EC", 2023, i),
            disciplina_principal="alg" if i <= num_itens // 2 else "redes",
            disciplinas_secundarias=("so",),
        )
        for i in range(1, num_itens + 1)
    )
    ouro = ConjuntoOuro("1.0", taxonomia, agora, itens)
    preds = []
    for idx, item in enumerate(itens, start=1):
        principal = (
            item.disciplina_principal
            if idx <= acertos_principal
            else ("redes" if item.disciplina_principal == "alg" else "alg")
        )
        secs = ("so",) if idx <= acertos_sec else ()
        preds.append(
            PredicaoClassificacao(
                chave=item.chave,
                conclusao_valida=True,
                disciplina_principal=principal,
                disciplinas_secundarias=secs,
                confianca=0.90,
            )
        )
    av = calcular_avaliacao_classificacao(
        ouro,
        preds,
        perfil_codigo="v2",
        perfil_versao="v1",
        modelo_identidade="modelo",
        executado_em=agora,
    )
    payload = avaliacao_para_dict(av)
    payload["conjunto_ouro_digest"] = digest_ouro
    caminho.write_text(json.dumps(payload), encoding="utf-8")


def test_cli_comparar_exit_codes_e_nao_importa_presentation_main(tmp_path: Path) -> None:
    env = os.environ.copy()
    src_dir = str(Path(__file__).resolve().parents[2] / "src")
    pythonpath_atual = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{pythonpath_atual}" if pythonpath_atual else src_dir

    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, presentation.cli.eval_cli; "
                "from typer.testing import CliRunner; "
                "res = CliRunner().invoke(presentation.cli.eval_cli.app, ['--help']); "
                "assert res.exit_code == 0, res.output; "
                "assert 'presentation.main' not in sys.modules"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    base_path = tmp_path / "base.json"
    cand_ok_path = tmp_path / "cand_ok.json"
    cand_reg_path = tmp_path / "cand_reg.json"
    cand_digest_path = tmp_path / "cand_digest.json"

    _gravar_relatorio_teste(base_path, num_itens=100, acertos_principal=90, acertos_sec=90)
    _gravar_relatorio_teste(cand_ok_path, num_itens=100, acertos_principal=91, acertos_sec=90)
    _gravar_relatorio_teste(cand_reg_path, num_itens=100, acertos_principal=88, acertos_sec=90)
    _gravar_relatorio_teste(cand_digest_path, num_itens=100, acertos_principal=91, acertos_sec=90, digest_ouro="outro")

    runner = CliRunner()

    res_ok = runner.invoke(app, ["comparar", str(base_path), str(cand_ok_path)])
    assert res_ok.exit_code == 0, res_ok.output
    assert "APROVADO" in res_ok.output

    res_reg = runner.invoke(app, ["comparar", str(base_path), str(cand_reg_path)])
    assert res_reg.exit_code == 1
    assert "REPROVADO" in res_reg.output

    res_migr = runner.invoke(app, ["comparar", str(base_path), str(cand_reg_path), "--modo-migracao"])
    assert res_migr.exit_code == 0, res_migr.output
    assert "APROVADO" in res_migr.output

    res_digest = runner.invoke(app, ["comparar", str(base_path), str(cand_digest_path)])
    assert res_digest.exit_code == 1
    assert "Conjunto-Ouro distintos" in res_digest.output
