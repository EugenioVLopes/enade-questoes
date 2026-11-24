import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown, { type Components, type Options } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { cn } from "@/lib/utils";
import { LINGUAGENS_HIGHLIGHT } from "@/components/markdown/linguagens";

type Schema = NonNullable<Parameters<typeof rehypeSanitize>[0]>;
type Atributos = NonNullable<Schema["attributes"]>;

// O remark-math marca as fórmulas com classes (`language-math math-inline|math-display`) que o rehype-katex lê.
// A sanitização roda ANTES do KaTeX/highlight: o HTML vindo do usuário é filtrado (sem rehype-raw, HTML bruto
// nem chega a virar elemento) e só então o KaTeX e o highlight geram marcação confiável.
const CLASSES_MATEMATICA = ["language-math", "math-inline", "math-display"];

function atributosSemClassName(atributos: Atributos, tag: string) {
  return (atributos[tag] ?? []).filter((item) => !(Array.isArray(item) && item[0] === "className"));
}

const SANITIZE_SCHEMA: Schema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [
      ...atributosSemClassName(defaultSchema.attributes ?? {}, "code"),
      ["className", /^language-./, ...CLASSES_MATEMATICA],
    ],
    span: [
      ...atributosSemClassName(defaultSchema.attributes ?? {}, "span"),
      ["className", "math-inline"],
    ],
    div: [
      ...atributosSemClassName(defaultSchema.attributes ?? {}, "div"),
      ["className", "math-display"],
    ],
  },
};

const REMARK_PLUGINS: NonNullable<Options["remarkPlugins"]> = [remarkGfm, remarkMath];
const REHYPE_PLUGINS: NonNullable<Options["rehypePlugins"]> = [
  [rehypeSanitize, SANITIZE_SCHEMA],
  rehypeKatex,
  [rehypeHighlight, { languages: LINGUAGENS_HIGHLIGHT, detect: false, plainText: ["text", "txt"] }],
];

type Props<T extends keyof JSX.IntrinsicElements> = ComponentPropsWithoutRef<T> & { node?: unknown };

// O react-markdown injeta `node` (AST) nas props; não pode ir para o DOM.
function semNode<P extends { node?: unknown }>(props: P): Omit<P, "node"> {
  const copia = { ...props };
  delete copia.node;
  return copia;
}

const COMPONENTES: Components = {
  table: (props: Props<"table">) => {
    const { className, ...resto } = semNode(props);
    return (
      <div className="my-4 overflow-x-auto rounded-md border border-border">
        <table className={cn("w-full border-collapse text-sm", className)} {...resto} />
      </div>
    );
  },
  th: (props: Props<"th">) => {
    const { className, ...resto } = semNode(props);
    return <th className={cn("border-b border-r last:border-r-0 bg-surface px-3 py-2 text-left text-xs font-semibold text-foreground", className)} {...resto} />;
  },
  td: (props: Props<"td">) => {
    const { className, ...resto } = semNode(props);
    return <td className={cn("border-b border-r last:border-r-0 px-3 py-2 align-top text-foreground", className)} {...resto} />;
  },
  pre: (props: Props<"pre">) => {
    const { className, ...resto } = semNode(props);
    return (
      <pre
        className={cn("my-4 overflow-x-auto rounded-md border border-border bg-surface/80 p-3.5 font-mono text-[13px] leading-relaxed", className)}
        {...resto}
      />
    );
  },
  code: (props: Props<"code">) => {
    const { className, ...resto } = semNode(props);
    return <code className={cn("font-mono text-[0.9em]", className)} {...resto} />;
  },
  a: (props: Props<"a">) => (
    <a className="text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary" target="_blank" rel="noopener noreferrer" {...semNode(props)} />
  ),
  ul: (props: Props<"ul">) => {
    const { className, ...resto } = semNode(props);
    return <ul className={cn("my-2.5 list-disc space-y-1.5 pl-6", className)} {...resto} />;
  },
  ol: (props: Props<"ol">) => {
    const { className, ...resto } = semNode(props);
    return <ol className={cn("my-2.5 list-decimal space-y-1.5 pl-6", className)} {...resto} />;
  },
  p: (props: Props<"p">) => {
    const { className, ...resto } = semNode(props);
    return <p className={cn("my-2.5 leading-[1.7] first:mt-0 last:mb-0", className)} {...resto} />;
  },
  blockquote: (props: Props<"blockquote">) => {
    const { className, ...resto } = semNode(props);
    return <blockquote className={cn("my-3 border-l-2 border-primary/50 bg-surface/50 py-1.5 pl-3.5 pr-3 text-muted-foreground", className)} {...resto} />;
  },
};

export interface MarkdownContentProps {
  source: string;
  className?: string;
}

export function MarkdownContent({ source, className }: MarkdownContentProps) {
  return (
    <div className={cn("markdown-content break-words text-[15px] leading-[1.7] text-foreground", className)}>
      <ReactMarkdown remarkPlugins={REMARK_PLUGINS} rehypePlugins={REHYPE_PLUGINS} components={COMPONENTES}>
        {source}
      </ReactMarkdown>
    </div>
  );
}
