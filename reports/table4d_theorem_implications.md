# Table 4d — Theorem Implications

> **Companion to** `theorem1_statement.md` (the theorem) and `theorem1_proof_sketch.md` (the derivation).
> This table is the *consequences* document: what Theorem 1 changes about how a self-evolving system should
> be built and deployed.
>
> **Theorem 1, in one line.** $\Delta_t(\tau) = (1-\tau^2)/2$, hence
> $\tau_c = \sqrt{1 - 2\Delta_t^{\max}}$.
>
> **Assumptions inherited.** Everything below presupposes **(A1)** binary symmetric judge noise with flip
> probability $p = (1-\tau)/2$, **(A2)** two *independent* judgments per round, and **(A3)** agreement
> scoring on a binary task. §3.1 is where (A2) does real work — the calibration estimator is unbiased only
> while the two judgments stay independent — and §4.1 is where (A3) is relaxed to M-ary tasks.

---

## 1. Interpretation of "Judge Scarcity"

**The central point: $\tau_c$ is a function of the tolerated bias, not a constant of the system.**

It is tempting to read "we only have a 55 %-reliable judge" as a fatal limitation. Theorem 1 says the
opposite for a tolerant system. The design rule fixes the *relationship*, and the requirement moves with
the target:

| $\Delta_t^{\max}$ | 0.05 | 0.10 | 0.15 | 0.20 | 0.25 | 0.35 | 0.45 |
|---|---|---|---|---|---|---|---|
| required $\tau_c$ | 0.949 | 0.894 | 0.837 | 0.775 | 0.707 | **0.548** | 0.316 |
| verdict | judge must be near-perfect | | | | | a 55 % judge suffices | almost any signal helps |

**Worked case — $\Delta_t^{\max} = 0.35$.** Then

$$\tau_c = \sqrt{1 - 2(0.35)} = \sqrt{0.30} = 0.5477 \approx 0.55$$

A judge that is wrong on roughly **one verdict in five** still keeps the system inside the safe region.
This is not a hypothetical: it is exactly where the real-API sweep landed, with $\tau_c(B) = \tau_c(D) =
0.55$ measured at the grid's lower edge and $\Delta_t^{\max} = 0.349$ read back off the closed form.

**The flip side — tightening is expensive.** The inverse form is steep near the origin. Halving the
tolerance from 0.20 to 0.10 moves the requirement from $\tau_c = 0.775$ to $0.894$; going to 0.05 demands
$0.949$. Judge scarcity therefore has two regimes:

- **Tolerant regime** ($\Delta_t^{\max} \gtrsim 0.30$): an ordinary formal checker, or even a noisy
  LLM-as-judge, is enough. Cheap judges are usable.
- **Strict regime** ($\Delta_t^{\max} \lesssim 0.15$): only a near-deterministic judge qualifies.
  Cheap judges are *not* usable, and no amount of population/diversity machinery compensates — those
  mechanisms act on the generator bottleneck, not the judge bottleneck.

**Reachability bound.** Because $\Delta_t(0) = 1/2$, the tolerance can never be pushed below $0.5$ no
matter how the system is built. A design targeting $\Delta_t^{\max} < 0.5$ *requires* a judge; there is no
architecture-only path to it.

---

## 2. Practical Guidance

Before deployment, measure **two** quantities — and note that the paper measures both with the same 2400
and 800 rounds of logs already in this repository.

| Quantity | What it is | How to measure it here |
|---|---|---|
| $\tau$ | **judge reliability** — how often the formal anchor's verdict is actually correct | `argus/z3_anchor.py::verify_with_noise` with a known ground truth; or compare anchor verdicts against a hand-audited sample |
| $\Delta_t^{\max}$ | **system tolerance** — the largest evaluation bias the loop can absorb and still improve | task-dependent; for a curriculum loop, the bias at which the difficulty controller starts rewarding unverifiable tasks |

Then apply the decision rule:

$$\boxed{\;\text{safe} \iff \tau \;\ge\; \sqrt{\,1 - 2\,\Delta_t^{\max}\,}\;}$$

