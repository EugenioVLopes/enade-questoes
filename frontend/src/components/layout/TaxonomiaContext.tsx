import { useCallback, useEffect, useMemo } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { findDefaultTaxonomia, useTaxonomiasQuery } from "@/api/taxonomias";
import {
  TAXONOMIA_SEARCH_PARAM,
  TAXONOMIA_STORAGE_KEY,
  TaxonomiaContext,
  type TaxonomiaContextValue,
} from "@/components/layout/useTaxonomia";

function safeReadSessionStorage(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWriteSessionStorage(key: string, value: string): void {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // Ignora falhas de sessionStorage em ambientes restritos.
  }
}

export function TaxonomiaProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const taxonomiasQuery = useTaxonomiasQuery();

  const taxonomias = useMemo(
    () => taxonomiasQuery.data?.itens ?? [],
    [taxonomiasQuery.data?.itens],
  );

  const urlTaxonomiaId = searchParams.get(TAXONOMIA_SEARCH_PARAM);

  const activeTaxonomiaId = useMemo(() => {
    if (taxonomias.length === 0) {
      return null;
    }

    if (urlTaxonomiaId && taxonomias.some((item) => item.id === urlTaxonomiaId)) {
      return urlTaxonomiaId;
    }

    const storedId = safeReadSessionStorage(TAXONOMIA_STORAGE_KEY);
    if (storedId && taxonomias.some((item) => item.id === storedId)) {
      return storedId;
    }

    const fallback = findDefaultTaxonomia(taxonomias) ?? taxonomias[0] ?? null;
    return fallback?.id ?? null;
  }, [taxonomias, urlTaxonomiaId]);

  useEffect(() => {
    if (!activeTaxonomiaId) {
      return;
    }

    safeWriteSessionStorage(TAXONOMIA_STORAGE_KEY, activeTaxonomiaId);

    if (urlTaxonomiaId !== activeTaxonomiaId) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set(TAXONOMIA_SEARCH_PARAM, activeTaxonomiaId);
          return next;
        },
        { replace: true },
      );
    }
  }, [activeTaxonomiaId, setSearchParams, urlTaxonomiaId]);

  const setActiveTaxonomiaId = useCallback(
    (nextId: string) => {
      safeWriteSessionStorage(TAXONOMIA_STORAGE_KEY, nextId);
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set(TAXONOMIA_SEARCH_PARAM, nextId);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const activeTaxonomia = useMemo(
    () => taxonomias.find((item) => item.id === activeTaxonomiaId) ?? null,
    [taxonomias, activeTaxonomiaId],
  );

  const error = useMemo(() => {
    if (!taxonomiasQuery.error) {
      return null;
    }
    return taxonomiasQuery.error instanceof Error
      ? taxonomiasQuery.error
      : new Error(String(taxonomiasQuery.error));
  }, [taxonomiasQuery.error]);

  const value = useMemo<TaxonomiaContextValue>(
    () => ({
      taxonomias,
      activeTaxonomiaId,
      activeTaxonomia,
      setActiveTaxonomiaId,
      isLoading: taxonomiasQuery.isLoading,
      error,
    }),
    [
      taxonomias,
      activeTaxonomiaId,
      activeTaxonomia,
      setActiveTaxonomiaId,
      taxonomiasQuery.isLoading,
      error,
    ],
  );

  return <TaxonomiaContext.Provider value={value}>{children}</TaxonomiaContext.Provider>;
}
