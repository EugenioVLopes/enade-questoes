import { useState } from "react";
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

export function AppShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { activeTaxonomiaId } = useTaxonomia();
  const homeHref = `/provas${buildSearchWithTaxonomia("", activeTaxonomiaId)}`;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b bg-card px-4 lg:px-6">
        <div className="flex items-center gap-3">
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="md:hidden"
                aria-label="Abrir navegação"
              >
                <Menu className="h-5 w-5" aria-hidden="true" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-4">
              <SheetHeader className="mb-4 text-left">
                <SheetTitle>Enade Questões</SheetTitle>
                <SheetDescription className="sr-only">
                  Navegação entre as seções principais
                </SheetDescription>
              </SheetHeader>
              <SidebarNav onNavigate={() => setMobileNavOpen(false)} />
            </SheetContent>
          </Sheet>

          <Link
            to={homeHref}
            className="text-lg font-semibold tracking-tight text-foreground hover:opacity-90"
          >
            Enade Questões
          </Link>
        </div>

        <div className="flex items-center gap-3">
          <WorkerStatusPill />
          <TaxonomiaSelector />
        </div>
      </header>

      <div className="flex min-h-[calc(100vh-4rem)]">
        <aside
          aria-label="Navegação principal"
          className="hidden border-r bg-card px-3 py-4 md:flex md:w-64 md:flex-col"
        >
          <SidebarNav />
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
