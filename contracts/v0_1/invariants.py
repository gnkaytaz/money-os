"""Pure checks over a supplied snapshot. No IO, network, persistence or execution.

Schema/graph validity is separate from TEST eligibility and from semantic truth.
"""

import hashlib
from decimal import Decimal, Inexact, Rounded, localcontext
from urllib.parse import urlsplit

from .definitions import (COLLECTIONS, ContractError, decimal, require, timestamp,
                          validate_structure)


def digest(text):
    try:
        return hashlib.sha256(text.encode("utf-8", errors="strict")).hexdigest()
    except UnicodeError as exc:
        raise ContractError("G-TEXT", "not Unicode scalar text") from exc


def web_url(value):
    try:
        parsed = urlsplit(value)
        require(parsed.scheme in ("http", "https") and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None,
                "G-URL", "public web URL shape required; no network policy implied")
    except ValueError as exc:
        raise ContractError("G-URL", value) from exc


def dependencies(claim):
    if claim["kind"] == "inference":
        return claim["premises"]
    if claim["kind"] == "estimate":
        return [item["claim_id"] for item in claim["formula"]["inputs"]]
    if claim["kind"] == "unknown":
        return claim["context_claims"]
    return []


def claim_quantity(claim):
    if claim["kind"] == "fact":
        return claim["quantity"]
    if claim["kind"] == "estimate":
        return claim["formula"]["result"]
    return None


def evaluate_formula(claim, claims):
    formula = claim["formula"]
    operands = formula["inputs"]
    for operand in operands:
        source = claims[operand["claim_id"]]
        require(claim_quantity(source) is not None, "G-ESTIMATE-INPUT",
                "unknown/inference is not a measured numeric operand")
        require(operand["quantity"] == claim_quantity(source), "G-ESTIMATE-INPUT",
                "copied operand must equal its referenced quantity")
    left, right = [item["quantity"] for item in operands]
    result = formula["result"]
    op = formula["operation"]
    dims = lambda q: (q["unit"], q["currency"], q["period"])
    if op in ("add", "subtract"):
        require(dims(left) == dims(right) == dims(result), "G-UNITS", "add/subtract dimensions")
    elif op == "multiply":
        if left["unit"] == "ratio":
            require(left["period"] == "one_time" and dims(result) == dims(right), "G-UNITS", "ratio multiply")
        elif right["unit"] == "ratio":
            require(right["period"] == "one_time" and dims(result) == dims(left), "G-UNITS", "ratio multiply")
        else:
            hours, rate = (left, right) if left["unit"] == "hour" else (right, left)
            require(hours["unit"] == "hour" and rate["unit"] == "money_per_hour"
                    and rate["period"] == "hour" and result["unit"] == "money"
                    and result["currency"] == rate["currency"]
                    and result["period"] == hours["period"], "G-UNITS", "hours times hourly rate")
    else:
        require(right["unit"] == "ratio" and right["period"] == "one_time"
                and dims(left) == dims(result), "G-UNITS", "division by dimensionless ratio only")
    a, b = decimal(left["value"]), decimal(right["value"])
    require(op != "divide" or b != 0, "G-ARITHMETIC", "zero divisor")
    with localcontext() as ctx:
        ctx.prec = 50
        ctx.traps[Inexact] = True
        ctx.traps[Rounded] = True
        try:
            if op == "add":
                value = a + b
            elif op == "subtract":
                value = a - b
            elif op == "multiply":
                value = a * b
            else:
                value = a / b
        except (Inexact, Rounded) as exc:
            raise ContractError("G-ARITHMETIC", "non-exact result; no silent rounding") from exc
    require(value == decimal(result["value"]), "G-ARITHMETIC", "result does not reproduce")
    require(decimal(formula["range"]["low"]) <= value <= decimal(formula["range"]["high"]),
            "G-ARITHMETIC", "declared assumption range must enclose result")


