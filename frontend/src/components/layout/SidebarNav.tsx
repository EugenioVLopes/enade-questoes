import { ClipboardCheck, FileQuestion, FileText, Tags, type LucideIcon } from "lucide-react";
import { NavLink } from "react-router-dom";

import { useRevisaoContadoresQuery } from "@/api/revisao";
import { buildSearchWithTaxonomia, useTaxonomia } from "@/components/layout/useTaxonomia";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  badgeCount?: number;
}

export interface SidebarNavProps {
  onNavigate?: () => void;
}

export function SidebarNav({ onNavigate }: SidebarNavProps) {
  const { activeTaxonomiaId } = useTaxonomia();
  const contadoresQuery = useRevisaoContadoresQuery(activeTaxonomiaId);

  const revisaoBadgeCount = contadoresQuery.data?.totalBadge ?? 0;

  const items: NavItem[] = [
    { label: "Questões", path: "/questoes", icon: FileQuestion },
    {
      label: "Revisão",
      path: "/revisao",
      icon: ClipboardCheck,
      badgeCount: revisaoBadgeCount,
    },
    { label: "Provas", path: "/provas", icon: FileText },
    { label: "Taxonomias", path: "/taxonomias", icon: Tags },
  ];

  const search = buildSearchWithTaxonomia("", activeTaxonomiaId);

  return (
    <nav aria-label="Seções principais" className="flex flex-col gap-1">
      {items.map((item) => {
        const Icon = item.icon;
        const to = `${item.path}${search}`;

        return (
          <NavLink
            key={item.path}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center justify-between rounded-md border px-3 py-2 text-sm transition-colors",
                isActive
                  ? "border-border bg-card font-medium text-primary shadow-[inset_2.5px_0_0_0_oklch(var(--primary))]"
                  : "border-transparent text-muted-foreground hover:bg-card/70 hover:text-foreground",
              )
            }
          >
            <span className="flex items-center gap-2.5">
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{item.label}</span>
            </span>
            {item.badgeCount !== undefined && item.badgeCount > 0 ? (
              <Badge
                variant="secondary"
                className="font-mono text-[11px] font-medium"
                aria-label={`${item.badgeCount} pendências para revisão`}
              >
                {item.badgeCount}
              </Badge>
            ) : null}
          </NavLink>
        );
      })}
    </nav>
  );
}
