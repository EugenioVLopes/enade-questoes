import { useEffect, useState } from "react";
import { SlidersHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  contarMaisFiltrosAtivos,
  type FiltrosPatch,
  type FiltrosQuestoes,
  type FlagKey,
  type SituacaoGabaritoFiltro,
} from "@/features/questoes/filtrosUrl";

const TODAS = "__todas__";

const FLAGS: { key: FlagKey; label: string }[] = [
  { key: "com_alerta_extracao", label: "Com alerta de extração" },
  { key: "revisao_prioritaria", label: "Revisão prioritária" },
  { key: "com_divergencia", label: "Com divergência" },
  { key: "usa_disciplina_arquivada", label: "Usa disciplina arquivada" },
];

const SITUACOES: { value: SituacaoGabaritoFiltro; label: string }[] = [
  { value: "valida", label: "Válida" },
  { value: "anulada", label: "Anulada" },
  { value: "pendente", label: "Pendente" },
];

export interface MaisFiltrosPopoverProps {
  filtros: FiltrosQuestoes;
  onChange: (patch: FiltrosPatch) => void;
}

export function MaisFiltrosPopover({ filtros, onChange }: MaisFiltrosPopoverProps) {
  const [topico, setTopico] = useState(filtros.topico ?? "");
  const ativos = contarMaisFiltrosAtivos(filtros);

  useEffect(() => {
    setTopico(filtros.topico ?? "");
  }, [filtros.topico]);

  function aplicarTopico() {
    const valor = topico.trim();
    if (valor !== (filtros.topico ?? "")) {
      onChange({ topico: valor || undefined });
    }
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline">
          <SlidersHorizontal className="mr-2 h-4 w-4" aria-hidden="true" />
          {ativos > 0 ? `Mais filtros (${ativos})` : "Mais filtros"}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="filtro-topico">Tópico</Label>
          <Input
            id="filtro-topico"
            value={topico}
            onChange={(event) => setTopico(event.target.value)}
            onBlur={aplicarTopico}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                aplicarTopico();
              }
            }}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filtro-situacao-gabarito">Situação do gabarito</Label>
          <Select
            value={filtros.situacao_gabarito ?? TODAS}
            onValueChange={(value) =>
              onChange({ situacao_gabarito: value === TODAS ? undefined : (value as SituacaoGabaritoFiltro) })
            }
          >
            <SelectTrigger id="filtro-situacao-gabarito">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TODAS}>Todas</SelectItem>
              {SITUACOES.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          {FLAGS.map((flag) => (
            <div key={flag.key} className="flex items-center gap-2">
              <Checkbox
                id={`filtro-${flag.key}`}
                checked={filtros[flag.key]}
                onCheckedChange={(checked) => onChange({ [flag.key]: checked === true })}
              />
              <Label htmlFor={`filtro-${flag.key}`}>{flag.label}</Label>
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
