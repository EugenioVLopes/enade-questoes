import { useEffect, useRef } from "react";

interface AcoesAtalhosRevisao {
  aprovar?: () => void;
  editar?: () => void;
  anterior?: () => void;
  proxima?: () => void;
  fechar?: () => void;
  bloqueado?: boolean;
}

function alvoEhCampoDeEntrada(alvo: EventTarget | null): boolean {
  if (!(alvo instanceof HTMLElement)) {
    return false;
  }
  if (alvo.isContentEditable || alvo.getAttribute("contenteditable") === "true") {
    return true;
  }
  if (["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName)) {
    return true;
  }
  // Select/combobox do Radix e diálogos tratam as próprias teclas (typeahead, Esc).
  return alvo.closest('[role="listbox"], [role="combobox"], [role="dialog"], [role="alertdialog"]') !== null;
}

export function useAtalhosRevisao(acoes: AcoesAtalhosRevisao): void {
  const ref = useRef(acoes);
  useEffect(() => {
    ref.current = acoes;
  });

  useEffect(() => {
    function onKeyDown(evento: KeyboardEvent) {
      const atual = ref.current;
      if (atual.bloqueado || evento.defaultPrevented || evento.repeat) {
        return;
      }
      if (evento.ctrlKey || evento.metaKey || evento.altKey) {
        return;
      }
      if (alvoEhCampoDeEntrada(evento.target)) {
        return;
      }
      let acao: (() => void) | undefined;
      switch (evento.key) {
        case "a":
        case "A":
          acao = atual.aprovar;
          break;
        case "e":
        case "E":
          acao = atual.editar;
          break;
        case "ArrowLeft":
          acao = atual.anterior;
          break;
        case "ArrowRight":
          acao = atual.proxima;
          break;
        case "Escape":
          acao = atual.fechar;
          break;
      }
      if (acao) {
        evento.preventDefault();
        acao();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);
}
