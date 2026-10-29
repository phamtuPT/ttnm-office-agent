declare module "fast-formula-parser" {
  type Pos = { sheet: string; row: number; col: number };
  type RangeRef = { sheet: string; from: { row: number; col: number }; to: { row: number; col: number } };

  export class FormulaError {
    toString(): string;
  }

  export default class FormulaParser {
    static FormulaError: typeof FormulaError;
    constructor(config: {
      onCell: (ref: Pos) => unknown;
      onRange: (ref: RangeRef) => unknown[][];
      functions?: Record<string, (...args: unknown[]) => unknown>;
    });
    parse(formula: string, position: Pos, allowReturnArray?: boolean): unknown;
  }
}
