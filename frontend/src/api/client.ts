import { z } from "zod";

import {
  ApiError,
  ProvaConflictError,
  extractErrorMessage,
  extractValidationErrors,
  isConflitoProvaPayload,
} from "@/api/errors";
import type { components } from "@/api/schema";

export type HealthResponse = components["schemas"]["HealthResponse"];
export type WorkerHealthResponse = components["schemas"]["WorkerHealthResponse"];

const healthResponseSchema = z.object({
  status: z.enum(["ok", "degradado"]),
  banco_dados: z.enum(["conectado", "indisponivel"]),
  worker: z.object({
    estado: z.enum(["ocioso", "ocupado"]),
    tarefa_ativa: z.string().nullable().optional(),
    tipo: z.enum(["ingestao", "classificacao"]).nullable().optional(),
    alvo: z.string().nullable().optional(),
    processadas: z.number().int().nullable().optional(),
    total: z.number().int().nullable().optional(),
  }),
});

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | null;
  json?: unknown;
  query?: QueryParams;
  baseUrl?: string;
}

function buildUrl(path: string, query?: QueryParams, baseUrl = ""): string {
  const base = `${baseUrl}${path}`;
  if (!query) {
    return base;
  }

  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined) {
      searchParams.append(key, String(value));
    }
  }

  const serialized = searchParams.toString();
  if (!serialized) {
    return base;
  }

  return base.includes("?") ? `${base}&${serialized}` : `${base}?${serialized}`;
}

async function readResponsePayload(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) {
    return undefined;
  }

  if (typeof response.text === "function") {
    const text = await response.text();
    if (!text.trim()) {
      return undefined;
    }

    try {
      return JSON.parse(text) as unknown;
    } catch {
      return text;
    }
  }

  if (typeof response.json === "function") {
    try {
      return (await response.json()) as unknown;
    } catch {
      return undefined;
    }
  }

  return undefined;
}

function buildApiError(status: number, statusText: string, payload: unknown): ApiError {
  if (status === 409 && isConflitoProvaPayload(payload)) {
    return new ProvaConflictError(payload);
  }

  const validationErrors = extractValidationErrors(payload);
  const fallback =
    statusText.trim().length > 0
      ? `Erro ${status}: ${statusText}`
      : `Erro ${status} ao comunicar com a API.`;
  const detail = extractErrorMessage(payload, fallback);

  return new ApiError({
    status,
    detail,
    validationErrors,
    rawBody: payload,
  });
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { body, json, query, baseUrl = "", headers: initialHeaders, ...restInit } = options;

  const headers = new Headers(initialHeaders);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  let resolvedBody: BodyInit | null | undefined = body;
  if (json !== undefined) {
    resolvedBody = JSON.stringify(json);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  } else if (body instanceof FormData) {
    headers.delete("Content-Type");
  }

  const url = buildUrl(path, query, baseUrl);
  const response = await fetch(url, {
    ...restInit,
    headers,
    body: resolvedBody,
  });

  const payload = await readResponsePayload(response);

  if (!response.ok) {
    throw buildApiError(response.status, response.statusText, payload);
  }

  return payload as T;
}

export async function fetchHealth(baseUrl = ""): Promise<HealthResponse> {
  const response = await fetch(`${baseUrl}/api/v1/health`, {
    headers: { Accept: "application/json" },
  });
  const payload = await readResponsePayload(response);

  if (response.status === 200 || response.status === 503) {
    const parsed = healthResponseSchema.safeParse(payload);
    if (parsed.success) {
      return parsed.data;
    }
  }

  throw buildApiError(response.status, response.statusText, payload);
}
