# sentrydata_compiler.py
# Compilador SentryData - Versión Completa con soporte CSV y JSON

from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional
from enum import Enum
import csv
import json
import os

# ========== ENUMERACIONES ==========

class OpCode(Enum):
    PUSH       = "PUSH"
    POP        = "POP"
    DUP        = "DUP"
    DROP       = "DROP"
    SWAP       = "SWAP"
    ADD        = "ADD"
    SUB        = "SUB"
    MUL        = "MUL"
    DIV        = "DIV"
    EQ         = "EQ"
    NEQ        = "NEQ"
    LT         = "LT"
    GT         = "GT"
    LTE        = "LTE"
    GTE        = "GTE"
    AND        = "AND"
    OR         = "OR"
    NOT        = "NOT"
    JUMP       = "JUMP"
    JUMP_FALSE = "JUMP_FALSE"
    LABEL      = "LABEL"
    PRINT      = "PRINT"
    LOAD       = "LOAD"
    SAVE       = "SAVE"
    FILTER     = "FILTER"
    DELETE     = "DELETE"
    MODIFY     = "MODIFY"
    EXTRACT    = "EXTRACT"
    COUNT      = "COUNT"
    SHOW       = "SHOW"
    HALT       = "HALT"
    # ── JSON ──
    JLOAD      = "JLOAD"
    JSAVE      = "JSAVE"
    JGET       = "JGET"
    JSET       = "JSET"
    JDEL       = "JDEL"
    JFILTER    = "JFILTER"

# ========== ESTRUCTURAS DE DATOS ==========

@dataclass
class Token:
    type: str
    value: Any
    line: int
    column: int

@dataclass
class SymbolTableEntry:
    name: str
    type: str
    value: Any
    line: int

@dataclass
class CompilerError:
    line: int
    type: str
    description: str

@dataclass
class Instruction:
    opcode: OpCode
    operand: Any = None
    line: int = 0

    def __str__(self):
        if self.operand is not None:
            return f"{self.opcode.value:<12} {self.operand}"
        return self.opcode.value

@dataclass
class DataRecord:
    data: Dict[str, Any]
    row_number: int

# ========== COMPILADOR ==========

