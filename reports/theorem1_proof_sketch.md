# Proof Sketch

> **Companion to** `theorem1_statement.md`. This document expands the derivation sketched in §5.4,
> labelling **every path with its probability and its error contribution**.
>
> **Read this first.** The three-path decomposition below is *not* the one an acceptance-based model would
> give. Under agreement scoring, **the path where both judgments flip is scored as correct**, so it
> contributes **zero** error. The entire bias is carried by the single-flip path. Getting this wrong is
> what produces the rejected $\Delta_t = 1-\tau^2$; see §Remarks.

---

## Setup

Let the two judgments of round $i$ be independent Bernoulli variables describing whether the judgment
**flips** its verdict:

$$F_1, F_2 \;\overset{\text{iid}}{\sim}\; \mathrm{Bernoulli}(p),
\qquad p \;=\; \frac{1-\tau}{2}$$

so that each judgment is correct with probability

$$1-p \;=\; \frac{1+\tau}{2}$$

and the two are independent by (A2). Verdicts of type `error` / `unknown` are never flipped, so they are
outside the model (A1).

Define the round-level **error indicator**. By (A3) a round is scored correct exactly when the two
verdicts agree, i.e. when $F_1 = F_2$:

$$E_i \;=\; \mathbb{1}\!\left[\,F_1 \neq F_2\,\right]$$

The evaluation bias is the expectation of this indicator:

$$\Delta_t(\tau) \;=\; \mathbb{E}[E_i] \;=\; \sum_{\text{paths}} \Pr(\text{path}) \cdot \underbrace{\mathbb{E}[E_i \mid \text{path}]}_{\text{contribution}}$$

The three paths are exhaustive because $(F_1,F_2)$ has exactly four outcomes and the two "agree" outcomes
collapse into two paths.

---

## Path decomposition

### Path 1 — both judgments unflipped (both correct)

$$F_1 = 0,\; F_2 = 0$$

**Probability.** Independence gives

$$\Pr(\text{Path 1}) \;=\; (1-p)^{2} \;=\; \left(\frac{1+\tau}{2}\right)^{2}$$

**Verdicts.** Both judgments return the true verdict, so they **agree**.

**Scored.** Correct.

**Contribution.**

$$\mathbb{E}[E_i \mid \text{Path 1}] \;=\; 0$$

### Path 2 — exactly one judgment flips

$$(F_1, F_2) \in \{(1,0),\,(0,1)\}$$

**Probability.** Two disjoint orderings, each with probability $p(1-p)$:

$$\Pr(\text{Path 2}) \;=\; 2\,p\,(1-p) \;=\; 2 \cdot \frac{1-\tau}{2} \cdot \frac{1+\tau}{2} \;=\; \frac{1-\tau^{2}}{2}$$

**Verdicts.** One judgment returns the truth and the other its negation, so they **disagree**.

**Scored.** Incorrect.

**Contribution.**

$$\mathbb{E}[E_i \mid \text{Path 2}] \;=\; 1$$

> **This path carries the entire bias.** Its probability *is* the answer, because its contribution is
> exactly 1.

### Path 3 — both judgments flipped (both wrong)

$$F_1 = 1,\; F_2 = 1$$

**Probability.**

$$\Pr(\text{Path 3}) \;=\; p^{2} \;=\; \left(\frac{1-\tau}{2}\right)^{2}$$

**Verdicts.** Both judgments return the *negation* of the truth — so they still **agree with each other**.

**Scored.** Correct. The system has no way to detect the joint error, because agreement is the only
signal it has.

**Contribution.**

$$\mathbb{E}[E_i \mid \text{Path 3}] \;=\; 0$$

> **This is the step that is easy to get wrong.** Path 3 is *doubly wrong* yet contributes *zero* measured
> bias. Treating it as an error path (contribution $1$, or even $1/2$) yields a formula that contradicts
> the measured data by more than a factor of two.

---

## Aggregation

Summing the path contributions weighted by their probabilities:

$$
\begin{aligned}
\Delta_t(\tau)
&= \underbrace{\left(\frac{1+\tau}{2}\right)^{2}}_{\text{Path 1}} \cdot 0
 \;+\; \underbrace{\frac{1-\tau^{2}}{2}}_{\text{Path 2}} \cdot 1
 \;+\; \underbrace{\left(\frac{1-\tau}{2}\right)^{2}}_{\text{Path 3}} \cdot 0 \\[4pt]
&= \frac{1-\tau^{2}}{2}
\end{aligned}
$$

Equivalently, in closed form over both agreement paths, the success probability is

$$
\begin{aligned}
P(\text{correct}) \;=\; 1-\Delta_t(\tau)
&= \left(\frac{1+\tau}{2}\right)^{2} + \left(\frac{1-\tau}{2}\right)^{2} \\[4pt]
&= \frac{(1+\tau)^{2} + (1-\tau)^{2}}{4}
 \;=\; \frac{2 + 2\tau^{2}}{4}
 \;=\; \frac{1+\tau^{2}}{2}
\end{aligned}
$$

The two cross terms of the expansion cancel, which is where the pure $\tau^2$ dependence comes from.
Therefore

$$\boxed{\;\Delta_t(\tau) \;=\; 1 - \frac{1+\tau^{2}}{2} \;=\; \frac{1-\tau^{2}}{2}\;}$$

