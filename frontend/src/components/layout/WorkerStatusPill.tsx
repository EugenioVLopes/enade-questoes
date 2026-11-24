import { Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useWorkerStatus } from "@/api/operacao";
import { buildSearchWithTaxonomia, useTaxonomia } from "@/components/layout/useTaxonomia";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface WorkerStatusPillProps {
  className?: string;
}

export function WorkerStatusPill({ className }: WorkerStatusPillProps = {}) {
  const navigate = useNavigate();
  const { activeTaxonomiaId } = useTaxonomia();
  const workerStatus = useWorkerStatus();

  if (!workerStatus.isActive) {
    return null;
  }

  const targetHref = `${workerStatus.targetRoute}${buildSearchWithTaxonomia("", activeTaxonomiaId)}`;

  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onClick={() => navigate(targetHref)}
      aria-live="polite"
      className={cn(
        "gap-2 rounded-md border border-primary/25 bg-accent/80 text-xs text-accent-foreground hover:bg-accent",
        className,
      )}
    >
      <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" />
      <span className="truncate">{workerStatus.label ?? "Worker ativo"}</span>
    </Button>
  );
}