class SentryDataCompiler:
    def __init__(self) -> None:
        self.tokens: List[Token] = []
        self.symbol_table: Dict[str, SymbolTableEntry] = {}
        self.errors: List[CompilerError] = []
        self.stack: List[Any] = []
        self.current_line: int = 1
        self.bytecode: List[Instruction] = []
        self.loaded_data: List[DataRecord] = []
        self.current_headers: List[str] = []
        self.current_file: Optional[str] = None
        self.execution_log: List[Dict] = []
        self._build_symbol_table()

    # ========== TABLA DE SÍMBOLOS ==========

    def _build_symbol_table(self) -> None:
        for kw in ["AND", "OR", "NOT"]:
            self.symbol_table[kw] = SymbolTableEntry(kw, "KEYWORD-LÓGICO", None, 0)
        for kw in ["IF", "THEN", "ELSE", "ENDIF"]:
            self.symbol_table[kw] = SymbolTableEntry(kw, "KEYWORD-CONTROL", None, 0)
        for kw in ["DUP", "DROP", "SWAP", "PRINT"]:
            self.symbol_table[kw] = SymbolTableEntry(kw, "KEYWORD-PILA", None, 0)
        for kw in ["LOAD", "SAVE", "FILTER", "DELETE", "MODIFY", "EXTRACT", "COUNT", "SHOW"]:
            self.symbol_table[kw] = SymbolTableEntry(kw, "KEYWORD-DATOS", None, 0)
        for kw in ["JLOAD", "JSAVE", "JGET", "JSET", "JDEL", "JFILTER"]:
            self.symbol_table[kw] = SymbolTableEntry(kw, "KEYWORD-JSON", None, 0)
        for op in ["+", "-", "*", "/"]:
            self.symbol_table[op] = SymbolTableEntry(op, "OP-ARITMÉTICO", None, 0)
        for op in ["==", "!=", "<", ">", "<=", ">="]:
            self.symbol_table[op] = SymbolTableEntry(op, "OP-COMPARACIÓN", None, 0)

    def _register_symbol(self, token: Token) -> None:
        key = str(token.value)
        if token.type == "STRING" and key not in self.symbol_table:
            self.symbol_table[key] = SymbolTableEntry(key, "LITERAL-CADENA", token.value, token.line)
        elif token.type == "NUMBER" and key not in self.symbol_table:
            self.symbol_table[key] = SymbolTableEntry(key, "LITERAL-NÚMERO", token.value, token.line)

    # ========== FASE 1: ANÁLISIS LÉXICO ==========

    def lexical_analysis(self, code: str) -> List[Token]:
        self.tokens = []
        lines = code.splitlines()

        for line_index, raw_line in enumerate(lines):
            self.current_line = line_index + 1
            line = raw_line.strip()

            if not line or line.startswith("//"):
                continue

            column = 0
            i = 0
            while i < len(line):
                ch = line[i]

                if ch.isspace():
                    i += 1; column += 1
                    continue

                if ch == '/' and i + 1 < len(line) and line[i+1] == '/':
                    break

                # NÚMEROS
                if ch.isdigit() or (ch == '-' and i + 1 < len(line) and line[i+1].isdigit()):
                    start_col = column
                    num = ""
                    if ch == '-':
                        num += '-'; i += 1; column += 1
                    while i < len(line) and (line[i].isdigit() or line[i] == "."):
                        num += line[i]; i += 1; column += 1
                    tok = Token("NUMBER", float(num), self.current_line, start_col)
                    self.tokens.append(tok)
                    self._register_symbol(tok)
                    continue

                # STRINGS con comillas dobles
                if ch == '"':
                    start_col = column
                    i += 1; column += 1
                    value = ""
                    while i < len(line) and line[i] != '"':
                        value += line[i]; i += 1; column += 1
                    if i < len(line) and line[i] == '"':
                        i += 1; column += 1
                        tok = Token("STRING", value, self.current_line, start_col)
                        self.tokens.append(tok)
                        self._register_symbol(tok)
                    else:
                        self.errors.append(CompilerError(
                            self.current_line, "LÉXICO", "Error 002: String sin cerrar"
                        ))
                    continue

                # IDENTIFICADORES / KEYWORDS
                if ch.isalpha() or ch == "_":
                    start_col = column
                    ident = ""
                    while i < len(line) and (line[i].isalnum() or line[i] in ("_", ".", "/")):
                        ident += line[i]; i += 1; column += 1

                    keywords = {
                        "AND", "OR", "NOT", "IF", "THEN", "ELSE", "ENDIF",
                        "DELETE", "MODIFY", "EXTRACT", "FILTER", "LOAD", "SAVE",
                        "DUP", "DROP", "SWAP", "PRINT", "COUNT", "SHOW",
                        "JLOAD", "JSAVE", "JGET", "JSET", "JDEL", "JFILTER",
                    }
                    upper = ident.upper()
                    if upper in keywords:
                        self.tokens.append(Token("KEYWORD", upper, self.current_line, start_col))
                    else:
                        tok = Token("STRING", ident, self.current_line, start_col)
                        self.tokens.append(tok)
                        self._register_symbol(tok)
                    continue

                # OPERADORES
                operators = {
                    "==": "OP_EQ",  "!=": "OP_NEQ",
                    "<=": "OP_LTE", ">=": "OP_GTE",
                    "+":  "OP_ADD", "-":  "OP_SUB",
                    "*":  "OP_MUL", "/":  "OP_DIV",
                    "<":  "OP_LT",  ">":  "OP_GT"
                }
                if i + 1 < len(line):
                    two = line[i:i+2]
                    if two in operators:
                        self.tokens.append(Token("STRING", two, self.current_line, column))
                        i += 2; column += 2
                        continue
                if ch in operators:
                    if ch in ("+", "-", "*", "/"):
                        self.tokens.append(Token(operators[ch], ch, self.current_line, column))
                    else:
                        self.tokens.append(Token("STRING", ch, self.current_line, column))
                    i += 1; column += 1
                    continue

                self.errors.append(CompilerError(
                    self.current_line, "LÉXICO",
                    f"Error 001: Carácter no reconocido: '{ch}'"
                ))
                i += 1; column += 1

        self.tokens = self._fix_operator_context(self.tokens)
        return self.tokens

    def _fix_operator_context(self, tokens: List[Token]) -> List[Token]:
        op_map = {
            ">":  "OP_GT",  "<":  "OP_LT",
            ">=": "OP_GTE", "<=": "OP_LTE",
            "==": "OP_EQ",  "!=": "OP_NEQ",
        }
        comparison_ops = set(op_map.keys())
        result = []
        for i, tok in enumerate(tokens):
            if tok.type == "STRING" and tok.value in comparison_ops:
                next_keyword = None
                for j in range(i + 1, len(tokens)):
                    if tokens[j].type == "KEYWORD":
                        next_keyword = tokens[j].value.upper()
                        break
                if next_keyword in ("FILTER", "MODIFY", "JFILTER"):
                    result.append(tok)
                else:
                    result.append(Token(op_map[tok.value], tok.value, tok.line, tok.column))
            else:
                result.append(tok)
        return result

    # ========== FASE 2: ANÁLISIS SINTÁCTICO ==========

    def syntactic_analysis(self, tokens: List[Token]) -> bool:
        has_errors = False
        depth = 0
        control_stack: List[Dict[str, Any]] = []
        binary_ops = {
            "OP_ADD", "OP_SUB", "OP_MUL", "OP_DIV",
            "OP_EQ", "OP_NEQ", "OP_LT", "OP_GT", "OP_LTE", "OP_GTE"
        }

        if not tokens:
            self.errors.append(CompilerError(0, "SINTÁCTICO", "Error 118: Expresión vacía"))
            return False

        for token in tokens:
            self.current_line = token.line
            t = token.type

            if t in ("NUMBER", "STRING"):
                depth += 1; continue

            if t in binary_ops:
                if depth < 2:
                    self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                        f"Error 101: Operador '{token.value}' requiere 2 operandos"))
                    has_errors = True
                else:
                    depth -= 1
                continue

            if t == "KEYWORD":
                kw = token.value.upper()

                if kw in ("AND", "OR"):
                    if depth < 2:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            f"Error 102: Operador lógico '{kw}' requiere 2 operandos"))
                        has_errors = True
                    else:
                        depth -= 1
                    continue

                if kw == "NOT":
                    if depth < 1:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            "Error 103: 'NOT' requiere 1 operando"))
                        has_errors = True
                    continue

                if kw == "DUP":
                    if depth < 1:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            "Error 104: DUP requiere al menos 1 elemento en la pila"))
                        has_errors = True
                    else:
                        depth += 1
                    continue

                if kw in ("DROP", "PRINT"):
                    if depth < 1:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            f"Error 105: {kw} requiere al menos 1 elemento en la pila"))
                        has_errors = True
                    else:
                        depth -= 1
                    continue

                if kw == "SWAP":
                    if depth < 2:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            "Error 106: SWAP requiere al menos 2 elementos en la pila"))
                        has_errors = True
                    continue

                if kw == "IF":
                    if depth < 1:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            "Error 107: IF requiere una condición en la pila"))
                        has_errors = True
                    else:
                        depth -= 1
                    control_stack.append({"line": token.line, "has_then": False, "has_else": False})
                    continue

                if kw == "THEN":
                    if not control_stack:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            "Error 108: THEN sin IF correspondiente"))
                        has_errors = True
                    else:
                        top = control_stack[-1]
                        if top["has_then"]:
                            self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                                "Error 109: THEN duplicado"))
                            has_errors = True
                        else:
                            top["has_then"] = True
                    continue

                if kw == "ELSE":
                    if not control_stack:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            "Error 110: ELSE sin IF correspondiente"))
                        has_errors = True
                    else:
                        top = control_stack[-1]
                        if not top["has_then"]:
                            self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                                "Error 111: ELSE sin THEN previo"))
                            has_errors = True
                        elif top["has_else"]:
                            self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                                "Error 112: ELSE duplicado"))
                            has_errors = True
                        else:
                            top["has_else"] = True
                    continue

                if kw == "ENDIF":
                    if not control_stack:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            "Error 113: ENDIF sin IF correspondiente"))
                        has_errors = True
                    else:
                        top = control_stack.pop()
                        if not top["has_then"]:
                            self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                                "Error 114: Bloque IF sin THEN"))
                            has_errors = True
                    continue

                if kw in {"DELETE", "EXTRACT"}:
                    if depth < 1:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            f"Error 115: {kw} requiere 1 parámetro en la pila"))
                        has_errors = True
                    continue

                if kw in ("MODIFY", "FILTER"):
                    if depth < 3:
                        code_err = "119" if kw == "MODIFY" else "120"
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            f"Error {code_err}: {kw} requiere 3 parámetros (campo, operador, valor)"))
                        has_errors = True
                    else:
                        depth -= 2
                    continue

                if kw in {"LOAD", "SAVE"}:
                    if depth < 1:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            f"Error 121: {kw} requiere nombre de archivo"))
                        has_errors = True
                    continue

                if kw in {"COUNT", "SHOW"}:
                    depth += 1
                    continue

                # ── JSON ──────────────────────────────────────────
                if kw in {"JLOAD", "JSAVE"}:
                    if depth < 1:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            f"Error 122: {kw} requiere nombre de archivo"))
                        has_errors = True
                    continue

                if kw in {"JGET", "JDEL"}:
                    if depth < 1:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            f"Error 123: {kw} requiere 1 parámetro (clave)"))
                        has_errors = True
                    continue

                if kw == "JSET":
                    if depth < 2:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            "Error 124: JSET requiere 2 parámetros (clave, valor)"))
                        has_errors = True
                    else:
                        depth -= 1
                    continue

                if kw == "JFILTER":
                    if depth < 3:
                        self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                            "Error 125: JFILTER requiere 3 parámetros (clave, operador, valor)"))
                        has_errors = True
                    else:
                        depth -= 2
                    continue

                continue

            self.errors.append(CompilerError(token.line, "SINTÁCTICO",
                f"Error 116: Token inesperado '{t}'"))
            has_errors = True

        for pending in control_stack:
            self.errors.append(CompilerError(pending["line"], "SINTÁCTICO",
                "Error 117: Bloque IF sin ENDIF de cierre"))
            has_errors = True

        return not has_errors

    # ========== FASE 3: ANÁLISIS SEMÁNTICO ==========

    def semantic_analysis(self, tokens: List[Token]) -> bool:
        has_errors = False
        type_stack: List[str] = []

        binary_ops_map = {
            "OP_ADD": "NUMBER", "OP_SUB": "NUMBER",
            "OP_MUL": "NUMBER", "OP_DIV": "NUMBER",
            "OP_EQ":  "ANY",    "OP_NEQ": "ANY",
            "OP_LT":  "NUMBER", "OP_GT":  "NUMBER",
            "OP_LTE": "NUMBER", "OP_GTE": "NUMBER",
        }

        for token in tokens:
            t = token.type

            if t == "NUMBER":
                type_stack.append("NUMBER"); continue
            if t == "STRING":
                type_stack.append("STRING"); continue

            if t in binary_ops_map:
                expected = binary_ops_map[t]
                if len(type_stack) >= 2:
                    right = type_stack.pop()
                    left  = type_stack.pop()
                    if expected == "NUMBER":
                        if left not in ("NUMBER", "ANY") or right not in ("NUMBER", "ANY"):
                            self.errors.append(CompilerError(token.line, "SEMÁNTICO",
                                f"Error 201: Operador '{token.value}' espera operandos numéricos, "
                                f"recibió '{left}' y '{right}'"))
                            has_errors = True
                type_stack.append("NUMBER" if expected == "NUMBER" else "BOOLEAN")
                continue

            if t == "KEYWORD":
                kw = token.value.upper()

                if kw in ("AND", "OR"):
                    if len(type_stack) >= 2:
                        type_stack.pop(); type_stack.pop()
                    type_stack.append("BOOLEAN")
                    continue

                if kw == "NOT":
                    if type_stack:
                        type_stack[-1] = "BOOLEAN"
                    continue

                if kw in ("LOAD", "JLOAD"):
                    if type_stack: type_stack.pop()
                    type_stack.append("NUMBER")
                    continue

                if kw in ("SAVE", "JSAVE"):
                    if type_stack: type_stack.pop()
                    continue

                if kw in ("FILTER", "MODIFY", "JFILTER"):
                    if len(type_stack) >= 3:
                        type_stack.pop(); type_stack.pop(); type_stack.pop()
                    continue

                if kw == "JSET":
                    if len(type_stack) >= 2:
                        type_stack.pop(); type_stack.pop()
                    continue

                if kw in ("JGET", "JDEL"):
                    if type_stack: type_stack.pop()
                    continue

                if kw == "DUP" and type_stack:
                    type_stack.append(type_stack[-1]); continue
                if kw == "DROP" and type_stack:
                    type_stack.pop(); continue
                if kw == "SWAP" and len(type_stack) >= 2:
                    type_stack[-1], type_stack[-2] = type_stack[-2], type_stack[-1]; continue
                if kw == "COUNT":
                    type_stack.append("NUMBER"); continue
                if kw in ("PRINT", "SHOW"):
                    continue

        return not has_errors

    # ========== FASE 4: GENERACIÓN DE BYTECODE ==========

    def generate_bytecode(self, tokens: List[Token]) -> List[Instruction]:
        self.bytecode = []
        label_counter = [0]
        control_stack: List[Dict[str, Any]] = []

        def new_label() -> str:
            label_counter[0] += 1
            return f"L{label_counter[0]}"

        token_to_opcode = {
            "OP_ADD": OpCode.ADD, "OP_SUB": OpCode.SUB,
            "OP_MUL": OpCode.MUL, "OP_DIV": OpCode.DIV,
            "OP_EQ":  OpCode.EQ,  "OP_NEQ": OpCode.NEQ,
            "OP_LT":  OpCode.LT,  "OP_GT":  OpCode.GT,
            "OP_LTE": OpCode.LTE, "OP_GTE": OpCode.GTE,
        }

        keyword_to_opcode = {
            "AND":     OpCode.AND,     "OR":      OpCode.OR,
            "NOT":     OpCode.NOT,     "DUP":     OpCode.DUP,
            "DROP":    OpCode.DROP,    "SWAP":    OpCode.SWAP,
            "PRINT":   OpCode.PRINT,   "LOAD":    OpCode.LOAD,
            "SAVE":    OpCode.SAVE,    "FILTER":  OpCode.FILTER,
            "DELETE":  OpCode.DELETE,  "MODIFY":  OpCode.MODIFY,
            "EXTRACT": OpCode.EXTRACT, "COUNT":   OpCode.COUNT,
            "SHOW":    OpCode.SHOW,
            # ── JSON ──
            "JLOAD":   OpCode.JLOAD,   "JSAVE":   OpCode.JSAVE,
            "JGET":    OpCode.JGET,    "JSET":    OpCode.JSET,
            "JDEL":    OpCode.JDEL,    "JFILTER": OpCode.JFILTER,
        }

        for token in tokens:
            t = token.type

            if t in ("NUMBER", "STRING"):
                self.bytecode.append(Instruction(OpCode.PUSH, token.value, token.line))
                continue

            if t in token_to_opcode:
                self.bytecode.append(Instruction(token_to_opcode[t], None, token.line))
                continue

            if t == "KEYWORD":
                kw = token.value.upper()

                if kw == "IF":
                    lbl_else = new_label()
                    lbl_end  = new_label()
                    self.bytecode.append(Instruction(OpCode.JUMP_FALSE, lbl_else, token.line))
                    control_stack.append({
                        "lbl_else": lbl_else,
                        "lbl_end":  lbl_end,
                        "jump_end_idx": None
                    })
                    continue

                if kw == "THEN":
                    continue

                if kw == "ELSE":
                    top = control_stack[-1]
                    top["jump_end_idx"] = len(self.bytecode)
                    self.bytecode.append(Instruction(OpCode.JUMP,  top["lbl_end"],  token.line))
                    self.bytecode.append(Instruction(OpCode.LABEL, top["lbl_else"], token.line))
                    continue

                if kw == "ENDIF":
                    top = control_stack.pop()
                    if top["jump_end_idx"] is None:
                        self.bytecode.append(Instruction(OpCode.LABEL, top["lbl_else"], token.line))
                    self.bytecode.append(Instruction(OpCode.LABEL, top["lbl_end"], token.line))
                    continue

                if kw in keyword_to_opcode:
                    self.bytecode.append(Instruction(keyword_to_opcode[kw], None, token.line))
                    continue

        self.bytecode.append(Instruction(OpCode.HALT, None, 0))
        return self.bytecode

    # ========== FASE 5: OPTIMIZACIÓN ==========

    def optimize_bytecode(self, bytecode: List[Instruction]) -> List[Instruction]:
        changed = True
        optimized = list(bytecode)

        while changed:
            changed = False

            # Optimización 1: PUSH + DROP → eliminados
            new_code = []
            i = 0
            while i < len(optimized):
                if (optimized[i].opcode == OpCode.PUSH and
                        i + 1 < len(optimized) and
                        optimized[i+1].opcode == OpCode.DROP):
                    i += 2; changed = True; continue
                new_code.append(optimized[i]); i += 1
            optimized = new_code

            # Optimización 2: Plegado de constantes numéricas
            fold_ops = {
                OpCode.ADD: lambda a, b: a + b,
                OpCode.SUB: lambda a, b: a - b,
                OpCode.MUL: lambda a, b: a * b,
                OpCode.DIV: lambda a, b: a / b if b != 0 else None,
            }
            new_code = []
            i = 0
            while i < len(optimized):
                instr = optimized[i]
                if (instr.opcode == OpCode.PUSH and
                        isinstance(instr.operand, (int, float)) and
                        i + 1 < len(optimized) and
                        optimized[i+1].opcode == OpCode.PUSH and
                        isinstance(optimized[i+1].operand, (int, float)) and
                        i + 2 < len(optimized) and
                        optimized[i+2].opcode in fold_ops):
                    a = instr.operand
                    b = optimized[i+1].operand
                    res = fold_ops[optimized[i+2].opcode](a, b)
                    if res is not None:
                        new_code.append(Instruction(OpCode.PUSH, res, instr.line))
                        i += 3; changed = True; continue
                new_code.append(instr); i += 1
            optimized = new_code

            # Optimización 3: JUMP a etiqueta inmediata siguiente
            new_code = []
            i = 0
            while i < len(optimized):
                instr = optimized[i]
                if (instr.opcode == OpCode.JUMP and
                        i + 1 < len(optimized) and
                        optimized[i+1].opcode == OpCode.LABEL and
                        optimized[i+1].operand == instr.operand):
                    i += 1; changed = True; continue
                new_code.append(instr); i += 1
            optimized = new_code

        return optimized

    # ========== FASE 6: MÁQUINA VIRTUAL ==========

    def execute_vm(self, bytecode: List[Instruction]) -> None:
        self.execution_log = []

        label_map: Dict[str, int] = {}
        for idx, instr in enumerate(bytecode):
            if instr.opcode == OpCode.LABEL:
                label_map[instr.operand] = idx

        pc = 0
        while pc < len(bytecode):
            instr = bytecode[pc]

            if instr.opcode == OpCode.HALT:
                break
            if instr.opcode == OpCode.LABEL:
                pc += 1; continue

            action = self._execute_instruction(instr)

            self.execution_log.append({
                "pc":     pc,
                "instr":  str(instr),
                "action": action,
                "stack":  list(self.stack),
            })

            if instr.opcode == OpCode.JUMP:
                if instr.operand in label_map:
                    pc = label_map[instr.operand]
                    continue

            if instr.opcode == OpCode.JUMP_FALSE:
                if self.stack:
                    condition = self.stack.pop()
                    if not bool(condition):
                        if instr.operand in label_map:
                            pc = label_map[instr.operand]
                            continue

            pc += 1

    def _execute_instruction(self, instr: Instruction) -> str:
        op = instr.opcode

        if op == OpCode.PUSH:
            self.stack.append(instr.operand)
            return f"PUSH {instr.operand}"

        if op == OpCode.ADD: return self._bin_op("+",  lambda a, b: b + a)
        if op == OpCode.SUB: return self._bin_op("-",  lambda a, b: b - a)
        if op == OpCode.MUL: return self._bin_op("*",  lambda a, b: b * a)
        if op == OpCode.DIV:
            if len(self.stack) >= 2 and self.stack[-1] == 0:
                self.errors.append(CompilerError(instr.line, "EJECUCIÓN", "Error 301: División por cero"))
                return "ERROR: División por cero"
            return self._bin_op("/", lambda a, b: b / a)

        if op == OpCode.EQ:  return self._bin_op("==", lambda a, b: b == a)
        if op == OpCode.NEQ: return self._bin_op("!=", lambda a, b: b != a)
        if op == OpCode.LT:  return self._bin_op("<",  lambda a, b: b <  a)
        if op == OpCode.GT:  return self._bin_op(">",  lambda a, b: b >  a)
        if op == OpCode.LTE: return self._bin_op("<=", lambda a, b: b <= a)
        if op == OpCode.GTE: return self._bin_op(">=", lambda a, b: b >= a)

        if op == OpCode.AND: return self._bin_op("AND", lambda a, b: bool(b) and bool(a))
        if op == OpCode.OR:  return self._bin_op("OR",  lambda a, b: bool(b) or  bool(a))

        if op == OpCode.NOT:
            if not self.stack:
                return "ERROR: Stack underflow en NOT"
            a = self.stack.pop()
            r = not bool(a)
            self.stack.append(r)
            return f"NOT {a} = {r}"

        if op == OpCode.DUP:
            if not self.stack:
                return "ERROR: Stack underflow en DUP"
            self.stack.append(self.stack[-1])
            return f"DUP {self.stack[-1]}"

        if op == OpCode.DROP:
            if not self.stack:
                return "ERROR: Stack underflow en DROP"
            v = self.stack.pop()
            return f"DROP {v}"

        if op == OpCode.SWAP:
            if len(self.stack) < 2:
                return "ERROR: Stack underflow en SWAP"
            self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]
            return f"SWAP {self.stack[-2]} <-> {self.stack[-1]}"

        if op == OpCode.PRINT:
            if not self.stack:
                return "ERROR: Stack underflow en PRINT"
            v = self.stack[-1]
            return f"PRINT {v}"

        if op == OpCode.LOAD:    return self.execute_load()
        if op == OpCode.SAVE:    return self.execute_save()
        if op == OpCode.FILTER:  return self.execute_filter()
        if op == OpCode.DELETE:  return self.execute_delete()
        if op == OpCode.MODIFY:  return self.execute_modify()
        if op == OpCode.EXTRACT: return self.execute_extract()

        if op == OpCode.COUNT:
            c = len(self.loaded_data)
            self.stack.append(c)
            return f"COUNT = {c}"

        if op == OpCode.SHOW:
            return self.execute_show()

        # ── JSON ──
        if op == OpCode.JLOAD:   return self.execute_jload()
        if op == OpCode.JSAVE:   return self.execute_jsave()
        if op == OpCode.JGET:    return self.execute_jget()
        if op == OpCode.JSET:    return self.execute_jset()
        if op == OpCode.JDEL:    return self.execute_jdel()
        if op == OpCode.JFILTER: return self.execute_jfilter()

        if op in (OpCode.JUMP, OpCode.JUMP_FALSE):
            return f"{op.value} → {instr.operand}"

        return f"NOP ({op.value})"

    def _bin_op(self, name: str, func) -> str:
        if len(self.stack) < 2:
            self.errors.append(CompilerError(self.current_line, "EJECUCIÓN",
                f"Stack underflow: '{name}' requiere 2 operandos"))
            return f"ERROR: Stack underflow en {name}"
        a = self.stack.pop()
        b = self.stack.pop()
        r = func(a, b)
        self.stack.append(r)
        return f"{b} {name} {a} = {r}"

    # ========== OPERACIONES CSV ==========

    def execute_load(self) -> str:
        if not self.stack:
            return "ERROR: Stack underflow en LOAD"
        filename = str(self.stack.pop())
        if not os.path.exists(filename):
            self.errors.append(CompilerError(self.current_line, "EJECUCIÓN",
                f"Archivo no encontrado: '{filename}'"))
            return f"ERROR: '{filename}' no encontrado"
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.current_headers = list(reader.fieldnames or [])
                self.loaded_data = []
                for idx, row in enumerate(reader, start=1):
                    processed = {}
                    for k, v in row.items():
                        try:
                            processed[k] = float(v)
                        except (ValueError, TypeError):
                            processed[k] = v
                    self.loaded_data.append(DataRecord(processed, idx))
            self.current_file = filename
            self.stack.append(len(self.loaded_data))
            return f"LOAD '{filename}' → {len(self.loaded_data)} registros"
        except Exception as e:
            self.errors.append(CompilerError(self.current_line, "EJECUCIÓN", f"Error al leer CSV: {e}"))
            return f"ERROR: {e}"

    def execute_save(self) -> str:
        if not self.stack:
            return "ERROR: Stack underflow en SAVE"
        filename = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos para guardar"
        try:
            with open(filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.current_headers)
                writer.writeheader()
                for record in self.loaded_data:
                    writer.writerow(record.data)
            return f"SAVE '{filename}' → {len(self.loaded_data)} registros guardados"
        except Exception as e:
            return f"ERROR: {e}"

    def execute_filter(self) -> str:
        if len(self.stack) < 3:
            return "ERROR: Stack underflow en FILTER"
        value    = self.stack.pop()
        operator = str(self.stack.pop())
        field    = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos cargados"
        ops = {
            "==":  lambda fv, v: fv == v, "!=":  lambda fv, v: fv != v,
            "<":   lambda fv, v: fv <  v, ">":   lambda fv, v: fv >  v,
            "<=":  lambda fv, v: fv <= v, ">=":  lambda fv, v: fv >= v,
        }
        fn = ops.get(operator) or ops.get(operator.lower())
        if not fn:
            return f"ERROR: Operador '{operator}' no reconocido"
        original = len(self.loaded_data)
        result = []
        for rec in self.loaded_data:
            if field not in rec.data:
                continue
            fv = rec.data[field]
            try:
                if isinstance(value, (int, float)):
                    fv = float(fv) if not isinstance(fv, (int, float)) else fv
                if fn(fv, value):
                    result.append(rec)
            except Exception:
                continue
        self.loaded_data = result
        return f"FILTER {field} {operator} {value} → {original} → {len(result)} registros"

    def execute_delete(self) -> str:
        if not self.stack:
            return "ERROR: Stack underflow en DELETE"
        field = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos cargados"
        original = len(self.loaded_data)
        self.loaded_data = [
            r for r in self.loaded_data
            if field not in r.data or not r.data[field]
        ]
        deleted = original - len(self.loaded_data)
        return f"DELETE campo '{field}' → {deleted} registros eliminados"

    def execute_modify(self) -> str:
        if len(self.stack) < 3:
            return "ERROR: Stack underflow en MODIFY"
        new_value = self.stack.pop()
        operator  = str(self.stack.pop())
        field     = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos cargados"
        count = 0
        for rec in self.loaded_data:
            if field in rec.data and operator == "=":
                rec.data[field] = new_value
                count += 1
        return f"MODIFY {field} = {new_value} → {count} registros modificados"

    def execute_extract(self) -> str:
        if not self.stack:
            return "ERROR: Stack underflow en EXTRACT"
        field = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos cargados"
        values = [r.data[field] for r in self.loaded_data if field in r.data]
        self.stack.append(values)
        return f"EXTRACT '{field}' → {len(values)} valores"

    def execute_show(self) -> str:
        if not self.loaded_data:
            return "SHOW: No hay datos cargados"
        return f"SHOW {len(self.loaded_data)} registros"

    # ========== OPERACIONES JSON ==========

    def execute_jload(self) -> str:
        if not self.stack:
            return "ERROR: Stack underflow en JLOAD"
        filename = str(self.stack.pop())
        if not os.path.exists(filename):
            self.errors.append(CompilerError(self.current_line, "EJECUCIÓN",
                f"Archivo no encontrado: '{filename}'"))
            return f"ERROR: '{filename}' no encontrado"
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                records = next((v for v in data.values() if isinstance(v, list)), [data])
            else:
                return "ERROR: El JSON debe ser un array de objetos"

            if not records:
                return "ERROR: El JSON está vacío"

            self.current_headers = list(records[0].keys()) if records else []
            self.loaded_data = []
            for idx, obj in enumerate(records, start=1):
                processed = {}
                for k, v in obj.items():
                    try:
                        processed[k] = float(v) if isinstance(v, str) else v
                    except (ValueError, TypeError):
                        processed[k] = v
                self.loaded_data.append(DataRecord(processed, idx))

            self.current_file = filename
            self.stack.append(len(self.loaded_data))
            return f"JLOAD '{filename}' → {len(self.loaded_data)} registros"
        except Exception as e:
            self.errors.append(CompilerError(self.current_line, "EJECUCIÓN",
                f"Error al leer JSON: {e}"))
            return f"ERROR: {e}"

    def execute_jsave(self) -> str:
        if not self.stack:
            return "ERROR: Stack underflow en JSAVE"
        filename = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos para guardar"
        try:
            records = []
            for rec in self.loaded_data:
                obj = {}
                for h in self.current_headers:
                    if h in rec.data:
                        val = rec.data[h]
                        if isinstance(val, float) and val.is_integer():
                            val = int(val)
                        obj[h] = val
                for k, v in rec.data.items():
                    if k not in obj:
                        if isinstance(v, float) and v.is_integer():
                            v = int(v)
                        obj[k] = v
                records.append(obj)

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

            return f"JSAVE '{filename}' → {len(self.loaded_data)} registros guardados"
        except Exception as e:
            return f"ERROR: {e}"

    def execute_jget(self) -> str:
        if not self.stack:
            return "ERROR: Stack underflow en JGET"
        key = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos cargados"
        values = [rec.data.get(key) for rec in self.loaded_data if key in rec.data]
        self.stack.append(values)
        return f"JGET '{key}' → {len(values)} valores extraídos"

    def execute_jset(self) -> str:
        if len(self.stack) < 2:
            return "ERROR: Stack underflow en JSET"
        new_value = self.stack.pop()
        key       = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos cargados"
        count = 0
        for rec in self.loaded_data:
            rec.data[key] = new_value
            count += 1
        if key not in self.current_headers:
            self.current_headers.append(key)
        return f"JSET '{key}' = {new_value} → {count} registros modificados"

    def execute_jdel(self) -> str:
        if not self.stack:
            return "ERROR: Stack underflow en JDEL"
        key = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos cargados"
        count = 0
        for rec in self.loaded_data:
            if key in rec.data:
                del rec.data[key]
                count += 1
        if key in self.current_headers:
            self.current_headers.remove(key)
        return f"JDEL '{key}' → clave eliminada de {count} registros"

    def execute_jfilter(self) -> str:
        if len(self.stack) < 3:
            return "ERROR: Stack underflow en JFILTER"
        value    = self.stack.pop()
        operator = str(self.stack.pop())
        key      = str(self.stack.pop())
        if not self.loaded_data:
            return "ERROR: No hay datos cargados"
        ops = {
            "==":  lambda fv, v: fv == v, "!=":  lambda fv, v: fv != v,
            "<":   lambda fv, v: fv <  v, ">":   lambda fv, v: fv >  v,
            "<=":  lambda fv, v: fv <= v, ">=":  lambda fv, v: fv >= v,
        }
        fn = ops.get(operator)
        if not fn:
            return f"ERROR: Operador '{operator}' no reconocido"
        original = len(self.loaded_data)
        result = []
        for rec in self.loaded_data:
            if key not in rec.data:
                continue
            fv = rec.data[key]
            try:
                if isinstance(value, (int, float)):
                    fv = float(fv) if not isinstance(fv, (int, float)) else fv
                if fn(fv, value):
                    result.append(rec)
            except Exception:
                continue
        self.loaded_data = result
        return f"JFILTER {key} {operator} {value} → {original} → {len(result)} registros"

    # ========== ÁRBOL SEMÁNTICO ==========

    def build_semantic_tree(self, tokens: List[Token]) -> dict:
        root  = {"label": "PROGRAMA", "type": "ROOT", "dtype": "", "children": []}
        stack = []

        binary_ops = {
            "OP_ADD": ("+",  "NUMBER"),  "OP_SUB": ("-",  "NUMBER"),
            "OP_MUL": ("*",  "NUMBER"),  "OP_DIV": ("/",  "NUMBER"),
            "OP_EQ":  ("==", "BOOLEAN"), "OP_NEQ": ("!=", "BOOLEAN"),
            "OP_LT":  ("<",  "BOOLEAN"), "OP_GT":  (">",  "BOOLEAN"),
            "OP_LTE": ("<=", "BOOLEAN"), "OP_GTE": (">=", "BOOLEAN"),
        }

        def make_node(label, ntype, dtype, children=None):
            return {"label": label, "type": ntype, "dtype": dtype, "children": children or []}

        for tok in tokens:
            t = tok.type

            if t == "NUMBER":
                stack.append(make_node(str(tok.value), "NÚMERO", "NUMBER"))
                continue
            if t == "STRING":
                stack.append(make_node(f'"{tok.value}"', "CADENA", "STRING"))
                continue

            if t in binary_ops:
                sym, dtype = binary_ops[t]
                right = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                left  = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                stack.append(make_node(sym, "OP-BINARIO", dtype, [left, right]))
                continue

            if t == "KEYWORD":
                kw = tok.value.upper()

                if kw in ("AND", "OR"):
                    right = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    left  = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    stack.append(make_node(kw, "OP-LÓGICO", "BOOLEAN", [left, right]))
                    continue
                if kw == "NOT":
                    child = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    stack.append(make_node("NOT", "OP-LÓGICO", "BOOLEAN", [child]))
                    continue
                if kw == "DUP":
                    child = stack[-1] if stack else make_node("?", "VACÍO", "ANY")
                    stack.append(make_node("DUP", "OP-PILA", child.get("dtype","ANY"), [child]))
                    continue
                if kw == "DROP":
                    child = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("DROP", "OP-PILA", "VOID", [child]))
                    continue
                if kw == "SWAP":
                    b = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    a = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("SWAP", "OP-PILA", "VOID", [a, b]))
                    continue
                if kw == "PRINT":
                    child = stack[-1] if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("PRINT", "SALIDA", "VOID", [child]))
                    continue
                if kw == "LOAD":
                    fname = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("LOAD", "OP-DATOS", "NUMBER", [fname]))
                    continue
                if kw == "SAVE":
                    fname = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("SAVE", "OP-DATOS", "VOID", [fname]))
                    continue
                if kw == "FILTER":
                    val   = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    op    = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    field = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("FILTER", "OP-DATOS", "VOID", [field, op, val]))
                    continue
                if kw == "MODIFY":
                    val   = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    op    = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    field = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("MODIFY", "OP-DATOS", "VOID", [field, op, val]))
                    continue
                if kw == "DELETE":
                    field = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("DELETE", "OP-DATOS", "VOID", [field]))
                    continue
                if kw == "EXTRACT":
                    field = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("EXTRACT", "OP-DATOS", "VOID", [field]))
                    continue
                if kw == "COUNT":
                    root["children"].append(make_node("COUNT", "OP-DATOS", "NUMBER"))
                    continue
                if kw == "SHOW":
                    root["children"].append(make_node("SHOW", "OP-DATOS", "VOID"))
                    continue
                if kw == "IF":
                    cond = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("IF", "CONTROL", "VOID", [cond]))
                    continue
                if kw in ("THEN", "ELSE", "ENDIF"):
                    root["children"].append(make_node(kw, "CONTROL", "VOID"))
                    continue

                # ── JSON en árbol ──
                if kw == "JLOAD":
                    fname = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("JLOAD", "OP-JSON", "NUMBER", [fname]))
                    continue
                if kw == "JSAVE":
                    fname = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("JSAVE", "OP-JSON", "VOID", [fname]))
                    continue
                if kw == "JFILTER":
                    val   = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    op    = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    field = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("JFILTER", "OP-JSON", "VOID", [field, op, val]))
                    continue
                if kw == "JSET":
                    val  = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    key  = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("JSET", "OP-JSON", "VOID", [key, val]))
                    continue
                if kw == "JGET":
                    key = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("JGET", "OP-JSON", "STRING", [key]))
                    continue
                if kw == "JDEL":
                    key = stack.pop() if stack else make_node("?", "VACÍO", "ANY")
                    root["children"].append(make_node("JDEL", "OP-JSON", "VOID", [key]))
                    continue

        for leftover in stack:
            root["children"].append(leftover)

        return root

    # ========== INSPECCIÓN ==========

    def get_errors(self) -> List[CompilerError]:
        return self.errors

    def get_stack(self) -> List[Any]:
        return self.stack
