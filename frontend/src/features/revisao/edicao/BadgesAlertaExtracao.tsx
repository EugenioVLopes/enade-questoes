import { AlertTriangle, CheckCircle2, Info, Loader2 } from "lucide-react";

import type { AlertaExtracaoResponse } from "@/api/revisao";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ROTULOS_ALERTA, ehAlertaInspecao } from "@/features/revisao/edicao/editorUtils";

export interface BadgesAlertaExtracaoProps {
  alertas: readonly AlertaExtracaoResponse[];
  onVerificarAlerta?: (alertaId: string) => void;
  verificandoAlertaId?: string | null;
  erroAlerta?: string | null;
}

export function BadgesAlertaExtracao({
  alertas,
  onVerificarAlerta,
  verificandoAlertaId,
  erroAlerta,
}: BadgesAlertaExtracaoProps) {
  const abertos = alertas.filter((alerta) => alerta.status === "aberto");
  if (abertos.length === 0 && !erroAlerta) {
    return null;
  }

  return (
    <div className="space-y-2">
      {abertos.length > 0 ? (
        <ul className="flex flex-wrap items-center gap-2" aria-label="Alertas de Extração">
          {abertos.map((alerta) => {
            const critico = alerta.severidade === "critico";
            const rotulo = ROTULOS_ALERTA[alerta.codigo] ?? alerta.codigo;
            const verificando = verificandoAlertaId === alerta.id;

            return (
              <li key={alerta.id} className="flex flex-wrap items-center gap-1.5">
                <Badge
                  variant={critico ? "destructive" : "outline"}
                  className="gap-1"
                  title={alerta.mensagem}
                  data-severidade={alerta.severidade}
                >
                  {critico ? (
                    <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                  ) : (
                    <Info className="h-3 w-3" aria-hidden="true" />
                  )}
                  <span className="sr-only">
                    {critico ? "Alerta crítico: " : "Alerta informativo: "}
                  </span>
                  {rotulo}
                </Badge>
                {ehAlertaInspecao(alerta.codigo) && onVerificarAlerta ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    disabled={verificando}
                    onClick={() => onVerificarAlerta(alerta.id)}
                  >
                    {verificando ? (
                      <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                    ) : (
                      <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                    )}
                    Marcar como verificado
                    <span className="sr-only"> ({rotulo})</span>
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {erroAlerta ? (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{erroAlerta}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
