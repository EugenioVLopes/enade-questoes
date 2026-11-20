import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "@/app/App";

describe("App", () => {
  it("renderiza o shell inicial do Enade Questões", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /Enade Questões/i })).toBeInTheDocument();
    expect(screen.getByText(/Ambiente inicial configurado/i)).toBeInTheDocument();
  });
});
