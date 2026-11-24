import type { ClassificacaoResponse, DivergenciaResponse } from "@/api/revisao";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatarConfianca, nomeDaDisciplina, type NomesDisciplinas } from "@/features/revisao/classificacaoUtils";

interface Linha {
  chave: string;
  rotulo: string;
  vigente: string;
  candidata: string;
}

function lista(codigos: readonly string[], formatar: (c: string) => string = (c) => c): string {
  return codigos.length === 0 ? "—" : codigos.map(formatar).join(", ");
}

function mesmoConjunto(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((item) => b.includes(item));
}

function abreviar(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : "—";
}

function montarLinhas(
  vigente: ClassificacaoResponse,
  divergencia: DivergenciaResponse,
  nomes: NomesDisciplinas,
): Linha[] {
  const nome = (codigo: string) => nomeDaDisciplina(nomes, codigo);
  return [
    {
      chave: "principal",
      rotulo: "Disciplina principal",
      vigente: nome(vigente.disciplina_principal),
      candidata: nome(divergencia.disciplina_principal_candidata),
    },
    {
      chave: "secundarias",
      rotulo: "Disciplinas secundárias",
      vigente: lista(vigente.disciplinas_secundarias, nome),
      candidata: lista(divergencia.disciplinas_secundarias_candidatas, nome),
    },
    {
      chave: "topicos",
      rotulo: "Tópicos",
      vigente: lista(vigente.topicos),
      candidata: lista(divergencia.topicos_candidatos),
    },
    {
      chave: "justificativa",
      rotulo: "Justificativa",
      vigente: vigente.justificativa || "—",
      candidata: divergencia.justificativa_candidata || "—",
    },
    {
      chave: "execucao",
      rotulo: "Execução de Classificação de origem",
      vigente: abreviar(vigente.execucao_id),
      candidata: abreviar(divergencia.execucao_id),
    },
  ];
}

function diferente(
  linha: Linha,
  vigente: ClassificacaoResponse,
  divergencia: DivergenciaResponse,
): boolean {
  switch (linha.chave) {
    case "secundarias":
      return !mesmoConjunto(vigente.disciplinas_secundarias, divergencia.disciplinas_secundarias_candidatas);
    case "topicos":
      return !mesmoConjunto(vigente.topicos, divergencia.topicos_candidatos);
    default:
      return linha.vigente !== linha.candidata;
  }
}

export interface ComparadorDivergenciaProps {
  vigente: ClassificacaoResponse;
  divergencia: DivergenciaResponse;
  nomes: NomesDisciplinas;
}

export function ComparadorDivergencia({ vigente, divergencia, nomes }: ComparadorDivergenciaProps) {
  const linhas = montarLinhas(vigente, divergencia, nomes);
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full table-fixed border-collapse text-sm" aria-label="Comparador de Divergência">
        <thead>
          <tr className="border-b border-border bg-surface/65 text-left">
            <th scope="col" className="w-1/4 p-2 text-xs font-medium text-muted-foreground" />
            <th scope="col" className="border-l border-border p-2 text-xs font-semibold text-foreground">
              Vigente humana
              <span className="block font-mono text-[11px] font-normal text-muted-foreground">
                {vigente.origem === "humana" ? "Humana" : "IA"}
              </span>
            </th>
            <th scope="col" className="border-l border-border p-2 text-xs font-semibold text-foreground">
              Candidata IA
              <span className="block font-mono text-[11px] font-normal text-muted-foreground">
                Confiança {formatarConfianca(divergencia.confianca_candidata)}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((linha) => {
            const difere = diferente(linha, vigente, divergencia);
            return (
              <tr
                key={linha.chave}
                data-diferente={difere ? "true" : "false"}
                className="border-t border-border align-top"
              >
                <th scope="row" className="bg-surface/35 p-2 text-left text-xs font-medium text-foreground">
                  {linha.rotulo}
                  {difere ? (
                    <Badge variant="outline" className="ml-1 mt-1 border-amber-700/30 bg-amber-50 text-amber-900">
                      Difere
                    </Badge>
                  ) : null}
                </th>
                <td className={cn("break-words border-l border-border p-2 text-[13px]", difere && "bg-amber-50/70")}>
                  {linha.vigente}
                </td>
                <td className={cn("break-words border-l border-border p-2 text-[13px]", difere && "bg-amber-50/70")}>
                  {linha.candidata}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
