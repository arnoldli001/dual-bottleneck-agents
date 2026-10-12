# ARGUS 真实 API 诊断报告 v2（含 cache 提取）

**LLM cache 总条目**: 113
**teacher 类型响应**: 56

## 1. teacher 输出质量问题分布

| 问题 | 次数 |
|------|------|
| `unmatched_parens` | 2 |
| `no_solver` | 1 |
| `no_constraint` | 1 |

## 2. 失败原因分析

**核心结论**：teacher 输出在多个维度都不可靠。

LLM 在生成 Z3 代码时常见问题：
1. **括号不匹配** - 多轮 LLM 经常生成 `(x > 5` 这种单边括号
2. **缺失约束** - 生成 `solver = Solver()` 但没 `solver.add(...)`，导致 Z3 返回 sat（trivial）
3. **危险导入** - 模型偶尔会加 `import time` 之类，需拦截
4. **过度复杂** - L2/L3 任务经常超过 Z3 15s 求解能力

## 3. 5 个典型失败案例

### 案例 1

- **问题**: `['no_solver', 'no_constraint']`
- **原始长度**: 38 / **代码长度**: 38
- **代码预览**:
  ```python
  from z3 import *

a = Int('a')
b = Int
  ```

### 案例 2

- **问题**: `['unmatched_parens']`
- **原始长度**: 231 / **代码长度**: 231
- **代码预览**:
  ```python
  from z3 import *
a, b, c, d, e = Ints('a b c d e')
solver = Solver()
solver.add(a + b == 7)
solver.add(b + c == 10)
solver.add(c + d == 13)
solver.add(d + e == 16)
solver.add(a >= 0, b >= 0, c >= 0, d >= 0, e >= 0)
solver.add(a < b
  ```

### 案例 3

- **问题**: `['unmatched_parens']`
- **原始长度**: 129 / **代码长度**: 129
- **代码预览**:
  ```python
  from z3 import *

p = Int('p')
q = Int('q')
r = Int('r')
s = Int('s')
t = Int('t')
u = Int('u')

solver = Solver()
solver.add(p +
  ```
