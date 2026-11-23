import { TAMANHO_PAGINA_FILA, type FilaRevisaoParams } from "@/api/revisao";
import {
  REVISAO_MODO_PARAM,
  REVISAO_MODO_RECORTE,
  TAXONOMIA_SEARCH_PARAM,
} from "@/components/layout/useTaxonomia";
import { filtrosParaApi, parseFiltros, type FiltrosQuestoes } from "@/features/questoes/filtrosUrl";

export const ABAS = ["pendentes", "divergencias", "disciplina_arquivada"] as const;
export type AbaRevisao = (typeof ABAS)[number];

const ABA_PADRAO: AbaRevisao = "pendentes";
const ABA_PARAM = "aba";
const QUESTAO_PARAM = "questao";

export const ROTULOS_ABAS: Record<AbaRevisao, string> = {
  pendentes: "Pendentes",
  divergencias: "Divergências",
  disciplina_arquivada: "Disciplina arquivada",
};

export type ModoRevisao = { tipo: "abas"; aba: AbaRevisao } | { tipo: "recorte"; filtros: FiltrosQuestoes };

interface EstadoUrlRevisao {
  modo: ModoRevisao;
  questaoId: string | null;
}

export function parseRevisaoUrl(search: URLSearchParams): EstadoUrlRevisao {
  const questaoId = search.get(QUESTAO_PARAM)?.trim() || null;
  if (search.get(REVISAO_MODO_PARAM) === REVISAO_MODO_RECORTE) {
    return { modo: { tipo: "recorte", filtros: parseFiltros(search) }, questaoId };
  }
  const aba = ABAS.find((item) => item === search.get(ABA_PARAM)) ?? ABA_PADRAO;
  return { modo: { tipo: "abas", aba }, questaoId };
}

export function paramsDaFila(modo: ModoRevisao, taxonomiaId: string): FilaRevisaoParams {
  if (modo.tipo === "recorte") {
    const params = filtrosParaApi(modo.filtros, taxonomiaId, TAMANHO_PAGINA_FILA);
    delete params.pagina;
    return params;
  }
  const base = { taxonomia_id: taxonomiaId, tamanho_pagina: TAMANHO_PAGINA_FILA };
  switch (modo.aba) {
    case "pendentes":
      return { ...base, status_revisao: "pendente", ordenacao: "fila_revisao" };
    case "divergencias":
      return { ...base, com_divergencia: true, ordenacao: "consulta" };
    case "disciplina_arquivada":
      return { ...base, usa_disciplina_arquivada: true, ordenacao: "consulta" };
  }
}

export function assinaturaDaUrl(search: URLSearchParams): string {
  return [search.get(REVISAO_MODO_PARAM), search.get(ABA_PARAM), search.get(QUESTAO_PARAM)].join("|");
}

export function comQuestao(prev: URLSearchParams, questaoId: string | null): URLSearchParams {
  const next = new URLSearchParams(prev);
  if (questaoId) {
    next.set(QUESTAO_PARAM, questaoId);
  } else {
    next.delete(QUESTAO_PARAM);
  }
  return next;
}

export function comAba(prev: URLSearchParams, aba: AbaRevisao): URLSearchParams {
  const next = new URLSearchParams();
  const taxonomia = prev.get(TAXONOMIA_SEARCH_PARAM);
  if (taxonomia) {
    next.set(TAXONOMIA_SEARCH_PARAM, taxonomia);
  }
  next.set(ABA_PARAM, aba);
  return next;
}
