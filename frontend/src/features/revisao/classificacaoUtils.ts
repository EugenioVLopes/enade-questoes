export type NomesDisciplinas = ReadonlyMap<string, string>;

export function nomeDaDisciplina(nomes: NomesDisciplinas, codigo: string): string {
  return nomes.get(codigo) ?? codigo;
}

export function formatarConfianca(valor: number): string {
  return `${Math.round(valor * 100)}%`;
}
