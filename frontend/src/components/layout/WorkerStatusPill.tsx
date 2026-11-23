import { Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useWorkerStatus } from "@/api/operacao";
import { buildSearchWithTaxonomia, useTaxonomia } from "@/components/layout/useTaxonomia";
import { Button } from "@/components/ui/button";

export function WorkerStatusPill() {
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
      className="gap-2 rounded-full border border-primary/20 bg-accent text-accent-foreground hover:bg-accent/80"
    >
      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
      <span>{workerStatus.label ?? "Worker ativo"}</span>
    </Button>
  );
}
