import { Link } from "react-router-dom";

import { useProvasQuery } from "@/api/provas";
import { buildIngerirHref, useTaxonomia } from "@/components/layout/useTaxonomia";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export type AppSectionKey = "questoes" | "revisao" | "provas" | "taxonomias";

interface SectionCopy {
  title: string;
  description: string;
}

const SECTION_COPY: Record<AppSectionKey, SectionCopy> = {
  questoes: {
    title: "Questões",
    description:
      "Consulta textual, filtros por Disciplina, edição e recorte de Questões sob a Taxonomia ativa.",
  },
  revisao: {
    title: "Revisão",
    description:
      "Fila de curadoria sequencial para Classificações pendentes, Divergências de Reclassificação e Disciplinas arquivadas.",
  },
  provas: {
    title: "Provas",
    description:
      "Listagem de Provas, nova Ingestão de Provas, atualização independente de Gabarito e reprocessamento.",
  },
  taxonomias: {
    title: "Taxonomias",
    description:
      "Gestão de Taxonomias, Disciplinas, Perfis de Classificação e Execuções de Classificação.",
  },
};

export interface PlaceholderSectionPageProps {
  section: AppSectionKey;
}

export function PlaceholderSectionPage({ section }: PlaceholderSectionPageProps) {
  const { activeTaxonomiaId, activeTaxonomia } = useTaxonomia();
  const provasQuery = useProvasQuery();

  const copy = SECTION_COPY[section];
  const showEmptyCta =
    (section === "questoes" || section === "revisao" || section === "provas") &&
    !provasQuery.isLoading &&
    !provasQuery.isError &&
    (provasQuery.data?.total ?? 0) === 0;

  return (
    <section className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{copy.title}</h1>
        <p className="text-sm text-muted-foreground">{copy.description}</p>
        {activeTaxonomia ? (
          <p className="text-xs text-muted-foreground">
            Taxonomia ativa: <span className="font-medium text-foreground">{activeTaxonomia.nome}</span>
          </p>
        ) : null}
      </div>

      {showEmptyCta ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Nenhuma Prova ingerida ainda</CardTitle>
            <CardDescription>
              Comece realizando a primeira Ingestão de uma Prova e, opcionalmente, de seu Gabarito.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link to={buildIngerirHref(activeTaxonomiaId)}>Ingerir primeira prova</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Seção em preparação</CardTitle>
            <CardDescription>
              Os fluxos detalhados de {copy.title} serão conectados nas próximas etapas mantendo a
              Taxonomia ativa selecionada.
            </CardDescription>
          </CardHeader>
        </Card>
      )}
    </section>
  );
}
