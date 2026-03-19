# sentrydata_core.py

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
        "all_errors": [],
    }

    tokens = compiler.lexical_analysis(code)
    result["tokens"] = [
        {
            "type": t.type,
            "value": t.value,
            "line": t.line,
            "column": t.column,
        } for t in tokens
    ]
    result["lexical_errors"] = [
        e for e in compiler.errors if e.type == "LÉXICO"
    ]

    ok_syntax = compiler.syntactic_analysis(tokens)
    result["syntax_ok"] = ok_syntax
    result["syntax_errors"] = [
        e for e in compiler.errors if e.type == "SINTÁCTICO"
    ]

    ok_semantic = compiler.semantic_analysis(tokens)
    result["semantic_ok"] = ok_semantic
    result["semantic_errors"] = [
        e for e in compiler.errors if e.type == "SEMÁNTICO"
    ]

    bytecode = compiler.generate_bytecode(tokens)
    optimized = compiler.optimize_bytecode(bytecode)
    compiler.execute_vm(optimized)

    result["bytecode"] = [str(instr) for instr in optimized]
    result["execution_log"] = compiler.execution_log
    result["stack"] = compiler.get_stack()

    if compiler.loaded_data:
        result["data_summary"] = {
            "file": compiler.current_file,
            "records": len(compiler.loaded_data),
            "headers": compiler.current_headers,
        }

    result["all_errors"] = compiler.get_errors()
    return result
