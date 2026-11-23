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
    return <Skeleton className="h-9 w-64" aria-label="Carregando taxonomias" />;
  }

  if (error && taxonomias.length === 0) {
    return (
      <span className="text-sm text-muted-foreground" role="status">
        Taxonomia indisponível
      </span>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Label
        htmlFor="global-taxonomia-select"
        className="sr-only sm:not-sr-only sm:text-xs sm:text-muted-foreground"
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
          className="h-9 w-[220px] sm:w-[280px]"
        >
          <SelectValue placeholder="Selecione uma Taxonomia" />
        </SelectTrigger>
        <SelectContent>
          {taxonomias.map((taxonomia) => (
            <SelectItem key={taxonomia.id} value={taxonomia.id}>
              {taxonomia.nome}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
