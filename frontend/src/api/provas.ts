import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import type { components } from "@/api/schema";

export type ListaProvasResponse = components["schemas"]["ListaProvasResponse"];
export type ProvaDetalheResponse = components["schemas"]["ProvaDetalheResponse"];
export type IngestaoResumoResponse = components["schemas"]["IngestaoResumoResponse"];
export type StatusIngestao = IngestaoResumoResponse["status"];
export type ClassificacaoEncadeadaResponse =
  components["schemas"]["ClassificacaoEncadeadaResponse"];
export type ContagemQuestoesResponse = components["schemas"]["ContagemQuestoesResponse"];
export type ContagemAlertasResponse = components["schemas"]["ContagemAlertasResponse"];
export type ProvaIngestaoAceitaResponse = components["schemas"]["ProvaIngestaoAceitaResponse"];
export type ResumoAtualizacaoGabaritoResponse =
  components["schemas"]["ResumoAtualizacaoGabaritoResponse"];
export type ReprocessarProvaRequest = components["schemas"]["ReprocessarProvaRequest"];
export type ReprocessarProvaAceitaResponse =
  components["schemas"]["ReprocessarProvaAceitaResponse"];

export interface CriarProvaInput {
  arquivo_prova: File;
  curso: string;
  ano: number;
  exame?: string;
  arquivo_gabarito?: File | null;
  questao_inicio?: number | null;
  questao_fim?: number | null;
  taxonomia_id?: string | null;
  perfil_id?: string | null;
}

export interface AtualizarGabaritoInput {
  provaId: string;
  arquivo_gabarito: File;
}

export interface ReprocessarProvaInput {
  provaId: string;
  sobrescrever_editadas?: boolean;
}

export const POLL_INTERVAL_MS = 2000;

const ACTIVE_CLASSIFICACAO_ENCADEADA_STATUSES = new Set<string>([
  "aguardando_ingestao",
  "aguardando_agendamento",
  "agendada",
  "pendente",
  "processando",
]);

export function isIngestaoAtiva(status: StatusIngestao | null | undefined): boolean {
  return status === "pendente" || status === "processando";
}

export function isClassificacaoEncadeadaAtiva(
  classificacao: ClassificacaoEncadeadaResponse | null | undefined,
): boolean {
  if (!classificacao?.solicitada || !classificacao.status) {
    return false;
  }

  return ACTIVE_CLASSIFICACAO_ENCADEADA_STATUSES.has(classificacao.status);
}

export function isProvaAtiva(prova: ProvaDetalheResponse): boolean {
  if (isIngestaoAtiva(prova.ultima_ingestao?.status)) {
    return true;
  }

  return (
    prova.ultima_ingestao?.status === "concluida" &&
    isClassificacaoEncadeadaAtiva(prova.classificacao_encadeada)
  );
}

export function listarProvas(): Promise<ListaProvasResponse> {
  return apiRequest<ListaProvasResponse>("/api/v1/provas");
}

export function obterProva(provaId: string): Promise<ProvaDetalheResponse> {
  return apiRequest<ProvaDetalheResponse>(`/api/v1/provas/${encodeURIComponent(provaId)}`);
}

export function criarProva(input: CriarProvaInput): Promise<ProvaIngestaoAceitaResponse> {
  const formData = new FormData();
  formData.append("arquivo_prova", input.arquivo_prova);
  formData.append("curso", input.curso.trim());
  formData.append("ano", String(input.ano));

  const exameTrimmed = input.exame?.trim();
  if (exameTrimmed) {
    formData.append("exame", exameTrimmed);
  }

  if (input.arquivo_gabarito) {
    formData.append("arquivo_gabarito", input.arquivo_gabarito);
  }

  if (input.questao_inicio != null && input.questao_fim != null) {
    formData.append("questao_inicio", String(input.questao_inicio));
    formData.append("questao_fim", String(input.questao_fim));
  }

  const taxonomiaId = input.taxonomia_id?.trim();
  if (taxonomiaId) {
    formData.append("taxonomia_id", taxonomiaId);
    const perfilId = input.perfil_id?.trim();
    if (perfilId) {
      formData.append("perfil_id", perfilId);
    }
  }

  return apiRequest<ProvaIngestaoAceitaResponse>("/api/v1/provas", {
    method: "POST",
    body: formData,
  });
}

export function atualizarGabarito({
  provaId,
  arquivo_gabarito,
}: AtualizarGabaritoInput): Promise<ResumoAtualizacaoGabaritoResponse> {
  const formData = new FormData();
  formData.append("arquivo_gabarito", arquivo_gabarito);

  return apiRequest<ResumoAtualizacaoGabaritoResponse>(
    `/api/v1/provas/${encodeURIComponent(provaId)}/gabarito`,
    {
      method: "PUT",
      body: formData,
    },
  );
}

export function reprocessarProva({
  provaId,
  sobrescrever_editadas = false,
}: ReprocessarProvaInput): Promise<ReprocessarProvaAceitaResponse> {
  const payload: ReprocessarProvaRequest = { sobrescrever_editadas };

  return apiRequest<ReprocessarProvaAceitaResponse>(
    `/api/v1/provas/${encodeURIComponent(provaId)}/reprocessar`,
    {
      method: "POST",
      json: payload,
    },
  );
}

export function useProvasQuery(options?: { activeHint?: boolean }) {
  const queryClient = useQueryClient();
  const activeHint = options?.activeHint ?? false;

  const query = useQuery({
    queryKey: queryKeys.provas.list(),
    queryFn: listarProvas,
    refetchInterval: (currentQuery) => {
      const hasActiveProva = currentQuery.state.data?.itens.some(isProvaAtiva) ?? false;
      return activeHint || hasActiveProva ? POLL_INTERVAL_MS : false;
    },
  });

  const hasActiveProva = query.data?.itens.some(isProvaAtiva) ?? false;
  const wasActiveRef = useRef(false);

  useEffect(() => {
    if (wasActiveRef.current && !hasActiveProva) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.questoes.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.health.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.execucoesClassificacao.all });
    }
    wasActiveRef.current = hasActiveProva;
  }, [hasActiveProva, queryClient]);

  return query;
}

export function useCriarProvaMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: criarProva,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.provas.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.health.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.execucoesClassificacao.all });
    },
  });
}

export function useAtualizarGabaritoMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: atualizarGabarito,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.provas.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.questoes.all });
    },
  });
}

export function useReprocessarProvaMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: reprocessarProva,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.provas.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.health.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.execucoesClassificacao.all });
    },
  });
}
