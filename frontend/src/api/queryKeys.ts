import type { ListarQuestoesParams } from "@/api/questoes";

export const queryKeys = {
  health: {
    all: ["health"] as const,
  },
  taxonomias: {
    all: ["taxonomias"] as const,
  },
  perfisClassificacao: {
    all: ["perfis-classificacao"] as const,
  },
  provas: {
    all: ["provas"] as const,
    list: () => ["provas", "list"] as const,
    detail: (provaId: string) => ["provas", "detail", provaId] as const,
  },
  questoes: {
    all: ["questoes"] as const,
    list: (params: ListarQuestoesParams) => ["questoes", "list", params] as const,
    fila: (params: ListarQuestoesParams) => ["questoes", "fila", params] as const,
    detalhe: (questaoId: string, taxonomiaId: string) =>
      ["questoes", "detalhe", questaoId, taxonomiaId] as const,
    contadores: (taxonomiaId?: string | null) =>
      ["questoes", "contadores", taxonomiaId ?? null] as const,
  },
  execucoesClassificacao: {
    all: ["execucoes-classificacao"] as const,
    list: (taxonomiaId?: string | null) =>
      ["execucoes-classificacao", "list", taxonomiaId ?? null] as const,
  },
} as const;
