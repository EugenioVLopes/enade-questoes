import { useState } from "react";

import type { AtivoVisualResponse } from "@/api/revisao";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

export interface GaleriaAtivosProps {
  ativos: readonly AtivoVisualResponse[];
  rotulo: string;
  onAbertoChange?: (aberto: boolean) => void;
}

export function GaleriaAtivos({ ativos, rotulo, onAbertoChange }: GaleriaAtivosProps) {
  const [aberto, setAberto] = useState<AtivoVisualResponse | null>(null);

  if (ativos.length === 0) {
    return null;
  }

  function alterar(valor: AtivoVisualResponse | null) {
    setAberto(valor);
    onAbertoChange?.(valor !== null);
  }

  return (
    <>
      <ul className="flex flex-wrap gap-3" aria-label={rotulo}>
        {ativos.map((ativo, indice) => (
          <li key={ativo.id}>
            <button
              type="button"
              className="group block overflow-hidden rounded-md border border-border bg-white p-2 transition-all duration-150 hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Ampliar ${rotulo.toLowerCase()} ${indice + 1}`}
              onClick={() => alterar(ativo)}
            >
              <img
                src={ativo.url_arquivo}
                alt={`${rotulo} ${indice + 1}`}
                className="max-h-60 max-w-full object-contain transition-transform duration-200 group-hover:scale-[1.02] sm:max-w-sm"
              />
            </button>
          </li>
        ))}
      </ul>
      <Dialog open={aberto !== null} onOpenChange={(open) => !open && alterar(null)}>
        <DialogContent className="max-w-4xl">
          <DialogTitle>{rotulo}</DialogTitle>
          <DialogDescription className="sr-only">Imagem ampliada. Pressione Esc para fechar.</DialogDescription>
          {aberto ? (
            <img src={aberto.url_arquivo} alt={`${rotulo} ampliado`} className="max-h-[75vh] w-full object-contain" />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
