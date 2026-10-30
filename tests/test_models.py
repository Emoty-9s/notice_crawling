"""Contract and persisted-data validation for the shared M02 models."""

import json
import unittest
from dataclasses import FrozenInstanceError

from src.core.models import GeminiResult, GeminiStatus, Notice, NoticeStatus


def make_notice(**overrides) -> Notice:
    values = dict(
        notice_id="supplied-id", source_id="example", institution="예시 기관",
        title="협력기관 모집", url="https://example.org/notices/1",
        content_text="공개 웹 본문", content_hash="supplied-hash",
        first_seen_at="2026-10-30T09:00:00+09:00",
        last_seen_at="2026-10-30T09:00:00+09:00",
        updated_at="2026-10-30T09:00:00+09:00",
    )
    values.update(overrides)
    return Notice(**values)


class NoticeModelTests(unittest.TestCase):
    def test_normal_notice_and_contract_keys(self):
        notice = make_notice(published_at="2026-10-30")
        self.assertEqual(notice.title, "협력기관 모집")
        self.assertIs(notice.status, NoticeStatus.NEW)
        self.assertEqual(set(notice.to_dict()), {
            "notice_id", "source_id", "institution", "title", "category",
            "published_at", "apply_start", "apply_end", "url", "content_text",
            "content_hash", "status", "gemini", "first_seen_at", "last_seen_at",
            "updated_at",
        })

    def test_optional_none_serializes_as_null(self):
        data = json.loads(make_notice().to_json())
        for name in ("category", "published_at", "apply_start", "apply_end"):
            self.assertIsNone(data[name])
        self.assertEqual(set(data["gemini"]), {
            "status", "relevant", "score", "reason", "category", "analyzed_at",
            "analyzed_content_hash",
            "participation_type", "keywords",
        })
        self.assertIs(make_notice().gemini.status, GeminiStatus.NOT_ANALYZED)
        for name, value in data["gemini"].items():
            if name != "status":
                self.assertIsNone(value)

    def test_populated_json_round_trip(self):
        notice = make_notice(
            category="입찰", published_at="2026-10-30", apply_start="2026-10-30",
            apply_end="2026-11-10", status=NoticeStatus.UPDATED,
            gemini=GeminiResult(
                status=GeminiStatus.SUCCESS, relevant=True, score=89.5,
                reason="수행기관 대상", category="특허",
                analyzed_at="2026-10-30T00:00:00Z",
                analyzed_content_hash="supplied-hash",
            ),
        )
        encoded = notice.to_json()
        self.assertIn("협력기관", encoded)
        restored = Notice.from_json(encoded)
        self.assertEqual(restored, notice)
        self.assertIsInstance(restored.gemini, GeminiResult)
        self.assertIs(restored.status, NoticeStatus.UPDATED)
        self.assertIs(restored.gemini.status, GeminiStatus.SUCCESS)

    def test_default_round_trip_and_independent_defaults(self):
        notice = make_notice()
        self.assertEqual(Notice.from_json(notice.to_json()), notice)
        self.assertIsNot(notice.gemini, make_notice().gemini)

    def test_all_notice_statuses_accept_strings_and_round_trip(self):
        for value in ("NEW", "UPDATED", "EXISTING"):
            with self.subTest(value=value):
                notice = make_notice(status=value)
                self.assertIs(notice.status, NoticeStatus(value))
                self.assertEqual(Notice.from_json(notice.to_json()), notice)

    def test_invalid_notice_status_rejected_on_both_paths(self):
        for value in ("new", "UNKNOWN", "", None, 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    make_notice(status=value)
                data = make_notice().to_dict()
                data["status"] = value
                with self.assertRaises(ValueError):
                    Notice.from_json(json.dumps(data))

    def test_missing_required_field_and_unknown_field_rejected(self):
        for name in ("notice_id", "content_hash", "source_id", "first_seen_at"):
            data = make_notice().to_dict()
            del data[name]
            with self.subTest(name=name), self.assertRaises(TypeError):
                Notice.from_dict(data)
        data = make_notice().to_dict()
        data["unexpected"] = 1
        with self.assertRaises(TypeError):
            Notice.from_dict(data)

    def test_required_text_and_nested_types_rejected(self):
        for overrides in ({"title": None}, {"content_hash": 42}, {"gemini": None}):
            with self.subTest(overrides=overrides), self.assertRaises(TypeError):
                make_notice(**overrides)
        data = make_notice().to_dict()
        data["gemini"] = []
        with self.assertRaises(TypeError):
            Notice.from_dict(data)

    def test_optional_text_rejects_empty_or_wrong_type(self):
        for value in ("", "  ", 42):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                make_notice(category=value)

    def test_serialization_does_not_mutate_input(self):
        data = make_notice(gemini=GeminiResult(status="PENDING")).to_dict()
        before = json.dumps(data)
        Notice.from_dict(data)
        self.assertEqual(json.dumps(data), before)

    def test_identity_hash_dates_and_body_are_not_normalized(self):
        notice = make_notice(content_text="  raw\nbody  ", published_at="2026.10.30")
        self.assertEqual(notice.notice_id, "supplied-id")
        self.assertEqual(notice.content_hash, "supplied-hash")
        self.assertEqual(notice.published_at, "2026.10.30")
        self.assertEqual(notice.content_text, "  raw\nbody  ")
        self.assertEqual(make_notice(content_text="").content_text, "")

    def test_frozen_models_prevent_invalid_status_assignment(self):
        notice = make_notice()
        with self.assertRaises(FrozenInstanceError):
            notice.status = "invalid"
        with self.assertRaises(FrozenInstanceError):
            notice.gemini.status = "invalid"


class GeminiResultTests(unittest.TestCase):
    def test_all_statuses_accept_strings_and_round_trip(self):
        for value in ("NOT_ANALYZED", "SUCCESS", "FAILED", "PENDING"):
            with self.subTest(value=value):
                result = GeminiResult(status=value)
                self.assertIs(result.status, GeminiStatus(value))
                self.assertEqual(GeminiResult.from_json(result.to_json()), result)
                notice = make_notice(gemini=result)
                self.assertEqual(Notice.from_json(notice.to_json()), notice)

    def test_invalid_status_rejected_on_nested_deserialization(self):
        for value in ("success", "UNKNOWN", None, ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    GeminiResult(status=value)
                data = make_notice().to_dict()
                data["gemini"]["status"] = value
                with self.assertRaises(ValueError):
                    Notice.from_dict(data)

    def test_output_types_and_non_finite_scores_rejected(self):
        for values in ({"relevant": 1}, {"relevant": "true"}, {"score": True},
                       {"score": "90"}, {"reason": 123}, {"score": float("nan")},
                       {"score": float("inf")}, {"score": -float("inf")}):
            with self.subTest(values=values), self.assertRaises((TypeError, ValueError)):
                GeminiResult(**values)

    def test_false_and_zero_are_preserved(self):
        result = GeminiResult(status="SUCCESS", relevant=False, score=0)
        restored = GeminiResult.from_json(result.to_json())
        self.assertIs(restored.relevant, False)
        self.assertEqual(restored.score, 0)

    def test_invalid_json_and_non_object_payloads(self):
        for model in (Notice, GeminiResult):
            with self.subTest(model=model), self.assertRaises(json.JSONDecodeError):
                model.from_json("{broken")
            for payload in ("[]", "null", '"text"', "42"):
                with self.subTest(model=model, payload=payload), self.assertRaises(TypeError):
                    model.from_json(payload)


if __name__ == "__main__":
    unittest.main()
