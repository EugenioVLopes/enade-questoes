import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarkdownContent } from "@/components/markdown/MarkdownContent";

function renderMd(source: string) {
  return render(<MarkdownContent source={source} />).container;
}

describe("MarkdownContent", () => {
  it("renderiza tabela GFM", () => {
    const c = renderMd("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(c.querySelectorAll("table th")).toHaveLength(2);
    expect(c.querySelector("td")?.textContent).toBe("1");
  });

  it("renderiza bloco de código com destaque (C e Verilog)", () => {
    const c = renderMd("```c\nint main(void) { return 0; }\n```\n\n```verilog\nmodule m(input a); endmodule\n```");
    const codes = c.querySelectorAll("pre code");
    expect(codes).toHaveLength(2);
    expect(codes[0].className).toContain("hljs");
    expect(codes[0].querySelector(".hljs-keyword")).not.toBeNull();
    expect(codes[1].className).toContain("hljs");
    expect(codes[1].querySelector(".hljs-keyword")).not.toBeNull();
  });

  it("renderiza fórmula inline e em bloco com KaTeX", () => {
    const c = renderMd("Inline $x^2$ e bloco:\n\n$$\n\\frac{a}{b}\n$$");
    expect(c.querySelector(".katex")).not.toBeNull();
    expect(c.querySelector(".katex-display")).not.toBeNull();
    expect(c.querySelectorAll(".katex").length).toBeGreaterThanOrEqual(2);
  });

  it("fórmula $$...$$ em uma única linha renderiza como KaTeX (em linha, convenção do remark-math)", () => {
    const c = renderMd("$$x+y$$");
    expect(c.querySelector(".katex")).not.toBeNull();
  });

  it("não deixa script, onerror nem javascript: chegarem ao DOM", () => {
    const c = renderMd(
      [
        "<script>window.__xss = 1</script>",
        '<img src="x" onerror="window.__xss = 2">',
        "[clique](javascript:alert(1))",
        '<a href="javascript:alert(2)" onclick="alert(3)">raw</a>',
        "<b onmouseover=\"alert(4)\">negrito</b>",
      ].join("\n\n"),
    );
    expect(c.querySelector("script")).toBeNull();
    expect(c.querySelector("img")).toBeNull();
    expect(c.innerHTML).not.toMatch(/javascript:/i);
    expect(c.innerHTML).not.toMatch(/onerror|onclick|onmouseover/i);
    expect(c.querySelector("a[href^='javascript']")).toBeNull();
    expect((window as unknown as { __xss?: number }).__xss).toBeUndefined();
  });

  it("mantém links http(s) seguros", () => {
    const c = renderMd("[ok](https://example.com)");
    const a = c.querySelector("a");
    expect(a?.getAttribute("href")).toBe("https://example.com");
    expect(a?.getAttribute("rel")).toContain("noopener");
  });
});
