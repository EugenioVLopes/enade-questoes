import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { ClassificacaoResponse, DetalheQuestaoResponse } from "@/api/revisao";
import { Badge } from "@/components/ui/badge";
import type { NomesDisciplinas } from "@/features/revisao/classificacaoUtils";
import { ResumoClassificacao } from "@/features/revisao/ResumoClassificacao";

function formatarData(valor: string | null | undefined): string {
  if (!valor) {
    return "";
  }
  const data = new Date(valor);
  return Number.isNaN(data.getTime()) ? "" : data.toLocaleString("pt-BR");
}

function rotuloEntrada(classificacao: ClassificacaoResponse): string {
  return classificacao.origem === "automatica" ? "Predição da IA" : "Revisão humana";
}

export interface OutrasTaxonomiasHistoricoProps {
  outrasTaxonomias: DetalheQuestaoResponse["outras_taxonomias"];
  historico: DetalheQuestaoResponse["historico"];
  nomes: NomesDisciplinas;
}

export function OutrasTaxonomiasHistorico({ outrasTaxonomias, historico, nomes }: OutrasTaxonomiasHistoricoProps) {
  const [aberto, setAberto] = useState(false);
  const rotulo = `Outras taxonomias (${outrasTaxonomias.length}) e histórico`;
  return (
    <section className="overflow-hidden rounded-md border border-border bg-surface/35">
      <h3>
        <button
          type="button"
          className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-xs font-semibold text-foreground transition-colors hover:bg-surface/70"
          aria-expanded={aberto}
          onClick={() => setAberto(!aberto)}
        >
          {aberto ? <ChevronDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
          {rotulo}
        </button>
      </h3>
      {aberto ? (
        <div className="space-y-4 border-t border-border bg-card p-3.5">
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Outras Taxonomias</h4>
            {outrasTaxonomias.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma Classificação em outras Taxonomias.</p>
            ) : (
              <ul className="space-y-3">
                {outrasTaxonomias.map((item) => (
                  <li key={item.taxonomia_id} className="space-y-1 rounded-md border p-2">
                    <p className="text-sm font-medium">{item.taxonomia_nome}</p>
                    <ResumoClassificacao classificacao={item.classificacao} nomes={nomes} />
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Histórico (imutável)</h4>
            {historico.length === 0 ? (
              <p className="text-sm text-muted-foreground">Sem histórico nesta Taxonomia.</p>
            ) : (
              <ol className="space-y-3">
                {historico.map((item) => (
                  <li key={item.id} className="space-y-1 rounded-md border p-2" data-origem={item.origem}>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <Badge variant={item.origem === "automatica" ? "secondary" : "outline"}>{rotuloEntrada(item)}</Badge>
                      <span>{item.status === "aprovada" ? "Aprovada" : "Pendente de revisão"}</span>
                      {item.vigente ? <Badge variant="default">Vigente</Badge> : null}
                      <span className="text-muted-foreground">{formatarData(item.revisada_em ?? item.criada_em)}</span>
                    </div>
                    <ResumoClassificacao classificacao={item} nomes={nomes} />
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
