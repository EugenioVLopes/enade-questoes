import type { ListarQuestoesParams } from "@/api/questoes";
import type { components } from "@/api/schema";
import {
  REVISAO_MODO_PARAM,
  REVISAO_MODO_RECORTE,
  TAXONOMIA_SEARCH_PARAM,
} from "@/components/layout/useTaxonomia";

type StatusRevisaoApi = components["schemas"]["StatusRevisao"];
type SituacaoGabaritoApi = components["schemas"]["SituacaoGabarito"];

export const STATUS_REVISAO_VALUES = [
  "sem_classificacao",
  "pendente_revisao",
  "aprovada",
  "pendente",
] as const satisfies readonly StatusRevisaoApi[];
export const SITUACAO_GABARITO_VALUES = [
  "valida",
  "anulada",
  "pendente",
] as const satisfies readonly SituacaoGabaritoApi[];

// Exaustividade: um valor novo no enum do backend (schema.d.ts) quebra o type-check até entrar nos arrays.
type ValoresFaltantes = Exclude<StatusRevisaoApi, (typeof STATUS_REVISAO_VALUES)[number]> |
  Exclude<SituacaoGabaritoApi, (typeof SITUACAO_GABARITO_VALUES)[number]>;
export type EnumsDoSchemaCobertos = [ValoresFaltantes] extends [never] ? true : { faltando: ValoresFaltantes };
const _enumsCobertos: EnumsDoSchemaCobertos = true;
void _enumsCobertos;

export const FLAG_KEYS = [
  "com_alerta_extracao",
  "revisao_prioritaria",
  "com_divergencia",
  "usa_disciplina_arquivada",
] as const;

export type StatusRevisaoFiltro = (typeof STATUS_REVISAO_VALUES)[number];
export type SituacaoGabaritoFiltro = (typeof SITUACAO_GABARITO_VALUES)[number];
export type FlagKey = (typeof FLAG_KEYS)[number];

export interface FiltrosQuestoes {
  q?: string;
  disciplina_id?: string;
  somentePrincipal: boolean;
  prova_id?: string;
  ano?: number;
  status_revisao?: StatusRevisaoFiltro;
  topico?: string;
  situacao_gabarito?: SituacaoGabaritoFiltro;
  com_alerta_extracao: boolean;
  revisao_prioritaria: boolean;
  com_divergencia: boolean;
  usa_disciplina_arquivada: boolean;
  pagina: number;
}

export type FiltrosPatch = Partial<Omit<FiltrosQuestoes, "pagina">> & { pagina?: number };

export const TAMANHO_PAGINA = 20;

const ANO_MIN = 1900;
const ANO_MAX = 2100;
const PAGINA_MAXIMA = 100000; // limite do backend (PAGINA_MAXIMA em v1/questoes.py)
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function texto(search: URLSearchParams, key: string): string | undefined {
  const value = search.get(key)?.trim();
  return value ? value : undefined;
}

function uuid(search: URLSearchParams, key: string): string | undefined {
  const value = texto(search, key);
  return value && UUID_RE.test(value) ? value : undefined;
}

function oneOf<T extends string>(value: string | undefined, allowed: readonly T[]): T | undefined {
  return allowed.find((item) => item === value);
}

export function parseFiltros(search: URLSearchParams): FiltrosQuestoes {
  const anoRaw = texto(search, "ano");
  const anoNumero = anoRaw && /^\d+$/.test(anoRaw) ? Number(anoRaw) : undefined;
  const ano = anoNumero !== undefined && anoNumero >= ANO_MIN && anoNumero <= ANO_MAX ? anoNumero : undefined;
  const disciplinaId = uuid(search, "disciplina_id");
  const paginaRaw = texto(search, "pagina");
  const pagina = paginaRaw && /^\d+$/.test(paginaRaw) && Number(paginaRaw) >= 1 && Number(paginaRaw) <= PAGINA_MAXIMA
      ? Number(paginaRaw)
      : 1;

  return {
    q: texto(search, "q"),
    disciplina_id: disciplinaId,
    somentePrincipal: disciplinaId !== undefined && search.get("incluir_secundarias") === "false",
    prova_id: uuid(search, "prova_id"),
    ano,
    status_revisao: oneOf(texto(search, "status_revisao"), STATUS_REVISAO_VALUES),
    topico: texto(search, "topico"),
    situacao_gabarito: oneOf(texto(search, "situacao_gabarito"), SITUACAO_GABARITO_VALUES),
    com_alerta_extracao: search.get("com_alerta_extracao") === "true",
    revisao_prioritaria: search.get("revisao_prioritaria") === "true",
    com_divergencia: search.get("com_divergencia") === "true",
    usa_disciplina_arquivada: search.get("usa_disciplina_arquivada") === "true",
    pagina,
  };
}

export function filtrosParaApi(
  f: FiltrosQuestoes,
  taxonomiaId: string,
  tamanhoPagina: number = TAMANHO_PAGINA,
): ListarQuestoesParams {
  return {
    taxonomia_id: taxonomiaId,
    ordenacao: "consulta",
    q: f.q,
    disciplina_id: f.disciplina_id,
    incluir_secundarias: !f.somentePrincipal,
    prova_id: f.prova_id,
    ano: f.ano,
    status_revisao: f.status_revisao,
    topico: f.topico,
    situacao_gabarito: f.situacao_gabarito,
    com_alerta_extracao: f.com_alerta_extracao ? true : undefined,
    revisao_prioritaria: f.revisao_prioritaria ? true : undefined,
    com_divergencia: f.com_divergencia ? true : undefined,
    usa_disciplina_arquivada: f.usa_disciplina_arquivada ? true : undefined,
    pagina: f.pagina,
    tamanho_pagina: tamanhoPagina,
  };
}

