import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AlertCircle, ChevronLeft, ChevronRight, FileText, Pencil } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueryClient, type InfiniteData } from "@tanstack/react-query";

import { useResolverAlertaExtracaoMutation } from "@/api/edicaoQuestao";
import { useCriarExecucaoMutation } from "@/api/execucoes";
import { getErrorMessage } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import type { ListaQuestoesResponse } from "@/api/questoes";
import {
  useAprovarClassificacaoMutation,
  useCorrigirClassificacaoMutation,
  useFilaRevisaoQuery,
  useQuestaoDetalheQuery,
  useResolverDivergenciaMutation,
  type CorrigirClassificacaoRequest,
  type DetalheQuestaoResponse,
  type ResolverDivergenciaRequest,
} from "@/api/revisao";
import { findDefaultPerfil, usePerfisClassificacaoQuery } from "@/api/taxonomias";
import { buildSearchWithTaxonomia, useTaxonomia } from "@/components/layout/useTaxonomia";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { BannerReclassificacao } from "@/features/revisao/edicao/BannerReclassificacao";
import { EditorConteudoQuestao } from "@/features/revisao/edicao/EditorConteudoQuestao";
import { VisualizadorPdfPagina } from "@/features/revisao/edicao/VisualizadorPdfPagina";
import { PainelVeredito } from "@/features/revisao/PainelVeredito";
import { QuestaoLeitura } from "@/features/revisao/QuestaoLeitura";
import { useAtalhosRevisao } from "@/features/revisao/useAtalhosRevisao";
import {
  ABAS,
  ROTULOS_ABAS,
  comAba,
  comQuestao,
  paramsDaFila,
  parseRevisaoUrl,
  assinaturaDaUrl,
  type AbaRevisao,
  type ModoRevisao,
} from "@/features/revisao/revisaoUrl";

export interface RevisaoPageProps {
  renderAcoesQuestao?: (questao: DetalheQuestaoResponse) => ReactNode;
}

type FilaData = InfiniteData<ListaQuestoesResponse>;

function idsDaFila(data: FilaData | undefined): string[] {
  return data?.pages.flatMap((pagina) => pagina.itens.map((item) => item.id)) ?? [];
}