**Validate the mechanism before trusting the number.** The §5.5 discriminating test distinguishes the two
candidate mechanisms from a single measured `correct_rate`, with no fitting: the two-independent-judgment
model predicts $(1+\tau^2)/2$ while the judge-plus-acceptance model predicts $\tau^2$. Across the 16
$(\tau, \text{condition})$ cells the two differ by a factor of **six** in MAE (0.0389 vs 0.2291), so the
measurement decides between them outright. Running this check first matters because the acceptance model
implies $\Delta_t = 1-\tau^2$ — exactly twice the correct value — and would therefore mis-set $\tau_c$ by a
wide margin.

If $\tau < \tau_c$ the system **degrades** rather than merely underperforming: a wrong "correct" verdict is
written into memory as a positive example, so the error is *reused* in later rounds. This is what makes the
failure silent — the loop keeps producing logs and keeps reporting success on the rounds it can complete.

**Three practical corollaries:**

1. **Measure τ directly, do not infer it from downstream accuracy.** Downstream accuracy is confounded by
   the generator bottleneck (§4.3); a collapsing valid-task rate looks like a worse judge but is not one.
2. **Report Δ_t under a stated caliber.** §4.2 and `table2c_delta_t_semantics.md` show A = 0.150 / B = 0.000
   under the valid-only caliber versus A = 0.243 / B = 0.245 under the global caliber. The decision rule
   needs the caliber to be fixed before $\Delta_t^{\max}$ means anything.
3. **Budget the bottleneck split.** By the composition law
   $1-\Delta_t^{\text{global}} = (1-\Delta_t^{\text{gen}})(1-\Delta_t^{\text{judge}})$, the judge budget is
   what is *left over*:
   $\Delta_{\text{judge}}^{\text{budget}} = 1 - \frac{1-\Delta_t^{\max}}{1-\Delta_t^{\text{gen}}}$.
   A condition whose generator bottleneck already exceeds $\Delta_t^{\max}$ cannot be rescued by any judge.

---

## 3. New Architecture Direction

Theorem 1 implies the threshold is only actionable if the system *knows* its own $\tau$ and
$\Delta_t^{\max}$ at runtime. Neither is currently instrumented; both are recoverable from data the
architecture already produces. Two modules close the gap.

### 3.1 Judge Calibration Module

**Purpose.** Continuously estimate $\tau$ from the system's own operation.

**Signal.** The anchor already emits three verdict types — `sat`, `unsat`, and `error`/`unknown`. An
`error` verdict carries no truth value and is never flipped (A1), so it is excluded from the estimate. The
calibration channel is **agreement between independent judgments**: by Theorem 1 the observed
round-level `correct_rate` satisfies $\mathbb{E}[\text{correct\_rate}] = (1+\tau^2)/2$, so

$$\hat{\tau} = \sqrt{\,2\cdot\widehat{\text{correct\_rate}} - 1\,}$$

**Guard.** This estimator is only valid while (A2) holds — the two judgments must be genuinely
independent. A shared cache, a shared model call, or a reused seed breaks it, and the failure is
conservative in the dangerous direction (it *overstates* τ). The module must therefore assert
independence: distinct Z3 calls, distinct noise draws, no verdict reuse within a round.

**Cost.** Zero API calls. `argus/z3_anchor.py` already logs `flipped` on every noisy verdict.

### 3.2 Tolerance Assessor

**Purpose.** Estimate $\Delta_t^{\max}$ — the bias the loop can absorb before self-improvement stalls.

**Signal.** The difficulty controller's own state. The pseudo-difficulty trap (§4.3) is precisely the
regime where bias exceeds tolerance: the controller raises the level, the teacher keeps failing, and the
level stays high. The onset of that pattern is an observable proxy for $\Delta_t^{\max}$ being crossed.

**Practical estimator.** Run the curriculum and record the valid-task rate at each level. The tolerance is
the bias at which the level-advance gate stops being earned by real capability. In this repository that
gate is `scripts/difficulty_controller.py` (five consecutive rounds ≥ 80 % valid to advance, three
consecutive < 50 % to retreat).

