import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { Link, Outlet } from "react-router-dom";

import { SidebarNav } from "@/components/layout/SidebarNav";
import { TaxonomiaSelector } from "@/components/layout/TaxonomiaSelector";
import { buildSearchWithTaxonomia, useTaxonomia } from "@/components/layout/useTaxonomia";
import { WorkerStatusPill } from "@/components/layout/WorkerStatusPill";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

function BrandMark() {
  return (
    <span
      className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-sm bg-primary text-primary-foreground"
      aria-hidden="true"
    >
      <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none">
        <path
          d="M2.5 4h11M2.5 8h7.5M2.5 12h11"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="square"
        />
      </svg>
    </span>
  );
}

function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return false;
    }
    return window.matchMedia("(max-width: 767px)").matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mq = window.matchMedia("(max-width: 767px)");
    const onChange = (event: MediaQueryListEvent) => setIsMobile(event.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return isMobile;
}

export function AppShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const isMobile = useIsMobile();
  const { activeTaxonomiaId } = useTaxonomia();
  const homeHref = `/provas${buildSearchWithTaxonomia("", activeTaxonomiaId)}`;

  return (
    <div className="min-h-screen bg-background text-foreground md:flex">
      {isMobile ? (
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-2 border-b border-border bg-card px-4 md:hidden">
          <div className="flex min-w-0 items-center gap-2.5">
            <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
              <SheetTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="Abrir navegação"
                >
                  <Menu className="h-5 w-5" aria-hidden="true" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="flex w-72 flex-col bg-surface/95 p-4">
                <SheetHeader className="mb-4 text-left">
                  <SheetTitle className="flex items-center gap-2.5 text-base font-semibold tracking-tight">
                    <BrandMark />
                    Enade Questões
                  </SheetTitle>
                  <SheetDescription className="sr-only">
                    Navegação entre as seções principais e seleção de Taxonomia
                  </SheetDescription>
                </SheetHeader>
                <div className="mb-4 border-b border-border pb-4">
                  <TaxonomiaSelector />
                </div>
                <SidebarNav onNavigate={() => setMobileNavOpen(false)} />
              </SheetContent>
            </Sheet>

            <Link
              to={homeHref}
              className="flex min-w-0 items-center gap-2 text-sm font-semibold tracking-[-0.02em] text-foreground"
            >
              <BrandMark />
              <span className="truncate">Enade Questões</span>
            </Link>
          </div>

          <WorkerStatusPill className="max-w-[165px]" />
        </header>
      ) : (
        <aside
          aria-label="Navegação principal"
          className="hidden border-r border-border bg-surface/65 md:sticky md:top-0 md:flex md:h-screen md:w-64 md:shrink-0 md:flex-col"
        >
          <div className="flex h-14 shrink-0 items-center border-b border-border/80 px-4">
            <Link
              to={homeHref}
              className="flex min-w-0 items-center gap-2.5 text-base font-semibold tracking-[-0.02em] text-foreground transition-opacity hover:opacity-85"
            >
              <BrandMark />
              <span className="truncate">Enade Questões</span>
            </Link>
          </div>

          <div className="shrink-0 border-b border-border/80 px-3.5 py-3.5">
            <TaxonomiaSelector />
          </div>

          <div className="flex-1 overflow-y-auto px-3 py-4">
            <SidebarNav />
          </div>

          <div className="shrink-0 space-y-2.5 border-t border-border/80 px-3.5 py-3.5">
            <WorkerStatusPill className="w-full justify-start" />
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              Curadoria e classificação curricular desacoplada por Taxonomia.
            </p>
          </div>
        </aside>
      )}

      <main className="min-w-0 flex-1 overflow-y-auto px-4 py-5 sm:px-5 lg:px-6 lg:py-6">
        <div className="w-full">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
