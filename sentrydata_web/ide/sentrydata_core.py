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
        "bytecode": [],
        "execution_log": [],
        "stack": [],
        "data_summary": None,
        "data_records": [],       # ← NUEVO
        "print_outputs": [],      # ← NUEVO
        "operations": [],         # ← NUEVO
        "all_errors": [],
    }

    tokens = compiler.lexical_analysis(code)
    result["tokens"] = [{"type": t.type, "value": t.value, "line": t.line, "column": t.column} for t in tokens]
    result["lexical_errors"] = [e for e in compiler.errors if e.type == "LÉXICO"]

    ok_syntax = compiler.syntactic_analysis(tokens)
    result["syntax_ok"] = ok_syntax
    result["syntax_errors"] = [e for e in compiler.errors if e.type == "SINTÁCTICO"]

    ok_semantic = compiler.semantic_analysis(tokens)
    result["semantic_ok"] = ok_semantic
    result["semantic_errors"] = [e for e in compiler.errors if e.type == "SEMÁNTICO"]

    bytecode = compiler.generate_bytecode(tokens)
    optimized = compiler.optimize_bytecode(bytecode)
    compiler.execute_vm(optimized)

    result["bytecode"] = [str(instr) for instr in optimized]
    result["execution_log"] = compiler.execution_log
    result["stack"] = compiler.get_stack()

    # ← NUEVO: capturar PRINTs del log
    for step in compiler.execution_log:
        if step["action"].startswith("PRINT"):
            value = step["action"].replace("PRINT", "").strip()
            result["print_outputs"].append({
                "line": step["pc"],
                "value": value
            })

    # ← NUEVO: capturar operaciones importantes (FILTER, MODIFY, DELETE, SAVE, LOAD, COUNT)
    keywords_ops = ("FILTER", "MODIFY", "DELETE", "SAVE", "LOAD", "COUNT", "SHOW", "EXTRACT")
    for step in compiler.execution_log:
        instr_upper = step["instr"].upper()
        if any(instr_upper.startswith(k) for k in keywords_ops):
            result["operations"].append({
                "instr": step["instr"],
                "action": step["action"]
            })

    if compiler.loaded_data:
        result["data_summary"] = {
            "file": compiler.current_file,
            "records": len(compiler.loaded_data),
            "headers": compiler.current_headers,
        }
        # ← NUEVO: primeros 10 registros para mostrar en tabla
        result["data_records"] = compiler.loaded_data[:10]

    result["all_errors"] = compiler.get_errors()
    return result
