import { z } from "zod";

import type { components } from "@/api/schema";

export type HealthResponse = components["schemas"]["HealthResponse"];

const healthResponseSchema = z.object({
  status: z.enum(["ok", "degradado"]),
  banco_dados: z.enum(["conectado", "indisponivel"]),
  worker: z.object({
    estado: z.enum(["ocioso", "ocupado"]),
    tarefa_ativa: z.string().nullable(),
    tipo: z.enum(["ingestao", "classificacao"]).nullable().optional(),
    alvo: z.string().nullable().optional(),
    processadas: z.number().int().nullable().optional(),
    total: z.number().int().nullable().optional(),
  }),
});

export async function fetchHealth(baseUrl = ""): Promise<HealthResponse> {
  const response = await fetch(`${baseUrl}/api/v1/health`);
  const data: unknown = await response.json();
  return healthResponseSchema.parse(data);
}
