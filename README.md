# ClaimVerifier

**Standalone GenLayer Intelligent Contract primitive for evidence-based claim verification**

Submit a natural-language claim + supporting/refuting evidence URLs.  
GenLayer validators independently fetch the live evidence, analyse it with an LLM, and reach consensus on a structured decision (`status` + `confidence`) under a custom Equivalence Principle.

This is a reusable building block, not a one-off demo.

---

## Why this exists

Many real-world processes require judgment over unstructured evidence:

- Fact-checking and dispute resolution
- Insurance / parametric claims
- Prediction-market resolution
- DAO proposal evaluation
- Agentic-commerce delivery verification
- Research or audit claim validation

Traditional smart contracts cannot do this. ClaimVerifier turns natural-language claims + live web evidence into consensus-backed on-chain outcomes.

---

## How consensus is used

1. **Leader** fetches every evidence URL and asks an LLM for a structured judgment.
2. **Validators** independently re-fetch the same URLs and produce their own judgment.
3. Equivalence is checked **only on the decision fields**:
   - `status` must match exactly (`supported` | `partially_supported` | `refuted` | `inconclusive`)
   - `confidence` (0–100) may differ by at most 20 points (tolerance for model variance)
4. Free-text reasoning is stored but never used for equivalence.
5. State is updated only after consensus succeeds.

This follows GenLayer best practices for non-deterministic blocks and the Equivalence Principle.

---

## Public interface

### `submit_claim(claim_text: str, evidence_urls_json: str) → str`
- `claim_text`: the natural-language claim
- `evidence_urls_json`: JSON array of URLs, e.g. `'["https://a.com","https://b.com"]'`
- Returns the new `claim_id`

### `resolve_claim(claim_id: str) → str`
Triggers consensus resolution. Returns the accepted JSON result.

### View methods
- `get_claim_count()`
- `get_claim_text(claim_id)`
- `get_claim_submitter(claim_id)`
- `get_claim_evidence(claim_id)`
- `get_claim_status(claim_id)`
- `get_claim_confidence(claim_id)`
- `get_claim_reasoning(claim_id)`
- `is_resolved(claim_id)`

---

## Design goals (why it qualifies as a strong primitive)

- Real multi-source web + LLM consensus
- Clear, minimal state design (TreeMaps of simple types)
- Thoughtful validators (status exact match + confidence tolerance)
- Useful beyond a single demo
- Readable source + documentation so other builders can reuse or extend it

---

## Typical usage flow

1. Caller submits a claim + list of evidence URLs → receives `claim_id`
2. Anyone calls `resolve_claim(claim_id)`
3. Validators reach consensus
4. Status, confidence and reasoning are stored on-chain

---

## License

MIT

---

Built as a clean, reusable primitive for the GenLayer ecosystem.
