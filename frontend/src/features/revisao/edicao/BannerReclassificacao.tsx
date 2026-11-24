import { Loader2, RefreshCw, X } from "lucide-react";

import { Button } from "@/components/ui/button";

export interface BannerReclassificacaoProps {
  enviando: boolean;
  erro: string | null;
  criadaId: string | null;
  semPerfil: boolean;
  onReclassificar: () => void;
  onDispensar: () => void;
}

export function BannerReclassificacao({
  enviando,
  erro,
  criadaId,
  semPerfil,
  onReclassificar,
  onDispensar,
}: BannerReclassificacaoProps) {
  return (
    <section
      role="region"
      aria-label="Reclassificação sob demanda"
      className="rounded-lg border border-primary/30 bg-primary/[0.04] px-4 py-3 text-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground">
            Conteúdo ou Ativos Visuais atualizados. A Classificação não foi disparada
            automaticamente.
          </p>
          {semPerfil ? (
            <p className="mt-1.5 text-xs text-muted-foreground">
              Nenhum Perfil de Classificação disponível.
            </p>
          ) : null}
          {criadaId ? (
            <p role="status" className="mt-1.5 text-xs text-foreground">
              Reclassificação enfileirada no worker local. O novo resultado aparecerá quando a
              Execução de Classificação concluir.
            </p>
          ) : null}
          {erro ? (
            <p role="alert" className="mt-1.5 text-xs text-destructive">
              {erro}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Button
            type="button"
            size="sm"
            disabled={enviando || semPerfil}
            onClick={onReclassificar}
          >
            {enviando ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            Reclassificar esta questão
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label="Dispensar aviso de reclassificação"
            onClick={onDispensar}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </section>
  );
}
