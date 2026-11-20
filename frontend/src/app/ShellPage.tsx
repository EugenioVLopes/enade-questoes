export function ShellPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-12">
      <div className="rounded-lg border bg-card p-8 text-card-foreground shadow-sm">
        <p className="text-sm font-medium text-muted-foreground">Fundação local v1</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Enade Questões</h1>
        <p className="mt-3 text-base text-muted-foreground">
          Ambiente inicial configurado. As seções de Questões, Revisão, Provas e Taxonomias serão
          conectadas nas próximas etapas.
        </p>
      </div>
    </main>
  );
}