export function RevisaoPage({ renderAcoesQuestao }: RevisaoPageProps = {}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { activeTaxonomiaId, activeTaxonomia, isLoading: taxonomiasLoading, error: taxonomiasError } = useTaxonomia();

  const urlAtualRef = useRef(searchParams);
  useEffect(() => {
    urlAtualRef.current = searchParams;
  }, [searchParams]);

  const estado = useMemo(() => parseRevisaoUrl(searchParams), [searchParams]);
  const modo: ModoRevisao = useMemo(() => {
    if (estado.modo.tipo === "recorte" && activeTaxonomia && estado.modo.filtros.disciplina_id) {
      const alvo = estado.modo.filtros.disciplina_id.toLowerCase();
      const disciplina = activeTaxonomia.disciplinas.find((d) => d.id.toLowerCase() === alvo);
      return {
        tipo: "recorte",
        filtros: disciplina
          ? { ...estado.modo.filtros, disciplina_id: disciplina.id }
          : { ...estado.modo.filtros, disciplina_id: undefined, somentePrincipal: false },
      };
    }
    return estado.modo;
  }, [estado.modo, activeTaxonomia]);

  const paramsFila = useMemo(
    () => (activeTaxonomiaId ? paramsDaFila(modo, activeTaxonomiaId) : null),
    [modo, activeTaxonomiaId],
  );
  const fila = useFilaRevisaoQuery(paramsFila);
  const itens = useMemo(() => fila.data?.pages.flatMap((pagina) => pagina.itens) ?? [], [fila.data]);
  const total = fila.data?.pages.at(-1)?.total ?? 0;
  const contadores = fila.data?.pages[0]?.contadores ?? null;

  const [questaoFixada, setQuestaoFixada] = useState<{ id: string; searchAntes: string } | null>(null);
  useEffect(() => {
    if (questaoFixada && questaoFixada.searchAntes !== searchParams.toString()) {
      setQuestaoFixada(null);
    }
  }, [questaoFixada, searchParams]);

  const selecionadaId =
    estado.questaoId ??
    (questaoFixada && questaoFixada.searchAntes === searchParams.toString() ? questaoFixada.id : null) ??
    itens[0]?.id ??
    null;
  const indice = selecionadaId ? itens.findIndex((item) => item.id === selecionadaId) : -1;

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = fila;
  useEffect(() => {
    if (estado.questaoId && indice < 0 && fila.data && hasNextPage && !isFetchingNextPage) {
      void fetchNextPage();
    }
  }, [estado.questaoId, indice, fila.data, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const detalhe = useQuestaoDetalheQuery(selecionadaId, activeTaxonomiaId);
  const questao = detalhe.data;

  const [editandoId, setEditandoId] = useState<string | null>(null);
  const [editandoConteudoId, setEditandoConteudoId] = useState<string | null>(null);
  const [pdfAberto, setPdfAberto] = useState(false);
  const [revisoesAtivos, setRevisoesAtivos] = useState<Record<string, number>>({});
  const [bannerReclassificarId, setBannerReclassificarId] = useState<string | null>(null);
  const [reclassificacaoCriada, setReclassificacaoCriada] = useState<{ id: string; execucaoId: string } | null>(null);
  const [reclassificacaoErro, setReclassificacaoErro] = useState<{ id: string; mensagem: string } | null>(null);
  const [verificandoAlertaId, setVerificandoAlertaId] = useState<string | null>(null);
  const [erroAlerta, setErroAlerta] = useState<{ id: string; mensagem: string } | null>(null);
  const [erroVeredito, setErroVeredito] = useState<{ id: string; mensagem: string } | null>(null);
  const [execucaoCriada, setExecucaoCriada] = useState<{ id: string; execucaoId: string } | null>(null);
  const [execucaoErro, setExecucaoErro] = useState<{ id: string; mensagem: string } | null>(null);
  const [lightboxAberto, setLightboxAberto] = useState(false);
  const editando = selecionadaId !== null && editandoId === selecionadaId;
  const editandoConteudo = selecionadaId !== null && editandoConteudoId === selecionadaId;
  const bannerReclassificarAtivo = selecionadaId !== null && bannerReclassificarId === selecionadaId;

  useEffect(() => {
    setEditandoId(null);
    setEditandoConteudoId(null);
    setPdfAberto(false);
    setBannerReclassificarId(null);
    setErroAlerta(null);
  }, [selecionadaId, activeTaxonomiaId]);

  const perfisQuery = usePerfisClassificacaoQuery({
    enabled: Boolean(questao) && (!questao?.classificacao_vigente || editandoConteudo || bannerReclassificarAtivo),
  });
  const perfilPadrao = perfisQuery.data ? findDefaultPerfil(perfisQuery.data.itens) : undefined;

  const aprovar = useAprovarClassificacaoMutation();
  const corrigir = useCorrigirClassificacaoMutation();
  const resolver = useResolverDivergenciaMutation();
  const criarExecucao = useCriarExecucaoMutation();
  const resolverAlerta = useResolverAlertaExtracaoMutation();
  const ocupado = aprovar.isPending || corrigir.isPending || resolver.isPending;
  const vereditoEmAndamentoRef = useRef(false);

  const foraDaFila = indice < 0 && Boolean(fila.data) && !fila.hasNextPage && !fila.isFetchingNextPage;
  const podeIrProxima =
    indice >= 0 ? indice + 1 < itens.length || fila.hasNextPage : foraDaFila && itens.length > 0;

  function irPara(id: string | null) {
    const proxima = comQuestao(urlAtualRef.current, id);
    urlAtualRef.current = proxima;
    setSearchParams(proxima, { replace: true });
  }

  function fixarQuestao(id: string) {
    if (parseRevisaoUrl(urlAtualRef.current).questaoId !== id) {
      setQuestaoFixada({ id, searchAntes: urlAtualRef.current.toString() });
      irPara(id);
    }
  }

  async function buscarProximaPagina(): Promise<string[]> {
    const resultado = await fila.fetchNextPage();
    return idsDaFila(resultado.data);
  }

  async function irParaProxima() {
    if (indice < 0) {
      if (!fila.hasNextPage && itens.length > 0) {
        irPara(itens[0].id);
      }
      return;
    }
    if (indice + 1 < itens.length) {
      irPara(itens[indice + 1].id);
    } else if (fila.hasNextPage) {
      const proxima = (await buscarProximaPagina())[indice + 1];
      if (proxima) {
        irPara(proxima);
      }
    }
  }

  function irParaAnterior() {
    if (indice > 0) {
      irPara(itens[indice - 1].id);
    }
  }

  async function avancarAposVeredito(idsAntes: readonly string[], idAtual: string, assinaturaAntes: string) {
    const irSeInalterada = (id: string | null) => {
      if (assinaturaDaUrl(urlAtualRef.current) === assinaturaAntes) {
        irPara(id);
      }
    };
    const atualizados = idsDaFila(queryClient.getQueryData<FilaData>(queryKeys.questoes.fila(paramsFila ?? {})));
    const posicao = idsAntes.indexOf(idAtual);
    const seguinte = idsAntes.slice(posicao + 1).find((id) => atualizados.includes(id));
    if (seguinte) {
      irSeInalterada(seguinte);
      return;
    }
    if (fila.hasNextPage) {
      const novo = (await buscarProximaPagina()).find((id) => !idsAntes.includes(id));
      if (novo) {
        irSeInalterada(novo);
        return;
      }
    }
    if (atualizados.includes(idAtual)) {
      return;
    }
    irSeInalterada(atualizados.at(-1) ?? null);
  }

  async function executarVeredito(operacao: () => Promise<unknown>, opcoes?: { manterEdicaoNoErro?: boolean }) {
    if (!questao || ocupado || vereditoEmAndamentoRef.current) {
      return;
    }
    vereditoEmAndamentoRef.current = true;
    const idAtual = questao.id;
    const idsAntes = idsDaFila(fila.data);
    const assinaturaAntes = assinaturaDaUrl(urlAtualRef.current);
    setErroVeredito(null);
    try {
      try {
        await operacao();
      } catch (error) {
        setErroVeredito({ id: idAtual, mensagem: getErrorMessage(error) });
        if (opcoes?.manterEdicaoNoErro) {
          setEditandoId(idAtual);
        }
        if (assinaturaDaUrl(urlAtualRef.current) === assinaturaAntes) {
          fixarQuestao(idAtual);
        }
        void queryClient.invalidateQueries({ queryKey: queryKeys.questoes.all });
        return;
      }
      setEditandoId(null);
      await avancarAposVeredito(idsAntes, idAtual, assinaturaAntes);
    } finally {
      vereditoEmAndamentoRef.current = false;
    }
  }

  function handleAprovar() {
    if (!questao || !activeTaxonomiaId) return;
    void executarVeredito(() => aprovar.mutateAsync({ questaoId: questao.id, taxonomiaId: activeTaxonomiaId }));
  }

  function handleCorrigir(correcao: CorrigirClassificacaoRequest) {
    if (!questao || !activeTaxonomiaId) return;
    void executarVeredito(
      () => corrigir.mutateAsync({ questaoId: questao.id, taxonomiaId: activeTaxonomiaId, correcao }),
      { manterEdicaoNoErro: true },
    );
  }

  function handleResolver(resolucao: ResolverDivergenciaRequest["resolucao"], classificacao?: CorrigirClassificacaoRequest) {
    if (!questao?.divergencia_aberta) return;
    const divergenciaId = questao.divergencia_aberta.id;
    void executarVeredito(
      () =>
        resolver.mutateAsync({
          questaoId: questao.id,
          divergenciaId,
          resolucao,
          ...(classificacao ? { classificacao } : {}),
        }),
      { manterEdicaoNoErro: resolucao === "editar_manualmente" },
    );
  }

  async function handleExecutarClassificacao() {
    if (!questao || !activeTaxonomiaId || !perfilPadrao) return;
    const id = questao.id;
    setExecucaoErro(null);
    try {
      const aceita = await criarExecucao.mutateAsync({
        taxonomia_id: activeTaxonomiaId,
        perfil_id: perfilPadrao.id,
        escopo: "questao_ids",
        questao_ids: [id],
        incluir_revisadas: false,
      });
      setExecucaoCriada({ id, execucaoId: aceita.execucao_id });
    } catch (error) {
      setExecucaoErro({ id, mensagem: getErrorMessage(error) });
    }
  }

  async function handleVerificarAlerta(alertaId: string) {
    if (!questao || !activeTaxonomiaId) return;
    const id = questao.id;
    fixarQuestao(id);
    setErroAlerta(null);
    setVerificandoAlertaId(alertaId);
    try {
      await resolverAlerta.mutateAsync({
        questaoId: id,
        alertaId,
        taxonomiaId: activeTaxonomiaId,
      });
    } catch (error) {
      setErroAlerta({ id, mensagem: getErrorMessage(error) });
    } finally {
      setVerificandoAlertaId(null);
    }
  }

  async function handleReclassificarQuestao() {
    if (!questao || !activeTaxonomiaId || !perfilPadrao) return;
    const id = questao.id;
    setReclassificacaoErro(null);
    try {
      const aceita = await criarExecucao.mutateAsync({
        taxonomia_id: activeTaxonomiaId,
        perfil_id: perfilPadrao.id,
        escopo: "questao_ids",
        questao_ids: [id],
        incluir_revisadas: true,
      });
      setReclassificacaoCriada({ id, execucaoId: aceita.execucao_id });
    } catch (error) {
      setReclassificacaoErro({ id, mensagem: getErrorMessage(error) });
    }
  }

  function sinalizarAlteracaoConteudo(questaoId: string) {
    setBannerReclassificarId(questaoId);
    setReclassificacaoCriada((prev) => (prev?.id === questaoId ? null : prev));
    setReclassificacaoErro((prev) => (prev?.id === questaoId ? null : prev));
  }

  function abrirEdicaoConteudo(id: string) {
    fixarQuestao(id);
    setEditandoConteudoId(id);
  }

  function handleMidiaAlterada(opcoes?: { ativoSubstituidoId?: string }) {
    if (opcoes?.ativoSubstituidoId) {
      const ativoId = opcoes.ativoSubstituidoId;
      setRevisoesAtivos((prev) => ({ ...prev, [ativoId]: (prev[ativoId] ?? 0) + 1 }));
    }
    if (questao) {
      fixarQuestao(questao.id);
      sinalizarAlteracaoConteudo(questao.id);
    }
  }

  function handleSalvarConteudoSucesso(atualizada: DetalheQuestaoResponse) {
    fixarQuestao(atualizada.id);
    setEditandoConteudoId(null);
    sinalizarAlteracaoConteudo(atualizada.id);
  }

  const podeAprovar =
    questao?.classificacao_vigente?.status === "pendente_revisao" && !questao.divergencia_aberta && !editando && !ocupado;
  useAtalhosRevisao({
    bloqueado: lightboxAberto || pdfAberto || editandoConteudo,
    aprovar: podeAprovar ? handleAprovar : undefined,
    editar:
      questao?.classificacao_vigente && !editando && !ocupado
        ? () => setEditandoId(questao.id)
        : undefined,
    anterior: indice > 0 ? irParaAnterior : undefined,
    proxima: podeIrProxima ? () => void irParaProxima() : undefined,
    fechar: editando ? () => setEditandoId(null) : undefined,
  });

  const nomes = useMemo(
    () => new Map((activeTaxonomia?.disciplinas ?? []).map((d) => [d.codigo, d.nome] as const)),
    [activeTaxonomia],
  );

  const abaAtiva: AbaRevisao | null = modo.tipo === "abas" ? modo.aba : null;
  const contagemAba: Record<AbaRevisao, number> = {
    pendentes: contadores?.pendentes ?? 0,
    divergencias: contadores?.divergencias ?? 0,
    disciplina_arquivada: contadores?.disciplina_arquivada ?? 0,
  };

  const rotuloPosicao =
    indice >= 0
      ? `${indice + 1} de ${total}`
      : foraDaFila
        ? total > 0
          ? `Fora da fila · ${total} na fila`
          : "Fora da fila · fila vazia"
        : `${total} na fila`;

  const navegacao = (
    <nav className="flex items-center gap-2" aria-label="Navegação da fila">
      <Button type="button" variant="outline" size="sm" disabled={indice <= 0} onClick={irParaAnterior}>
        <ChevronLeft className="mr-0.5 h-4 w-4" aria-hidden="true" />
        Anterior
      </Button>
      <span
        className="rounded-sm border border-border bg-surface/70 px-2.5 py-1 font-mono text-xs font-medium text-muted-foreground tabular-nums"
        data-testid="revisao-posicao"
      >
        {rotuloPosicao}
      </span>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={!podeIrProxima}
        onClick={() => void irParaProxima()}
      >
        Próxima
        <ChevronRight className="ml-0.5 h-4 w-4" aria-hidden="true" />
      </Button>
    </nav>
  );

  const semTaxonomia = !activeTaxonomiaId && !taxonomiasLoading;

  let conteudo: ReactNode;
  if (semTaxonomia) {
    conteudo = (
      <Alert variant={taxonomiasError ? "destructive" : "default"}>
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        <AlertTitle>{taxonomiasError ? "Não foi possível carregar as Taxonomias" : "Nenhuma Taxonomia cadastrada"}</AlertTitle>
        <AlertDescription>
          {taxonomiasError ? getErrorMessage(taxonomiasError) : "Cadastre uma Taxonomia para revisar Questões."}{" "}
          <Link to="/taxonomias" className="underline">
            Ir para Taxonomias
          </Link>
        </AlertDescription>
      </Alert>
    );
  } else if (!activeTaxonomiaId || fila.isLoading) {
    conteudo = (
      <div className="space-y-3" role="status" aria-label="Carregando fila de Revisão">
        <Skeleton className="h-10 w-full rounded-lg" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  } else if (fila.isError) {
    conteudo = (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        <AlertTitle>Não foi possível carregar a fila de Revisão</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{getErrorMessage(fila.error)}</p>
          <Button type="button" variant="outline" size="sm" onClick={() => void fila.refetch()}>
            Tentar novamente
          </Button>
        </AlertDescription>
      </Alert>
    );
  } else if (!selecionadaId) {
    conteudo = (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Fila vazia</CardTitle>
          <CardDescription>
            {modo.tipo === "recorte" ? "Nenhuma Questão neste recorte." : `Nenhuma Questão em "${ROTULOS_ABAS[modo.aba]}".`}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  } else {
    const erro = erroVeredito && erroVeredito.id === selecionadaId ? erroVeredito.mensagem : null;
    conteudo = (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {navegacao}
          <div
            className="hidden items-center gap-3 text-xs text-muted-foreground xl:flex"
            aria-hidden="true"
          >
            <span className="inline-flex items-center gap-1">
              <kbd className="kbd-cap">A</kbd> Aprovar
            </span>
            <span className="inline-flex items-center gap-1">
              <kbd className="kbd-cap">E</kbd> Editar
            </span>
            <span className="inline-flex items-center gap-1">
              <kbd className="kbd-cap">←</kbd>
              <kbd className="kbd-cap">→</kbd> Navegar
            </span>
            <span className="inline-flex items-center gap-1">
              <kbd className="kbd-cap">Esc</kbd> Fechar
            </span>
          </div>
        </div>
        {detalhe.isError ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>Não foi possível carregar a Questão</AlertTitle>
            <AlertDescription className="space-y-3">
              <p>{getErrorMessage(detalhe.error)}</p>
              <Button type="button" variant="outline" size="sm" onClick={() => void detalhe.refetch()}>
                Tentar novamente
              </Button>
            </AlertDescription>
          </Alert>
        ) : !questao || !activeTaxonomia ? (
          <Skeleton className="h-64 w-full rounded-lg" role="status" aria-label="Carregando Questão" />
        ) : (
          (() => {
            const acoesPadraoQuestao = (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={questao.paginas.length === 0}
                  title={questao.paginas.length === 0 ? "Questão sem página de PDF registrada." : undefined}
                  onClick={() => setPdfAberto(true)}
                >
                  <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                  Ver página original do PDF
                </Button>
                {!editandoConteudo ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => abrirEdicaoConteudo(questao.id)}
                  >
                    <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                    Editar conteúdo
                  </Button>
                ) : null}
              </>
            );
            const acoesQuestao = renderAcoesQuestao ? renderAcoesQuestao(questao) : acoesPadraoQuestao;

            return (
              <div className="grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(340px,1fr)]">
                <div
                  className="min-w-0 lg:max-h-[calc(100vh-11rem)] lg:overflow-y-auto lg:pr-1"
                  data-testid="coluna-leitura"
                >
                  <div className="space-y-4">
                    {bannerReclassificarAtivo ? (
                      <BannerReclassificacao
                        enviando={criarExecucao.isPending}
                        erro={reclassificacaoErro?.id === questao.id ? reclassificacaoErro.mensagem : null}
                        criadaId={reclassificacaoCriada?.id === questao.id ? reclassificacaoCriada.execucaoId : null}
                        semPerfil={perfisQuery.isSuccess && !perfilPadrao}
                        onReclassificar={() => void handleReclassificarQuestao()}
                        onDispensar={() => setBannerReclassificarId(null)}
                      />
                    ) : null}
                    {editandoConteudo ? (
                      <EditorConteudoQuestao
                        key={questao.id}
                        questao={questao}
                        taxonomiaId={activeTaxonomiaId}
                        acoesExtras={acoesQuestao}
                        revisoesAtivos={revisoesAtivos}
                        onVerificarAlerta={(alertaId) => void handleVerificarAlerta(alertaId)}
                        verificandoAlertaId={verificandoAlertaId}
                        erroAlerta={erroAlerta?.id === questao.id ? erroAlerta.mensagem : null}
                        onSalvarSucesso={handleSalvarConteudoSucesso}
                        onMidiaAlterada={handleMidiaAlterada}
                        onCancelar={() => setEditandoConteudoId(null)}
                        onRecarregarQuestao={async () => (await detalhe.refetch()).data}
                      />
                    ) : (
                      <QuestaoLeitura
                        questao={questao}
                        acoesExtras={acoesQuestao}
                        onLightboxChange={setLightboxAberto}
                        revisoesAtivos={revisoesAtivos}
                        onVerificarAlerta={(alertaId) => void handleVerificarAlerta(alertaId)}
                        verificandoAlertaId={verificandoAlertaId}
                        erroAlerta={erroAlerta?.id === questao.id ? erroAlerta.mensagem : null}
                      />
                    )}
                  </div>
                </div>
                <aside
                  className="min-w-0 lg:sticky lg:top-4 lg:max-h-[calc(100vh-11rem)] lg:self-start lg:overflow-y-auto"
                  aria-label="Veredito"
                  data-testid="coluna-veredito"
                >
                  <PainelVeredito
                    key={questao.id}
                    questao={questao}
                    taxonomia={activeTaxonomia}
                    nomes={nomes}
                    editando={editando}
                    onEditandoChange={(valor) => setEditandoId(valor ? questao.id : null)}
                    ocupado={ocupado}
                    erro={erro}
                    onAprovar={handleAprovar}
                    onCorrigir={handleCorrigir}
                    onResolver={handleResolver}
                    onExecutarClassificacao={() => void handleExecutarClassificacao()}
                    execucao={{
                      enviando: criarExecucao.isPending,
                      erro: execucaoErro?.id === questao.id ? execucaoErro.mensagem : null,
                      criadaId: execucaoCriada?.id === questao.id ? execucaoCriada.execucaoId : null,
                      semPerfil: perfisQuery.isSuccess && !perfilPadrao,
                    }}
                  />
                </aside>
              </div>
            );
          })()
        )}
      </div>
    );
  }

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-[-0.025em] text-foreground">Revisão</h1>
        <p className="text-sm text-muted-foreground">
          Aprove, corrija e resolva Divergências sob a Taxonomia ativa
          {activeTaxonomia ? (
            <>
              : <span className="font-medium text-foreground">{activeTaxonomia.nome}</span>
            </>
          ) : null}
          .
        </p>
      </header>

      {modo.tipo === "abas" ? (
        <div role="tablist" aria-label="Filas de Revisão" className="flex flex-wrap gap-1 border-b border-border">
          {ABAS.map((aba) => (
            <button
              key={aba}
              id={`aba-revisao-${aba}`}
              type="button"
              role="tab"
              aria-selected={abaAtiva === aba}
              aria-controls="painel-revisao"
              className={cn(
                "-mb-px border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors",
                abaAtiva === aba
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
              )}
              onClick={() => setSearchParams((prev) => comAba(prev, aba))}
            >
              {ROTULOS_ABAS[aba]} ({contagemAba[aba]})
            </button>
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-surface/65 px-3.5 py-2.5 text-sm">
          <span className="font-medium text-foreground">Recorte filtrado</span>
          <Button asChild variant="outline" size="sm">
            <Link to={`/revisao${buildSearchWithTaxonomia("", activeTaxonomiaId)}`}>Ver filas por aba</Link>
          </Button>
        </div>
      )}

      <div
        id="painel-revisao"
        role={modo.tipo === "abas" ? "tabpanel" : undefined}
        aria-labelledby={abaAtiva ? `aba-revisao-${abaAtiva}` : undefined}
      >
        {conteudo}
      </div>

      {questao ? (
        <VisualizadorPdfPagina
          open={pdfAberto}
          onOpenChange={setPdfAberto}
          prova={questao.prova}
          numeroQuestao={questao.numero}
          paginas={questao.paginas}
        />
      ) : null}
    </section>
  );
}
