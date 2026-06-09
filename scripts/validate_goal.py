#!/usr/bin/env python3
# validate_goal.py — goalgoal 산출물(goal.json)의 단일 진실 원천(SSOT) 검증기.
# 이 스크립트가 통과/실패의 기준이다. assets/goal.schema.json은 '참조용'이며,
# jsonschema가 설치돼 있고 스키마 파일이 있으면 2차(드리프트 경고)로만 돌린다.
#
# 검증 철학: 하드 게이트.
#   - errors가 하나라도 있으면 pass=false, enforced_status="needs_review",
#     종료코드 1. 즉 모호하거나 /goal 계약을 안 지킨 목표는 절대 ready로 못 나간다.
#   - --strict: warnings도 종료코드 1로 막는다.
#
# 검사:
#   1) 스키마        — 필수 필드 존재 + 타입 + enum
#   2) 측정가능성     — (양성 규칙) 각 success_criteria는 관찰 가능 신호를 반드시 포함
#   3) Loop 호환성    — done≠stop 분리, max_iterations 양의 정수
#   4) /goal 계약     — goal_command 존재·≤4000자·턴바운드 포함·demonstrable
#   5) 안전           — risk_tier=elevated면 safety 블록 필수
#
# 사용법: python3 validate_goal.py <goal.json 경로> [--strict]

import json
import os
import re
import sys

REQUIRED_STR = ["goal", "goal_command", "domain", "scale",
                "done_definition", "verification_method"]
REQUIRED_LIST = ["success_criteria"]
DOMAINS = {"code", "data", "infra", "automation", "creative", "analysis"}
SCALES = {"spike", "mvp", "production"}
CONFIDENCE = {"high", "medium", "low"}
STATUS = {"ready", "needs_review"}
RISK_TIERS = {"none", "low", "elevated"}
SAFETY_KEYS = ["permissions_needed", "destructive_ops", "approval_gate", "privacy_notes"]
GOAL_COMMAND_MAX = 4000

# 관찰 가능 신호(양성 규칙). 숫자·단위·통과실패·이진검증 동사 포함.
OBSERVABLE = re.compile(
    r"(\d|%|퍼센트|초\b|분\b|시간|회\b|ms|통과|실패|동작|작동|실행|표시|노출|응답|"
    r"이상|이하|미만|초과|개\b|건\b|pass|fail|exit\s*0|2\d\d\b|status|<|>|=|✅|❌)",
    re.IGNORECASE,
)
# 측정 불가(모호) 표현 — 에러 메시지 보조용. 게이트는 OBSERVABLE 부재로 결정.
VAGUE = [
    "좋은", "좋게", "좋아", "적당", "어느 정도", "어느정도", "멋진", "멋지", "깔끔",
    "편한", "편하", "편해", "편리", "충분", "대충", "원활", "괜찮", "안정적", "유연",
    "사용성", "만족", "보기 좋", "느낌",
    "nice", "good", "fast", "better", "clean", "easy", "robust", "scalable", "smooth",
]
# /goal 턴/시간 바운드 신호 (무한루프 안전장치)
TURN_BOUND = re.compile(
    r"(stop\s+after|after\s+\d+\s+turns?|\d+\s*turns?|\d+\s*턴|"
    r"\d+\s*회\s*(반복|이내|초과|연속|후)|반복\s*\d+|max[_\s]*iterations?|"
    r"\d+\s*분\s*(후|이내|경과))",
    re.IGNORECASE,
)
# demonstrable 위반 안티패턴 (평가자가 대화로 확인 불가) — 경고
NON_DEMONSTRABLE = [
    "사용자가 만족", "만족스러", "보기 좋", "예뻐", "느낌이", "마음에 들",
    "파일을 읽어 확인", "파일을 열어 확인", "user is happy", "looks good", "feels",
]


def vague_hits(text):
    low = text.lower()
    return [w for w in VAGUE if w.lower() in low]


