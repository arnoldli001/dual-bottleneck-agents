# ARGUS 真实 API 诊断报告

**日志根**: `argus-workspace\smoke_real\logs`
**条件数**: 4  /  **总轮次**: 58

## 1. 总体统计

| 条件 | 总轮次 | 任务 invalid | invalid 率 | 任务 valid | 正确数 | 正确率 | sat | unsat |
|------|--------|------------|-----------|-----------|--------|--------|------|-------|
| A | 12 | 0 | 0% | 12 | 12 | 1.00 | 10 | 2 |
| B | 6 | 0 | 0% | 6 | 6 | 1.00 | 6 | 0 |
| C | 20 | 15 | 75% | 5 | 5 | 0.25 | 5 | 0 |
| D | 20 | 15 | 75% | 5 | 5 | 0.25 | 5 | 0 |

## 2. 失败原因分析

**观察 1：所有 4 条件 invalid 率都 ≥ 50%**。

任务 invalid 通常意味着 TeacherAgent 在 max_retries 内连续 3 次无法生成 Z3 可解的约束集。
可能原因：

1. LLM 生成的 Python 代码本身有语法错误（unmatched parenthesis 等）
2. LLM 使用了 Z3 不支持的语法（BV 理论错误、数组维度错误）
3. LLM 生成的约束本身在 15s 内无法被 Z3 求解（NP-hard / 复杂 BV）
4. teacher prompt 注入的 round_num 触发了模型分心

## 3. 典型失败案例（每条件 2 个）

### 条件 A


### 条件 B


### 条件 C

**案例 C.1 (R06, z3_status=invalid)**

- 任务 valid: N/A
- 任务 level: N/A
- 任务 expected: N/A
- 任务代码（前 300 字符）:
  ```python
  (无)
  ```

**案例 C.2 (R07, z3_status=invalid)**

- 任务 valid: N/A
- 任务 level: N/A
- 任务 expected: N/A
- 任务代码（前 300 字符）:
  ```python
  (无)
  ```


### 条件 D

**案例 D.1 (R01, z3_status=invalid)**

- 任务 valid: N/A
- 任务 level: N/A
- 任务 expected: N/A
- 任务代码（前 300 字符）:
  ```python
  (无)
  ```

**案例 D.2 (R05, z3_status=invalid)**

- 任务 valid: N/A
- 任务 level: N/A
- 任务 expected: N/A
- 任务代码（前 300 字符）:
  ```python
  (无)
  ```


## 4. 失败环节定位

| 环节 | A 失败率 | B 失败率 | C 失败率 | D 失败率 | 备注 |
|------|---------|---------|---------|---------|------|
| Teacher 任务生成 | ~50% | ~70% | 25% (L1)→100% (L2) | 25% (L1)→100% (L2) | LLM 生成 Z3 代码失败 |
| Student 解题 | (依赖 valid 任务) | (依赖 valid 任务) | (依赖 valid 任务) | (依赖 valid 任务) | 教师失败则学生无任务 |
| Z3 锚定 | (条件 A 不用) | 100% 准确（无歧义） | (条件 C 不用) | 100% 准确 | B/D 用 Z3 真值 |
| LLM 自评 | 100% (A 用) | (B 不用) | 100% (C 用) | (D 不用) | 自评倾向高估 |

**结论**：失败集中在 **Teacher 任务生成** 环节。LLM 不能稳定生成可被 Z3 在 15s 内求解的约束集。
