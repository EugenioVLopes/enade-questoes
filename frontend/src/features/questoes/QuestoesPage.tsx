import { useEffect, useMemo, useState } from "react";
import { AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { useProvasQuery } from "@/api/provas";
import { useQuestoesQuery } from "@/api/questoes";
import { useTaxonomiasQuery } from "@/api/taxonomias";
import { buildIngerirHref, useTaxonomia } from "@/components/layout/useTaxonomia";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { FiltrosBar } from "@/features/questoes/FiltrosBar";
import { QuestaoCard } from "@/features/questoes/QuestaoCard";
import {
  TAMANHO_PAGINA,
  aplicarFiltros,
  buildRevisaoRecorteHrefDeFiltros,
  filtrosParaApi,
  limparFiltros,
  limparFiltrosDaTaxonomia,
  parseFiltros,
  temFiltrosAtivos,
  temFiltrosDaTaxonomia,
  type FiltrosPatch,
} from "@/features/questoes/filtrosUrl";

export function QuestoesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { activeTaxonomiaId, activeTaxonomia, taxonomias, isLoading: taxonomiasLoading, error: taxonomiasError } =
    useTaxonomia();
  const taxonomiasQuery = useTaxonomiasQuery();
  const provasQuery = useProvasQuery();

  const filtros = useMemo(() => {
    const parsed = parseFiltros(searchParams);
    // Disciplina de outra Taxonomia seria rejeitada pela API: só vale se pertencer à Taxonomia ativa carregada.
    if (activeTaxonomia && parsed.disciplina_id) {
      const alvo = parsed.disciplina_id.toLowerCase();
      const disciplina = activeTaxonomia.disciplinas.find((d) => d.id.toLowerCase() === alvo);
      if (!disciplina) {
        return { ...parsed, disciplina_id: undefined, somentePrincipal: false };
      }
      // Envia o id como cadastrado na Taxonomia (a URL pode vir em maiúsculas).
      return { ...parsed, disciplina_id: disciplina.id };
    }
    return parsed;
  }, [searchParams, activeTaxonomia]);

  // Disciplina e Tópico dependem da Taxonomia: ao trocá-la, esses filtros e a página são descartados,
  // e a consulta fica suspensa enquanto a URL ainda os carrega.
  const [taxonomiaVista, setTaxonomiaVista] = useState<string | null>(null);
  const comFiltrosDaTaxonomia = temFiltrosDaTaxonomia(searchParams);
  const trocaPendente = taxonomiaVista !== null && activeTaxonomiaId !== null && taxonomiaVista !== activeTaxonomiaId && comFiltrosDaTaxonomia;
  useEffect(() => {
    if (!activeTaxonomiaId || taxonomiaVista === activeTaxonomiaId) {
      return;
    }
    if (taxonomiaVista !== null && comFiltrosDaTaxonomia) {
      setSearchParams((prev) => limparFiltrosDaTaxonomia(prev), { replace: true });
      return;
    }
    setTaxonomiaVista(activeTaxonomiaId);
  }, [activeTaxonomiaId, taxonomiaVista, comFiltrosDaTaxonomia, setSearchParams]);

  const params = useMemo(
    () => (activeTaxonomiaId ? filtrosParaApi(filtros, activeTaxonomiaId, TAMANHO_PAGINA) : null),
    [filtros, activeTaxonomiaId],
  );
  const consultaHabilitada = params !== null && !trocaPendente;
  const questoesQuery = useQuestoesQuery(params ?? {}, { enabled: consultaHabilitada });

  const nomesDisciplinas = useMemo(
    () => new Map((activeTaxonomia?.disciplinas ?? []).map((d) => [d.codigo, d.nome] as const)),
    [activeTaxonomia],
  );

  function handleChange(patch: FiltrosPatch) {
    setSearchParams((prev) => aplicarFiltros(prev, patch));
  }

  function irParaPagina(pagina: number) {
    setSearchParams((prev) => aplicarFiltros(prev, { pagina }));
  }

  const semProvas = !provasQuery.isLoading && !provasQuery.isError && (provasQuery.data?.total ?? 0) === 0;
  // H1/H2: enquanto exibe o dado do recorte anterior (placeholder), nada navega com os filtros novos.
  const dadoAnterior = questoesQuery.isPlaceholderData;
  const itens = questoesQuery.data?.itens ?? [];
  const total = questoesQuery.data?.total ?? 0;
  const totalPaginas = Math.max(1, Math.ceil(total / TAMANHO_PAGINA));
  const revisarHref = buildRevisaoRecorteHrefDeFiltros(filtros, activeTaxonomiaId);
  const paginaInexistente = questoesQuery.data !== undefined && itens.length === 0 && total > 0;

  const paginacao = (
    <nav className="flex items-center justify-between pt-2" aria-label="Paginação">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={filtros.pagina <= 1}
        onClick={() => irParaPagina(Math.min(filtros.pagina - 1, totalPaginas))}
      >
        <ChevronLeft className="mr-1 h-4 w-4" aria-hidden="true" />
        Anterior
      </Button>
      <span className="text-sm text-muted-foreground">
        Página {filtros.pagina} de {totalPaginas}
      </span>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={filtros.pagina >= totalPaginas}
        onClick={() => irParaPagina(filtros.pagina + 1)}
      >
        Próxima
        <ChevronRight className="ml-1 h-4 w-4" aria-hidden="true" />
      </Button>
    </nav>
  );

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Questões</h1>
          <p className="text-sm text-muted-foreground">
            Consulta textual e filtros sob a Taxonomia ativa
            {activeTaxonomia ? (
              <>
                : <span className="font-medium text-foreground">{activeTaxonomia.nome}</span>
              </>
            ) : null}
            .
          </p>
        </div>
        {!semProvas && questoesQuery.data && !(dadoAnterior && total === 0) ? (
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground" data-testid="questoes-total">
              {`${total} questão(ões)`}
            </span>
            {total === 0 || dadoAnterior ? (
              <Button type="button" disabled>
                Revisar este recorte ({total})
              </Button>
            ) : (
              <Button asChild>
                <Link to={revisarHref}>Revisar este recorte ({total})</Link>
              </Button>
            )}
          </div>
        ) : null}
      </div>

      {semProvas ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Nenhuma Prova ingerida ainda</CardTitle>
            <CardDescription>
              Comece realizando a primeira Ingestão de uma Prova e, opcionalmente, de seu Gabarito.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link to={buildIngerirHref(activeTaxonomiaId)}>Ingerir primeira prova</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <FiltrosBar
            filtros={filtros}
            disciplinas={activeTaxonomia?.disciplinas ?? []}
            provas={provasQuery.data?.itens ?? []}
            onChange={handleChange}
          />

          {params === null && !taxonomiasLoading && taxonomiasError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" aria-hidden="true" />
              <AlertTitle>Não foi possível carregar as Taxonomias</AlertTitle>
              <AlertDescription className="space-y-3">
                <p>{getErrorMessage(taxonomiasError)}</p>
                <Button type="button" variant="outline" size="sm" onClick={() => void taxonomiasQuery.refetch()}>
                  Tentar novamente
                </Button>
              </AlertDescription>
            </Alert>
          ) : params === null && !taxonomiasLoading && taxonomias.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Nenhuma Taxonomia cadastrada</CardTitle>
                <CardDescription>Cadastre uma Taxonomia para consultar as Questões.</CardDescription>
              </CardHeader>
              <CardContent>
                <Button asChild>
                  <Link to="/taxonomias">Cadastrar Taxonomia</Link>
                </Button>
              </CardContent>
            </Card>
          ) : !consultaHabilitada || questoesQuery.isLoading || (dadoAnterior && itens.length === 0) ? (
            <div className="space-y-3" aria-label="Carregando Questões">
              <Skeleton className="h-28 w-full rounded-lg" />
              <Skeleton className="h-28 w-full rounded-lg" />
            </div>
          ) : questoesQuery.isError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" aria-hidden="true" />
              <AlertTitle>Não foi possível carregar as Questões</AlertTitle>
              <AlertDescription className="space-y-3">
                <p>{getErrorMessage(questoesQuery.error)}</p>
                <Button type="button" variant="outline" size="sm" onClick={() => void questoesQuery.refetch()}>
                  Tentar novamente
                </Button>
              </AlertDescription>
            </Alert>
          ) : paginaInexistente ? (
            <div className="space-y-3">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Página {filtros.pagina} não existe</CardTitle>
                  <CardDescription>
                    O recorte tem {totalPaginas} página(s). Volte para a última página válida.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button type="button" variant="outline" onClick={() => irParaPagina(totalPaginas)}>
                    Ir para a última página
                  </Button>
                </CardContent>
              </Card>
            </div>
          ) : itens.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Nenhuma questão encontrada</CardTitle>
                <CardDescription>
                  {temFiltrosAtivos(filtros)
                    ? "Nenhuma Questão corresponde aos filtros aplicados."
                    : "Não há Questões para a Taxonomia ativa."}
                </CardDescription>
              </CardHeader>
              {temFiltrosAtivos(filtros) ? (
                <CardContent>
                  <Button type="button" variant="outline" onClick={() => setSearchParams(limparFiltros)}>
                    Limpar filtros
                  </Button>
                </CardContent>
              ) : null}
            </Card>
          ) : (
            <div className="space-y-3" aria-busy={dadoAnterior}>
              {itens.map((item) => (
                <QuestaoCard
                  key={item.id}
                  item={item}
                  href={dadoAnterior ? null : buildRevisaoRecorteHrefDeFiltros(filtros, activeTaxonomiaId, item.id)}
                  nomesDisciplinas={nomesDisciplinas}
                />
              ))}
              {paginacao}
            </div>
          )}
        </>
      )}
    </section>
  );
}