/** Filtros do popover "Mais filtros" ativos (Tópico, Situação do gabarito e 4 flags). */
export function contarMaisFiltrosAtivos(f: FiltrosQuestoes): number {
  return (
    (f.topico ? 1 : 0) +
    (f.situacao_gabarito ? 1 : 0) +
    FLAG_KEYS.filter((key) => f[key]).length
  );
}

/** True quando há algum filtro (excluindo a página) que restringe a consulta. */
export function temFiltrosAtivos(f: FiltrosQuestoes): boolean {
  return Boolean(
    f.q ||
      f.disciplina_id ||
      f.somentePrincipal ||
      f.prova_id ||
      f.ano !== undefined ||
      f.status_revisao ||
      contarMaisFiltrosAtivos(f) > 0,
  );
}

function setOrDelete(params: URLSearchParams, key: string, value: string | undefined) {
  if (value === undefined || value === "") {
    params.delete(key);
  } else {
    params.set(key, value);
  }
}

/** Aplica alterações de filtro sobre a URL atual; qualquer mudança de filtro volta à página 1. */
export function aplicarFiltros(prev: URLSearchParams, patch: FiltrosPatch): URLSearchParams {
  const next = new URLSearchParams(prev);
  for (const [key, value] of Object.entries(patch)) {
    switch (key) {
      case "somentePrincipal":
        if (value) {
          next.set("incluir_secundarias", "false");
        } else {
          next.delete("incluir_secundarias");
        }
        break;
      case "disciplina_id":
        setOrDelete(next, key, value === undefined ? undefined : String(value));
        if (value === undefined) {
          next.delete("incluir_secundarias");
        }
        break;
      case "pagina":
        break;
      default:
        if (typeof value === "boolean") {
          if (value) {
            next.set(key, "true");
          } else {
            next.delete(key);
          }
        } else {
          setOrDelete(next, key, value === undefined ? undefined : String(value));
        }
    }
  }
  if (patch.pagina !== undefined && patch.pagina > 1) {
    next.set("pagina", String(patch.pagina));
  } else {
    next.delete("pagina");
  }
  return next;
}

/** Remove todos os filtros e a página, preservando apenas a Taxonomia ativa. */
export function limparFiltros(prev: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams();
  const taxonomia = prev.get(TAXONOMIA_SEARCH_PARAM);
  if (taxonomia) {
    next.set(TAXONOMIA_SEARCH_PARAM, taxonomia);
  }
  return next;
}

/** True quando a URL carrega filtros que dependem da Taxonomia (Disciplina, Tópico) ou a página. */
export function temFiltrosDaTaxonomia(search: URLSearchParams): boolean {
  return ["disciplina_id", "topico", "pagina"].some((key) => search.has(key));
}

/** Remove os filtros que dependem da Taxonomia (Disciplina, Somente principal, Tópico) e a página. */
export function limparFiltrosDaTaxonomia(prev: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(prev);
  next.delete("disciplina_id");
  next.delete("incluir_secundarias");
  next.delete("topico");
  next.delete("pagina");
  return next;
}

/** Href de `/revisao` com o recorte `filtros` (sem `pagina`); `questaoId` acrescenta `questao=<id>`. */
export function buildRevisaoRecorteHrefDeFiltros(
  filtros: FiltrosQuestoes,
  taxonomiaId: string | null,
  questaoId?: string,
): string {
  const params = new URLSearchParams();
  if (taxonomiaId) {
    params.set(TAXONOMIA_SEARCH_PARAM, taxonomiaId);
  }
  // Marcador explícito: distingue o recorte da Revisão do modo abas (`aba=...`), mesmo sem nenhum filtro.
  params.set(REVISAO_MODO_PARAM, REVISAO_MODO_RECORTE);
  const valores: [string, string | undefined][] = [
    ["q", filtros.q],
    ["disciplina_id", filtros.disciplina_id],
    ["incluir_secundarias", filtros.somentePrincipal ? "false" : undefined],
    ["prova_id", filtros.prova_id],
    ["ano", filtros.ano === undefined ? undefined : String(filtros.ano)],
    ["status_revisao", filtros.status_revisao],
    ["topico", filtros.topico],
    ["situacao_gabarito", filtros.situacao_gabarito],
    ...FLAG_KEYS.map((key): [string, string | undefined] => [key, filtros[key] ? "true" : undefined]),
  ];
  for (const [key, value] of valores) {
    if (value !== undefined) {
      params.set(key, value);
    }
  }
  if (questaoId) {
    params.set("questao", questaoId);
  }
  return `/revisao?${params.toString()}`;
}

/** Href de `/revisao` com o recorte da URL atual; `taxonomiaId` tem precedência sobre o param da URL. */
export function buildRevisaoRecorteHref(
  search: URLSearchParams,
  questaoId?: string,
  taxonomiaId?: string | null,
): string {
  return buildRevisaoRecorteHrefDeFiltros(
    parseFiltros(search),
    taxonomiaId ?? search.get(TAXONOMIA_SEARCH_PARAM),
    questaoId,
  );
}
