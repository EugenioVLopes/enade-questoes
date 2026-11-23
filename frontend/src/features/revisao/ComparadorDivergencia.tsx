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
    <table className="w-full table-fixed border-collapse text-sm" aria-label="Comparador de Divergência">
      <thead>
        <tr className="text-left">
          <th scope="col" className="w-1/4 p-1.5" />
          <th scope="col" className="p-1.5">
            Vigente humana
            <span className="block text-xs font-normal text-muted-foreground">{vigente.origem === "humana" ? "Humana" : "IA"}</span>
          </th>
          <th scope="col" className="p-1.5">
            Candidata IA
            <span className="block text-xs font-normal text-muted-foreground">
              Confiança {formatarConfianca(divergencia.confianca_candidata)}
            </span>
          </th>
        </tr>
      </thead>
      <tbody>
        {linhas.map((linha) => {
          const difere = diferente(linha, vigente, divergencia);
          return (
            <tr key={linha.chave} data-diferente={difere ? "true" : "false"} className="align-top">
              <th scope="row" className="p-1.5 text-left font-medium">
                {linha.rotulo}
                {difere ? (
                  <Badge variant="outline" className="ml-1 border-amber-500/50 text-amber-700">
                    Difere
                  </Badge>
                ) : null}
              </th>
              <td className={cn("break-words border p-1.5", difere && "bg-amber-500/10")}>{linha.vigente}</td>
              <td className={cn("break-words border p-1.5", difere && "bg-amber-500/10")}>{linha.candidata}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
