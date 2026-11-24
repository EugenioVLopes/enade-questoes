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

export function ResumoClassificacao({ classificacao, nomes }: ResumoClassificacaoProps) {
  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge variant="default" className="px-2.5 py-1 text-xs">
          {nomeDaDisciplina(nomes, classificacao.disciplina_principal)}
        </Badge>
        {classificacao.disciplinas_secundarias.map((codigo) => (
          <Badge key={codigo} variant="outline" className="py-1">
            {nomeDaDisciplina(nomes, codigo)}
          </Badge>
        ))}
        {classificacao.confianca !== undefined ? (
          <span className="ml-auto rounded-sm bg-surface px-2 py-0.5 font-mono text-[11px] font-medium text-muted-foreground tabular-nums">
            Confiança {formatarConfianca(classificacao.confianca)}
          </span>
        ) : null}
      </div>
      {classificacao.topicos.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {classificacao.topicos.map((topico) => (
            <Badge key={topico} variant="secondary" className="font-mono text-[11px] font-normal">
              {topico}
            </Badge>
          ))}
        </div>
      ) : null}
      {classificacao.justificativa ? (
        <p className="rounded-md border border-border/80 bg-surface/50 px-3.5 py-3 text-[13.5px] leading-relaxed text-foreground/85">
          {classificacao.justificativa}
        </p>
      ) : null}
    </div>
  );
}
