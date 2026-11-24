import type { ItemQuestaoResponse } from "@/api/questoes";
import type { BadgeProps } from "@/components/ui/badge";

export interface StatusBadgeItem {
  key: string;
  label: string;
  variant: NonNullable<BadgeProps["variant"]>;
  className?: string;
}

const AMBAR = "border-amber-700/25 bg-amber-50 text-amber-900";
const VERDE = "border-emerald-700/25 bg-emerald-50 text-emerald-800";

/** Badges de status do card, na ordem: Pendente, Prioritária, Aprovada, Divergência, Anulada, Disciplina arquivada. */
export function getStatusBadges(item: ItemQuestaoResponse): StatusBadgeItem[] {
  const badges: StatusBadgeItem[] = [];
  const classificacao = item.classificacao;

  if (!classificacao || classificacao.status === "pendente_revisao") {
    badges.push({ key: "pendente", label: "Pendente", variant: "secondary", className: AMBAR });
  }
  if (item.revisao_prioritaria) {
    badges.push({ key: "prioritaria", label: "Prioritária", variant: "destructive" });
  }
  if (classificacao?.status === "aprovada") {
    badges.push({ key: "aprovada", label: "Aprovada", variant: "outline", className: VERDE });
  }
  if (item.tem_divergencia_aberta) {
    badges.push({ key: "divergencia", label: "Divergência", variant: "secondary", className: AMBAR });
  }
  if (item.situacao_gabarito === "anulada") {
    badges.push({ key: "anulada", label: "Anulada", variant: "destructive" });
  }
  if (item.usa_disciplina_arquivada) {
    badges.push({ key: "disciplina-arquivada", label: "Disciplina arquivada", variant: "outline" });
  }
  return badges;
}

export function getGabaritoLabel(situacao: ItemQuestaoResponse["situacao_gabarito"]): string {
  switch (situacao) {
    case "valida":
      return "Gabarito válido";
    case "anulada":
      return "Gabarito anulado";
    case "pendente":
      return "Gabarito pendente";
  }
}
