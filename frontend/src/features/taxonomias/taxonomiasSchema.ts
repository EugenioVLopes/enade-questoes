import { z } from "zod";

const obrigatorio = (mensagem: string) => z.string().trim().min(1, mensagem);

export const taxonomiaCriarSchema = z.object({
  codigo: obrigatorio("Informe o código da Taxonomia."),
  nome: obrigatorio("Informe o nome da Taxonomia."),
  curso_referencia: z.string().trim(),
});

export const taxonomiaEditarSchema = taxonomiaCriarSchema.omit({ codigo: true });

export const disciplinaCriarSchema = z.object({
  codigo: obrigatorio("Informe o código da Disciplina."),
  nome: obrigatorio("Informe o nome da Disciplina."),
  ementa: z.string().trim(),
});

export const disciplinaEditarSchema = disciplinaCriarSchema.omit({ codigo: true });

export const perfilNovaVersaoSchema = z.object({
  versao: obrigatorio("Informe o identificador da nova versão."),
  descricao: z.string().trim(),
  diretrizes_gerais: obrigatorio("Informe as diretrizes gerais."),
  guia_fronteiras: z.string(),
  template_prompt: obrigatorio("Informe o template do prompt."),
});

export const execucaoSchema = z
  .object({
    taxonomia_id: z.string().min(1, "Selecione a Taxonomia."),
    perfil_id: z.string().min(1, "Selecione o Perfil de Classificação."),
    escopo: z.enum(["todas", "prova_id", "pendentes", "disciplina_arquivada"]),
    prova_id: z.string(),
    incluir_revisadas: z.boolean(),
  })
  .superRefine((value, ctx) => {
    if (value.escopo === "prova_id" && !value.prova_id) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["prova_id"],
        message: "Selecione a Prova do escopo.",
      });
    }
  });

export type FieldErrors = Record<string, string>;

export function collectFieldErrors(error: z.ZodError): FieldErrors {
  const errors: FieldErrors = {};
  for (const issue of error.issues) {
    const key = String(issue.path[0] ?? "form");
    errors[key] ??= issue.message;
  }
  return errors;
}
