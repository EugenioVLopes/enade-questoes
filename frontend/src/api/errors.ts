import type { components } from "@/api/schema";

export type ErroDetalheResponse = components["schemas"]["ErroDetalheResponse"];
export type ConflitoProvaResponse = components["schemas"]["ConflitoProvaResponse"];
export type ValidationError = components["schemas"]["ValidationError"];
export type HTTPValidationError = components["schemas"]["HTTPValidationError"];

const LOCATION_PREFIXES = new Set<string | number>(["body", "query", "path"]);

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isValidationErrorItem(value: unknown): value is ValidationError {
  if (!isRecord(value)) {
    return false;
  }

  return (
    Array.isArray(value.loc) &&
    typeof value.msg === "string" &&
    typeof value.type === "string"
  );
}

export function isConflitoProvaPayload(value: unknown): value is ConflitoProvaResponse {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.detail === "string" &&
    typeof value.prova_id === "string" &&
    typeof value.exame === "string" &&
    typeof value.curso === "string" &&
    typeof value.ano === "number"
  );
}

function formatValidationErrors(items: ValidationError[]): string | null {
  const formatted = items
    .map((item) => {
      const segments = item.loc.filter((segment, index) => {
        if (index === 0 && LOCATION_PREFIXES.has(segment)) {
          return false;
        }
        return true;
      });
      const fieldPath = segments.map(String).join(".");
      return fieldPath.length > 0 ? `${fieldPath}: ${item.msg}` : item.msg;
    })
    .filter((msg) => msg.trim().length > 0);

  return formatted.length > 0 ? formatted.join("; ") : null;
}

export function extractValidationErrors(payload: unknown): ValidationError[] | undefined {
  if (!isRecord(payload) || !Array.isArray(payload.detail)) {
    return undefined;
  }

  const items = payload.detail.filter(isValidationErrorItem);
  return items.length > 0 ? items : undefined;
}

export function extractErrorMessage(
  payload: unknown,
  fallback = "Erro inesperado ao comunicar com a API.",
): string {
  if (typeof payload === "string") {
    const trimmed = payload.trim();
    return trimmed.length > 0 ? trimmed : fallback;
  }

  if (isRecord(payload)) {
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail.trim();
    }

    if (Array.isArray(payload.detail)) {
      const items = payload.detail.filter(isValidationErrorItem);
      const formatted = formatValidationErrors(items);
      if (formatted) {
        return formatted;
      }
    }

    if (typeof payload.message === "string" && payload.message.trim().length > 0) {
      return payload.message.trim();
    }
  }

  return fallback;
}

export interface ApiErrorOptions {
  status: number;
  detail: string;
  validationErrors?: ValidationError[];
  rawBody?: unknown;
  message?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly validationErrors?: ValidationError[];
  readonly rawBody?: unknown;

  constructor(options: ApiErrorOptions) {
    super(options.message ?? options.detail);
    this.name = "ApiError";
    this.status = options.status;
    this.detail = options.detail;
    this.validationErrors = options.validationErrors;
    this.rawBody = options.rawBody;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class ProvaConflictError extends ApiError {
  readonly conflito: ConflitoProvaResponse;
  readonly provaId: string;

  constructor(conflito: ConflitoProvaResponse) {
    super({
      status: 409,
      detail: conflito.detail,
      rawBody: conflito,
    });
    this.name = "ProvaConflictError";
    this.conflito = conflito;
    this.provaId = conflito.prova_id;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function isProvaConflictError(error: unknown): error is ProvaConflictError {
  return error instanceof ProvaConflictError;
}

export function getErrorMessage(
  error: unknown,
  fallback = "Ocorreu um erro inesperado.",
): string {
  if (isApiError(error)) {
    return error.detail;
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message.trim();
  }

  return fallback;
}