def validate_graph(doc):
    """Check structure and links; intentionally does NOT grant TEST."""
    validate_structure(doc)
    run = doc["run"]
    start = timestamp(run["created_at"])
    require((run["state"] == "running") == (run["finished_at"] is None), "G-RUN", "terminal time")
    if run["finished_at"] is not None:
        require(timestamp(run["finished_at"]) >= start, "G-TIME", "run completion")
    require((run["state"] in ("failed", "interrupted")) == (run["error"] is not None
            and run["error_stage"] is not None), "G-RUN", "failure reason and stage")
    require(run["parent_run_id"] != run["id"], "G-SCOPE", "run cannot be its own parent")
    indices = {name: {} for name in COLLECTIONS}
    ids = {run["id"]}
    for name in COLLECTIONS:
        for item in doc[name]:
            require(item["id"] not in ids, "G-ID", "unique local entity IDs")
            ids.add(item["id"])
            indices[name][item["id"]] = item
            require(item["run_id"] == run["id"], "G-SCOPE", f"foreign run on {item['id']}")
            require(item["synthetic"] == run["synthetic"], "G-SYNTHETIC", item["id"])
            require(timestamp(item["created_at"]) >= start, "G-TIME", item["id"])
            if name in ("decisions", "tests", "artifacts", "events", "feedback"):
                require(item["actor"]["kind"] == "human", "G-HUMAN", item["id"])
                require(run["finished_at"] is not None and timestamp(item["created_at"]) >=
                        timestamp(run["finished_at"]), "G-TIME", "manual work follows dossier")
            elif run["finished_at"] is not None:
                require(timestamp(item["created_at"]) <= timestamp(run["finished_at"]),
                        "G-TIME", "research snapshot frozen at completion")

    def ref(collection, identifier):
        require(identifier in indices[collection], "G-REF", f"missing/foreign {collection}: {identifier}")
        return indices[collection][identifier]

    def follows(item, previous):
        require(timestamp(item["created_at"]) >= timestamp(previous["created_at"]),
                "G-TIME", f"{item['id']} recorded before {previous['id']}")

    for memory in run["memory_inputs"]:
        require(memory["origin_run_id"] != run["id"], "G-MEMORY", "external historical snapshot, not local entity")
        require(memory["sha256"] == digest(memory["text"]), "G-HASH", "memory snapshot")
        require(memory["selected_by"]["kind"] == "human" and timestamp(memory["selected_at"]) <= start,
                "G-MEMORY", "explicit human selection before run")
    memory_keys = [(m["origin_run_id"], m["feedback_id"]) for m in run["memory_inputs"]]
    require(len(memory_keys) == len(set(memory_keys)), "G-MEMORY", "duplicate memory selection")
    io_keys = [(io["stage"], io["attempt"]) for io in run["model_io"]]
    require(len(io_keys) == len(set(io_keys)), "G-RUN", "duplicate model attempt")
    require(not run["model_io"] or run["model"] is not None, "G-RUN", "model provenance")

    for source in doc["sources"]:
        web_url(source["original_url"])
        web_url(source["final_url"])
        require(source["sha256"] == digest(source["text"]), "G-HASH", source["id"])
        require(len(source["text"]) <= source["char_limit"], "G-SNAPSHOT", "snapshot limit")
        require(timestamp(source["retrieved_at"]) <= timestamp(source["created_at"]), "G-TIME", "retrieval")
        require(source["kind"] != "page" or source["error"] is None, "G-SNAPSHOT", "failed crawl is not page")
    for observation in doc["observations"]:
        source = ref("sources", observation["source_id"])
        follows(observation, source)
        require(observation["end"] <= len(source["text"]) and
                source["text"][observation["start"]:observation["end"]] == observation["quote"],
                "G-QUOTE", "exact Unicode codepoint slice [start,end), no normalization")
    for evidence in doc["evidence"]:
        ref("claims", evidence["claim_id"])
        observation = ref("observations", evidence["observation_id"])
        follows(evidence, observation)
    claims = indices["claims"]
    for claim in doc["claims"]:
        for identifier in dependencies(claim):
            ref("claims", identifier)
        if claim["kind"] == "unknown":
            for identifier in claim["context_sources"]:
                ref("sources", identifier)
            require(not any(e["relation"] == "supports" and e["claim_id"] == claim["id"]
                            for e in doc["evidence"]), "G-UNKNOWN", "no proof of unknown value")
        if claim["kind"] == "fact":
            supports = [e for e in doc["evidence"] if e["claim_id"] == claim["id"]
                        and e["relation"] == "supports" and e["directness"] == "direct"
                        and ref("sources", ref("observations", e["observation_id"])["source_id"])["kind"] == "page"]
            require(bool(supports), "G-FACT", f"direct page quote required: {claim['id']}")

    visiting, visited = set(), set()

    def visit(identifier):
        require(identifier not in visiting, "G-DAG", "cyclic Claim dependencies")
        if identifier in visited:
            return
        visiting.add(identifier)
        for parent in dependencies(claims[identifier]):
            visit(parent)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in claims:
        visit(identifier)
    for claim in doc["claims"]:
        if claim["kind"] == "estimate":
            evaluate_formula(claim, claims)

    def has_anchor(identifier, seen=None):
        seen = set() if seen is None else seen
        if identifier in seen:
            return False
        seen.add(identifier)
        claim = claims[identifier]
        return claim["kind"] == "fact" or (claim["kind"] != "unknown" and any(
            has_anchor(parent, seen) for parent in dependencies(claim)))

    for claim in doc["claims"]:
        if claim["kind"] in ("inference", "estimate"):
            require(has_anchor(claim["id"]), "G-ANCHOR", "derived claim needs path to observation")

    require(len(doc["problems"]) <= 1 and len(doc["opportunities"]) <= 1,
            "G-CARDINALITY", "one dossier per run")
    require((run["state"] == "completed") == bool(doc["opportunities"]), "G-RUN", "dossier outcome")
    if run["state"] == "insufficient_evidence":
        require(not doc["problems"] and not doc["opportunities"], "G-ANCHOR", "no fabricated candidate")
    for problem in doc["problems"]:
        for identifier in problem["fields"].values():
            ref("claims", identifier)
        require(has_anchor(problem["fields"]["discrepancy"]), "G-ANCHOR", "problem needs observable support")
    for opportunity in doc["opportunities"]:
        problem = ref("problems", opportunity["problem_id"])
        for identifier in opportunity["fields"].values():
            ref("claims", identifier)
        if any(claims[i]["kind"] == "unknown" for i in
               list(problem["fields"].values()) + list(opportunity["fields"].values())):
            require(opportunity["completeness"] == "incomplete_candidate", "G-COMPLETENESS", "explicit unknowns")
    for decision in doc["decisions"]:
        ref("opportunities", decision["opportunity_id"])
        require(decision["dossier_version"] == run["dossier_version"], "G-VERSION", "decision dossier snapshot")
        reviewed = [a["claim_id"] for a in decision["review"]["claims"]]
        require(len(reviewed) == len(set(reviewed)), "G-ID", "duplicate review assertion")
        for identifier in reviewed + decision["review"]["gap_claim_ids"]:
            ref("claims", identifier)
        if decision["plan"] is not None:
            for key in ("hypothesis_claim", "useful_result_claim", "success_claim", "kill_claim"):
                ref("claims", decision["plan"][key])
            require(decision["plan"]["recipient"]["synthetic"] == run["synthetic"], "G-SYNTHETIC", "recipient")
            require(timestamp(decision["plan"]["response_deadline"]) > timestamp(decision["created_at"]),
                    "G-TIME", "future response deadline at decision")
    decisions_used = set()
    for test in doc["tests"]:
        decision = ref("decisions", test["decision_id"])
        require(decision["action"] == "TEST", "G-TEST", "test requires TEST decision")
        require(test["opportunity_id"] == decision["opportunity_id"] and test["plan"] == decision["plan"],
                "G-TEST", "test cannot silently change authorized plan")
        require(decision["id"] not in decisions_used, "G-CARDINALITY", "one test per decision")
        decisions_used.add(decision["id"])
        follows(test, decision)
        require(timestamp(test["created_at"]) < timestamp(test["plan"]["response_deadline"]),
                "G-TIME", "test before deadline")
    versions = set()
    for artifact in doc["artifacts"]:
        test = ref("tests", artifact["test_id"])
        follows(artifact, test)
        key = (test["id"], artifact["version"])
        require(key not in versions, "G-IMMUTABLE", "one ID per test version")
        versions.add(key)
        if artifact["version"] == 1:
            require(artifact["previous_version_id"] is None, "G-VERSION", "first version has no parent")
        else:
            previous = ref("artifacts", artifact["previous_version_id"])
            require(previous["test_id"] == test["id"] and previous["version"] + 1 == artifact["version"],
                    "G-VERSION", "contiguous immutable version chain")
            follows(artifact, previous)
        for identifier in artifact["claim_ids"]:
            ref("claims", identifier)
        if artifact["content"]["kind"] == "text":
            require(artifact["content"]["sha256"] == digest(artifact["content"]["text"]), "G-HASH", "artifact")
        else:
            web_url(artifact["content"]["url"])
    for event in doc["events"]:
        test = ref("tests", event["test_id"])
        follows(event, test)
        occurred = timestamp(event["occurred_at"])
        require(timestamp(test["created_at"]) <= occurred <= timestamp(event["created_at"]), "G-TIME", "event time")
        if event["kind"] == "sent":
            artifact = ref("artifacts", event["artifact_id"])
            require(artifact["test_id"] == test["id"], "G-ARTIFACT-TEST", "sent artifact belongs to same test")
            require(timestamp(artifact["created_at"]) <= occurred, "G-TIME", "prepare before send")
            require(event["recipient_alias"] == test["plan"]["recipient"]["alias"] and
                    event["channel"] == test["plan"]["channel"], "G-TEST", "sent authorized recipient/channel")
        else:
            sent = ref("events", event["sent_id"])
            require(sent["kind"] == "sent" and sent["test_id"] == test["id"], "G-EVENT", "same-test sent required")
            follows(event, sent)
            require(timestamp(sent["occurred_at"]) <= occurred, "G-TIME", "send precedes outcome")
            if event["kind"] in ("interested", "rejected"):
                responded = ref("events", event["responded_id"])
                require(responded["kind"] == "responded" and responded["test_id"] == test["id"]
                        and responded["sent_id"] == sent["id"], "G-EVENT", "response before interpretation")
                follows(event, responded)
                require(timestamp(responded["occurred_at"]) <= occurred, "G-TIME", "response time")
            if event["kind"] == "no_response":
                require(event["channel_checked"] and timestamp(test["plan"]["response_deadline"]) <=
                        timestamp(event["checked_at"]) == occurred, "G-DEADLINE", "manual check after deadline")
                require(not any(e["test_id"] == test["id"] and e["kind"] in
                        ("responded", "interested", "rejected", "meeting", "paid") and
                        timestamp(e["occurred_at"]) <= occurred for e in doc["events"]),
                        "G-NO-RESPONSE", "known response before no_response")
            if event["kind"] == "meeting":
                when = timestamp(event["meeting_at"])
                require((event["status"] == "scheduled" and when >= occurred) or
                        (event["status"] == "held" and when == occurred), "G-TIME", "meeting status/time")
            if event["kind"] == "paid":
                require(timestamp(event["paid_at"]) == occurred, "G-TIME", "observed payment time")
        if event["correction_of"] is None:
            require(event["correction_reason"] is None, "G-CORRECTION", "no unexplained correction")
        else:
            previous = ref("events", event["correction_of"])
            require(previous["id"] != event["id"] and previous["test_id"] == test["id"]
                    and previous["kind"] == event["kind"] and event["correction_reason"] is not None
                    and timestamp(previous["created_at"]) < timestamp(event["created_at"]),
                    "G-CORRECTION", "append-only same-kind correction")
    for feedback in doc["feedback"]:
        ref("opportunities", feedback["opportunity_id"])
        for identifier in feedback["claim_ids"]:
            ref("claims", identifier)
        if feedback["kind"] == "research":
            parent = ref("decisions", feedback["decision_id"])
            require(parent["opportunity_id"] == feedback["opportunity_id"], "G-FEEDBACK", "decision opportunity")
        else:
            parent = ref("events", feedback["event_id"])
            test = ref("tests", feedback["test_id"])
            require(parent["test_id"] == test["id"] and test["opportunity_id"] == feedback["opportunity_id"],
                    "G-FEEDBACK", "outcome event/test/opportunity")
        follows(feedback, parent)
    return indices


