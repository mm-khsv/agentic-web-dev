"""Unit tests for orchestrator.workflow (Milestone M1).

These tests never write to the live run-history directory. The only access
to ``workflow/runs/`` is a read-only byte comparison against the fixtures,
and it is skipped if the originals are not present.
"""

import ast
import copy
import dataclasses
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from orchestrator import workflow as wf

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
FIXTURES = TESTS_DIR / "fixtures"
LIVE_RUNS = PROJECT_ROOT / "workflow" / "runs"
WORKFLOW_SOURCE = PROJECT_ROOT / "orchestrator" / "workflow.py"

# SHA-256 of the two legacy run records as they existed when M1 started.
LEGACY_HASHES = {
    "ac10609e-598e-4a39-a3b2-32d372556cde.json":
        "d4404df34a086d67686cd52930cdfc4c459e4a5a93873e2ed8b1edbecb805ce6",
    "c6ee6df4-64af-4ed2-ba6d-8ce681e8c5f3.json":
        "9f5d40d728a67b5aa7792a036aad92f1544937d7a1f5ecad77d6a926cced781c",
}

EXPECTED_STAGE_IDS = (
    "requirements", "ux_design", "architecture", "planning",
    "build", "verify", "release", "operate",
)
EXPECTED_GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6")

# A complete, explicit set of decisions for tests that need G2 or
# conditional approvals to be answerable.
G2_CONFIG = wf.WorkflowConfig(
    approver_roles={"G2": ("product-owner", "tech-lead")}
)


