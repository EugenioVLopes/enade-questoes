import { createContext, useContext } from "react";

import type { TaxonomiaResponse } from "@/api/taxonomias";

export const TAXONOMIA_STORAGE_KEY = "enade.activeTaxonomiaId";
export const TAXONOMIA_SEARCH_PARAM = "taxonomia";

export interface TaxonomiaContextValue {
  taxonomias: TaxonomiaResponse[];
  activeTaxonomiaId: string | null;
  activeTaxonomia: TaxonomiaResponse | null;
  setActiveTaxonomiaId: (id: string) => void;
  isLoading: boolean;
  error: Error | null;
}

export const TaxonomiaContext = createContext<TaxonomiaContextValue | null>(null);

export function useTaxonomia(): TaxonomiaContextValue {
  const context = useContext(TaxonomiaContext);
  if (!context) {
    throw new Error("useTaxonomia deve ser utilizado dentro de <TaxonomiaProvider>.");
  }
  return context;
}

export function buildSearchWithTaxonomia(
  currentSearch: string,
  taxonomiaId: string | null,
  extraParams?: Record<string, string>,
): string {
  const params = new URLSearchParams(currentSearch);

  if (taxonomiaId) {
    params.set(TAXONOMIA_SEARCH_PARAM, taxonomiaId);
  } else {
    params.delete(TAXONOMIA_SEARCH_PARAM);
  }

  if (extraParams) {
    for (const [key, value] of Object.entries(extraParams)) {
      params.set(key, value);
    }
  }

  const serialized = params.toString();
  return serialized.length > 0 ? `?${serialized}` : "";
}

export function buildIngerirHref(taxonomiaId: string | null): string {
  return `/provas${buildSearchWithTaxonomia("", taxonomiaId, { acao: "ingerir" })}`;
}

export function buildRevisaoProvaHref(provaId: string, taxonomiaId: string | null): string {
  return `/revisao${buildSearchWithTaxonomia("", taxonomiaId, { prova_id: provaId })}`;
}
