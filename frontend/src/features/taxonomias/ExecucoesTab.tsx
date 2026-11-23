import { useState } from "react";
import { AlertCircle, Loader2, Play, RotateCcw } from "lucide-react";

import {
  podeRetomarExecucao,
  useExecucoesDaTaxonomiaQuery,
  useRetomarExecucao,
} from "@/api/execucoes";
import { getErrorMessage } from "@/api/errors";
import type { ExecucaoClassificacaoResumoResponse } from "@/api/operacao";
import { useTaxonomia } from "@/components/layout/useTaxonomia";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { NovaExecucaoDialog } from "@/features/taxonomias/NovaExecucaoDialog";

const STATUS_ROTULO: Record<string, string> = {
  pendente: "Pendente",
  processando: "Processando",
  concluida: "Concluída",
  concluida_com_erros: "Concluída com erros",
  interrompida: "Interrompida",
  erro: "Erro",
};

const ESCOPO_ROTULO: Record<string, string> = {
  todas: "Todas as questões",
  prova_id: "Por Prova",
  pendentes: "Pendentes",
  disciplina_arquivada: "Com Disciplina arquivada",
  questao_ids: "Questões selecionadas",
};

function formatarData(valor?: string | null): string {
  if (!valor) {
    return "—";
  }
  const data = new Date(valor);
  return Number.isNaN(data.getTime()) ? valor : data.toLocaleString("pt-BR");
}

function Metrica({ rotulo, valor }: { rotulo: string; valor: string | number }) {
  return (
    <div className="rounded-md border p-3">
      <p className="text-xs text-muted-foreground">{rotulo}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{valor}</p>
    </div>
  );
}

function ExecucaoCard({
  execucao,
  onRetomar,
  retomando,
}: {
  execucao: ExecucaoClassificacaoResumoResponse;
  onRetomar: () => void;
  retomando: boolean;
}) {
  const retomavel = podeRetomarExecucao(execucao.status);

  return (
    <Card data-testid={`execucao-card-${execucao.id}`}>
      <CardHeader className="gap-2">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="text-lg">{formatarData(execucao.criada_em)}</CardTitle>
            <CardDescription>
              {execucao.snapshot_resumo.taxonomia.nome} · {execucao.snapshot_resumo.perfil.codigo}{" "}
              {execucao.snapshot_resumo.perfil.versao} · {ESCOPO_ROTULO[execucao.escopo] ?? execucao.escopo}
              {execucao.incluir_revisadas ? " · inclui revisadas" : ""}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={execucao.status === "erro" ? "destructive" : "secondary"}>
              {STATUS_ROTULO[execucao.status] ?? execucao.status}
            </Badge>
            <Button
              type="button"
              variant="outline"
              disabled={!retomavel || retomando}
              onClick={onRetomar}
              aria-label={`Retomar / Reprocessar falhas da execução ${execucao.id}`}
            >
              {retomando ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <RotateCcw className="mr-1.5 h-4 w-4" aria-hidden="true" />
              )}
              Retomar / Reprocessar falhas
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Metrica rotulo="Progresso" valor={`${execucao.processadas}/${execucao.total_itens}`} />
          <Metrica rotulo="Erros" valor={execucao.total_erros} />
          <Metrica rotulo="Divergências na rodada" valor={execucao.divergencias_abertas} />
          <Metrica rotulo="Hits de cache" valor={execucao.cache_hits} />
          <Metrica rotulo="Tokens de prompt" valor={execucao.prompt_tokens} />
          <Metrica rotulo="Tokens de resposta" valor={execucao.completion_tokens} />
        </div>
      </CardContent>
    </Card>
  );
}

export function ExecucoesTab() {
  const { activeTaxonomiaId, isLoading: taxonomiasLoading } = useTaxonomia();
  const execucoesQuery = useExecucoesDaTaxonomiaQuery(activeTaxonomiaId);
  // Retomadas em voo vêm do MutationCache e sobrevivem à troca de aba.
  const { retomar, retomandoIds } = useRetomarExecucao();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [retomarError, setRetomarError] = useState<string | null>(null);

  const execucoes = execucoesQuery.data?.itens ?? [];

  async function handleRetomar(execucaoId: string) {
    setRetomarError(null);
    try {
      await retomar(execucaoId);
    } catch (error) {
      setRetomarError(getErrorMessage(error, "Não foi possível retomar a Execução."));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button type="button" onClick={() => setDialogOpen(true)}>
          <Play className="mr-1.5 h-4 w-4" aria-hidden="true" />
          Nova Execução
        </Button>
      </div>

      {retomarError ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Falha ao retomar Execução</AlertTitle>
          <AlertDescription>{retomarError}</AlertDescription>
        </Alert>
      ) : null}

      {taxonomiasLoading || execucoesQuery.isLoading ? (
        <Skeleton className="h-32 w-full" aria-label="Carregando execuções" />
      ) : execucoesQuery.error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Falha ao carregar Execuções</AlertTitle>
          <AlertDescription>
            {getErrorMessage(execucoesQuery.error, "Não foi possível listar as Execuções.")}
          </AlertDescription>
        </Alert>
      ) : activeTaxonomiaId === null ? (
        <p className="text-sm text-muted-foreground">Selecione uma Taxonomia para ver as Execuções.</p>
      ) : execucoes.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhuma Execução de Classificação para esta Taxonomia.
        </p>
      ) : (
        execucoes.map((execucao) => (
          <ExecucaoCard
            key={execucao.id}
            execucao={execucao}
            retomando={retomandoIds.has(execucao.id)}
            onRetomar={() => void handleRetomar(execucao.id)}
          />
        ))
      )}

      <NovaExecucaoDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
