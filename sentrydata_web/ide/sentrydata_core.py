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
        "search_results": [],   # snapshots de registros tras FILTER/SHOW/JFILTER
        "all_errors": [],
    }

    # ── FASE 1: LÉXICO ──────────────────────────────────────────
    tokens = compiler.lexical_analysis(code)
    result["tokens"] = [
        {"type": t.type, "value": t.value, "line": t.line, "column": t.column}
        for t in tokens
    ]
    result["lexical_errors"] = [e for e in compiler.errors if e.type == "LÉXICO"]

    # ── FASE 2: SINTÁCTICO ───────────────────────────────────────
    ok_syntax = compiler.syntactic_analysis(tokens)
    result["syntax_ok"] = ok_syntax
    result["syntax_errors"] = [e for e in compiler.errors if e.type == "SINTÁCTICO"]

    # ── FASE 3: SEMÁNTICO ────────────────────────────────────────
    ok_semantic = compiler.semantic_analysis(tokens)
    result["semantic_ok"] = ok_semantic
    result["semantic_errors"] = [e for e in compiler.errors if e.type == "SEMÁNTICO"]
    result["semantic_tree"] = compiler.build_semantic_tree(tokens)

    # ── FASE 4-5: BYTECODE + OPTIMIZACIÓN ───────────────────────
    bytecode  = compiler.generate_bytecode(tokens)
    optimized = compiler.optimize_bytecode(bytecode)

    # ── FASE 6: EJECUCIÓN VM ─────────────────────────────────────
    compiler.execute_vm(optimized)

    result["bytecode"]      = [str(instr) for instr in optimized]
    result["execution_log"] = compiler.execution_log
    result["stack"]         = compiler.get_stack()

    # ── CAPTURAR SALIDAS PRINT ───────────────────────────────────
    for step in compiler.execution_log:
        if step["action"].startswith("PRINT"):
            value = step["action"].replace("PRINT", "").strip()
            result["print_outputs"].append({"line": step["pc"], "value": value})

    # ── CAPTURAR OPERACIONES IMPORTANTES ────────────────────────
    keywords_ops = ("FILTER", "MODIFY", "DELETE", "SAVE", "LOAD", "COUNT", "SHOW", "EXTRACT",
                    "JLOAD", "JSAVE", "JFILTER", "JGET", "JSET", "JDEL")
    for step in compiler.execution_log:
        instr_upper = step["instr"].upper()
        if any(instr_upper.startswith(k) for k in keywords_ops):
            result["operations"].append({"instr": step["instr"], "action": step["action"]})

    # ── SNAPSHOTS DE BÚSQUEDA (FILTER / SHOW / JFILTER) ─────────
    # Recorremos el log buscando instrucciones que producen resultados visibles
    snapshot_ops = ("FILTER", "SHOW", "JFILTER")
    for step in compiler.execution_log:
        instr_upper = step["instr"].upper()
        if any(instr_upper.startswith(k) for k in snapshot_ops):
            # El snapshot de datos es el estado actual de loaded_data al momento
            # del paso. Como la VM ya terminó, usamos loaded_data final para SHOW/FILTER.
            # Para múltiples FILTERs, el estado final ya refleja todos los filtros.
            result["search_results"].append({
                "operation": step["instr"],
                "summary":   step["action"],
                "headers":   compiler.current_headers,
                "records": [
                    {"row_number": rec.row_number, "data": rec.data}
                    for rec in compiler.loaded_data
                ],
            })
            break  # un solo snapshot del estado final (evitar duplicados si hay SHOW+FILTER)

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
