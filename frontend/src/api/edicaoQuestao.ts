import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import type {
  AlertaExtracaoResponse,
  AtivoVisualResponse,
  DetalheQuestaoResponse,
} from "@/api/revisao";
import type { components } from "@/api/schema";

export type { AlertaExtracaoResponse, AtivoVisualResponse, DetalheQuestaoResponse };
export type EditarQuestaoRequest = components["schemas"]["EditarQuestaoRequest"];
export type AlternativaEdicaoRequest = components["schemas"]["AlternativaEdicaoRequest"];
export type GabaritoEdicaoRequest = components["schemas"]["GabaritoEdicaoRequest"];
export type AtualizarAlertaRequest = components["schemas"]["AtualizarAlertaRequest"];
export type LetraAlternativa = components["schemas"]["LetraAlternativa"];
export type SituacaoGabarito = components["schemas"]["SituacaoGabarito"];
export type OrigemAtivoVisual = components["schemas"]["OrigemAtivoVisual"];

export function urlPaginaProvaImagem(provaId: string, pagina: number, dpi?: number): string {
  const base = `/api/v1/provas/${encodeURIComponent(provaId)}/paginas/${pagina}/imagem`;
  if (dpi === undefined || dpi === 150) {
    return base;
  }
  return `${base}?dpi=${dpi}`;
}

export function editarConteudoQuestao({
  questaoId,
  taxonomiaId,
  payload,
}: {
  questaoId: string;
  taxonomiaId?: string | null;
  payload: EditarQuestaoRequest;
}): Promise<DetalheQuestaoResponse> {
  return apiRequest<DetalheQuestaoResponse>(`/api/v1/questoes/${encodeURIComponent(questaoId)}`, {
    method: "PATCH",
    query: taxonomiaId ? { taxonomia_id: taxonomiaId } : undefined,
    json: payload,
  });
}

export function resolverAlertaExtracao({
  questaoId,
  alertaId,
  taxonomiaId,
}: {
  questaoId: string;
  alertaId: string;
  taxonomiaId?: string | null;
}): Promise<DetalheQuestaoResponse> {
  return apiRequest<DetalheQuestaoResponse>(
    `/api/v1/questoes/${encodeURIComponent(questaoId)}/alertas/${encodeURIComponent(alertaId)}`,
    {
      method: "PATCH",
      query: taxonomiaId ? { taxonomia_id: taxonomiaId } : undefined,
      json: { status: "resolvido" } satisfies AtualizarAlertaRequest,
    },
  );
}

export function adicionarAtivoVisual({
  questaoId,
  arquivo,
  alternativaLetra,
  ordem,
}: {
  questaoId: string;
  arquivo: File;
  alternativaLetra?: LetraAlternativa | null;
  ordem?: number | null;
}): Promise<AtivoVisualResponse> {
  const formData = new FormData();
  formData.append("arquivo", arquivo);
  if (alternativaLetra != null) {
    formData.append("alternativa_letra", alternativaLetra);
  }
  if (ordem != null) {
    formData.append("ordem", String(ordem));
  }

  return apiRequest<AtivoVisualResponse>(
    `/api/v1/questoes/${encodeURIComponent(questaoId)}/ativos-visuais`,
    {
      method: "POST",
      body: formData,
    },
  );
}

export function atualizarAtivoVisual({
  ativoId,
  arquivo,
  ordem,
  alternativaLetra,
  removerAlternativaLetra,
}: {
  ativoId: string;
  arquivo?: File | null;
  ordem?: number | null;
  alternativaLetra?: LetraAlternativa | null;
  removerAlternativaLetra?: boolean;
}): Promise<AtivoVisualResponse> {
  const formData = new FormData();
  if (arquivo != null) {
    formData.append("arquivo", arquivo);
  }
  if (ordem != null) {
    formData.append("ordem", String(ordem));
  }
  // O contrato do endpoint rejeita alternativa_letra e remover_alternativa_letra=true juntos.
  if (removerAlternativaLetra === true) {
    formData.append("remover_alternativa_letra", "true");
  } else if (alternativaLetra != null) {
    formData.append("alternativa_letra", alternativaLetra);
  }

  return apiRequest<AtivoVisualResponse>(`/api/v1/ativos-visuais/${encodeURIComponent(ativoId)}`, {
    method: "PATCH",
    body: formData,
  });
}

export function removerAtivoVisual(ativoId: string): Promise<void> {
  return apiRequest<void>(`/api/v1/ativos-visuais/${encodeURIComponent(ativoId)}`, {
    method: "DELETE",
  });
}

export async function reordenarAtivosVisuais(
  atualizacoes: readonly { ativoId: string; ordem: number }[],
): Promise<AtivoVisualResponse[]> {
  const resultados: AtivoVisualResponse[] = [];
  // Atualização sequencial evita condição de corrida na escrita do agregado Questão.
  for (const item of atualizacoes) {
    const atualizado = await atualizarAtivoVisual({
      ativoId: item.ativoId,
      ordem: item.ordem,
    });
    resultados.push(atualizado);
  }
  return resultados;
}

function useInvalidarQuestoes() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.questoes.all });
}

function useAtualizarDetalheQuestao() {
  const queryClient = useQueryClient();
  return async (
    atualizada: DetalheQuestaoResponse,
    variaveis: { questaoId: string; taxonomiaId?: string | null },
  ) => {
    if (variaveis.taxonomiaId) {
      queryClient.setQueryData(
        queryKeys.questoes.detalhe(variaveis.questaoId, variaveis.taxonomiaId),
        atualizada,
      );
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.questoes.all });
  };
}

export function useEditarConteudoQuestaoMutation() {
  const onSuccess = useAtualizarDetalheQuestao();
  return useMutation({ mutationFn: editarConteudoQuestao, onSuccess });
}

export function useResolverAlertaExtracaoMutation() {
  const onSuccess = useAtualizarDetalheQuestao();
  return useMutation({ mutationFn: resolverAlertaExtracao, onSuccess });
}

export function useAdicionarAtivoVisualMutation() {
  const invalidar = useInvalidarQuestoes();
  return useMutation({ mutationFn: adicionarAtivoVisual, onSuccess: invalidar });
}

export function useAtualizarAtivoVisualMutation() {
  const invalidar = useInvalidarQuestoes();
  return useMutation({ mutationFn: atualizarAtivoVisual, onSuccess: invalidar });
}

export function useReordenarAtivosVisuaisMutation() {
  const invalidar = useInvalidarQuestoes();
  return useMutation({ mutationFn: reordenarAtivosVisuais, onSuccess: invalidar });
}

export function useRemoverAtivoVisualMutation() {
  const invalidar = useInvalidarQuestoes();
  return useMutation({ mutationFn: removerAtivoVisual, onSuccess: invalidar });
}
