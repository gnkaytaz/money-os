"""Closed v0.1 record definitions, checked explicitly using only the stdlib.

This is not a JSON Schema implementation or a runtime application model.
All keys are required (nullable is explicit); extra keys and coercion fail.
"""

import json
import re
from datetime import datetime
from decimal import Decimal


class ContractError(ValueError):
    def __init__(self, invariant, detail):
        self.invariant = invariant
        super().__init__(f"{invariant}: {detail}")


def require(condition, invariant, detail):
    if not condition:
        raise ContractError(invariant, detail)


def load_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "S-JSON", f"duplicate key {key}")
            result[key] = value
        return result

    def constant(value):
        raise ContractError("S-JSON", f"non-JSON constant {value}")

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError("S-JSON", str(exc)) from exc


def record(value, fields):
    """Small exact-key/type assertion, not a recursive schema interpreter."""
    require(type(value) is dict, "S-SHAPE", "expected object")
    require(set(value) == set(fields), "S-SHAPE",
            f"missing={set(fields) - set(value)}, extra={set(value) - set(fields)}")
    for key, expected in fields.items():
        allowed = expected if type(expected) is tuple else (expected,)
        require(type(value[key]) in allowed, "S-TYPE", key)
        if type(value[key]) is str:
            require(bool(value[key].strip()), "S-TYPE", f"empty {key}")


NULL = type(None)
TEXT_OR_NULL = (str, NULL)
COMMON = dict(id=str, run_id=str, synthetic=bool, created_at=str, actor=dict)
COLLECTIONS = ("sources", "observations", "claims", "evidence", "problems",
               "opportunities", "decisions", "tests", "artifacts", "events", "feedback")
PROBLEM_FIELDS = ("discrepancy", "segment", "bearer", "cost", "frequency",
                  "workaround", "gap")
OPPORTUNITY_FIELDS = ("buyer", "reachable_buyer", "valuable_result", "wedge",
                      "key_unknown", "next_test", "success", "kill", "objections",
                      "existing_solution")
EVENT_KINDS = ("sent", "responded", "interested", "rejected", "no_response",
               "meeting", "paid")


def choice(value, options):
    require(value in options, "S-ENUM", f"{value!r} not in {options}")


def timestamp(value):
    require(type(value) is str and bool(re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value)),
        "S-TIME", "timestamp must have timezone and seconds")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("S-TIME", value) from exc
    require(parsed.utcoffset() is not None, "S-TIME", value)
    return parsed


def strings(values, nonempty=False):
    require(type(values) is list and all(type(x) is str and x.strip() for x in values),
            "S-TYPE", "expected list of nonempty strings")
    require(len(values) == len(set(values)), "S-SHAPE", "duplicate list member")
    require(not nonempty or bool(values), "S-SHAPE", "empty list")


def decimal(value):
    require(type(value) is str and bool(re.fullmatch(r"-?(?:0|[1-9]\d{0,17})(?:\.\d{1,6})?", value)),
            "S-DECIMAL", "bounded base-10 string required (18 integer / 6 fractional digits)")
    return Decimal(value)


def quantity(value):
    record(value, dict(value=str, unit=str, currency=TEXT_OR_NULL, period=str))
    decimal(value["value"])
    choice(value["unit"], ("money", "money_per_hour", "hour", "count", "ratio"))
    choice(value["period"], ("one_time", "month", "week", "hour", "unspecified"))
    if value["unit"] in ("money", "money_per_hour"):
        require(type(value["currency"]) is str and bool(re.fullmatch(r"[A-Z]{3}", value["currency"])),
                "S-UNIT", "money requires ISO-style currency code")
    else:
        require(value["currency"] is None, "S-UNIT", "non-money has no currency")


def actor(value):
    record(value, dict(kind=str, id=str))
    choice(value["kind"], ("human", "model", "system"))


def entity(value, fields):
    record(value, COMMON | fields)
    timestamp(value["created_at"])
    actor(value["actor"])


def plan(value):
    record(value, dict(hypothesis_claim=str, useful_result_claim=str,
                      recipient=dict, channel=str, artifact_plan=str,
                      success_claim=str, kill_claim=str, spend_limit=dict,
                      response_deadline=str))
    record(value["recipient"], dict(alias=str, role=str, organization=str, synthetic=bool))
    choice(value["channel"], ("manual_email", "manual_in_person"))
    quantity(value["spend_limit"])
    require(value["spend_limit"]["unit"] == "money" and
            decimal(value["spend_limit"]["value"]) >= 0, "S-UNIT", "nonnegative money budget")
    timestamp(value["response_deadline"])


