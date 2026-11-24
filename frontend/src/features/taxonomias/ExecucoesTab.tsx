import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDownLeft,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  GitCompareArrows,
  ListChecks,
  Loader2,
  Play,
  RotateCcw,
  XCircle,
  Zap,
  type LucideIcon,
} from "lucide-react";

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

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "concluida":
      return <CheckCircle2 className="mr-1 h-3 w-3 shrink-0" aria-hidden="true" />;
    case "concluida_com_erros":
      return <AlertTriangle className="mr-1 h-3 w-3 shrink-0" aria-hidden="true" />;
    case "erro":
    case "interrompida":
      return <XCircle className="mr-1 h-3 w-3 shrink-0" aria-hidden="true" />;
    case "processando":
      return <Loader2 className="mr-1 h-3 w-3 shrink-0 animate-spin" aria-hidden="true" />;
    default:
      return <Clock className="mr-1 h-3 w-3 shrink-0" aria-hidden="true" />;
  }
}

function Metrica({
  rotulo,
  valor,
  icon: Icon,
  iconClassName,
  valorClassName,
}: {
  rotulo: string;
  valor: string | number;
  icon: LucideIcon;
  iconClassName?: string;
  valorClassName?: string;
}) {
  return (
    <div className="p-3">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Icon
          className={`h-3.5 w-3.5 shrink-0 ${iconClassName ?? "text-muted-foreground/80"}`}
          aria-hidden="true"
        />
        <p className="truncate text-[11px] font-medium">{rotulo}</p>
      </div>
      <p
        className={`mt-1.5 font-mono text-base font-semibold tabular-nums ${valorClassName ?? "text-foreground"}`}
      >
        {valor}
      </p>
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
  const temErros = execucao.total_erros > 0;
  const temDivergencias = execucao.divergencias_abertas > 0;

  return (
    <Card data-testid={`execucao-card-${execucao.id}`} className="overflow-hidden">
      <CardHeader className="gap-2 pb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 font-mono text-base font-semibold">
              <Clock className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span>{formatarData(execucao.criada_em)}</span>
            </CardTitle>
            <CardDescription className="text-xs">
              <span className="font-medium text-foreground/80">{execucao.snapshot_resumo.taxonomia.nome}</span> ·{" "}
              <span className="font-mono">
                {execucao.snapshot_resumo.perfil.codigo} {execucao.snapshot_resumo.perfil.versao}
              </span>{" "}
              · {ESCOPO_ROTULO[execucao.escopo] ?? execucao.escopo}
              {execucao.incluir_revisadas ? " · inclui revisadas" : ""}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant={execucao.status === "erro" ? "destructive" : "secondary"}
              className={
                execucao.status === "concluida"
                  ? "border-emerald-700/25 bg-emerald-50 text-emerald-800"
                  : execucao.status === "concluida_com_erros"
                    ? "border-amber-700/25 bg-amber-50 text-amber-900"
                    : undefined
              }
            >
              <StatusIcon status={execucao.status} />
              <span>{STATUS_ROTULO[execucao.status] ?? execucao.status}</span>
            </Badge>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!retomavel || retomando}
              onClick={onRetomar}
              aria-label={`Retomar / Reprocessar falhas da execução ${execucao.id}`}
            >
              {retomando ? (
                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <RotateCcw className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
              )}
              Retomar / Reprocessar falhas
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pb-5">
        <div className="grid grid-cols-2 divide-x divide-y divide-border rounded-md border border-border bg-surface/45 sm:grid-cols-3 lg:grid-cols-6 lg:divide-y-0">
          <Metrica
            rotulo="Progresso"
            valor={`${execucao.processadas}/${execucao.total_itens}`}
            icon={ListChecks}
          />
          <Metrica
            rotulo="Erros"
            valor={execucao.total_erros}
            icon={AlertCircle}
            iconClassName={temErros ? "text-destructive" : undefined}
            valorClassName={temErros ? "text-destructive" : undefined}
          />
          <Metrica
            rotulo="Divergências na rodada"
            valor={execucao.divergencias_abertas}
            icon={GitCompareArrows}
            iconClassName={temDivergencias ? "text-amber-700" : undefined}
            valorClassName={temDivergencias ? "text-amber-900" : undefined}
          />
          <Metrica rotulo="Hits de cache" valor={execucao.cache_hits} icon={Zap} />
          <Metrica rotulo="Tokens de prompt" valor={execucao.prompt_tokens} icon={ArrowUpRight} />
          <Metrica rotulo="Tokens de resposta" valor={execucao.completion_tokens} icon={ArrowDownLeft} />
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
