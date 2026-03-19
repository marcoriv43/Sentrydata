from django.shortcuts import render
from .sentrydata_core import run_in_memory  # importa tu función
# o from .sentrydata_v3_1 import run_in_memory si mantienes el nombre

def ide_view(request):
    context = {
        "code": "",
        "result": None,
    }

    if request.method == "POST":
        code = request.POST.get("code", "")
        context["code"] = code

        if code.strip():
            result = run_in_memory(code)
            context["result"] = result

    return render(request, "ide/ide.html", context)