def validate_structure(doc):
    record(doc, dict(contract_version=str, run=dict) | {k: list for k in COLLECTIONS})
    choice(doc["contract_version"], ("0.1",))
    run = doc["run"]
    record(run, dict(id=str, synthetic=bool, created_at=str, actor=dict, query=dict,
                     state=str, finished_at=TEXT_OR_NULL, error=TEXT_OR_NULL,
                     error_stage=TEXT_OR_NULL, model=TEXT_OR_NULL, prompt_version=str,
                     schema_version=str, model_io=list, memory_inputs=list,
                     parent_run_id=TEXT_OR_NULL, dossier_version=str))
    actor(run["actor"])
    timestamp(run["created_at"])
    if run["finished_at"] is not None:
        timestamp(run["finished_at"])
    choice(run["state"], ("running", "completed", "insufficient_evidence", "failed", "interrupted"))
    choice(run["schema_version"], ("0.1",))
    record(run["query"], dict(question=str, segment=str, constraints=list,
                             primary_search=str, counter_search=str, search_limit=int, page_limit=int))
    strings(run["query"]["constraints"], True)
    require(1 <= run["query"]["search_limit"] <= 8 and 1 <= run["query"]["page_limit"] <= 5,
            "S-LIMIT", "search/page budgets")
    require(len(run["memory_inputs"]) <= 12, "S-LIMIT", "memory budget")
    for memory in run["memory_inputs"]:
        record(memory, dict(origin_run_id=str, feedback_id=str, kind=str, text=str,
                            sha256=str, selected_by=dict, selected_at=str))
        choice(memory["kind"], ("research", "outcome"))
        actor(memory["selected_by"])
        timestamp(memory["selected_at"])
    for io in run["model_io"]:
        record(io, dict(stage=str, attempt=int, input=str, output=str, at=str))
        choice(io["stage"], ("extract", "synthesize"))
        require(io["attempt"] in (1, 2), "S-LIMIT", "at most one repair")
        timestamp(io["at"])

    for source in doc["sources"]:
        entity(source, dict(original_url=str, final_url=str, title=str, kind=str,
                            publisher=TEXT_OR_NULL, published_at=TEXT_OR_NULL,
                            retrieved_at=str, search_query=str, rank=int, method=str,
                            text=str, sha256=str, normalization=str, truncated=bool,
                            char_limit=int, error=TEXT_OR_NULL, origin_key=str,
                            dependence=str, dependence_note=str, trust=str))
        choice(source["kind"], ("page", "snippet"))
        choice(source["method"], ("manual_snapshot", "crawler", "search"))
        choice(source["normalization"], ("none-codepoints-v1",))
        choice(source["dependence"], ("declared_original", "reprint", "unknown"))
        choice(source["trust"], ("untrusted",))
        timestamp(source["retrieved_at"])
        if source["published_at"] is not None:
            timestamp(source["published_at"])
        require(source["rank"] > 0 and source["char_limit"] > 0, "S-LIMIT", "source limits")

    for observation in doc["observations"]:
        entity(observation, dict(source_id=str, start=int, end=int, quote=str))
        require(0 <= observation["start"] < observation["end"], "S-QUOTE", "half-open nonempty range")

    for claim in doc["claims"]:
        require(type(claim) is dict and "kind" in claim, "S-SHAPE", "claim kind")
        kind = claim["kind"]
        choice(kind, ("fact", "inference", "estimate", "unknown"))
        extra = {
            "fact": dict(quantity=(dict, NULL)),
            "inference": dict(premises=list, rationale=str, falsifier=str),
            "estimate": dict(formula=dict, assumptions=list),
            "unknown": dict(reason=str, context_claims=list, context_sources=list),
        }[kind]
        entity(claim, dict(kind=str, text=str, scope=str, limitations=list, next_check=str) | extra)
        strings(claim["limitations"], True)
        if kind == "fact" and claim["quantity"] is not None:
            quantity(claim["quantity"])
        elif kind == "inference":
            strings(claim["premises"], True)
        elif kind == "unknown":
            strings(claim["context_claims"])
            strings(claim["context_sources"])
        elif kind == "estimate":
            strings(claim["assumptions"], True)
            formula = claim["formula"]
            record(formula, dict(operation=str, inputs=list, result=dict, range=dict))
            choice(formula["operation"], ("add", "subtract", "multiply", "divide"))
            require(len(formula["inputs"]) == 2, "S-FORMULA", "exactly two typed operands")
            for item in formula["inputs"]:
                record(item, dict(claim_id=str, quantity=dict))
                quantity(item["quantity"])
            quantity(formula["result"])
            record(formula["range"], dict(low=str, high=str))
            decimal(formula["range"]["low"])
            decimal(formula["range"]["high"])

    for evidence in doc["evidence"]:
        entity(evidence, dict(claim_id=str, observation_id=str, relation=str,
                              directness=str, strength=str, relevance=str))
        choice(evidence["relation"], ("supports", "contradicts", "context"))
        choice(evidence["directness"], ("direct", "indirect"))
        choice(evidence["strength"], ("weak", "medium", "strong"))
    for problem in doc["problems"]:
        entity(problem, dict(fields=dict))
        record(problem["fields"], {key: str for key in PROBLEM_FIELDS})
    for opportunity in doc["opportunities"]:
        entity(opportunity, dict(problem_id=str, completeness=str, fields=dict))
        choice(opportunity["completeness"], ("incomplete_candidate", "reviewable_hypothesis"))
        record(opportunity["fields"], {key: str for key in OPPORTUNITY_FIELDS})

    for decision in doc["decisions"]:
        entity(decision, dict(opportunity_id=str, action=str, reason=str,
                              dossier_version=str, review=dict, plan=(dict, NULL)))
        choice(decision["action"], ("REJECT", "INVESTIGATE", "TEST"))
        review = decision["review"]
        record(review, dict(claims=list, sources_reviewed=bool, contradictions_reviewed=bool,
                            risks_accepted=bool, problem_supported=bool,
                            existing_solution=str, residual_gap_verified=bool,
                            gap_claim_ids=list, recipient_reachable=bool,
                            buyer_strategy=str, explanation=str))
        choice(review["existing_solution"], ("adequate", "inadequate", "unknown"))
        strings(review["gap_claim_ids"])
        for assertion in review["claims"]:
            record(assertion, dict(claim_id=str, verdict=str, reason=str))
            choice(assertion["verdict"], ("supported", "conditional", "unknown", "unsupported"))
        if decision["plan"] is not None:
            plan(decision["plan"])
    for test in doc["tests"]:
        entity(test, dict(decision_id=str, opportunity_id=str, plan=dict))
        plan(test["plan"])
    for artifact in doc["artifacts"]:
        entity(artifact, dict(test_id=str, version=int, previous_version_id=TEXT_OR_NULL,
                              title=str, purpose=str, content=dict, claim_ids=list, caveats=list))
        require(artifact["version"] >= 1, "S-VERSION", "positive artifact version")
        strings(artifact["claim_ids"], True)
        strings(artifact["caveats"], True)
        content = artifact["content"]
        require(type(content) is dict and "kind" in content, "S-SHAPE", "content kind")
        choice(content["kind"], ("text", "link"))
        if content["kind"] == "text":
            record(content, dict(kind=str, text=str, sha256=str))
        else:
            record(content, dict(kind=str, url=str, version_description=str))
    for event in doc["events"]:
        require(type(event) is dict and "kind" in event, "S-SHAPE", "event kind")
        kind = event["kind"]
        choice(kind, EVENT_KINDS)
        extra = {
            "sent": dict(artifact_id=str, recipient_alias=str, channel=str),
            "responded": dict(sent_id=str, response=str),
            "interested": dict(sent_id=str, responded_id=str, signal=str),
            "rejected": dict(sent_id=str, responded_id=str, reason=TEXT_OR_NULL),
            "no_response": dict(sent_id=str, checked_at=str, channel_checked=bool),
            "meeting": dict(sent_id=str, status=str, meeting_at=str, agreement=str),
            "paid": dict(sent_id=str, amount=dict, paid_at=str, purpose=str, payment_basis=str),
        }[kind]
        entity(event, dict(test_id=str, kind=str, occurred_at=str, description=str,
                           basis=str, correction_of=TEXT_OR_NULL, correction_reason=TEXT_OR_NULL) | extra)
        timestamp(event["occurred_at"])
        if kind == "sent":
            choice(event["channel"], ("manual_email", "manual_in_person"))
        if kind == "no_response":
            timestamp(event["checked_at"])
        if kind == "meeting":
            choice(event["status"], ("scheduled", "held"))
            timestamp(event["meeting_at"])
        if kind == "paid":
            quantity(event["amount"])
            timestamp(event["paid_at"])
            require(event["amount"]["unit"] == "money" and decimal(event["amount"]["value"]) > 0,
                    "S-PAYMENT", "positive observed payment")
    for feedback in doc["feedback"]:
        require(type(feedback) is dict and "kind" in feedback, "S-SHAPE", "feedback kind")
        choice(feedback["kind"], ("research", "outcome"))
        extra = (dict(decision_id=str, proposed_correction=str) if feedback["kind"] == "research"
                 else dict(test_id=str, event_id=str, remaining_unknown=str))
        entity(feedback, dict(opportunity_id=str, kind=str, reason=str, claim_ids=list,
                              conclusion=str, next_step=str) | extra)
        strings(feedback["claim_ids"], True)
