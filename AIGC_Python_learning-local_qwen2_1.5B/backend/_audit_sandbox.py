"""临时审计脚本：验证沙箱安全性与超时机制（运行后删除）"""
import sys, os, threading, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.sandbox.sandbox import run_code
from app.services.sandbox.security_check import SecurityChecker

print("=" * 70)
print("测试 1：format 字符串绕过 AST 属性检查（沙箱逃逸）")
print("=" * 70)

escape_payloads = [
    # 通过 str.format 的格式迷你语言访问 __class__ 等属性，AST 只看到字符串常量
    "print('{0.__class__}'.format(1))",
    "print('{0.__class__.__mro__}'.format(1))",
    "print(len('{0.__class__.__mro__[1].__subclasses__()}'.format(1)))",
]
for p in escape_payloads:
    checker = SecurityChecker()
    ok, errs = checker.check_code(p)
    print(f"\n载荷: {p}")
    print(f"  安全检查通过(未被拦截): {ok}")
    if not ok:
        print(f"  拦截原因: {[e['message'] for e in errs]}")
    res = run_code(p, timeout=5)
    print(f"  沙箱执行 success={res['success']}")
    out = (res.get("output") or "").strip()
    print(f"  实际输出: {out[:160]}")

print()
print("=" * 70)
print("测试 2：线程超时是否真正终止失控代码")
print("=" * 70)
before = threading.active_count()
t0 = time.time()
res = run_code("while True:\n    pass", timeout=2)
elapsed = time.time() - t0
# 给线程一点时间观察
time.sleep(0.2)
after = threading.active_count()
print(f"  run_code 返回耗时: {elapsed:.2f}s (设定超时 2s)")
print(f"  内部线程数: 执行前={before} 执行后={after} (差={after - before})")
print(f"  返回给前端的 errors: {res['errors']}")

print()
print("=" * 70)
print("测试 3：危险模块白名单是否形同虚设（ALLOWED 与 DANGEROUS 冲突）")
print("=" * 70)
from app.services.sandbox.security_check import DANGEROUS_MODULES, ALLOWED_MODULES
conflict = DANGEROUS_MODULES & ALLOWED_MODULES
print(f"  同时出现在黑名单和白名单的模块: {sorted(conflict)}")
