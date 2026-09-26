"""Run ONLY with: python3 -m unittest discover -s tests/stage0 -v."""

import copy
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

from contracts.v0_1.definitions import ContractError, load_json, validate_structure
from contracts.v0_1.invariants import (digest, source_families, test_gate,
                                      validate_extension, validate_graph, validate_snapshot)


FIXTURES = Path(__file__).parent / "fixtures"


def read(name):
    return load_json((FIXTURES / name).read_text())


def materialize(case):
    """Only explicit path replacements/deletions over checked-in readable data."""
    doc = read(case["base"])
    for change in case["changes"]:
        target = doc
        for component in change["path"][:-1]:
            target = target[component]
        key = change["path"][-1]
        if change.get("delete", False):
            del target[key]
        else:
            target[key] = copy.deepcopy(change["value"])
    return doc


class AcceptanceCases(unittest.TestCase):
    def check_case(self, case):
        expected = case["expected"]
        self.assertTrue(case["reason"])
        self.assertTrue(case["semantic_oracle"]["reason"])
        if not expected["structure"]:
            with self.assertRaises(ContractError) as caught:
                validate_structure(materialize(case))
            self.assertEqual(expected["invariant"], caught.exception.invariant)
            return
        doc = materialize(case)
        original = copy.deepcopy(doc)
        validate_structure(doc)
        if not expected["graph"]:
            with self.assertRaises(ContractError) as caught:
                validate_graph(doc)
            self.assertEqual(expected["invariant"], caught.exception.invariant)
            return
        validate_graph(doc)
        decisions = [d for d in doc["decisions"] if d["action"] == "TEST"]
        denials = {reason for d in decisions for reason in test_gate(doc, d)}
        if expected["gate"] == "denied":
            self.assertIn(expected["invariant"], denials)
            with self.assertRaises(ContractError):
                validate_snapshot(doc)
        elif expected["gate"] == "allowed":
            self.assertTrue(decisions)
            self.assertEqual(set(), denials)
            validate_snapshot(doc)
        else:
            self.assertFalse(decisions, "not_requested must not conceal a TEST")
            validate_snapshot(doc)
        if "source_family_count" in expected:
            self.assertEqual(expected["source_family_count"], len(source_families(doc)))
        if "extension_from" in case:
            validate_extension(read(case["extension_from"]), doc)
            self.assertEqual("artifact-1", doc["events"][0]["artifact_id"])
        self.assertEqual(original, doc, "pure checks must not mutate input")


# One unittest per declared case; no hidden generated scenario data.
for entry in read("index.json"):
    case = read(entry["input"])
    def run_case(self, case=case):
        self.check_case(case)
    run_case.__doc__ = case["title"]
    setattr(AcceptanceCases, "test_" + case["id"].replace("-", "_"), run_case)


class SnapshotInvariants(unittest.TestCase):
    def test_inventory_is_complete(self):
        indexed = {entry["input"] for entry in read("index.json")}
        actual = {str(p.relative_to(FIXTURES)) for p in (FIXTURES / "cases").glob("*.json")}
        self.assertEqual(actual, indexed)

    def test_all_valid_inputs_are_synthetic_with_reserved_domains(self):
        for entry in read("index.json"):
            case = read(entry["input"])
            if not case["expected"]["graph"]:
                continue
            doc = materialize(case)
            self.assertIs(doc["run"]["synthetic"], True)
            for source in doc["sources"]:
                for key in ("original_url", "final_url"):
                    self.assertTrue(urlsplit(source[key]).hostname.endswith(".example"))
            for collection, records in doc.items():
                if isinstance(records, list):
                    for record in records:
                        self.assertIs(record["synthetic"], True, collection)

    def test_golden_path_and_separation(self):
        doc = read("golden.json")
        validate_snapshot(doc)
        self.assertEqual(["sent", "responded", "rejected"], [e["kind"] for e in doc["events"]])
        self.assertEqual("TEST", doc["decisions"][0]["action"])
        self.assertEqual("outcome", doc["feedback"][0]["kind"])
        self.assertEqual("event-rejected", doc["feedback"][0]["event_id"])

    def test_negative_research_separate_from_denied_attempt(self):
        validate_snapshot(read("negative_research.json"))
        denied = read("negative_test_attempt.json")
        validate_graph(denied)
        self.assertIn("T-EXISTING", test_gate(denied, denied["decisions"][0]))
        with self.assertRaises(ContractError):
            validate_snapshot(denied)

    def test_immutable_artifact_even_with_recomputed_hash(self):
        before = read("golden.json")
        after = copy.deepcopy(before)
        after["artifacts"][0]["content"]["text"] += " Alteration."
        after["artifacts"][0]["content"]["sha256"] = digest(after["artifacts"][0]["content"]["text"])
        validate_snapshot(after)
        with self.assertRaises(ContractError) as caught:
            validate_extension(before, after)
        self.assertEqual("G-IMMUTABLE", caught.exception.invariant)

    def test_cannot_delete_history(self):
        before = read("golden.json")
        after = copy.deepcopy(before)
        after["feedback"] = []
        with self.assertRaises(ContractError) as caught:
            validate_extension(before, after)
        self.assertEqual("G-IMMUTABLE", caught.exception.invariant)

    def test_mutable_source_not_hidden_by_rehash(self):
        before = read("golden.json")
        after = copy.deepcopy(before)
        source = after["sources"][0]
        source["text"] += " New content."
        source["sha256"] = digest(source["text"])
        with self.assertRaises(ContractError) as caught:
            validate_extension(before, after)
        self.assertEqual("G-IMMUTABLE", caught.exception.invariant)

    def test_no_normalization_or_utf16_offsets(self):
        doc = read("candidate.json")
        source = doc["sources"][0]
        source["text"] = "🧪 e\u0301 synthetic ручная работа"
        source["sha256"] = digest(source["text"])
        observation = doc["observations"][0]
        observation.update(start=2, end=4, quote="e\u0301")
        validate_graph(doc)
        observation["quote"] = "é"
        with self.assertRaises(ContractError) as caught:
            validate_graph(doc)
        self.assertEqual("G-QUOTE", caught.exception.invariant)

    def test_json_nan_rejected(self):
        with self.assertRaises(ContractError) as caught:
            load_json('{"amount": NaN}')
        self.assertEqual("S-JSON", caught.exception.invariant)


if __name__ == "__main__":
    unittest.main()