def approved(*gate_ids):
    return {g: "approved" for g in gate_ids}


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class StageAndGateDefinitionTests(unittest.TestCase):
    def test_eight_stages_in_pdf_order(self):
        self.assertEqual(wf.STAGE_IDS, EXPECTED_STAGE_IDS)
        self.assertEqual(
            [s.number for s in wf.STAGES], list(range(1, 9))
        )
        self.assertEqual(
            [s.name for s in wf.STAGES],
            ["Requirements", "UX design", "Architecture", "Planning",
             "Build", "Verify", "Release", "Operate"],
        )

    def test_six_gates_in_order(self):
        self.assertEqual(wf.GATE_IDS, EXPECTED_GATE_IDS)
        self.assertEqual([g.number for g in wf.GATES], list(range(1, 7)))

    def test_documented_gate_positions(self):
        positions = {g.id: g.after_stage_ids for g in wf.GATES}
        self.assertEqual(positions["G1"], ("requirements",))
        self.assertEqual(positions["G2"], ("ux_design", "architecture"))
        self.assertEqual(positions["G3"], ("planning",))
        self.assertEqual(positions["G4"], ("verify",))
        self.assertEqual(positions["G5"], ("verify",))
        self.assertEqual(positions["G6"], ("release",))

    def test_stage_gate_labels_match_gate_positions(self):
        for stage in wf.STAGES:
            expected = tuple(
                g.id for g in wf.GATES if stage.id in g.after_stage_ids
            )
            self.assertEqual(stage.gate_ids, expected, stage.id)

    def test_build_and_operate_have_no_g_gate(self):
        self.assertEqual(wf.get_stage("build").gate_ids, ())
        self.assertEqual(wf.get_stage("operate").gate_ids, ())

    def test_documented_approver_roles(self):
        roles = {g.id: g.documented_approver_roles for g in wf.GATES}
        self.assertEqual(roles["G1"], ("product-owner",))
        self.assertEqual(roles["G2"], ("product-owner", "tech-lead"))
        self.assertEqual(roles["G3"], ("tech-lead",))
        self.assertEqual(roles["G4"], ("product-owner",))
        self.assertEqual(roles["G5"], ("security-owner",))
        self.assertEqual(roles["G6"], ("tech-lead",))

    def test_every_item_has_valid_pdf_page_references(self):
        for item in list(wf.STAGES) + list(wf.GATES):
            self.assertTrue(item.pdf_pages, item.id)
            for page in item.pdf_pages:
                self.assertTrue(1 <= page <= 156, (item.id, page))

    def test_every_stage_has_lead_roles_and_paths_are_not_invented(self):
        for stage in wf.STAGES:
            self.assertTrue(stage.lead_roles, stage.id)
        self.assertEqual(
            wf.get_stage("requirements").output_paths, ("specs/NNN/spec.md",)
        )
        self.assertEqual(
            wf.get_stage("planning").output_paths, ("specs/NNN/tasks.md",)
        )
        # 'NNN' stays a literal placeholder (A10).
        self.assertIn("specs/NNN/design.md",
                      wf.get_stage("architecture").output_paths)

    def test_unresolved_refs_all_resolve(self):
        known = {q.id for q in wf.UNRESOLVED_QUESTIONS}
        for item in list(wf.STAGES) + list(wf.GATES):
            for ref in item.unresolved_refs:
                self.assertIn(ref, known, (item.id, ref))

    def test_required_ambiguities_are_preserved_as_unresolved(self):
        by_id = {q.id: q for q in wf.UNRESOLVED_QUESTIONS}
        for qid in ("A2", "A3", "A4", "A5", "A6", "A7", "A8"):
            self.assertEqual(by_id[qid].status, "unresolved", qid)
            self.assertTrue(by_id[qid].pdf_pages, qid)
        self.assertIn("G2", by_id["A2"].affects_gate_ids)
        self.assertIn("G2", by_id["A3"].affects_gate_ids)
        self.assertEqual(
            {"G4", "G5"} - set(by_id["A8"].affects_gate_ids), set()
        )

    def test_g2_is_marked_disputed_with_alternate_readings(self):
        g2 = wf.get_gate("G2")
        self.assertEqual(g2.approver_roles_status, "disputed")
        self.assertGreaterEqual(len(g2.alternate_approver_readings), 3)
        for gate in wf.GATES:
            if gate.id != "G2":
                self.assertEqual(gate.approver_roles_status, "documented")

    def test_design_decisions_await_approval(self):
        self.assertTrue(wf.DESIGN_DECISIONS)
        for decision in wf.DESIGN_DECISIONS:
            self.assertEqual(decision.status, "awaiting_approval")

    def test_definitions_are_immutable(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            wf.get_stage("build").name = "Changed"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            wf.get_gate("G3").number = 99


class RequiredGateDerivationTests(unittest.TestCase):
    def test_required_gates_per_stage(self):
        expected = {
            "requirements": (),
            "ux_design": ("G1",),
            "architecture": ("G1",),
            "planning": ("G1", "G2"),
            "build": ("G1", "G2", "G3"),
            "verify": ("G1", "G2", "G3"),
            "release": ("G1", "G2", "G3", "G4", "G5"),
            "operate": ("G1", "G2", "G3", "G4", "G5", "G6"),
        }
        for stage_id, gates in expected.items():
            self.assertEqual(
                wf.required_gates_for_stage(stage_id), gates, stage_id
            )

    def test_explicit_pdf_rules_are_recorded_separately(self):
        self.assertEqual(
            wf.get_stage("build").explicit_required_gate_ids, ("G3",)
        )
        self.assertEqual(
            wf.get_gate("G6").explicit_required_gate_ids, ("G4", "G5")
        )

    def test_g4_and_g5_do_not_precede_each_other(self):
        self.assertNotIn("G5", wf.required_gates_for_gate_decision("G4"))
        self.assertNotIn("G4", wf.required_gates_for_gate_decision("G5"))
        self.assertEqual(
            wf.required_gates_for_gate_decision("G6"),
            ("G1", "G2", "G3", "G4", "G5"),
        )


class StageStartTests(unittest.TestCase):
    def test_first_stage_needs_no_gate(self):
        self.assertTrue(wf.can_start_stage("requirements"))
        self.assertTrue(wf.can_start_stage("requirements", {}))

    def test_build_blocked_before_g3_approved(self):
        for g3 in (None, "pending", "rejected"):
            states = {"G1": "approved", "G2": "approved", "G3": g3}
            check = wf.check_stage_start("build", states)
            self.assertFalse(check.allowed, g3)
            self.assertEqual(check.missing_gate_ids, ("G3",))
            self.assertEqual(check.explicit_required_gate_ids, ("G3",))
        self.assertFalse(wf.can_start_stage("build"))

    def test_build_allowed_once_g3_approved(self):
        self.assertTrue(
            wf.can_start_stage("build", approved("G1", "G2", "G3"))
        )

    def test_build_still_blocked_if_only_g3_approved(self):
        # Derived rule D2: earlier gates are also required.
        check = wf.check_stage_start("build", approved("G3"))
        self.assertFalse(check.allowed)
        self.assertEqual(check.missing_gate_ids, ("G1", "G2"))

    def test_architecture_needs_only_g1_not_g2(self):
        self.assertTrue(wf.can_start_stage("architecture", approved("G1")))
        self.assertFalse(wf.can_start_stage("architecture"))

    def test_planning_needs_g2(self):
        self.assertFalse(wf.can_start_stage("planning", approved("G1")))
        self.assertTrue(wf.can_start_stage("planning", approved("G1", "G2")))

    def test_release_needs_both_g4_and_g5(self):
        base = approved("G1", "G2", "G3")
        self.assertFalse(wf.can_start_stage("release", base))
        self.assertFalse(
            wf.can_start_stage("release", {**base, "G4": "approved"})
        )
        self.assertFalse(
            wf.can_start_stage("release", {**base, "G5": "approved"})
        )
        self.assertTrue(
            wf.can_start_stage(
                "release", {**base, "G4": "approved", "G5": "approved"}
            )
        )

    def test_operate_needs_g6(self):
        base = approved("G1", "G2", "G3", "G4", "G5")
        self.assertFalse(wf.can_start_stage("operate", base))
        self.assertTrue(
            wf.can_start_stage("operate", {**base, "G6": "approved"})
        )

    def test_result_reports_unresolved_refs_for_ambiguous_stages(self):
        check = wf.check_stage_start("release", approved("G1", "G2", "G3"))
        self.assertIn("A6", check.unresolved_refs)

    def test_conditional_approval_requires_explicit_decision(self):
        states = {"G1": "approved_with_conditions"}
        with self.assertRaises(wf.UnresolvedDecisionError):
            wf.check_stage_start("ux_design", states)
        yes = wf.WorkflowConfig(conditional_approval_satisfies_gate=True)
        no = wf.WorkflowConfig(conditional_approval_satisfies_gate=False)
        self.assertTrue(wf.can_start_stage("ux_design", states, config=yes))
        self.assertFalse(wf.can_start_stage("ux_design", states, config=no))

    def test_inputs_are_not_mutated(self):
        states = approved("G1", "G2")
        before = copy.deepcopy(states)
        wf.check_stage_start("planning", states)
        self.assertEqual(states, before)

    def test_unknown_stage_id_rejected(self):
        for bad in ("intake", "deploy", "", None, 5, ["build"]):
            with self.assertRaises(wf.UnknownStageError, msg=repr(bad)):
                wf.check_stage_start(bad)

    def test_unknown_gate_id_rejected(self):
        with self.assertRaises(wf.UnknownGateError):
            wf.check_stage_start("build", {"G7": "approved"})
        with self.assertRaises(wf.UnknownGateError):
            wf.check_stage_start("build", {"g3": "approved"})

    def test_invalid_gate_state_value_rejected(self):
        with self.assertRaises(wf.InvalidGateStateError):
            wf.check_stage_start("build", {"G3": "yes"})
        with self.assertRaises(wf.InvalidGateStateError):
            wf.check_stage_start("build", ["G3"])

    def test_unsupported_and_unknown_lanes_rejected(self):
        for lane in ("express", "standard", "critical"):
            with self.assertRaises(wf.UnsupportedLaneError, msg=lane):
                wf.check_stage_start("build", lane=lane)
        for lane in ("hotfix", "", None, 3):
            with self.assertRaises(wf.UnsupportedLaneError, msg=repr(lane)):
                wf.check_stage_start("build", lane=lane)

    def test_feature_lane_is_the_only_supported_lane(self):
        self.assertEqual(
            [lane.id for lane in wf.LANES if lane.supported], ["feature"]
        )
        self.assertEqual(
            wf.LANE_IDS, ("express", "standard", "feature", "critical")
        )
        self.assertEqual(wf.require_supported_lane("feature").id, "feature")


class TransitionTests(unittest.TestCase):
    def test_full_forward_walk_with_gates_approved_in_order(self):
        states = {}
        previous = None
        for index, stage_id in enumerate(wf.STAGE_IDS):
            check = wf.check_transition(previous, stage_id, states)
            self.assertTrue(check.allowed, (previous, stage_id, check))
            previous = stage_id
            for gate_id in wf.get_stage(stage_id).gate_ids:
                # Gate approved only after its last documented stage.
                gate = wf.get_gate(gate_id)
                if gate.after_stage_ids[-1] == stage_id:
                    states[gate_id] = "approved"

    def test_run_must_begin_at_requirements(self):
        self.assertTrue(wf.check_transition(None, "requirements").allowed)
        self.assertFalse(wf.check_transition(None, "ux_design").allowed)
        self.assertFalse(wf.check_transition(None, "build").allowed)

    def test_skipping_is_not_allowed(self):
        check = wf.check_transition(
            "requirements", "architecture", approved("G1")
        )
        self.assertFalse(check.allowed)
        self.assertTrue(check.reasons)

    def test_backward_and_repeat_are_not_allowed(self):
        states = approved("G1", "G2", "G3", "G4", "G5", "G6")
        self.assertFalse(wf.check_transition("build", "planning", states).allowed)
        self.assertFalse(wf.check_transition("build", "build", states).allowed)
        self.assertIn("A4", wf.check_transition(
            "build", "planning", states).unresolved_refs)

    def test_nothing_leaves_the_final_stage(self):
        states = approved("G1", "G2", "G3", "G4", "G5", "G6")
        check = wf.check_transition("operate", "requirements", states)
        self.assertFalse(check.allowed)
        self.assertIn("A11", check.unresolved_refs)

    def test_requirements_to_ux_needs_g1(self):
        self.assertFalse(wf.check_transition("requirements", "ux_design").allowed)
        self.assertTrue(
            wf.check_transition(
                "requirements", "ux_design", approved("G1")
            ).allowed
        )

    def test_ux_to_architecture_allowed_but_always_flags_a2(self):
        check = wf.check_transition("ux_design", "architecture", approved("G1"))
        self.assertTrue(check.allowed)
        self.assertIn("A2", check.unresolved_refs)

    def test_architecture_to_planning_blocked_without_g2(self):
        check = wf.check_transition("architecture", "planning", approved("G1"))
        self.assertFalse(check.allowed)
        self.assertEqual(check.missing_gate_ids, ("G2",))

    def test_planning_to_build_blocked_without_g3(self):
        check = wf.check_transition(
            "planning", "build", approved("G1", "G2")
        )
        self.assertFalse(check.allowed)
        self.assertEqual(check.missing_gate_ids, ("G3",))

    def test_verify_to_release_needs_g4_and_g5(self):
        base = approved("G1", "G2", "G3")
        self.assertFalse(wf.check_transition("verify", "release", base).allowed)
        self.assertFalse(wf.check_transition(
            "verify", "release", {**base, "G4": "approved"}).allowed)
        self.assertTrue(wf.check_transition(
            "verify", "release",
            {**base, "G4": "approved", "G5": "approved"}).allowed)

    def test_unknown_ids_and_lanes_raise(self):
        with self.assertRaises(wf.UnknownStageError):
            wf.check_transition("intake", "requirements")
        with self.assertRaises(wf.UnknownStageError):
            wf.check_transition("requirements", "deploy")
        with self.assertRaises(wf.UnsupportedLaneError):
            wf.check_transition(None, "requirements", lane="express")


class GateDecisionPermissionTests(unittest.TestCase):
    BASE = approved("G1", "G2", "G3")

    def test_g6_blocked_until_both_g4_and_g5_approved(self):
        none = wf.check_gate_decision_allowed("G6", "approved", self.BASE)
        self.assertFalse(none.allowed)
        self.assertEqual(none.missing_gate_ids, ("G4", "G5"))

        only4 = wf.check_gate_decision_allowed(
            "G6", "approved", {**self.BASE, "G4": "approved"})
        self.assertFalse(only4.allowed)
        self.assertEqual(only4.missing_gate_ids, ("G5",))

        only5 = wf.check_gate_decision_allowed(
            "G6", "approved", {**self.BASE, "G5": "approved"})
        self.assertFalse(only5.allowed)
        self.assertEqual(only5.missing_gate_ids, ("G4",))

        both = wf.check_gate_decision_allowed(
            "G6", "approved",
            {**self.BASE, "G4": "approved", "G5": "approved"})
        self.assertTrue(both.allowed)
        self.assertEqual(both.explicit_required_gate_ids, ("G4", "G5"))

    def test_g6_conditional_approval_is_also_blocked(self):
        check = wf.check_gate_decision_allowed(
            "G6", "approved_with_conditions", self.BASE)
        self.assertFalse(check.allowed)

    def test_g4_and_g5_are_independent_of_each_other(self):
        self.assertTrue(wf.check_gate_decision_allowed(
            "G4", "approved", self.BASE).allowed)
        self.assertTrue(wf.check_gate_decision_allowed(
            "G5", "approved", self.BASE).allowed)

    def test_derived_prerequisites_block_early_gates(self):
        check = wf.check_gate_decision_allowed("G3", "approved", {})
        self.assertFalse(check.allowed)
        self.assertEqual(check.missing_gate_ids, ("G1", "G2"))
        self.assertTrue(wf.check_gate_decision_allowed(
            "G1", "approved", {}).allowed)

    def test_rejection_is_not_blocked_by_prerequisites(self):
        check = wf.check_gate_decision_allowed("G6", "rejected", {})
        self.assertTrue(check.allowed)
        self.assertTrue(check.notes)

    def test_invalid_inputs_raise(self):
        with self.assertRaises(wf.UnknownGateError):
            wf.check_gate_decision_allowed("G7", "approved")
        with self.assertRaises(wf.InvalidDecisionError):
            wf.check_gate_decision_allowed("G1", "maybe")
        with self.assertRaises(wf.UnsupportedLaneError):
            wf.check_gate_decision_allowed("G1", "approved", lane="critical")


class DecisionRecordTests(unittest.TestCase):
    def record(self, **overrides):
        base = {
            "gate_id": "G1",
            "outcome": "approved",
            "approver": "sara",
            "approver_role": "product-owner",
        }
        base.update(overrides)
        return base

    def test_valid_minimal_record(self):
        result = wf.validate_decision_record(self.record())
        self.assertEqual(result.gate_id, "G1")
        self.assertEqual(result.outcome, "approved")
        self.assertEqual(result.reason, "")
        self.assertEqual(result.conditions, ())
        self.assertIsNone(result.decided_at)

    def test_each_documented_gate_accepts_its_documented_role(self):
        cases = {
            "G1": "product-owner", "G3": "tech-lead", "G4": "product-owner",
            "G5": "security-owner", "G6": "tech-lead",
        }
        for gate_id, role in cases.items():
            result = wf.validate_decision_record(
                self.record(gate_id=gate_id, approver_role=role))
            self.assertEqual(result.gate_id, gate_id)

    def test_approver_role_mismatch_rejected(self):
        cases = [
            ("G1", "tech-lead"), ("G3", "product-owner"),
            ("G4", "security-owner"), ("G5", "tech-lead"),
            ("G6", "product-owner"),
            ("G1", "requirements-analyst"),  # an agent is not an approver
        ]
        for gate_id, role in cases:
            with self.assertRaises(wf.ApproverRoleError, msg=(gate_id, role)):
                wf.validate_decision_record(
                    self.record(gate_id=gate_id, approver_role=role))

    def test_g2_cannot_be_validated_without_an_explicit_decision(self):
        with self.assertRaises(wf.UnresolvedDecisionError):
            wf.validate_decision_record(
                self.record(gate_id="G2", approver_role="tech-lead"))

    def test_g2_with_explicit_config(self):
        result = wf.validate_decision_record(
            self.record(gate_id="G2", approver_role="tech-lead"),
            config=G2_CONFIG)
        self.assertEqual(result.gate_id, "G2")
        with self.assertRaises(wf.ApproverRoleError):
            wf.validate_decision_record(
                self.record(gate_id="G2", approver_role="security-owner"),
                config=G2_CONFIG)

    def test_config_override_applies_to_other_gates_too(self):
        cfg = wf.WorkflowConfig(approver_roles={"G1": ["tech-lead"]})
        wf.validate_decision_record(
            self.record(approver_role="tech-lead"), config=cfg)
        with self.assertRaises(wf.ApproverRoleError):
            wf.validate_decision_record(self.record(), config=cfg)

    def test_invalid_config_rejected(self):
        for bad in (
            wf.WorkflowConfig(approver_roles={"G9": ["x"]}),
            wf.WorkflowConfig(approver_roles={"G1": []}),
            wf.WorkflowConfig(approver_roles={"G1": "tech-lead"}),
            wf.WorkflowConfig(approver_roles={"G1": [""]}),
            wf.WorkflowConfig(conditional_approval_satisfies_gate="yes"),
        ):
            with self.assertRaises(wf.WorkflowError):
                wf.validate_decision_record(self.record(), config=bad)
        with self.assertRaises(wf.WorkflowError):
            wf.validate_decision_record(self.record(), config={"G1": 1})

    def test_unknown_gate_rejected(self):
        with self.assertRaises(wf.UnknownGateError):
            wf.validate_decision_record(self.record(gate_id="G9"))
        with self.assertRaises(wf.UnknownGateError):
            wf.validate_decision_record(self.record(gate_id=None))

    def test_invalid_outcome_rejected(self):
        for bad in ("maybe", "APPROVED", "", None, True):
            with self.assertRaises(wf.InvalidDecisionError, msg=repr(bad)):
                wf.validate_decision_record(self.record(outcome=bad))

    def test_missing_and_unknown_fields_rejected(self):
        for key in ("gate_id", "outcome", "approver", "approver_role"):
            rec = self.record()
            del rec[key]
            with self.assertRaises(wf.InvalidDecisionError, msg=key):
                wf.validate_decision_record(rec)
        with self.assertRaises(wf.InvalidDecisionError):
            wf.validate_decision_record(self.record(aprover="typo"))

    def test_non_mapping_rejected(self):
        for bad in (None, [], "G1", 3):
            with self.assertRaises(wf.InvalidDecisionError, msg=repr(bad)):
                wf.validate_decision_record(bad)

    def test_blank_approver_or_role_rejected(self):
        for field_name in ("approver", "approver_role"):
            for bad in ("", "   ", None, 7):
                with self.assertRaises(
                    wf.InvalidDecisionError, msg=(field_name, bad)
                ):
                    wf.validate_decision_record(
                        self.record(**{field_name: bad}))

    def test_rejection_requires_a_reason(self):
        with self.assertRaises(wf.InvalidDecisionError):
            wf.validate_decision_record(self.record(outcome="rejected"))
        with self.assertRaises(wf.InvalidDecisionError):
            wf.validate_decision_record(
                self.record(outcome="rejected", reason="  "))
        ok = wf.validate_decision_record(
            self.record(outcome="rejected", reason="  Acceptance criteria "
                        "incomplete  "))
        self.assertEqual(ok.reason, "Acceptance criteria incomplete")

    def test_conditions_rules(self):
        with self.assertRaises(wf.InvalidDecisionError):
            wf.validate_decision_record(
                self.record(outcome="approved_with_conditions"))
        with self.assertRaises(wf.InvalidDecisionError):
            wf.validate_decision_record(self.record(
                outcome="approved_with_conditions", conditions=[]))
        with self.assertRaises(wf.InvalidDecisionError):
            wf.validate_decision_record(self.record(
                outcome="approved_with_conditions", conditions=[""]))
        with self.assertRaises(wf.InvalidDecisionError):
            wf.validate_decision_record(self.record(conditions=["x"]))
        ok = wf.validate_decision_record(self.record(
            outcome="approved_with_conditions",
            conditions="add hold extension"))
        self.assertEqual(ok.conditions, ("add hold extension",))

    def test_decided_at_validation(self):
        ok = wf.validate_decision_record(
            self.record(decided_at="2026-09-10"))
        self.assertEqual(ok.decided_at, "2026-09-10")
        wf.validate_decision_record(
            self.record(decided_at="2026-10-28T02:22:49.235231+00:00"))
        for bad in ("yesterday", 20260910, ""):
            with self.assertRaises(wf.InvalidDecisionError, msg=repr(bad)):
                wf.validate_decision_record(self.record(decided_at=bad))

    def test_validated_record_is_immutable_and_input_untouched(self):
        rec = self.record(reason=" ok ")
        before = copy.deepcopy(rec)
        result = wf.validate_decision_record(rec)
        self.assertEqual(rec, before)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.outcome = "rejected"


class LegacyClassificationTests(unittest.TestCase):
    def load(self, name):
        return (FIXTURES / name).read_bytes()

    def test_both_real_legacy_records_are_legacy_and_not_g1(self):
        for name in LEGACY_HASHES:
            result = wf.classify_run_json(self.load(name))
            self.assertEqual(result.kind, "legacy", name)
            self.assertIsNone(result.schema_version)
            self.assertEqual(result.workflow_position, "legacy_intake_review")
            self.assertIsNone(result.mapped_stage_id)
            self.assertEqual(result.gate_approvals, ())
            self.assertFalse(result.counts_as_g1_approval)
            self.assertIn("never", result.interpretation.lower())

    def test_legacy_status_is_reported_but_not_interpreted(self):
        approved_run = wf.classify_run_json(
            self.load("c6ee6df4-64af-4ed2-ba6d-8ce681e8c5f3.json"))
        rejected_run = wf.classify_run_json(
            self.load("ac10609e-598e-4a39-a3b2-32d372556cde.json"))
        self.assertEqual(approved_run.legacy_status, "approved")
        self.assertEqual(rejected_run.legacy_status, "rejected")
        # The old 'approved' status must not turn into a G1 approval, and
        # must not allow the next stage to start.
        self.assertFalse(approved_run.counts_as_g1_approval)
        self.assertEqual(approved_run.gate_approvals, ())
        self.assertFalse(wf.can_start_stage("ux_design", {}))

    def test_synthetic_approved_legacy_record_is_never_g1(self):
        record = {
            "run_id": "11111111-1111-4111-8111-111111111111",
            "status": "approved",
            "current_stage": "intake",
            "decision": {"outcome": "approved", "reason": "ok"},
            "events": [{"type": "human_decision", "outcome": "approved"}],
        }
        result = wf.classify_run_record(record)
        self.assertEqual(result.kind, "legacy")
        self.assertFalse(result.counts_as_g1_approval)
        self.assertEqual(result.gate_approvals, ())

    def test_legacy_record_with_other_stage_is_unmapped(self):
        result = wf.classify_run_record(
            {"run_id": "x", "status": "approved", "current_stage": "build"})
        self.assertEqual(result.kind, "legacy")
        self.assertEqual(result.workflow_position, "legacy_unmapped")
        self.assertIsNone(result.mapped_stage_id)

    def test_incomplete_legacy_record_still_legacy_with_warnings(self):
        result = wf.classify_run_record({})
        self.assertEqual(result.kind, "legacy")
        self.assertEqual(len(result.warnings), 3)

    def test_versioned_record_is_not_interpreted(self):
        result = wf.classify_run_record(
            {"schema_version": 1, "status": "approved"})
        self.assertEqual(result.kind, "versioned")
        self.assertEqual(result.schema_version, 1)
        self.assertEqual(result.gate_approvals, ())
        self.assertFalse(result.counts_as_g1_approval)

    def test_invalid_schema_versions_rejected(self):
        for bad in (0, -1, "1", None, 1.0, True, [1]):
            with self.assertRaises(wf.InvalidRunRecordError, msg=repr(bad)):
                wf.classify_run_record({"schema_version": bad})

    def test_non_objects_and_bad_json_rejected(self):
        for bad in (None, [], "text", 3):
            with self.assertRaises(wf.InvalidRunRecordError, msg=repr(bad)):
                wf.classify_run_record(bad)
        for bad in (b"not json", b"[1, 2]", b"\xff\xfe\x00", "{", 12):
            with self.assertRaises(wf.InvalidRunRecordError, msg=repr(bad)):
                wf.classify_run_json(bad)

    def test_bom_prefixed_json_is_accepted(self):
        payload = b'\xef\xbb\xbf{"status": "approved", "current_stage": "intake"}'
        self.assertEqual(wf.classify_run_json(payload).kind, "legacy")
        self.assertEqual(
            wf.classify_run_json(payload.decode("utf-8")).kind, "legacy")

    def test_classification_does_not_mutate_the_record(self):
        record = json.loads(
            self.load("c6ee6df4-64af-4ed2-ba6d-8ce681e8c5f3.json"))
        before = copy.deepcopy(record)
        wf.classify_run_record(record)
        self.assertEqual(record, before)


class FixturePreservationTests(unittest.TestCase):
    def test_fixtures_match_the_pinned_original_hashes(self):
        for name, expected in LEGACY_HASHES.items():
            self.assertEqual(sha256_of(FIXTURES / name), expected, name)

    def test_fixtures_match_live_originals_when_present(self):
        compared = 0
        for name in LEGACY_HASHES:
            live = LIVE_RUNS / name
            if not live.is_file():
                continue
            compared += 1
            self.assertEqual(
                live.read_bytes(), (FIXTURES / name).read_bytes(), name)
        if compared == 0:
            self.skipTest("original run records are not present here")

    def test_classifying_a_file_copy_leaves_its_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, expected in LEGACY_HASHES.items():
                target = Path(tmp) / name
                shutil.copyfile(FIXTURES / name, target)
                wf.classify_run_json(target.read_bytes())
                self.assertEqual(sha256_of(target), expected, name)
                self.assertEqual(sha256_of(FIXTURES / name), expected, name)

    def test_only_the_two_legacy_records_are_fixtures(self):
        self.assertEqual(
            sorted(p.name for p in FIXTURES.glob("*.json")),
            sorted(LEGACY_HASHES),
        )

    def test_legacy_fixtures_keep_their_crlf_line_endings(self):
        for name in LEGACY_HASHES:
            data = (FIXTURES / name).read_bytes()
            self.assertIn(b"\r\n", data, name)
            self.assertFalse(data.startswith(b"\xef\xbb\xbf"), name)


class ModulePurityTests(unittest.TestCase):
    ALLOWED_IMPORTS = {"__future__", "json", "collections", "dataclasses",
                       "datetime", "typing"}
    FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__",
                       "input", "print"}

    def setUp(self):
        self.tree = ast.parse(WORKFLOW_SOURCE.read_text(encoding="utf-8"))

    def test_only_pure_standard_library_imports(self):
        imported = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "no relative imports")
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported <= self.ALLOWED_IMPORTS, imported)

    def test_no_file_or_process_calls(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, self.FORBIDDEN_CALLS)

    def test_does_not_reference_the_engine_or_runs_directory_constant(self):
        names = {n.id for n in ast.walk(self.tree) if isinstance(n, ast.Name)}
        self.assertNotIn("RUNS_DIR", names)
        self.assertNotIn("Orchestrator", names)


class ExistingOrchestratorTestsUntouchedTests(unittest.TestCase):
    def test_the_seven_orchestrator_tests_are_still_defined(self):
        tree = ast.parse(
            (TESTS_DIR / "test_orchestrator.py").read_text(encoding="utf-8"))
        methods = [
            item.name
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "OrchestratorTests"
            for item in node.body
            if isinstance(item, ast.FunctionDef)
            and item.name.startswith("test_")
        ]
        self.assertEqual(len(methods), 7, methods)


if __name__ == "__main__":
    unittest.main()