def check(goal_path, strict=False):
    errors, warnings, flags = [], [], []

    try:
        with open(goal_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {goal_path}", file=sys.stderr)
        return 2, None
    except json.JSONDecodeError as exc:
        print(f"JSON 파싱 실패: {exc}", file=sys.stderr)
        return 2, None
    if not isinstance(data, dict):
        print("최상위가 JSON 객체가 아닙니다.", file=sys.stderr)
        return 2, None

    # --- 1) 스키마 ---
    for key in REQUIRED_STR:
        val = data.get(key)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"필수 문자열 필드 누락/빈값: {key}")
    for key in REQUIRED_LIST:
        val = data.get(key)
        if not isinstance(val, list) or not [x for x in (val or []) if str(x).strip()]:
            errors.append(f"필수 리스트 필드 누락/빈값: {key}")
    if data.get("domain") not in DOMAINS:
        errors.append(f"domain은 {sorted(DOMAINS)} 중 하나여야 함 (현재: {data.get('domain')!r})")
    if data.get("scale") not in SCALES:
        errors.append(f"scale은 {sorted(SCALES)} 중 하나여야 함 (현재: {data.get('scale')!r})")
    if data.get("risk_tier") not in RISK_TIERS:
        errors.append(f"risk_tier는 {sorted(RISK_TIERS)} 중 하나여야 함 (현재: {data.get('risk_tier')!r})")
    if data.get("confidence") not in CONFIDENCE:
        warnings.append("confidence가 high/medium/low가 아님")
    if data.get("status") not in STATUS:
        errors.append("status는 ready 또는 needs_review여야 함")

    # --- 3) Loop 호환성 ---
    loop = data.get("loop_config")
    if not isinstance(loop, dict):
        errors.append("loop_config 객체 누락")
        loop = {}
    max_iter = loop.get("max_iterations")
    if not isinstance(max_iter, int) or isinstance(max_iter, bool) or max_iter <= 0:
        errors.append(f"loop_config.max_iterations는 양의 정수여야 함 (현재: {max_iter!r})")
    stop = loop.get("stop_condition")
    if not isinstance(stop, str) or not stop.strip():
        errors.append("loop_config.stop_condition 누락/빈값 (강제중단 안전장치 필수)")
    done = data.get("done_definition", "")
    if isinstance(done, str) and isinstance(stop, str) and done.strip() and \
            done.strip() == stop.strip():
        errors.append("done_definition과 stop_condition이 동일 — 완료/강제중단을 분리하세요")
    if isinstance(done, str) and re.search(r"(완성되면|끝나면|다 되면|done|finished)\s*$", done.strip()):
        warnings.append(f"done_definition이 자기참조적/모호: {done!r}")

    # --- 2) 측정가능성 (양성 규칙: 신호 없으면 ERROR) ---
    sc = data.get("success_criteria")
    if isinstance(sc, list):
        for item in sc:
            text = str(item)
            if not text.strip():
                continue
            if not OBSERVABLE.search(text):
                hits = vague_hits(text)
                hint = f" (모호어: {hits})" if hits else ""
                errors.append(f"[success_criteria] 관찰 가능 신호(숫자/통과·실패/동작·표시) 없음{hint}: {text!r}")
                flags.append({"field": "success_criteria", "text": text, "vague": hits})
    # done/stop도 모호어+신호부재면 경고
    for field, text in [("done_definition", done), ("stop_condition", stop)]:
        if isinstance(text, str) and text.strip() and not OBSERVABLE.search(text):
            hits = vague_hits(text)
            if hits:
                warnings.append(f"[{field}] 측정 불가 표현 {hits} 있고 신호 없음: {text!r}")

    # --- 4) /goal 계약 ---
    gc = data.get("goal_command")
    if isinstance(gc, str) and gc.strip():
        if len(gc) > GOAL_COMMAND_MAX:
            errors.append(f"goal_command가 {GOAL_COMMAND_MAX}자 초과 (현재 {len(gc)}자) — /goal 한도 위반")
        if not TURN_BOUND.search(gc):
            errors.append("goal_command에 턴/시간 바운드 없음 — 무한루프 방지 문구 필수 (예: 'or stop after 20 turns', '20턴 후 멈춘다')")
        nd = [p for p in NON_DEMONSTRABLE if p.lower() in gc.lower()]
        if nd:
            warnings.append(f"goal_command에 대화로 증명 불가한 표현 {nd} — 평가자(Haiku)는 도구·파일을 못 봄. 출력으로 증명되는 체크로 바꾸세요")

    # --- 5) 안전 (조건부 필수) ---
    if data.get("risk_tier") == "elevated":
        safety = data.get("safety")
        if not isinstance(safety, dict):
            errors.append("risk_tier=elevated인데 safety 블록 누락 (파일변경·시스템접근·콘텐츠읽기·외부전송 목표는 safety 필수)")
        else:
            for k in SAFETY_KEYS:
                v = safety.get(k)
                empty = (v is None or (isinstance(v, str) and not v.strip())
                         or (isinstance(v, list) and not v))
                if empty:
                    errors.append(f"safety.{k} 누락/빈값 (risk_tier=elevated 필수)")

    # --- 상태 일관성 + 하드게이트 enforce ---
    enforced_status = data.get("status")
    if errors:
        enforced_status = "needs_review"
        if data.get("status") == "ready":
            errors.append(f"status=ready인데 차단 이슈 {len(errors)}건 — needs_review로 강제 하향")

    # --- 6) 선택적 2차: jsonschema (드리프트 경고만) ---
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "assets", "goal.schema.json")
    try:
        import jsonschema  # type: ignore
        if os.path.exists(schema_path):
            with open(schema_path, encoding="utf-8") as sf:
                schema = json.load(sf)
            v = jsonschema.Draft7Validator(schema)
            for e in v.iter_errors(data):
                warnings.append(f"[schema 2차] {e.message}")
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"[schema 2차] 검사 건너뜀: {exc}")

    verdict = {
        "pass": len(errors) == 0,
        "enforced_status": enforced_status,
        "errors": errors,
        "warnings": warnings,
        "flags": flags,
        "summary": ("PASS" if not errors and not warnings
                    else ("PASS(경고 있음)" if not errors else "FAIL")),
    }
    print(json.dumps(verdict, ensure_ascii=False, indent=2))

    if errors:
        return 1, verdict
    if warnings and strict:
        return 1, verdict
    return 0, verdict


def main():
    args = [a for a in sys.argv[1:] if a != "--strict"]
    strict = "--strict" in sys.argv
    if len(args) != 1:
        print("사용법: python3 validate_goal.py <goal.json 경로> [--strict]", file=sys.stderr)
        sys.exit(2)
    code, _ = check(args[0], strict=strict)
    sys.exit(code)


if __name__ == "__main__":
    main()
