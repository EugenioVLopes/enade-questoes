import { ImageIcon, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";

import type { ItemQuestaoResponse } from "@/api/questoes";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { getGabaritoLabel, getStatusBadges } from "@/features/questoes/questoesStatus";

export interface QuestaoCardProps {
  item: ItemQuestaoResponse;
  /** null enquanto o dado exibido pertence a outro recorte (sem navegação). */
  href: string | null;
  nomesDisciplinas: ReadonlyMap<string, string>;
}

export function QuestaoCard({ item, href, nomesDisciplinas }: QuestaoCardProps) {
  const classificacao = item.classificacao;
  const nomeDisciplina = (codigo: string) => nomesDisciplinas.get(codigo) ?? codigo;
  const alertas = item.alertas_abertos.length;

  const classeContainer = "block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const conteudo = (
    <>
      <Card className="transition-colors hover:bg-accent/40">
        <CardContent className="space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium">
              {item.prova.exame} · {item.prova.curso} · {item.prova.ano}
              <span className="ml-2 text-muted-foreground">Questão Nº {item.numero}</span>
            </p>
            <div className="flex items-center gap-2 text-muted-foreground">
              {item.possui_ativos_visuais ? (
                <ImageIcon className="h-4 w-4" role="img" aria-label="Possui ativo visual" />
              ) : null}
              {alertas > 0 ? (
                <TriangleAlert
                  className="h-4 w-4 text-amber-600"
                  role="img"
                  aria-label={`${alertas} alerta(s) de extração aberto(s)`}
                />
              ) : null}
            </div>
          </div>

          <p className="line-clamp-2 overflow-hidden whitespace-normal break-words text-sm text-muted-foreground">
            {item.trecho}
          </p>

          <div className="flex flex-wrap items-center gap-1.5">
            {getStatusBadges(item).map((badge) => (
              <Badge key={badge.key} variant={badge.variant} className={badge.className}>
                {badge.label}
              </Badge>
            ))}
            <span className="text-xs text-muted-foreground">{getGabaritoLabel(item.situacao_gabarito)}</span>
          </div>

          {classificacao ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="default">{nomeDisciplina(classificacao.disciplina_principal)}</Badge>
              {classificacao.disciplinas_secundarias.map((codigo) => (
                <Badge key={`sec-${codigo}`} variant="outline">
                  {nomeDisciplina(codigo)}
                </Badge>
              ))}
              {classificacao.topicos.map((topico) => (
                <Badge key={`top-${topico}`} variant="secondary">
                  {topico}
                </Badge>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </>
  );

  return href === null ? (
    <div className={`${classeContainer} opacity-70`} aria-disabled="true">
      {conteudo}
    </div>
  ) : (
    <Link to={href} className={classeContainer}>
      {conteudo}
    </Link>
  );
}
