import type { ClassificacaoEncadeadaResponse, StatusIngestao } from "@/api/provas";
import type { BadgeProps } from "@/components/ui/badge";

export interface StatusBadgeMeta {
  label: string;
  variant: NonNullable<BadgeProps["variant"]>;
  className?: string;
  isActive?: boolean;
}

const INGESTAO_STATUS_META: Record<StatusIngestao, StatusBadgeMeta> = {
  pendente: {
    label: "Ingestão pendente",
    variant: "secondary",
    isActive: true,
  },
  processando: {
    label: "Ingestão em processamento",
    variant: "default",
    isActive: true,
  },
  concluida: {
    label: "Ingestão concluída",
    variant: "outline",
    className: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    isActive: false,
  },
  erro: {
    label: "Erro na ingestão",
    variant: "destructive",
    isActive: false,
  },
  interrompida: {
    label: "Ingestão interrompida",
    variant: "destructive",
    isActive: false,
  },
};

const SEM_INGESTAO_META: StatusBadgeMeta = {
  label: "Sem ingestão",
  variant: "outline",
  isActive: false,
};

const CLASSIFICACAO_STATUS_META: Record<string, StatusBadgeMeta> = {
  aguardando_ingestao: {
    label: "Classificação aguardando ingestão",
    variant: "secondary",
    isActive: true,
  },
  aguardando_agendamento: {
    label: "Classificação aguardando agendamento",
    variant: "secondary",
    isActive: true,
  },
  agendada: {
    label: "Classificação agendada",
    variant: "secondary",
    isActive: true,
  },
  pendente: {
    label: "Classificação pendente",
    variant: "secondary",
    isActive: true,
  },
  processando: {
    label: "Classificação em processamento",
    variant: "default",
    isActive: true,
  },
  concluida: {
    label: "Classificação concluída",
    variant: "outline",
    className: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    isActive: false,
  },
  concluida_com_erros: {
    label: "Classificação concluída com falhas",
    variant: "secondary",
    className: "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300",
    isActive: false,
  },
  interrompida: {
    label: "Classificação interrompida",
    variant: "destructive",
    isActive: false,
  },
  erro: {
    label: "Falha na Classificação",
    variant: "destructive",
    isActive: false,
  },
  nao_executada: {
    label: "Classificação não executada",
    variant: "outline",
    isActive: false,
  },
  hook_nao_configurado: {
    label: "Classificação automática indisponível",
    variant: "outline",
    isActive: false,
  },
  erro_agendamento: {
    label: "Falha ao agendar Classificação",
    variant: "destructive",
    isActive: false,
  },
};

export function getIngestaoStatusMeta(status: StatusIngestao | null | undefined): StatusBadgeMeta {
  if (!status) {
    return SEM_INGESTAO_META;
  }

  return INGESTAO_STATUS_META[status];
}

export function getClassificacaoEncadeadaBadgeMeta(
  classificacao: ClassificacaoEncadeadaResponse | null | undefined,
): StatusBadgeMeta | null {
  if (!classificacao?.solicitada) {
    return null;
  }

  const rawStatus = classificacao.status?.trim();
  if (!rawStatus) {
    return {
      label: "Classificação solicitada",
      variant: "outline",
      isActive: false,
    };
  }

  return (
    CLASSIFICACAO_STATUS_META[rawStatus] ?? {
      label: `Classificação: ${rawStatus}`,
      variant: "outline",
      isActive: false,
    }
  );
}

export function formatarDataHora(iso?: string | null): string | null {
  if (!iso) {
    return null;
  }

  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  try {
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(date);
  } catch {
    return null;
  }
}
