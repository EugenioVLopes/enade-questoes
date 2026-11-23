import type { ListarQuestoesParams } from "@/api/questoes";
import { TAMANHO_PAGINA_FILA } from "@/api/revisao";
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

/** Parâmetros da listagem da fila (sem `pagina`: a paginação é feita pela consulta infinita). */
export function paramsDaFila(modo: ModoRevisao, taxonomiaId: string): ListarQuestoesParams {
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
      // A API não ordena por execução mais recente; usa a ordenação de consulta (ano desc, número asc).
      return { ...base, com_divergencia: true, ordenacao: "consulta" };
    case "disciplina_arquivada":
      return { ...base, usa_disciplina_arquivada: true, ordenacao: "consulta" };
  }
}

/** Identifica fila + questão da URL, para detectar navegação do usuário durante uma operação assíncrona. */
export function assinaturaDaUrl(search: URLSearchParams): string {
  return [search.get(REVISAO_MODO_PARAM), search.get(ABA_PARAM), search.get(QUESTAO_PARAM)].join("|");
}

/** Atualiza a URL trocando só a questão selecionada (preserva modo, aba, recorte e Taxonomia). */
export function comQuestao(prev: URLSearchParams, questaoId: string | null): URLSearchParams {
  const next = new URLSearchParams(prev);
  if (questaoId) {
    next.set(QUESTAO_PARAM, questaoId);
  } else {
    next.delete(QUESTAO_PARAM);
  }
  return next;
}

/** Troca de aba: sai do recorte, preserva só a Taxonomia e limpa a questão selecionada. */
export function comAba(prev: URLSearchParams, aba: AbaRevisao): URLSearchParams {
  const next = new URLSearchParams();
  const taxonomia = prev.get(TAXONOMIA_SEARCH_PARAM);
  if (taxonomia) {
    next.set(TAXONOMIA_SEARCH_PARAM, taxonomia);
  }
  next.set(ABA_PARAM, aba);
  return next;
}
