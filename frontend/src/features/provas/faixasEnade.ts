export interface FaixaQuestoes {
  inicio: number;
  fim: number;
}

export function resolverFaixaPadraoPorAno(ano: number): FaixaQuestoes | null {
  if (!Number.isInteger(ano) || ano < 1900) {
    return null;
  }

  if (ano >= 2014 && ano <= 2019) {
    return { inicio: 9, fim: 35 };
  }

  if (ano === 2023) {
    return { inicio: 10, fim: 38 };
  }

  if (ano >= 2026) {
    return { inicio: 16, fim: 45 };
  }

  return null;
}

export function formatarFaixaCE(inicio: number, fim: number): string {
  return `${String(inicio).padStart(2, "0")}–${String(fim).padStart(2, "0")}`;
}
