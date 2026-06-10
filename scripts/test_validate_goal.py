#!/usr/bin/env python3
# test_validate_goal.py — validate_goal.py(SSOT)의 회귀 테스트.
# 표준 라이브러리만 사용. 픽스처를 임시 파일로 써서 check()를 호출하고,
# 기대한 pass/error/warning이 나오는지 검사한다.
#
# 사용법: python3 scripts/test_validate_goal.py
#   모두 통과하면 종료코드 0, 하나라도 실패하면 1.

import contextlib
import copy
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_goal  # noqa: E402


# 최소 유효 goal.json (risk_tier=none).
VALID = {
    "goal_command": (
        "모든 테스트가 통과할 때까지 멈추지 말고 인증 모듈을 구현한다. "
        "각 마일스톤이 끝나면 `npm test` 통과율 100%를 출력에 남긴다. "
        "제약: 다른 테스트 파일은 수정하지 않는다. "
        "종료 안전장치: 위가 충족되면 완료, 또는 20턴 후 멈춘다 (or stop after 20 turns), "
        "검증이 3회 연속 실패하면 자체 수정을 멈추고 사람의 결정을 기다린다."
    ),
    "goal": "auth 모듈의 모든 테스트를 통과시킨다",
    "domain": "code",
    "scale": "mvp",
    "success_criteria": ["`npm test` 통과율 100%가 출력에 표시된다"],
    "done_definition": "npm test가 통과율 100%로 출력되고 lint가 clean",
    "verification_method": "각 반복마다 npm test 결과를 출력에 남김",
    "risk_tier": "none",
    "loop_config": {
        "max_iterations": 20,
        "stop_condition": "반복 20회 초과 또는 테스트 3회 연속 실패",
    },
    "confidence": "high",
    "status": "ready",
}


def run(data, strict=False):
    """check()를 임시 파일에 대해 돌리고 verdict를 반환(표준출력 억제)."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
        path = fh.name
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _code, verdict = validate_goal.check(path, strict=strict)
        return verdict
    finally:
        os.unlink(path)


def mutate(**changes):
    d = copy.deepcopy(VALID)
    for k, v in changes.items():
        d[k] = v
    return d


# (이름, goal.json, 기대) — 기대는 'pass' / 'error' / 'warn'(통과+경고)
CASES = []


def case(name, data, expect):
    CASES.append((name, data, expect))


# --- 통과 ---
case("기본 유효", VALID, "pass")

# --- 약신호 단독 = 통과+경고 ---
case("동작/표시 단독은 경고",
     mutate(success_criteria=["메뉴바에 항목이 표시된다"]), "warn")

# --- 실패중단 문구 없으면 경고(턴바운드는 있음) ---
case("실패중단 문구 누락은 경고",
     mutate(goal_command=(
         "테스트가 통과할 때까지 구현한다. `npm test` 통과율 100%를 출력에 남긴다. "
         "또는 20턴 후 멈춘다 (or stop after 20 turns).")), "warn")

# --- 에러: 측정 불가 ---
case("잘 동작한다 = 약신호+모호어 에러",
     mutate(success_criteria=["앱이 잘 동작한다"]), "error")
case("사용성이 좋다 = 신호 전무 에러",
     mutate(success_criteria=["사용성이 좋다"]), "error")
case("제대로 작동 = 모호어+약신호 에러",
     mutate(success_criteria=["기능이 제대로 작동한다"]), "error")

# --- 에러: done == stop ---
case("done과 stop 동일 = 에러",
     mutate(done_definition="루프를 멈춘다",
            loop_config={"max_iterations": 20, "stop_condition": "루프를 멈춘다"}),
     "error")

# --- 에러: 턴바운드 없는 goal_command ---
case("goal_command 턴바운드 누락 = 에러",
     mutate(goal_command=(
         "테스트가 통과할 때까지 구현한다. `npm test` 통과율 100%를 출력에 남긴다. "
         "3회 연속 실패하면 사람의 결정을 기다린다.")), "error")

# --- 에러: goal_command 4000자 초과 ---
case("goal_command 4000자 초과 = 에러",
     mutate(goal_command="20턴 후 멈춘다. " + ("가" * 4100)), "error")

# --- 에러: elevated인데 safety 누락 ---
case("elevated + safety 누락 = 에러",
     mutate(risk_tier="elevated"), "error")

# --- 통과: elevated + 완전한 safety ---
case("elevated + safety 완비 = 통과",
     mutate(risk_tier="elevated", safety={
         "permissions_needed": ["풀디스크액세스"],
         "destructive_ops": ["파일 이동"],
         "approval_gate": "이동은 클릭 후에만",
         "privacy_notes": "파일명만 분류용으로 전달",
     }), "pass")

# --- 에러: 필수 필드 누락 ---
case("success_criteria 누락 = 에러",
     mutate(success_criteria=[]), "error")
case("잘못된 domain = 에러",
     mutate(domain="mobile"), "error")

# --- 에러: status ready인데 차단 이슈 → needs_review 강제 ---
case("ready인데 에러 있으면 needs_review 강제",
     mutate(success_criteria=["사용성이 좋다"], status="ready"), "error")


def main():
    failed = []
    for name, data, expect in CASES:
        v = run(data)
        has_err = len(v["errors"]) > 0
        has_warn = len(v["warnings"]) > 0
        if expect == "pass":
            ok = v["pass"] and not has_err
        elif expect == "warn":
            ok = v["pass"] and not has_err and has_warn
        elif expect == "error":
            ok = (not v["pass"]) and has_err
        else:
            ok = False

        # 추가 불변식: 에러가 있으면 enforced_status는 절대 ready가 아니다.
        if has_err and v["enforced_status"] == "ready":
            ok = False
            extra = " [enforced_status=ready 누수!]"
        else:
            extra = ""

        mark = "✅" if ok else "❌"
        print(f"{mark} {name} (기대={expect}, "
              f"errors={len(v['errors'])}, warnings={len(v['warnings'])})"
              f"{extra}")
        if not ok:
            failed.append(name)
            for e in v["errors"]:
                print(f"      err: {e}")
            for w in v["warnings"]:
                print(f"      warn: {w}")

    print(f"\n{len(CASES) - len(failed)}/{len(CASES)} 통과")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
