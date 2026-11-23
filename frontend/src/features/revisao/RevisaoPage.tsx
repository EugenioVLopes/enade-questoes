import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueryClient, type InfiniteData } from "@tanstack/react-query";

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
  /** Ponto de encaixe da Tarefa 13: "Editar conteúdo" e "Ver página do PDF" na coluna de leitura. */
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

  // Estado mais recente da URL: continuações assíncronas (avanço após veredito) não podem usar um `prev` obsoleto.
  const urlAtualRef = useRef(searchParams);
  useEffect(() => {
    urlAtualRef.current = searchParams;
  });

  const estado = useMemo(() => parseRevisaoUrl(searchParams), [searchParams]);
  const modo: ModoRevisao = useMemo(() => {
    // Disciplina de outra Taxonomia seria rejeitada pela API: só vale se pertencer à Taxonomia ativa.
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

  // Mantém a questão atual fixada entre o erro de veredito e o commit de `setSearchParams` (v7_startTransition),
  // impedindo que o refetch da fila troque `selecionadaId` para `itens[0]` nesse intervalo.
  const [questaoFixada, setQuestaoFixada] = useState<{ id: string; searchAntes: string } | null>(null);
  const selecionadaId =
    estado.questaoId ??
    (questaoFixada && questaoFixada.searchAntes === searchParams.toString() ? questaoFixada.id : null) ??
    itens[0]?.id ??
    null;
  const indice = selecionadaId ? itens.findIndex((item) => item.id === selecionadaId) : -1;

  // `questao=<id>` fora das páginas já carregadas: carrega as seguintes até posicionar (ou esgotar a fila).
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = fila;
  useEffect(() => {
    if (estado.questaoId && indice < 0 && fila.data && hasNextPage && !isFetchingNextPage) {
      void fetchNextPage();
    }
  }, [estado.questaoId, indice, fila.data, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const detalhe = useQuestaoDetalheQuery(selecionadaId, activeTaxonomiaId);
  const questao = detalhe.data;

  const perfisQuery = usePerfisClassificacaoQuery({ enabled: Boolean(questao) && !questao?.classificacao_vigente });
  const perfilPadrao = perfisQuery.data ? findDefaultPerfil(perfisQuery.data.itens) : undefined;

  const aprovar = useAprovarClassificacaoMutation();
  const corrigir = useCorrigirClassificacaoMutation();
  const resolver = useResolverDivergenciaMutation();
  const criarExecucao = useCriarExecucaoMutation();
  const ocupado = aprovar.isPending || corrigir.isPending || resolver.isPending;
  const vereditoEmAndamentoRef = useRef(false);

  // Estado de interface por questão: trocar de questão ou de Taxonomia descarta a edição aberta (efeito abaixo);
  // erros e execuções ficam ligados ao id da questão.
  const [editandoId, setEditandoId] = useState<string | null>(null);
  const [erroVeredito, setErroVeredito] = useState<{ id: string; mensagem: string } | null>(null);
  const [execucaoCriada, setExecucaoCriada] = useState<{ id: string; execucaoId: string } | null>(null);
  const [execucaoErro, setExecucaoErro] = useState<{ id: string; mensagem: string } | null>(null);
  const [lightboxAberto, setLightboxAberto] = useState(false);
  const editando = selecionadaId !== null && editandoId === selecionadaId;
  useEffect(() => {
    setEditandoId(null);
  }, [selecionadaId, activeTaxonomiaId]);

  const foraDaFila = indice < 0 && Boolean(fila.data) && !fila.hasNextPage && !fila.isFetchingNextPage;
  const podeIrProxima =
    indice >= 0 ? indice + 1 < itens.length || fila.hasNextPage : foraDaFila && itens.length > 0;

  function irPara(id: string | null) {
    const proxima = comQuestao(urlAtualRef.current, id);
    urlAtualRef.current = proxima;
    setSearchParams(proxima, { replace: true });
  }

  /** Busca a página seguinte da fila e devolve os ids de todas as páginas já carregadas. */
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

  /** Avança para o item seguinte da fila já atualizada (o aprovado some de Pendentes; no recorte permanece). */
  async function avancarAposVeredito(idsAntes: readonly string[], idAtual: string, assinaturaAntes: string) {
    // Se a aba, o recorte ou a questão mudaram durante a operação, o usuário já escolheu outro destino.
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
        // Fixa `questao=<idAtual>` na URL se o usuário não navegou para outro lugar:
        // evita que o refetch da fila remova o item e troque a questão selecionada, escondendo o erro/formulário.
        if (
          assinaturaDaUrl(urlAtualRef.current) === assinaturaAntes &&
          parseRevisaoUrl(urlAtualRef.current).questaoId !== idAtual
        ) {
          setQuestaoFixada({ id: idAtual, searchAntes: urlAtualRef.current.toString() });
          irPara(idAtual);
        }
        // O estado real pode ter mudado (ex.: 409 por já aprovada): refaz detalhe, fila e contadores.
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

  const podeAprovar =
    questao?.classificacao_vigente?.status === "pendente_revisao" && !questao.divergencia_aberta && !editando && !ocupado;
  useAtalhosRevisao({
    bloqueado: lightboxAberto,
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
        <ChevronLeft className="mr-1 h-4 w-4" aria-hidden="true" />
        Anterior
      </Button>
      <span className="text-sm text-muted-foreground" data-testid="revisao-posicao">
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
        <ChevronRight className="ml-1 h-4 w-4" aria-hidden="true" />
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
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">{navegacao}</div>
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
          <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
            <div className="min-w-0 lg:max-h-[calc(100vh-15rem)] lg:overflow-y-auto lg:pr-2" data-testid="coluna-leitura">
              <QuestaoLeitura
                questao={questao}
                acoesExtras={renderAcoesQuestao?.(questao)}
                onLightboxChange={setLightboxAberto}
              />
            </div>
            <aside
              className="min-w-0 lg:sticky lg:top-4 lg:max-h-[calc(100vh-15rem)] lg:self-start lg:overflow-y-auto"
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
        )}
      </div>
    );
  }

  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Revisão</h1>
        <p className="text-sm text-muted-foreground">
          Aprove, corrija e resolva Divergências sob a Taxonomia ativa
          {activeTaxonomia ? (
            <>
              : <span className="font-medium text-foreground">{activeTaxonomia.nome}</span>
            </>
          ) : null}
          .
        </p>
      </div>

      {modo.tipo === "abas" ? (
        <div role="tablist" aria-label="Filas de Revisão" className="flex flex-wrap gap-1 border-b">
          {ABAS.map((aba) => (
            <button
              key={aba}
              id={`aba-revisao-${aba}`}
              type="button"
              role="tab"
              aria-selected={abaAtiva === aba}
              aria-controls="painel-revisao"
              className={cn(
                "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                abaAtiva === aba ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setSearchParams((prev) => comAba(prev, aba))}
            >
              {ROTULOS_ABAS[aba]} ({contagemAba[aba]})
            </button>
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border bg-muted/40 px-3 py-2 text-sm">
          <span className="font-medium">Recorte filtrado</span>
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
    </section>
  );
}
