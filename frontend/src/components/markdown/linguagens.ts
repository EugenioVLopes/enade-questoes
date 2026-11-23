import verilog from "highlight.js/lib/languages/verilog";
import vhdl from "highlight.js/lib/languages/vhdl";
import { common } from "lowlight";

// `common` do lowlight já inclui C, C++, Java e SQL; Verilog e VHDL (Enade de Computação) são registradas aqui.
export const LINGUAGENS_HIGHLIGHT = { ...common, verilog, vhdl };
