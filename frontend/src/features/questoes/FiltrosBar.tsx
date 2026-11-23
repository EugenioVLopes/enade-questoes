import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";

import type { ProvaDetalheResponse } from "@/api/provas";
import type { DisciplinaResponse } from "@/api/taxonomias";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  STATUS_REVISAO_VALUES,
  type FiltrosPatch,
  type FiltrosQuestoes,
  type StatusRevisaoFiltro,
} from "@/features/questoes/filtrosUrl";
import { MaisFiltrosPopover } from "@/features/questoes/MaisFiltrosPopover";

const TODAS = "__todas__";
const BUSCA_DEBOUNCE_MS = 300;

const STATUS_LABELS: Record<StatusRevisaoFiltro, string> = {
  sem_classificacao: "Sem classificação",
  pendente: "Pendente (inclui sem classificação)",
  pendente_revisao: "Pendente de revisão",
  aprovada: "Aprovada",
};

export interface FiltrosBarProps {
  filtros: FiltrosQuestoes;
  disciplinas: DisciplinaResponse[];
  provas: ProvaDetalheResponse[];
  onChange: (patch: FiltrosPatch) => void;
}

export function FiltrosBar({ filtros, disciplinas, provas, onChange }: FiltrosBarProps) {
  const [busca, setBusca] = useState(filtros.q ?? "");
  const ultimoQEnviado = useRef<string | undefined>(filtros.q);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (filtros.q !== ultimoQEnviado.current) {
      ultimoQEnviado.current = filtros.q;
      setBusca(filtros.q ?? "");
    }
  }, [filtros.q]);

  useEffect(() => {
    const valor = busca.trim() || undefined;
    if (valor === ultimoQEnviado.current) {
      return;
    }
    const timer = setTimeout(() => {
      ultimoQEnviado.current = valor;
      onChangeRef.current({ q: valor });
    }, BUSCA_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [busca]);

  const anos = Array.from(new Set(provas.map((prova) => prova.ano))).sort((a, b) => b - a);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative min-w-[16rem] flex-1 space-y-1.5">
          <Label htmlFor="filtro-busca">Busca textual</Label>
          <Search
            className="pointer-events-none absolute bottom-3 left-3 h-4 w-4 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            id="filtro-busca"
            className="pl-9"
            placeholder="Buscar no enunciado, alternativas e tópicos"
            value={busca}
            onChange={(event) => setBusca(event.target.value)}
          />
        </div>
        <MaisFiltrosPopover filtros={filtros} onChange={onChange} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1.5">
          <Label htmlFor="filtro-disciplina">Disciplina</Label>
          <Select
            value={filtros.disciplina_id ?? TODAS}
            onValueChange={(value) => onChange({ disciplina_id: value === TODAS ? undefined : value })}
          >
            <SelectTrigger id="filtro-disciplina">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TODAS}>Todas</SelectItem>
              {disciplinas.map((disciplina) => (
                <SelectItem key={disciplina.id} value={disciplina.id}>
                  {disciplina.nome} ({disciplina.codigo}){disciplina.ativa ? "" : " (arquivada)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-2 pt-1">
            <Checkbox
              id="filtro-somente-principal"
              checked={filtros.somentePrincipal}
              disabled={!filtros.disciplina_id}
              onCheckedChange={(checked) => onChange({ somentePrincipal: checked === true })}
            />
            <Label htmlFor="filtro-somente-principal">Somente principal</Label>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filtro-prova">Prova</Label>
          <Select
            value={filtros.prova_id ?? TODAS}
            onValueChange={(value) => onChange({ prova_id: value === TODAS ? undefined : value })}
          >
            <SelectTrigger id="filtro-prova">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TODAS}>Todas</SelectItem>
              {provas.map((prova) => (
                <SelectItem key={prova.id} value={prova.id}>
                  {prova.exame} {prova.curso} {prova.ano}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filtro-ano">Ano</Label>
          <Select
            value={filtros.ano === undefined ? TODAS : String(filtros.ano)}
            onValueChange={(value) => onChange({ ano: value === TODAS ? undefined : Number(value) })}
          >
            <SelectTrigger id="filtro-ano">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TODAS}>Todos</SelectItem>
              {anos.map((ano) => (
                <SelectItem key={ano} value={String(ano)}>
                  {ano}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filtro-status-revisao">Status de revisão</Label>
          <Select
            value={filtros.status_revisao ?? TODAS}
            onValueChange={(value) =>
              onChange({ status_revisao: value === TODAS ? undefined : (value as StatusRevisaoFiltro) })
            }
          >
            <SelectTrigger id="filtro-status-revisao">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TODAS}>Todos</SelectItem>
              {STATUS_REVISAO_VALUES.map((value) => (
                <SelectItem key={value} value={value}>
                  {STATUS_LABELS[value]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
