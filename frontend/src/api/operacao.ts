import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  fetchHealth,
  type HealthResponse,
  type WorkerHealthResponse,
} from "@/api/client";
import {
  POLL_INTERVAL_MS,
  isIngestaoAtiva,
  isProvaAtiva,
  useProvasQuery,
} from "@/api/provas";
import { queryKeys } from "@/api/queryKeys";
import type { components } from "@/api/schema";

export type { HealthResponse, WorkerHealthResponse };
export type ListaExecucoesClassificacaoResponse =
  components["schemas"]["ListaExecucoesClassificacaoResponse"];
export type ExecucaoClassificacaoResumoResponse =
  components["schemas"]["ExecucaoClassificacaoResumoResponse"];
export type StatusExecucaoLiteral = components["schemas"]["StatusExecucaoLiteral"];

export function isExecucaoAtiva(status: StatusExecucaoLiteral): boolean {
  return status === "pendente" || status === "processando";
}

export function listarExecucoesClassificacao(
  taxonomiaId?: string | null,
): Promise<ListaExecucoesClassificacaoResponse> {
  return apiRequest<ListaExecucoesClassificacaoResponse>("/api/v1/execucoes-classificacao", {
    query: taxonomiaId ? { taxonomia_id: taxonomiaId } : undefined,
  });
}

export function useHealthQuery(options?: { activeHint?: boolean }) {
  const activeHint = options?.activeHint ?? false;

  return useQuery({
    queryKey: queryKeys.health.all,
    queryFn: () => fetchHealth(),
    refetchInterval: (currentQuery) => {
      const workerOccupied = currentQuery.state.data?.worker.estado === "ocupado";
      return activeHint || workerOccupied ? POLL_INTERVAL_MS : false;
    },
  });
}

export function useExecucoesClassificacaoQuery(
  taxonomiaId?: string | null,
  options?: { activeHint?: boolean; enabled?: boolean },
) {
  const activeHint = options?.activeHint ?? false;

  return useQuery({
    queryKey: queryKeys.execucoesClassificacao.list(taxonomiaId),
    queryFn: () => listarExecucoesClassificacao(taxonomiaId),
    enabled: options?.enabled ?? true,
    refetchInterval: (currentQuery) => {
      const hasActive =
        currentQuery.state.data?.itens.some((item) => isExecucaoAtiva(item.status)) ?? false;
      return activeHint || hasActive ? POLL_INTERVAL_MS : false;
    },
  });
}

export interface WorkerStatusState {
  isActive: boolean;
  label: string | null;
  tipo: "ingestao" | "classificacao" | null;
  processadas: number | null;
  total: number | null;
  targetRoute: "/provas" | "/taxonomias";
  activeProvaId: string | null;
  activeExecucaoId: string | null;
  bancoIndisponivel: boolean;
  health: HealthResponse | undefined;
  isLoading: boolean;
}

export function useWorkerStatus(taxonomiaId?: string | null): WorkerStatusState {
  const queryClient = useQueryClient();
  const [activeHint, setActiveHint] = useState(false);

  const healthQuery = useHealthQuery({ activeHint });
  const provasQuery = useProvasQuery({ activeHint });
  const execucoesQuery = useExecucoesClassificacaoQuery(taxonomiaId, { activeHint });

  const worker = healthQuery.data?.worker;
  const healthIsOccupied = worker?.estado === "ocupado";

  const activeProva = provasQuery.data?.itens.find(isProvaAtiva) ?? null;
  const activeExecucao =
    execucoesQuery.data?.itens.find((item) => isExecucaoAtiva(item.status)) ?? null;

  const isActive = Boolean(healthIsOccupied || activeProva || activeExecucao);

  useEffect(() => {
    if (activeHint !== isActive) {
      setActiveHint(isActive);
    }
  }, [activeHint, isActive]);

  const wasActiveRef = useRef(false);
  useEffect(() => {
    if (wasActiveRef.current && !isActive) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.provas.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.questoes.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.execucoesClassificacao.all });
    }
    wasActiveRef.current = isActive;
  }, [isActive, queryClient]);

  let label: string | null = null;
  let tipo: "ingestao" | "classificacao" | null = null;
  let processadas: number | null = null;
  let total: number | null = null;
  let targetRoute: "/provas" | "/taxonomias" = "/provas";

  if (healthIsOccupied && worker) {
    tipo = worker.tipo ?? null;
    processadas = worker.processadas ?? null;
    total = worker.total ?? null;
    targetRoute = worker.tipo === "classificacao" ? "/taxonomias" : "/provas";
    const activeText = worker.tarefa_ativa?.trim();
    if (activeText) {
      label = activeText;
    } else {
      const verb = worker.tipo === "classificacao" ? "Classificando" : "Ingerindo";
      label = worker.alvo ? `${verb} ${worker.alvo}` : verb;
    }
  } else if (activeProva) {
    const ingestaoEmAndamento = isIngestaoAtiva(activeProva.ultima_ingestao?.status);
    tipo = ingestaoEmAndamento ? "ingestao" : "classificacao";
    targetRoute = "/provas";
    label = `${ingestaoEmAndamento ? "Ingerindo" : "Classificando"} ${activeProva.exame} ${activeProva.ano}`;
  } else if (activeExecucao) {
    tipo = "classificacao";
    processadas = activeExecucao.processadas;
    total = activeExecucao.total_itens;
    targetRoute = "/taxonomias";
    label = `Classificando: ${activeExecucao.processadas}/${activeExecucao.total_itens}`;
  }

  return {
    isActive,
    label,
    tipo,
    processadas,
    total,
    targetRoute,
    activeProvaId: activeProva?.id ?? null,
    activeExecucaoId: activeExecucao?.id ?? null,
    bancoIndisponivel: healthQuery.data?.banco_dados === "indisponivel",
    health: healthQuery.data,
    isLoading: healthQuery.isLoading || provasQuery.isLoading || execucoesQuery.isLoading,
  };
}