### 3.3 The combined safety gate

With both quantities available, the deployment check becomes a single comparison evaluated per round:

$$\hat{\tau} \;\ge\; \sqrt{\,1 - 2\,\widehat{\Delta_t^{\max}}\,} \quad ?$$

Failing the gate should **stop the loop or freeze memory writes**, not merely log a warning. A loop that
continues writing experience while below threshold is actively accumulating poisoned positives — the
failure mode the whole framework exists to detect. In the language of §4.4, the gate is the runtime
implementation of the safe-region intersection.

> **Status.** Both modules are architectural proposals, not implemented code. They are listed here because
> Theorem 1 is what makes them well-posed: before the closed form, there was no scalar to compare.

---

## 4. Open Problem

Theorem 1 assumes **binary** tasks. The factor $1/2$ that anchors the curve is the probability that two
independent random verdicts agree on a binary variable — a property of the *task's arity*, not of the
judge.

### 4.1 M-ary tasks

Let the verdict take one of $M$ values and let a flipped judgment land uniformly on one of the other
$M-1$ values, still with flip probability $p = (1-\tau)/2$. Two independent judgments now agree either by
both being correct, or by both flipping **to the same wrong value**:

$$P(\text{agree}) = (1-p)^{2} + \frac{p^{2}}{M-1}
\qquad\Longrightarrow\qquad
\Delta_t(M,\tau) = 1 - (1-p)^{2} - \frac{p^{2}}{M-1}$$

This reduces correctly: at $M = 2$ it returns $(1-\tau^2)/2$ exactly, because $p^2/(M-1) = p^2$.
The bias **increases** with $M$ — a larger answer space makes accidental agreement less likely:

| $\Delta_t$ | M = 2 | M = 3 | M = 5 | M = 10 | M → ∞ |
|---|---|---|---|---|---|
| τ = 0.55 | 0.3488 | 0.3741 | 0.3867 | 0.3938 | 0.3994 |
| τ = 0.80 | 0.1800 | 0.1850 | 0.1875 | 0.1889 | 0.1900 |
| τ = 1.00 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

So the binary case is the **most forgiving** one. Grading a system on continuous or high-arity output
tightens the τ requirement for the same tolerance.

### 4.2 More judgment layers

The other natural axis is the number of independent judgments that must agree. If all $k$ must agree,

$$\Delta_t(k,\tau) = 1 - \left(\frac{1+\tau}{2}\right)^{k} - \left(\frac{1-\tau}{2}\right)^{k}$$

At $k = 2$ this is $(1-\tau^2)/2$; as $k \to \infty$ it tends to 1, since requiring many independent
noisy verdicts to agree eventually becomes impossible. Note that $k = 1$ is **degenerate** under this
form (a single judgment always agrees with itself), which is why the single-judgment case must be handled
separately as Ratchet's $p = (1-\tau)/2$ rather than as a limit of this family.

### 4.3 A candidate simple form, and why to be careful with it

A tempting compact guess is

$$\Delta_t = \frac{1-\tau^{k}}{k}$$

It matches at $k = 2$, giving $(1-\tau^2)/2$. But its base case does not: at $k = 1$ it gives $1-\tau$,
whereas Ratchet's single-judgment bound is $(1-\tau)/2$. Any claimed generalisation in this family must
reproduce **both** known endpoints — $k=1 \Rightarrow (1-\tau)/2$ and $k=2 \Rightarrow (1-\tau^2)/2$ —
and a form that reproduces only one of them should not be presented as a generalisation. The agreement
form in §4.2 and the arity form in §4.1 each reduce correctly on their own axis; a single formula covering
both axes at once is still open.

### 4.4 What would settle it

All three generalisations are testable with the existing harness and **without new theory**: sweep the
judge's answer cardinality (e.g. graded rubric scores instead of SAT/UNSAT) and the number of independent
verification layers, and fit $\Delta_t$ against both. The binary sweep in
`logs/tau_sweep_real/summary.json` already provides the $M=2$, $k=2$ anchor point.
