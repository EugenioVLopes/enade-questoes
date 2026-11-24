import { useSearchParams } from "react-router-dom";

import { cn } from "@/lib/utils";
import { ExecucoesTab } from "@/features/taxonomias/ExecucoesTab";
import { PerfisTab } from "@/features/taxonomias/PerfisTab";
import { TaxonomiasTab } from "@/features/taxonomias/TaxonomiasTab";

const ABAS = [
  { id: "taxonomias", rotulo: "Taxonomias" },
  { id: "perfis", rotulo: "Perfis" },
  { id: "execucoes", rotulo: "Execuções" },
] as const;

type AbaId = (typeof ABAS)[number]["id"];

export function TaxonomiasPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const param = searchParams.get("aba");
  const aba: AbaId = ABAS.some((item) => item.id === param) ? (param as AbaId) : "taxonomias";

  function selecionar(id: AbaId) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("aba", id);
        return next;
      },
      { replace: true },
    );
  }

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-[-0.025em] text-foreground">Taxonomias</h1>
        <p className="text-sm text-muted-foreground">
          Gerencie Taxonomias e Disciplinas, versione Perfis de Classificação e acompanhe
          Execuções.
        </p>
      </header>

      <div role="tablist" aria-label="Seções de Taxonomias" className="flex gap-1 border-b border-border">
        {ABAS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`aba-${item.id}`}
            aria-selected={aba === item.id}
            aria-controls="painel-taxonomias"
            onClick={() => selecionar(item.id)}
            className={cn(
              "-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              aba === item.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
            )}
          >
            {item.rotulo}
          </button>
        ))}
      </div>

      <div role="tabpanel" id="painel-taxonomias" aria-labelledby={`aba-${aba}`}>
        {aba === "taxonomias" ? <TaxonomiasTab /> : null}
        {aba === "perfis" ? <PerfisTab /> : null}
        {aba === "execucoes" ? <ExecucoesTab /> : null}
      </div>
    </section>
  );
}
