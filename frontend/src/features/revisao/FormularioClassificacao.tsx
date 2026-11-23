import { useState, type FormEvent, type KeyboardEvent } from "react";
import { X } from "lucide-react";

import type { CorrigirClassificacaoRequest } from "@/api/revisao";
import type { DisciplinaResponse } from "@/api/taxonomias";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const MAX_SECUNDARIAS = 2;
const MAX_TOPICOS = 20;
const NENHUMA = "__nenhuma__";

interface ValoresClassificacao {
  principal: string;
  secundarias: string[];
  topicos: string[];
  justificativa: string;
}

export interface FormularioClassificacaoProps {
  disciplinas: readonly DisciplinaResponse[];
  inicial?: Partial<ValoresClassificacao>;
  rotuloEnvio: string;
  enviando: boolean;
  erro: string | null;
  onEnviar: (correcao: CorrigirClassificacaoRequest) => void;
  onCancelar?: () => void;
  onAlterar?: () => void;
}

function ehAtiva(disciplinas: readonly DisciplinaResponse[], codigo: string): boolean {
  return disciplinas.some((d) => d.ativa && d.codigo === codigo);
}

export function FormularioClassificacao({
  disciplinas,
  inicial,
  rotuloEnvio,
  enviando,
  erro,
  onEnviar,
  onCancelar,
  onAlterar,
}: FormularioClassificacaoProps) {
  const ativas = disciplinas.filter((d) => d.ativa);
  const [principal, setPrincipal] = useState(() =>
    inicial?.principal && ehAtiva(disciplinas, inicial.principal) ? inicial.principal : "",
  );
  const [secundarias, setSecundarias] = useState<string[]>(() =>
    (inicial?.secundarias ?? []).filter((codigo) => ehAtiva(disciplinas, codigo)).slice(0, MAX_SECUNDARIAS),
  );
  const [topicos, setTopicos] = useState<string[]>(() => [...(inicial?.topicos ?? [])]);
  const [novoTopico, setNovoTopico] = useState("");
  const [justificativa, setJustificativa] = useState(inicial?.justificativa ?? "");
  const [erroLocal, setErroLocal] = useState<string | null>(null);

  const principalArquivada = Boolean(inicial?.principal) && principal === "" && !ehAtiva(disciplinas, inicial?.principal ?? "");

  function definirPrincipal(codigo: string) {
    setPrincipal(codigo);
    setSecundarias((atuais) => atuais.filter((s) => s !== codigo));
    onAlterar?.();
  }

  function definirSecundaria(indice: number, valor: string) {
    setSecundarias((atuais) => {
      const proximas = [...atuais];
      if (valor === NENHUMA) {
        proximas.splice(indice, 1);
      } else {
        proximas[indice] = valor;
      }
      return proximas;
    });
    onAlterar?.();
  }

  function adicionarTopico() {
    const valor = novoTopico.trim();
    if (!valor) {
      return;
    }
    if (topicos.length >= MAX_TOPICOS) {
      setErroLocal(`No máximo ${MAX_TOPICOS} Tópicos.`);
      return;
    }
    if (!topicos.some((t) => t.toLowerCase() === valor.toLowerCase())) {
      setTopicos([...topicos, valor]);
    }
    setNovoTopico("");
    setErroLocal(null);
    onAlterar?.();
  }

  function aoTeclarTopico(evento: KeyboardEvent<HTMLInputElement>) {
    if (evento.key === "Enter") {
      evento.preventDefault();
      adicionarTopico();
    }
  }

  function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (!principal) {
      setErroLocal("Selecione a Disciplina principal.");
      return;
    }
    setErroLocal(null);
    const pendente = novoTopico.trim();
    const todosTopicos =
      pendente && !topicos.some((t) => t.toLowerCase() === pendente.toLowerCase()) ? [...topicos, pendente] : topicos;
    if (todosTopicos.length > MAX_TOPICOS) {
      setErroLocal(`No máximo ${MAX_TOPICOS} Tópicos.`);
      return;
    }
    onEnviar({
      disciplina_principal: principal,
      disciplinas_secundarias: secundarias.filter((s) => Boolean(s) && s !== principal),
      topicos: todosTopicos,
      justificativa: justificativa.trim(),
    });
  }

  const mensagem = erroLocal ?? erro;
  const disponiveisSecundaria = (indice: number) =>
    ativas.filter((d) => d.codigo !== principal && !secundarias.some((s, i) => i !== indice && s === d.codigo));

  return (
    <form className="space-y-4" onSubmit={enviar} aria-label="Formulário de classificação">
      <div className="space-y-1.5">
        <Label htmlFor="form-principal">Disciplina principal</Label>
        <Select value={principal} onValueChange={definirPrincipal}>
          <SelectTrigger id="form-principal" aria-label="Disciplina principal">
            <SelectValue placeholder="Selecione" />
          </SelectTrigger>
          <SelectContent>
            {ativas.map((d) => (
              <SelectItem key={d.codigo} value={d.codigo}>
                {d.nome}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {principalArquivada ? (
          <p className="text-xs text-muted-foreground">
            A Disciplina principal atual está arquivada; escolha uma Disciplina ativa.
          </p>
        ) : null}
      </div>

      {Array.from({ length: MAX_SECUNDARIAS }, (_, indice) => {
        const valor = secundarias[indice] ?? "";
        const habilitada = indice === 0 || Boolean(secundarias[indice - 1]);
        return (
          <div className="space-y-1.5" key={indice}>
            <Label htmlFor={`form-secundaria-${indice + 1}`}>Disciplina secundária {indice + 1} (opcional)</Label>
            <Select
              value={valor === "" ? NENHUMA : valor}
              onValueChange={(v) => definirSecundaria(indice, v)}
              disabled={!habilitada || !principal}
            >
              <SelectTrigger id={`form-secundaria-${indice + 1}`} aria-label={`Disciplina secundária ${indice + 1}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NENHUMA}>Nenhuma</SelectItem>
                {disponiveisSecundaria(indice).map((d) => (
                  <SelectItem key={d.codigo} value={d.codigo}>
                    {d.nome}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        );
      })}

      <div className="space-y-1.5">
        <Label htmlFor="form-topico">Tópicos</Label>
        <ul className="flex flex-wrap gap-1.5" aria-label="Tópicos selecionados">
          {topicos.map((topico) => (
            <li key={topico}>
              <Badge variant="secondary" className="gap-1">
                {topico}
                <button
                  type="button"
                  className="rounded-full hover:text-destructive"
                  aria-label={`Remover Tópico ${topico}`}
                  onClick={() => {
                    setTopicos(topicos.filter((t) => t !== topico));
                    onAlterar?.();
                  }}
                >
                  <X className="h-3 w-3" aria-hidden="true" />
                </button>
              </Badge>
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <Input
            id="form-topico"
            value={novoTopico}
            onChange={(e) => {
              setNovoTopico(e.target.value);
              onAlterar?.();
            }}
            onKeyDown={aoTeclarTopico}
            placeholder="Novo Tópico"
          />
          <Button type="button" variant="outline" onClick={adicionarTopico}>
            Adicionar Tópico
          </Button>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="form-justificativa">Justificativa</Label>
        <Textarea
          id="form-justificativa"
          value={justificativa}
          onChange={(e) => {
            setJustificativa(e.target.value);
            onAlterar?.();
          }}
          rows={3}
        />
      </div>

      {mensagem ? (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{mensagem}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={enviando}>
          {rotuloEnvio}
        </Button>
        {onCancelar ? (
          <Button type="button" variant="ghost" onClick={onCancelar} disabled={enviando}>
            Cancelar
          </Button>
        ) : null}
      </div>
    </form>
  );
}
