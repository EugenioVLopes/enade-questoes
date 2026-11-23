import { z } from "zod";

import { resolverFaixaPadraoPorAno } from "@/features/provas/faixasEnade";

const VALID_PDF_MIME_TYPES = new Set(["", "application/pdf", "application/x-pdf"]);

export function isFileInstance(value: unknown): value is File {
  return typeof File !== "undefined" && value instanceof File;
}

export const pdfFileSchema = z
  .custom<File>(isFileInstance, {
    message: "Selecione um PDF válido.",
  })
  .superRefine((file, ctx) => {
    if (file.size <= 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "O PDF selecionado não pode estar vazio.",
      });
      return;
    }

    const hasPdfExtension = file.name.trim().toLowerCase().endsWith(".pdf");
    const mime = file.type.trim().toLowerCase();
    const hasValidMime = VALID_PDF_MIME_TYPES.has(mime);

    if (!hasPdfExtension || !hasValidMime) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Envie um documento no formato PDF (.pdf).",
      });
    }
  });

export const optionalPdfFileSchema = pdfFileSchema.nullable().optional();

export const atualizarGabaritoFormSchema = z.object({
  arquivo_gabarito: pdfFileSchema,
});

export const ingestaoFormSchema = z
  .object({
    exame: z.string().trim().min(1, "Informe o exame."),
    curso: z.string().trim().min(1, "Informe o curso."),
    ano: z
      .number({ invalid_type_error: "Informe o ano da Prova." })
      .int("Informe um ano inteiro válido.")
      .min(1900, "Informe um ano válido entre 1900 e 2100.")
      .max(2100, "Informe um ano válido entre 1900 e 2100."),
    questao_inicio: z
      .number({ invalid_type_error: "Informe um número inteiro maior ou igual a 1." })
      .int("Informe um número inteiro maior ou igual a 1.")
      .min(1, "Informe um número inteiro maior ou igual a 1.")
      .nullable(),
    questao_fim: z
      .number({ invalid_type_error: "Informe um número inteiro maior ou igual a 1." })
      .int("Informe um número inteiro maior ou igual a 1.")
      .min(1, "Informe um número inteiro maior ou igual a 1.")
      .nullable(),
    classificar_automaticamente: z.boolean().default(true),
    arquivo_prova: pdfFileSchema,
    arquivo_gabarito: optionalPdfFileSchema,
  })
  .superRefine((data, ctx) => {
    const inicioInformado = data.questao_inicio != null;
    const fimInformado = data.questao_fim != null;

    if (inicioInformado !== fimInformado) {
      if (!inicioInformado) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["questao_inicio"],
          message: "Informe a questão inicial e a questão final juntas.",
        });
      }
      if (!fimInformado) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["questao_fim"],
          message: "Informe a questão inicial e a questão final juntas.",
        });
      }
      return;
    }

    if (
      data.questao_inicio != null &&
      data.questao_fim != null &&
      data.questao_fim < data.questao_inicio
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["questao_fim"],
        message: "A questão final deve ser maior ou igual à questão inicial.",
      });
      return;
    }

    if (
      data.questao_inicio == null &&
      data.questao_fim == null &&
      resolverFaixaPadraoPorAno(data.ano) === null
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["questao_inicio"],
        message: "Ano sem faixa padrão conhecida. Informe a faixa em Opções avançadas.",
      });
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["questao_fim"],
        message: "Informe a questão final para este ano.",
      });
    }
  });

export type ValidatedIngestaoFormValues = z.infer<typeof ingestaoFormSchema>;

export type IngestaoFormField =
  | "exame"
  | "curso"
  | "ano"
  | "questao_inicio"
  | "questao_fim"
  | "classificar_automaticamente"
  | "arquivo_prova"
  | "arquivo_gabarito";

export type IngestaoFieldErrors = Partial<Record<IngestaoFormField, string>>;

export interface IngestaoFormRawValues {
  exame: string;
  curso: string;
  ano: string;
  questao_inicio: string;
  questao_fim: string;
  classificar_automaticamente: boolean;
  arquivo_prova: File | null;
  arquivo_gabarito: File | null;
}

export type ParseIngestaoResult =
  | { success: true; data: ValidatedIngestaoFormValues }
  | { success: false; fieldErrors: IngestaoFieldErrors };

function parseStrictIntegerInput(raw: string): {
  kind: "empty" | "invalid" | "valid";
  value: number | null;
} {
  const trimmed = raw.trim();
  if (trimmed.length === 0) {
    return { kind: "empty", value: null };
  }

  if (!/^-?\d+$/.test(trimmed)) {
    return { kind: "invalid", value: null };
  }

  const parsed = Number(trimmed);
  if (!Number.isSafeInteger(parsed)) {
    return { kind: "invalid", value: null };
  }

  return { kind: "valid", value: parsed };
}

export function parseIngestaoFormValues(raw: IngestaoFormRawValues): ParseIngestaoResult {
  const fieldErrors: IngestaoFieldErrors = {};

  const parsedAno = parseStrictIntegerInput(raw.ano);
  if (parsedAno.kind === "empty") {
    fieldErrors.ano = "Informe o ano da Prova.";
  } else if (parsedAno.kind === "invalid") {
    fieldErrors.ano = "Informe um ano inteiro válido.";
  }

  const parsedInicio = parseStrictIntegerInput(raw.questao_inicio);
  if (parsedInicio.kind === "invalid") {
    fieldErrors.questao_inicio = "Informe um número inteiro maior ou igual a 1.";
  }

  const parsedFim = parseStrictIntegerInput(raw.questao_fim);
  if (parsedFim.kind === "invalid") {
    fieldErrors.questao_fim = "Informe um número inteiro maior ou igual a 1.";
  }

  const candidate = {
    exame: raw.exame,
    curso: raw.curso,
    ano: parsedAno.kind === "valid" && parsedAno.value !== null ? parsedAno.value : 2023,
    questao_inicio: parsedInicio.kind === "valid" ? parsedInicio.value : null,
    questao_fim: parsedFim.kind === "valid" ? parsedFim.value : null,
    classificar_automaticamente: raw.classificar_automaticamente,
    arquivo_prova: raw.arquivo_prova,
    arquivo_gabarito: raw.arquivo_gabarito,
  };

  const result = ingestaoFormSchema.safeParse(candidate);
  if (!result.success) {
    for (const issue of result.error.issues) {
      const field = issue.path[0] as IngestaoFormField | undefined;
      if (field && !fieldErrors[field]) {
        if (
          (field === "questao_inicio" || field === "questao_fim") &&
          parsedAno.kind !== "valid" &&
          parsedInicio.kind === "empty" &&
          parsedFim.kind === "empty"
        ) {
          continue;
        }
        fieldErrors[field] = issue.message;
      }
    }
  }

  if (Object.keys(fieldErrors).length > 0 || !result.success) {
    return { success: false, fieldErrors };
  }

  return { success: true, data: result.data };
}