def test_gate(doc, decision):
    """Return denial IDs from explicit human assertions, never infer semantics.

    Call only after validate_graph. Candidate validity alone is NOT permission.
    """
    denied = []
    review = decision["review"]
    if decision["action"] != "TEST" or decision["actor"]["kind"] != "human":
        denied.append("T-HUMAN")
    if decision["plan"] is None:
        denied.append("T-PLAN")
    if not all(review[key] for key in ("sources_reviewed", "contradictions_reviewed", "risks_accepted")):
        denied.append("T-REVIEW")
    verdicts = {a["claim_id"]: a["verdict"] for a in review["claims"]}
    claims = {c["id"]: c for c in doc["claims"]}
    # Whole small dossier, including negative evidence and unknowns, is reviewed.
    if set(verdicts) != set(claims) or "unsupported" in verdicts.values():
        denied.append("T-SEMANTICS")
    for identifier, verdict in verdicts.items():
        if (claims[identifier]["kind"] == "fact" and verdict != "supported") or (
                claims[identifier]["kind"] == "unknown" and verdict != "unknown"):
            denied.append("T-SEMANTICS")
    if not review["problem_supported"]:
        denied.append("T-PROBLEM")
    if not review["recipient_reachable"]:
        denied.append("T-RECIPIENT")
    # A positive, reviewed residual gap is required to override an adequate solution.
    if review["existing_solution"] == "adequate":
        gaps = review["gap_claim_ids"]
        if not review["residual_gap_verified"] or not gaps or any(
                claims[i]["kind"] != "fact" or verdicts.get(i) != "supported" for i in gaps):
            denied.append("T-EXISTING")
    return sorted(set(denied))


