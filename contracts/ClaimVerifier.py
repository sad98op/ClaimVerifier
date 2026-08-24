# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json
import typing


class ClaimVerifier(gl.Contract):
    """
    ClaimVerifier — Evidence-Based Claim Verification Primitive

    Submit a natural-language claim + evidence URLs.
    Validators independently fetch evidence and reach consensus
    on status + confidence under the Equivalence Principle.

    Consensus pattern follows the supported leader/validator flow:
    all gl.nondet.* calls live inside leader_fn; validators re-run
    the same function and compare only decision fields.
    """

    next_claim_id: u256
    claim_texts: TreeMap[str, str]
    claim_submitters: TreeMap[str, str]
    claim_evidence: TreeMap[str, str]
    claim_status: TreeMap[str, str]
    claim_confidence: TreeMap[str, u256]
    claim_reasoning: TreeMap[str, str]
    claim_resolved: TreeMap[str, bool]

    def __init__(self):
        self.next_claim_id = u256(0)

    @gl.public.write
    def submit_claim(self, claim_text: str, evidence_urls_json: str) -> str:
        if not claim_text or not claim_text.strip():
            raise gl.vm.UserError("claim_text must be non-empty")

        try:
            urls = json.loads(evidence_urls_json)
        except Exception:
            raise gl.vm.UserError("evidence_urls_json must be valid JSON array of strings")

        if not isinstance(urls, list) or len(urls) == 0:
            raise gl.vm.UserError("at least one evidence URL is required")
        if len(urls) > 5:
            raise gl.vm.UserError("maximum 5 evidence URLs allowed")

        cleaned = [str(u).strip() for u in urls if str(u).strip()]
        if not cleaned:
            raise gl.vm.UserError("no valid evidence URLs")

        claim_id = str(self.next_claim_id)
        self.next_claim_id += u256(1)

        self.claim_texts[claim_id] = claim_text.strip()
        self.claim_submitters[claim_id] = str(gl.message.sender_address)
        self.claim_evidence[claim_id] = json.dumps(cleaned)
        self.claim_status[claim_id] = "pending"
        self.claim_confidence[claim_id] = u256(0)
        self.claim_reasoning[claim_id] = ""
        self.claim_resolved[claim_id] = False

        return claim_id

    @gl.public.write
    def resolve_claim(self, claim_id: str) -> str:
        if claim_id not in self.claim_texts:
            raise gl.vm.UserError(f"claim {claim_id} does not exist")
        if self.claim_resolved.get(claim_id, False):
            raise gl.vm.UserError(f"claim {claim_id} is already resolved")

        claim_text = self.claim_texts[claim_id]
        evidence_urls = json.loads(self.claim_evidence[claim_id])

        def leader_fn() -> dict:
            # All nondet calls must be reachable inside this function
            # so the GenVM linter recognizes the supported consensus flow.
            evidence_blocks: list[str] = []
            fetch_errors = 0

            for i, url in enumerate(evidence_urls):
                try:
                    resp = gl.nondet.web.get(url)
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    text = resp.body.decode("utf-8", errors="replace")[:12000]
                    evidence_blocks.append(f"--- Evidence {i+1} ({url}) ---\n{text}")
                except Exception as e:
                    fetch_errors += 1
                    evidence_blocks.append(
                        f"--- Evidence {i+1} ({url}) ---\n[FETCH FAILED: {type(e).__name__}]"
                    )

            if fetch_errors == len(evidence_urls):
                return {
                    "status": "inconclusive",
                    "confidence": 0,
                    "reasoning": "All evidence URLs failed to fetch.",
                }

            evidence_blob = "\n\n".join(evidence_blocks)

            prompt = f"""
You are a careful evidence analyst. Evaluate the following claim strictly against the provided evidence.

Claim:
\"\"\"{claim_text}\"\"\"

Evidence:
{evidence_blob}

Respond with ONLY a valid JSON object (no markdown, no extra text) containing exactly these keys:
- "status": one of ["supported", "partially_supported", "refuted", "inconclusive"]
- "confidence": integer from 0 to 100
- "reasoning": a short string (max 2 sentences) explaining the decision

Rules:
- "supported" = the evidence clearly and directly supports the claim.
- "partially_supported" = some important parts are supported, others are missing or weak.
- "refuted" = the evidence clearly contradicts the claim.
- "inconclusive" = evidence is insufficient, ambiguous, or contradictory without a clear direction.
- Base the decision only on the supplied evidence; do not use outside knowledge.
- Be conservative: when in doubt prefer "inconclusive" or lower confidence.
"""
            raw = gl.nondet.exec_prompt(prompt, response_format="json")

            if isinstance(raw, str):
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw.rsplit("```", 1)[0]
                data = json.loads(raw)
            elif isinstance(raw, dict):
                data = raw
            else:
                raise gl.vm.UserError(f"Unexpected LLM response type: {type(raw)}")

            status = str(data.get("status", "")).strip().lower()
            if status not in (
                "supported",
                "partially_supported",
                "refuted",
                "inconclusive",
            ):
                raise gl.vm.UserError(f"Invalid status returned: {status}")

            conf = data.get("confidence", 0)
            try:
                conf_int = int(round(float(conf)))
            except (TypeError, ValueError):
                raise gl.vm.UserError(f"Non-numeric confidence: {conf}")
            conf_int = max(0, min(100, conf_int))

            reasoning = str(data.get("reasoning", "")).strip()
            if len(reasoning) > 600:
                reasoning = reasoning[:600]

            return {
                "status": status,
                "confidence": conf_int,
                "reasoning": reasoning,
            }

        def validator_fn(leader_result) -> bool:
            # Supported pattern: check leader success, re-run leader_fn independently,
            # compare only decision fields (status exact + confidence band).
            if not isinstance(leader_result, gl.vm.Return):
                return False

            leader_data = leader_result.calldata
            if not isinstance(leader_data, dict):
                return False

            status = leader_data.get("status")
            conf = leader_data.get("confidence")
            if status not in (
                "supported",
                "partially_supported",
                "refuted",
                "inconclusive",
            ):
                return False
            if not isinstance(conf, (int, float)) or not (0 <= conf <= 100):
                return False

            try:
                own = leader_fn()
            except Exception:
                return False

            if own["status"] != status:
                return False
            if abs(int(own["confidence"]) - int(conf)) > 20:
                return False
            return True

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        self.claim_status[claim_id] = result["status"]
        self.claim_confidence[claim_id] = u256(int(result["confidence"]))
        self.claim_reasoning[claim_id] = result["reasoning"]
        self.claim_resolved[claim_id] = True

        return json.dumps(result, sort_keys=True)

    @gl.public.view
    def get_claim_count(self) -> u256:
        return self.next_claim_id

    @gl.public.view
    def get_claim_text(self, claim_id: str) -> str:
        return self.claim_texts.get(claim_id, "")

    @gl.public.view
    def get_claim_submitter(self, claim_id: str) -> str:
        return self.claim_submitters.get(claim_id, "")

    @gl.public.view
    def get_claim_evidence(self, claim_id: str) -> str:
        return self.claim_evidence.get(claim_id, "[]")

    @gl.public.view
    def get_claim_status(self, claim_id: str) -> str:
        return self.claim_status.get(claim_id, "")

    @gl.public.view
    def get_claim_confidence(self, claim_id: str) -> u256:
        return self.claim_confidence.get(claim_id, u256(0))

    @gl.public.view
    def get_claim_reasoning(self, claim_id: str) -> str:
        return self.claim_reasoning.get(claim_id, "")

    @gl.public.view
    def is_resolved(self, claim_id: str) -> bool:
        return self.claim_resolved.get(claim_id, False)
