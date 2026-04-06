from .sentrydata_compiler import SentryDataCompiler

def run_in_memory(code: str) -> dict:
    compiler = SentryDataCompiler()
    result = {
        "tokens": [],
        "lexical_errors": [],
        "syntax_ok": False,
        "syntax_errors": [],
        "semantic_ok": False,
        "semantic_errors": [],
        "semantic_tree": None,
        "bytecode": [],
        "execution_log": [],
        "stack": [],
        "data_summary": None,
        "data_records": [],
        "print_outputs": [],
        "operations": [],
        "search_results": [],
        "arithmetic_results": [],   # resultados de ops aritmeticas/logicas
        "all_errors": [],
    }

    # FASE 1: LEXICO
    tokens = compiler.lexical_analysis(code)
    result["tokens"] = [
        {"type": t.type, "value": t.value, "line": t.line, "column": t.column}
        for t in tokens
    ]
    result["lexical_errors"] = [e for e in compiler.errors if e.type == "LEXICO"]

    # FASE 2: SINTACTICO
    ok_syntax = compiler.syntactic_analysis(tokens)
    result["syntax_ok"] = ok_syntax
    result["syntax_errors"] = [e for e in compiler.errors if e.type == "SINTACTICO"]

    # FASE 3: SEMANTICO
    ok_semantic = compiler.semantic_analysis(tokens)
    result["semantic_ok"] = ok_semantic
    result["semantic_errors"] = [e for e in compiler.errors if e.type == "SEMANTICO"]
    result["semantic_tree"] = compiler.build_semantic_tree(tokens)

    # FASE 4-5: BYTECODE + OPTIMIZACION
    bytecode  = compiler.generate_bytecode(tokens)
    optimized = compiler.optimize_bytecode(bytecode)

    # FASE 6: EJECUCION VM
    compiler.execute_vm(optimized)

    result["bytecode"]      = [str(instr) for instr in optimized]
    result["execution_log"] = compiler.execution_log
    result["stack"]         = compiler.get_stack()

    # ── CLASIFICAR ENTRADAS DEL LOG ──────────────────────────────
    PRINT_OPS   = ("PRINT",)
    SEARCH_OPS  = ("FILTER", "SHOW", "JFILTER")
    DATA_OPS    = ("LOAD", "SAVE", "DELETE", "MODIFY", "EXTRACT", "COUNT",
                   "JLOAD", "JSAVE", "JGET", "JSET", "JDEL")
    ARITH_OPS   = ("ADD", "SUB", "MUL", "DIV", "EQ", "NEQ", "LT", "GT",
                   "LTE", "GTE", "AND", "OR", "NOT", "DUP", "DROP", "SWAP")

    seen_search = False
    for step in compiler.execution_log:
        instr_upper = step["instr"].upper().strip()
        action      = step["action"]

        # PRINT
        if any(instr_upper.startswith(k) for k in PRINT_OPS):
            value = action.replace("PRINT", "").strip()
            result["print_outputs"].append({"pc": step["pc"], "value": value})

        # Operaciones de datos (LOAD, SAVE, DELETE, etc.)
        elif any(instr_upper.startswith(k) for k in DATA_OPS):
            result["operations"].append({"instr": step["instr"], "action": action})

        # Busqueda/filtrado -> snapshot de registros
        elif any(instr_upper.startswith(k) for k in SEARCH_OPS):
            result["operations"].append({"instr": step["instr"], "action": action})
            if not seen_search:
                seen_search = True
                result["search_results"].append({
                    "operation": step["instr"],
                    "summary":   action,
                    "headers":   compiler.current_headers,
                    "records": [
                        {"row_number": rec.row_number, "data": rec.data}
                        for rec in compiler.loaded_data
                    ],
                })

        # Operaciones aritmeticas / logicas / pila
        elif any(instr_upper.startswith(k) for k in ARITH_OPS):
            if "ERROR" not in action:
                result["arithmetic_results"].append({
                    "pc":     step["pc"],
                    "instr":  step["instr"],
                    "action": action,
                    "stack":  step["stack"],
                })

    # ── DATOS CSV/JSON EN MEMORIA ────────────────────────────────
    if compiler.loaded_data:
        result["data_summary"] = {
            "file":    compiler.current_file,
            "records": len(compiler.loaded_data),
            "headers": compiler.current_headers,
        }
        result["data_records"] = [
            {"row_number": rec.row_number, "data": rec.data}
            for rec in compiler.loaded_data
        ]

    # ── TODOS LOS ERRORES ────────────────────────────────────────
    result["all_errors"] = compiler.get_errors()

    return result
