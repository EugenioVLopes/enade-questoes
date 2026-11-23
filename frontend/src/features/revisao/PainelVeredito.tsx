import { AlertTriangle } from "lucide-react";

import type { CorrigirClassificacaoRequest, DetalheQuestaoResponse, ResolverDivergenciaRequest } from "@/api/revisao";
import type { TaxonomiaResponse } from "@/api/taxonomias";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ComparadorDivergencia } from "@/features/revisao/ComparadorDivergencia";
import { FormularioClassificacao } from "@/features/revisao/FormularioClassificacao";
import { OutrasTaxonomiasHistorico } from "@/features/revisao/OutrasTaxonomiasHistorico";
import { nomeDaDisciplina, type NomesDisciplinas } from "@/features/revisao/classificacaoUtils";
import { ResumoClassificacao } from "@/features/revisao/ResumoClassificacao";

export interface PainelVereditoProps {
  questao: DetalheQuestaoResponse;
  taxonomia: TaxonomiaResponse;
  nomes: NomesDisciplinas;
  editando: boolean;
  onEditandoChange: (editando: boolean) => void;
  ocupado: boolean;
  erro: string | null;
  onAprovar: () => void;
  onCorrigir: (correcao: CorrigirClassificacaoRequest) => void;
  onResolver: (resolucao: ResolverDivergenciaRequest["resolucao"], classificacao?: CorrigirClassificacaoRequest) => void;
  onExecutarClassificacao: () => void;
  execucao: { enviando: boolean; erro: string | null; criadaId: string | null; semPerfil: boolean };
}

function ErroPainel({ erro }: { erro: string | null }) {
  return erro ? (
    <Alert variant="destructive" role="alert">
      <AlertDescription>{erro}</AlertDescription>
    </Alert>
  ) : null;
}

export function PainelVeredito({
  questao,
  taxonomia,
  nomes,
  editando,
  onEditandoChange,
  ocupado,
  erro,
  onAprovar,
  onCorrigir,
  onResolver,
  onExecutarClassificacao,
  execucao,
}: PainelVereditoProps) {
  const vigente = questao.classificacao_vigente ?? null;
  const divergencia = questao.divergencia_aberta ?? null;
  const disciplinas = taxonomia.disciplinas;
  const inicial = vigente
    ? {
        principal: vigente.disciplina_principal,
        secundarias: vigente.disciplinas_secundarias,
        topicos: vigente.topicos,
        justificativa: vigente.justificativa,
      }
    : undefined;

  const mostrarFormulario = !vigente || editando;
  const edicao = divergencia
    ? { rotulo: "Resolver com edição manual", enviar: (c: CorrigirClassificacaoRequest) => onResolver("editar_manualmente", c) }
    : { rotulo: vigente?.status === "pendente_revisao" ? "Corrigir e aprovar" : "Salvar classificação", enviar: onCorrigir };

  let corpo: JSX.Element;
  if (divergencia && vigente) {
    corpo = (
      <section className="space-y-3" aria-label="Divergência de Reclassificação">
        <h3 className="text-sm font-semibold">Divergência de Reclassificação</h3>
        <ComparadorDivergencia vigente={vigente} divergencia={divergencia} nomes={nomes} />
        {editando ? null : (
          <>
            <ErroPainel erro={erro} />
            <div className="flex flex-wrap gap-2">
              <Button type="button" disabled={ocupado} onClick={() => onResolver("manter_humana")}>
                Manter humana
              </Button>
              <Button type="button" variant="outline" disabled={ocupado} onClick={() => onResolver("aceitar_candidata")}>
                Aceitar candidata
              </Button>
              <Button type="button" variant="outline" disabled={ocupado} onClick={() => onEditandoChange(true)}>
                Editar manualmente
              </Button>
            </div>
          </>
        )}
      </section>
    );
  } else if (!vigente) {
    corpo = (
      <section className="space-y-4" aria-label="Sem classificação">
        <Alert>
          <AlertTitle>Sem classificação</AlertTitle>
          <AlertDescription>
            Esta Questão ainda não tem Classificação nesta Taxonomia. Classifique manualmente ou dispare uma Execução de
            Classificação.
          </AlertDescription>
        </Alert>
      </section>
    );
  } else if (vigente.status === "pendente_revisao") {
    corpo = (
      <section className="space-y-3" aria-label="Sugestão da IA">
        <h3 className="text-sm font-semibold">Sugestão da IA</h3>
        {vigente.revisao_prioritaria ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>Revisão prioritária</AlertTitle>
            <AlertDescription>A IA sinalizou esta Classificação para revisão prioritária.</AlertDescription>
          </Alert>
        ) : null}
        <ResumoClassificacao classificacao={vigente} nomes={nomes} />
        {editando ? null : (
          <>
            <ErroPainel erro={erro} />
            <div className="flex flex-wrap gap-2">
              <Button type="button" disabled={ocupado} onClick={onAprovar}>
                Aprovar sugestão
              </Button>
              <Button type="button" variant="outline" disabled={ocupado} onClick={() => onEditandoChange(true)}>
                Corrigir e aprovar
              </Button>
            </div>
          </>
        )}
      </section>
    );
  } else {
    corpo = (
      <section className="space-y-3" aria-label="Classificação vigente">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">Classificação vigente</h3>
          <Badge variant="outline">{vigente.origem === "humana" ? "Aprovada (humana)" : "Aprovada (IA)"}</Badge>
        </div>
        <ResumoClassificacao classificacao={vigente} nomes={nomes} />
        {editando ? null : (
          <>
            <ErroPainel erro={erro} />
            <Button type="button" variant="outline" disabled={ocupado} onClick={() => onEditandoChange(true)}>
              Editar classificação
            </Button>
          </>
        )}
      </section>
    );
  }

  return (
    <div className="space-y-4">
      {questao.disciplinas_arquivadas_em_uso.length > 0 ? (
        <Alert>
          <AlertTitle>Disciplina arquivada em uso</AlertTitle>
          <AlertDescription>
            {questao.disciplinas_arquivadas_em_uso.map((codigo) => nomeDaDisciplina(nomes, codigo)).join(", ")}
          </AlertDescription>
        </Alert>
      ) : null}
      {corpo}
      {mostrarFormulario ? (
        <FormularioClassificacao
          key={`formulario-${taxonomia.id}`}
          disciplinas={disciplinas}
          inicial={inicial}
          rotuloEnvio={edicao.rotulo}
          enviando={ocupado}
          erro={erro}
          onEnviar={edicao.enviar}
          onCancelar={vigente ? () => onEditandoChange(false) : undefined}
          onAlterar={!vigente ? () => onEditandoChange(true) : undefined}
        />
      ) : null}
      {!vigente ? (
        <div className="space-y-2 border-t pt-3">
          <Button
            type="button"
            variant="outline"
            disabled={execucao.enviando || execucao.semPerfil}
            onClick={onExecutarClassificacao}
          >
            Classificar com IA (Execução individual)
          </Button>
          {execucao.semPerfil ? (
            <p className="text-xs text-muted-foreground">Nenhum Perfil de classificação disponível.</p>
          ) : null}
          {execucao.criadaId ? (
            <p className="text-xs text-muted-foreground" role="status">
              Execução de Classificação enfileirada. A sugestão aparece nesta Questão quando for concluída.
            </p>
          ) : null}
          <ErroPainel erro={execucao.erro} />
        </div>
      ) : null}
      <OutrasTaxonomiasHistorico
        outrasTaxonomias={questao.outras_taxonomias}
        historico={questao.historico}
        nomes={nomes}
      />
    </div>
  );
}