**Inverse.** Solving $\Delta_t = (1-\tau^2)/2$ for τ:

$$2\Delta_t = 1-\tau^{2}
\quad\Longrightarrow\quad
\tau^{2} = 1-2\Delta_t
\quad\Longrightarrow\quad
\tau_c = \sqrt{\,1-2\,\Delta_t^{\max}\,}$$

---

## Boundary checks

| τ | Path 1 $(1{+}\tau)^2/4$ | Path 2 $(1{-}\tau^2)/2$ | Path 3 $(1{-}\tau)^2/4$ | $\Delta_t$ | note |
|---|---|---|---|---|---|
| 0.00 | 0.2500 | 0.5000 | 0.2500 | **0.5000** | reachability bound: random verdicts agree half the time |
| 0.50 | 0.5625 | 0.3750 | 0.0625 | **0.3750** | |
| **0.55** | 0.6006 | **0.3488** | 0.0506 | **0.3488** | grid lower edge; observed 0.3000 (B) / 0.3200 (D) |
| 0.80 | 0.8100 | 0.1800 | 0.0100 | **0.1800** | observed 0.1800 (B) — exact agreement |
| 0.95 | 0.9506 | 0.0488 | 0.0006 | **0.0488** | Ratchet bound gives 0.0250 at the same τ |
| 1.00 | 1.0000 | 0.0000 | 0.0000 | **0.0000** | perfect judge: the anchor's verdict *is* ground truth |

Probabilities sum to 1 in every row ($\text{Path 1} + \text{Path 2} + \text{Path 3} = 1$), and only the
Path 2 column ever contributes, so $\Delta_t$ is exactly the Path 2 column read off.

**τ = 0.5 gives Δ_t = 0.375**, matching the boundary value quoted in the theorem statement.

**τ = 0.55 gives Δ_t = 0.34875 ≈ 0.349**, which is the value quoted as $\Delta_t^{\max}$ in the theorem
statement and marked in Figure 5c — it is the tolerance implied by the measured $\tau_c = 0.55$.

---

## Remarks

### Remark A — where the $\tau^{2}$ comes from

It is the sum of the two **agreement** terms,
$\left(\frac{1+\tau}{2}\right)^{2} + \left(\frac{1-\tau}{2}\right)^{2}$, whose cross terms cancel. The
exponent 2 is therefore the **number of independent judgments per round** — it is a property of the
system's structure, not of the judge. This is the pivot that turns Theorem 1 into a design rule: adding an
independent judgment layer changes the exponent without touching τ.

### Remark B — relation to Ratchet

Ratchet (2026) gives $\Delta_t^{\text{Ratchet}} = p = (1-\tau)/2$ for the **single**-judgment case, where
one verdict is produced and acted upon. Theorem 1's quantity is the probability that exactly one of **two**
judgments flips:

$$\Delta_t^{\text{Theorem 1}} \;=\; 2p(1-p)$$

The two coincide to first order as $p \to 0$:

$$2p(1-p) \;\xrightarrow{\;p\to 0\;}\; 2p \;=\; 1-\tau$$

and diverge quadratically away from it. At τ = 0.95 the single-judgment bound predicts 0.0250 while
Theorem 1 predicts 0.0488 — requiring two independent verdicts to agree costs a factor of two in tolerated
error at that reliability.

> Note the direction: Theorem 1's bound is **looser** in τ but the quantity it bounds is a **different
> quantity**. Ratchet asks "how often is the judgment wrong"; Theorem 1 asks "how often do two judgments
> disagree". They are the same only in the noiseless limit.

### Remark C — why the acceptance model fails

If instead the system accepted the judge's verdict with probability τ and otherwise overrode it with its
own (also unreliable) evaluation, the correct outcome would require **both** events:

$$P(\text{correct}) = \tau \cdot \tau = \tau^{2} \qquad\Longrightarrow\qquad \Delta_t = 1-\tau^{2}$$

The three "incorrect" paths of that model — judge-correct-but-overridden $\tau(1-\tau)$, judge-wrong-but-
accepted $(1-\tau)\tau$, and both-wrong $(1-\tau)^{2}$ — sum to

$$\tau(1-\tau) + (1-\tau)\tau + (1-\tau)^{2} \;=\; (1-\tau)(1+\tau) \;=\; 1-\tau^{2}$$

i.e. exactly $1-\tau^2$. At τ = 0.55 that is **0.6975**, against a measured 0.3000 / 0.3200. The model is
rejected in §5.5 by the discriminating test (MAE 0.2291 vs 0.0389) and is not used anywhere in this paper.

### Remark D — scope and limits

- The theorem assumes the two judgments are **independent**. If they share a noise source — e.g. the same
  cached verdict, or a correlated model failure — the cross terms no longer cancel and $\Delta_t$ is
  bounded below by the shared-failure probability even at $\tau = 1$.
- The theorem assumes **binary** tasks. The factor $1/2$ is the random-agreement probability of a binary
  variable; for M-ary tasks it becomes $1/M$. See Open Problem 1 in `table4d_theorem_implications.md`.
- The theorem bounds the **evaluation bias**, not the **learning outcome**. A system with
  $\Delta_t < \Delta_t^{\max}$ can still fail to improve for reasons orthogonal to judge quality.
