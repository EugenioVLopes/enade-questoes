"""CLI local de avaliação offline ``enade-eval`` (Conjunto-Ouro, regressão e histórico IA × Humano)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from application.avaliacao import (
    PreflightConjuntoOuroError,
    ResultadoAvaliacaoOffline,
    ResultadoComparacaoAvaliacoes,
    ResultadoHistoricoConcordancia,
)
from domain.exceptions import ErroDominio
from domain.metricas_avaliacao import ROTULO_PREDICAO_INVALIDA
from presentation.cli.bootstrap import ProvedorDependenciasEval, criar_provedor_eval

app = typer.Typer(
    name="enade-eval",
    help="CLI local somente-leitura para Conjunto-Ouro, Avaliação de Classificação, Gate de Regressão e Histórico.",
    no_args_is_help=True,
)


@contextmanager
def _obter_provedor(ctx: typer.Context) -> Iterator[ProvedorDependenciasEval]:
    if isinstance(ctx.obj, ProvedorDependenciasEval):
        yield ctx.obj
        return
    provedor = criar_provedor_eval()
    try:
        yield provedor
    finally:
        provedor.close()


def _falhar(mensagem: str) -> None:
    Console(stderr=True).print(f"[red]Erro:[/red] {mensagem}")
    raise typer.Exit(code=1)


def _imprimir_resumo_avaliacao(resultado: ResultadoAvaliacaoOffline) -> None:
    console = Console()
    av = resultado.avaliacao
    c1 = av.camada1
    c2 = av.camada2
    c3 = av.camada3

    console.print(
        f"\n[bold]Avaliação concluída[/bold] — Taxonomia: [cyan]{av.taxonomia_codigo}[/cyan] "
        f"| Perfil: [cyan]{av.perfil_codigo}@{av.perfil_versao}[/cyan] "
        f"| Modelo: [cyan]{av.modelo_identidade}[/cyan]"
    )
    console.print(f"Digest Conjunto-Ouro: {av.conjunto_ouro_digest}")

    t1 = Table(title="Camada 1 — Acurácia Curricular")
    t1.add_column("Métrica", style="bold")
    t1.add_column("Valor", justify="right")
    t1.add_row("Total de itens", str(c1.total_itens))
    t1.add_row("Acurácia principal", f"{c1.acuracia_principal * 100:.2f}%")
    t1.add_row("Macro-F1 principal", f"{c1.macro_f1_principal * 100:.2f}%")
    t1.add_row("Jaccard médio secundárias", f"{c1.jaccard_secundarias * 100:.2f}%")
    t1.add_row("F1 médio secundárias", f"{c1.f1_secundarias * 100:.2f}%")
    t1.add_row("Exact Match combinado", f"{c1.exact_match * 100:.2f}%")
    console.print(t1)

    t2 = Table(title="Camada 2 — Diagnóstico de Fronteiras (Top Confusões)")
    t2.add_column("Esperada")
    t2.add_column("Predita")
    t2.add_column("Ocorrências", justify="right")
    if c2.pares_confusao_ranqueados:
        for par in c2.pares_confusao_ranqueados[:10]:
            t2.add_row(par.esperada, par.predita, str(par.contagem))
    else:
        t2.add_row("-", "-", "0")
    console.print(t2)

    if c2.divergencias:
        t_div = Table(title=f"Questões Divergentes ({len(c2.divergencias)})")
        t_div.add_column("Questão")
        t_div.add_column("Esperado")
        t_div.add_column("Predito")
        t_div.add_column("Conf.", justify="right")
        t_div.add_column("Rev.", justify="center")
        for div in c2.divergencias:
            esp_sec = ", ".join(div.esperadas_secundarias) or "-"
            pred_sec = ", ".join(div.preditas_secundarias) or "-"
            pred_princ = div.predita_principal or ROTULO_PREDICAO_INVALIDA
            t_div.add_row(
                f"{div.chave.exame} {div.chave.ano} Q{div.chave.numero:02d}",
                f"{div.esperada_principal} [{esp_sec}]",
                f"{pred_princ} [{pred_sec}]",
                f"{div.confianca:.2f}",
                "sim" if div.revisao_prioritaria else "não",
            )
        console.print(t_div)

    t3 = Table(title="Camada 3 — Saúde Operacional e Calibração")
    t3.add_column("Indicador", style="bold")
    t3.add_column("Valor", justify="right")
    t3.add_row("Conclusão válida", f"{c3.conclusao_valida * 100:.2f}%")
    t3.add_row("Validade 1ª tentativa", f"{c3.validade_primeira_tentativa * 100:.2f}%")
    t3.add_row("Taxa revisão prioritária", f"{c3.taxa_revisao_prioritaria * 100:.2f}%")
    t3.add_row(
        "Erro alta confiança (>= 0,85)",
        f"{c3.taxa_erro_alta_confianca * 100:.2f}% ({c3.erros_alta_confianca}/{c3.total_alta_confianca})",
    )
    t3.add_row("Tokens (prompt / completion)", f"{c3.prompt_tokens} / {c3.completion_tokens}")
    t3.add_row("Cache hits", f"{c3.cache_hits} ({c3.cache_hit_rate * 100:.2f}%)")
    t3.add_row("Latência média / p95 (ms)", f"{c3.latencia_media_ms:.2f} / {c3.latencia_p95_ms:.2f}")
    if c3.estabilidade_multipass is not None:
        t3.add_row("Estabilidade multipass", f"{c3.estabilidade_multipass * 100:.2f}%")
    console.print(t3)

    console.print(f"Relatório JSON: {resultado.caminho_json}")
    console.print(f"Relatório Markdown: {resultado.caminho_markdown}")


def _imprimir_comparacao(comp: ResultadoComparacaoAvaliacoes) -> None:
    console = Console()
    base = comp.baseline
    cand = comp.candidato
    gate = comp.gate

    modo_label = "MIGRAÇÃO" if gate.modo_migracao else "PADRÃO"
    console.print(
        f"\n[bold]Comparação (Gate {modo_label})[/bold] — Taxonomia: [cyan]{cand.taxonomia_codigo}[/cyan] "
        f"| Digest: {cand.conjunto_ouro_digest[:12]}"
    )

    tabela = Table(title="Baseline vs Candidato")
    tabela.add_column("Indicador", style="bold")
    tabela.add_column("Baseline", justify="right")
    tabela.add_column("Candidato", justify="right")
    tabela.add_column("Delta", justify="right")

    tabela.add_row(
        "Acurácia principal",
        f"{base.camada1.acuracia_principal * 100:.2f}%",
        f"{cand.camada1.acuracia_principal * 100:.2f}%",
        f"{gate.delta_acuracia * 100:+.2f} p.p.",
    )
    tabela.add_row(
        "Macro-F1 principal",
        f"{base.camada1.macro_f1_principal * 100:.2f}%",
        f"{cand.camada1.macro_f1_principal * 100:.2f}%",
        f"{gate.delta_macro_f1 * 100:+.2f} p.p.",
    )
    tabela.add_row(
        "Jaccard secundárias",
        f"{base.camada1.jaccard_secundarias * 100:.2f}%",
        f"{cand.camada1.jaccard_secundarias * 100:.2f}%",
        f"{gate.delta_jaccard * 100:+.2f} p.p.",
    )
    tabela.add_row(
        "Exact Match",
        f"{base.camada1.exact_match * 100:.2f}%",
        f"{cand.camada1.exact_match * 100:.2f}%",
        f"{gate.delta_exact_match * 100:+.2f} p.p.",
    )
    tabela.add_row(
        "Conclusão válida (piso 100%)",
        f"{base.camada3.conclusao_valida * 100:.2f}%",
        f"{cand.camada3.conclusao_valida * 100:.2f}%",
        f"{(cand.camada3.conclusao_valida - base.camada3.conclusao_valida) * 100:+.2f} p.p.",
    )
    tabela.add_row(
        "Validade 1ª tentativa (piso 95%)",
        f"{base.camada3.validade_primeira_tentativa * 100:.2f}%",
        f"{cand.camada3.validade_primeira_tentativa * 100:.2f}%",
        f"{(cand.camada3.validade_primeira_tentativa - base.camada3.validade_primeira_tentativa) * 100:+.2f} p.p.",
    )
    console.print(tabela)

    console.print(f"\n[bold green]Ganhos ({len(gate.ganhos)}):[/bold green]")
    if gate.ganhos:
        for item in gate.ganhos:
            console.print(
                f"  + {item.chave.exame} {item.chave.ano} Q{item.chave.numero:02d}: "
                f"{item.baseline_principal or ROTULO_PREDICAO_INVALIDA} {list(item.baseline_secundarias)} -> "
                f"{item.candidato_principal or ROTULO_PREDICAO_INVALIDA} {list(item.candidato_secundarias)}"
            )
    else:
        console.print("  (nenhum)")

    console.print(f"\n[bold red]Regressões ({len(gate.regressoes)}):[/bold red]")
    if gate.regressoes:
        for item in gate.regressoes:
            console.print(
                f"  - {item.chave.exame} {item.chave.ano} Q{item.chave.numero:02d}: "
                f"{item.baseline_principal or ROTULO_PREDICAO_INVALIDA} {list(item.baseline_secundarias)} -> "
                f"{item.candidato_principal or ROTULO_PREDICAO_INVALIDA} {list(item.candidato_secundarias)}"
            )
    else:
        console.print("  (nenhuma)")

    if gate.aprovado:
        console.print("\n[bold green]Veredito do Gate: APROVADO[/bold green]")
    else:
        console.print("\n[bold red]Veredito do Gate: REPROVADO[/bold red]")
        for motivo in gate.motivos_reprovacao:
            console.print(f"  * {motivo}")


def _imprimir_historico(historico: ResultadoHistoricoConcordancia) -> None:
    console = Console(width=140)
    titulo = (
        f"Histórico de Concordância IA × Humano ({historico.taxonomia_codigo})"
        if historico.taxonomia_codigo
        else "Histórico de Concordância IA × Humano (Todas as Taxonomias)"
    )
    if not historico.grupos:
        console.print(f"{titulo}: nenhuma classificação revisada originada por IA encontrada.")
        return

    tabela = Table(title=titulo)
    tabela.add_column("Perfil", style="bold", no_wrap=True)
    tabela.add_column("Modelo", no_wrap=True)
    tabela.add_column("Total", justify="right")
    tabela.add_column("Aprovação direta", justify="right")
    tabela.add_column("Correção principal", justify="right")
    tabela.add_column("Correção apenas secundárias", justify="right")

    for g in historico.grupos:
        perfil_fmt = f"{g.perfil_codigo}@{g.perfil_versao}" if g.perfil_versao else g.perfil_codigo
        tabela.add_row(
            perfil_fmt,
            g.modelo,
            str(g.total_revisadas),
            f"{g.aprovacoes_diretas} ({g.taxa_aprovacao_direta * 100:.2f}%)",
            f"{g.correcoes_principal} ({g.taxa_correcao_principal * 100:.2f}%)",
            f"{g.correcoes_apenas_secundarias} ({g.taxa_correcao_apenas_secundarias * 100:.2f}%)",
        )
    console.print(tabela)


@app.command(name="exportar-ouro")
def exportar_ouro(
    ctx: typer.Context,
    taxonomia: Annotated[str, typer.Option("--taxonomia", help="Código da Taxonomia alvo.")],
    saida: Annotated[
        Path | None,
        typer.Option("--saida", help="Caminho de saída do JSON (padrão: evals/golden/<taxonomia>.json)."),
    ] = None,
) -> None:
    """Exporta questões aprovadas e elegíveis do PostgreSQL para um snapshot versionado de Conjunto-Ouro."""
    destino = saida if saida is not None else Path("evals/golden") / f"{taxonomia.strip()}.json"
    with _obter_provedor(ctx) as provedor:
        use_case = provedor.criar_exportar_ouro()
        try:
            resultado = use_case.execute(taxonomia_codigo=taxonomia, destino=str(destino))
        except ErroDominio as err:
            _falhar(str(err))
            return

    edicoes = len({(item.chave.exame, item.chave.curso, item.chave.ano) for item in resultado.conjunto.itens})
    Console().print(
        f"Conjunto-Ouro exportado: {resultado.caminho_saida} | "
        f"taxonomia={resultado.conjunto.taxonomia_codigo} | "
        f"itens={resultado.conjunto.total_itens} | "
        f"edições={edicoes} | "
        f"digest={resultado.conjunto.digest()}"
    )


@app.command(name="avaliar")
def avaliar(
    ctx: typer.Context,
    ouro: Annotated[Path, typer.Option("--ouro", help="Caminho para o snapshot JSON do Conjunto-Ouro.")],
    perfil: Annotated[
        str,
        typer.Option("--perfil", help="Perfil no banco (<codigo>@<versao>) ou arquivo local (.yaml/.yml/.json)."),
    ],
    base_url: Annotated[str | None, typer.Option("--base-url", help="Override de base_url OpenAI-compatível.")] = None,
    model: Annotated[str | None, typer.Option("--model", help="Override do identificador de modelo LLM.")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="Override da chave de API LLM.")] = None,
    provider: Annotated[str | None, typer.Option("--provider", help="Override de provedor (ex.: vllm_qwen).")] = None,
    no_cache: Annotated[bool, typer.Option("--no-cache", help="Desativa leitura e gravação do cache LLM.")] = False,
    repeticoes: Annotated[
        int,
        typer.Option("--repeticoes", min=1, help="Número de passadas por questão para medir estabilidade."),
    ] = 1,
) -> None:
    """Executa Avaliação de Classificação offline (100% somente-leitura) contra um Conjunto-Ouro."""
    with _obter_provedor(ctx) as provedor:
        use_case = provedor.criar_avaliar(
            base_url=base_url,
            model=model,
            api_key=api_key,
            provider=provider,
        )
        try:
            resultado = use_case.execute(
                caminho_ouro=str(ouro),
                perfil_spec=perfil,
                no_cache=no_cache,
                repeticoes=repeticoes,
            )
        except PreflightConjuntoOuroError as err:
            _falhar(str(err))
            return
        except ErroDominio as err:
            _falhar(str(err))
            return

    _imprimir_resumo_avaliacao(resultado)


@app.command(name="comparar")
def comparar(
    ctx: typer.Context,
    baseline: Annotated[Path, typer.Argument(help="Relatório JSON baseline gerado por `avaliar`.")],
    candidato: Annotated[Path, typer.Argument(help="Relatório JSON candidato gerado por `avaliar`.")],
    modo_migracao: Annotated[
        bool,
        typer.Option("--modo-migracao", help="Aplica tolerâncias do gate para migração de modelo/provedor."),
    ] = False,
) -> None:
    """Compara dois relatórios de Avaliação de Classificação e aplica o gate determinístico de regressão."""
    with _obter_provedor(ctx) as provedor:
        use_case = provedor.criar_comparar()
        try:
            comp = use_case.execute(
                caminho_baseline=baseline,
                caminho_candidato=candidato,
                modo_migracao=modo_migracao,
            )
        except ErroDominio as err:
            _falhar(str(err))
            return

    _imprimir_comparacao(comp)
    if not comp.gate.aprovado:
        raise typer.Exit(code=1)


@app.command(name="historico")
def historico(
    ctx: typer.Context,
    taxonomia: Annotated[str | None, typer.Option("--taxonomia", help="Filtra pelo código da Taxonomia.")] = None,
) -> None:
    """Consulta concordância histórica IA × Humano diretamente no PostgreSQL (somente-leitura)."""
    with _obter_provedor(ctx) as provedor:
        use_case = provedor.criar_historico()
        try:
            res = use_case.execute(taxonomia_codigo=taxonomia)
        except ErroDominio as err:
            _falhar(str(err))
            return

    _imprimir_historico(res)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
