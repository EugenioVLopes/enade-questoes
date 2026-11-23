import type { ClassificacaoResponse } from "@/api/revisao";
import { Badge } from "@/components/ui/badge";

import { formatarConfianca, nomeDaDisciplina, type NomesDisciplinas } from "@/features/revisao/classificacaoUtils";

export interface ResumoClassificacaoProps {
  classificacao: Pick<
    ClassificacaoResponse,
    "disciplina_principal" | "disciplinas_secundarias" | "topicos" | "justificativa"
  > &
    Partial<Pick<ClassificacaoResponse, "confianca">>;
  nomes: NomesDisciplinas;
}

/** Disciplina principal, secundárias, Tópicos e justificativa de uma Classificação. */
export function ResumoClassificacao({ classificacao, nomes }: ResumoClassificacaoProps) {
  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge variant="default">{nomeDaDisciplina(nomes, classificacao.disciplina_principal)}</Badge>
        {classificacao.disciplinas_secundarias.map((codigo) => (
          <Badge key={codigo} variant="outline">
            {nomeDaDisciplina(nomes, codigo)}
          </Badge>
        ))}
        {classificacao.confianca !== undefined ? (
          <span className="text-xs text-muted-foreground">Confiança {formatarConfianca(classificacao.confianca)}</span>
        ) : null}
      </div>
      {classificacao.topicos.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {classificacao.topicos.map((topico) => (
            <Badge key={topico} variant="secondary">
              {topico}
            </Badge>
          ))}
        </div>
      ) : null}
      {classificacao.justificativa ? <p className="text-muted-foreground">{classificacao.justificativa}</p> : null}
    </div>
  );
}
