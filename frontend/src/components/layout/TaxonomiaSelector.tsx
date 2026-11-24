import { useTaxonomia } from "@/components/layout/useTaxonomia";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

export function TaxonomiaSelector() {
  const { taxonomias, activeTaxonomiaId, setActiveTaxonomiaId, isLoading, error } =
    useTaxonomia();

  if (isLoading) {
    return (
      <div className="space-y-1.5">
        <span className="block text-xs font-medium text-muted-foreground">Taxonomia</span>
        <Skeleton className="h-9 w-full" aria-label="Carregando taxonomias" />
      </div>
    );
  }

  if (error && taxonomias.length === 0) {
    return (
      <div className="space-y-1">
        <span className="block text-xs font-medium text-muted-foreground">Taxonomia</span>
        <span className="block text-xs text-muted-foreground" role="status">
          Taxonomia indisponível
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <Label
        htmlFor="global-taxonomia-select"
        className="block text-xs font-medium text-muted-foreground"
      >
        Taxonomia
      </Label>
      <Select
        value={activeTaxonomiaId ?? ""}
        onValueChange={setActiveTaxonomiaId}
        disabled={taxonomias.length === 0}
      >
        <SelectTrigger
          id="global-taxonomia-select"
          aria-label="Taxonomia ativa"
          className="h-auto min-h-9 w-full bg-card py-2 text-left text-[13px] font-medium leading-snug [&>span]:line-clamp-none [&>span]:whitespace-normal"
        >
          <SelectValue placeholder="Selecione uma Taxonomia" />
        </SelectTrigger>
        <SelectContent className="max-w-[var(--radix-select-trigger-width)]">
          {taxonomias.map((taxonomia) => (
            <SelectItem
              key={taxonomia.id}
              value={taxonomia.id}
              className="whitespace-normal py-2 leading-snug"
            >
              {taxonomia.nome}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