def validate_snapshot(doc):
    validate_graph(doc)
    for decision in doc["decisions"]:
        if decision["action"] == "TEST":
            denials = test_gate(doc, decision)
            require(not denials, denials[0] if denials else "T-GATE", ", ".join(denials))


def validate_extension(before, after):
    """Contract-only append check; no storage or locking guarantee."""
    validate_snapshot(before)
    validate_snapshot(after)
    require(before["run"] == after["run"], "G-IMMUTABLE", "run/dossier frozen")
    for collection in COLLECTIONS:
        old = {x["id"]: x for x in before[collection]}
        new = {x["id"]: x for x in after[collection]}
        require(all(new.get(key) == value for key, value in old.items()), "G-IMMUTABLE", collection)
        if collection in ("sources", "observations", "claims", "evidence", "problems", "opportunities"):
            require(old == new, "G-IMMUTABLE", "new research requires new run")


def source_families(doc):
    """Conservative groups by declared origin, exact URL OR text hash.

    Group count is NOT a claim of independence; undeclared reprints need review.
    """
    groups = []
    for source in doc["sources"]:
        keys = {("origin", source["origin_key"]), ("url", source["final_url"]), ("hash", source["sha256"])}
        members = {source["id"]}
        remaining = groups[:]
        # Revisit earlier groups when a later match bridges their keys.
        while True:
            matching = [(k, m) for k, m in remaining if keys & k]
            if not matching:
                break
            remaining = [(k, m) for k, m in remaining if not keys & k]
            for old_keys, old_members in matching:
                keys |= old_keys
                members |= old_members
        groups = remaining + [(keys, members)]
    return sorted(sorted(members) for _, members in groups)
