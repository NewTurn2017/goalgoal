# goal.json 스키마 & 측정가능성 가이드

산출물 `goal.json`은 Claude Code의 **`/goal`** 명령이 소비한다. `/goal`의 계약은 `references/loop-formats.md` 참조 — 이 문서는 필드 정의와 품질 규칙에 집중한다. 검증의 단일 진실 원천은 `scripts/validate_goal.py`이며, `assets/goal.schema.json`은 **참조용**이다.

## 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `goal_command` | string | ✅ **운영 1순위** | `/goal`에 그대로 넣는 ≤4,000자 산문 완료조건. 측정가능 종료상태 + **대화로 증명되는** 체크 + 제약 + 턴바운드 + 실패 시 사람 대기. 작성법: `loop-formats.md` |
| `goal` | string | ✅ | 한 문장 목표 (goal_command 합성의 씨앗) |
| `domain` | enum | ✅ | code · data · infra · automation · creative · analysis |
| `scale` | enum | ✅ | spike · mvp · production |
| `success_criteria` | string[] | ✅ | **관찰 가능 신호**(숫자·%·통과/실패·동작/표시)를 각 항목이 포함. 1개 이상 |
| `done_definition` | string | ✅ | 성공적으로 완료된 상태 (stop_condition과 별개) |
| `verification_method` | string | ✅ | 각 반복 결과를 대화 출력으로 어떻게 증명하나 |
| `risk_tier` | enum | ✅ | none · low · **elevated** (파일변경·시스템접근·사용자 콘텐츠 읽기·외부 전송) |
| `safety` | object | ⚠️ 조건부 | `risk_tier=elevated`면 **필수**. 아래 참조 |
| `loop_config` | object | ✅ | 아래 참조 |
| `loop_config.max_iterations` | int>0 | ✅ | 최대 반복 횟수 (goal_command 턴바운드의 N) |
| `loop_config.stop_condition` | string | ✅ | 루프 **강제 중단** 안전장치 (done과 별개) |
| `loop_config.checkpoint` | string | | 중간 저장 방식 (선택) |
| `constraints` | string[] | | 시간·비용·기술·금지사항 |
| `out_of_scope` | string[] | | 이번엔 하지 않을 것 |
| `risks` | string[] | | 가장 큰 실패 모드 |
| `confidence` | enum | ✅ | high · medium · low |
| `status` | enum | ✅ | ready · needs_review |
| `open_questions` | string[] | | 미정으로 남긴 항목 (이탈/재개 시 이어 물을 목록) |
| `freetext_note` | string | | Other 자유입력 보존용 (선택) |

### safety 블록 (risk_tier=elevated 필수)

| 키 | 설명 |
|----|------|
| `permissions_needed` | 필요한 시스템 권한 (예: 풀디스크액세스, 네트워크) |
| `destructive_ops` | 되돌리기 어려운 작업 (파일 이동·삭제·전송) |
| `approval_gate` | 사람 승인 게이트 (예: "파일 이동은 클릭 후에만") |
| `privacy_notes` | 어떤 사용자 데이터를 읽고 어디로 보내나 |

## ★ Demonstrable-in-conversation (핵심 철칙)

`/goal` 평가자(Haiku 계열)는 **도구를 못 돌리고 파일을 직접 못 읽는다.** 대화에 드러난 내용만으로 판정한다. 따라서 `success_criteria`·`goal_command`의 모든 체크는 **Claude가 출력으로 증명할 수 있는 것**이어야 한다.

```
BAD  "사용자가 쓰기 편하다"               # 평가자가 확인 불가
BAD  "config.json을 읽어 설정 확인"        # 평가자는 파일 못 읽음
GOOD "`swift build`가 exit 0으로 통과 (출력에 표시)"
GOOD "`ls ~/Desktop | wc -l` 결과가 10 이하로 출력"
GOOD "단위 테스트 통과율 100%가 테스트 출력에 표시"
```

## done_definition vs stop_condition

- **`done_definition`** = *성공적으로* 끝난 상태("목표 달성" 신호).
- **`loop_config.stop_condition`** = 성공과 무관하게 루프를 *멈춰야* 하는 안전장치.

둘은 반드시 분리한다. 동일하면 검증기가 **error**로 막는다(하드 게이트). goal_command에는 둘 다 들어간다(완료조건 + 턴바운드/실패중단).

## 측정가능성 휴리스틱 (양성 규칙)

각 `success_criteria`는 **관찰 가능 신호를 반드시 하나 이상 포함**해야 통과한다(없으면 검증기 error). 신호 = 숫자, `%`, 시간/횟수 단위, `통과/실패`, `exit 0`, 비교(`<`,`>`), 또는 이진검증 동사(`동작/작동/실행/표시/노출/응답`). 모호어 목록(`좋은/적당/사용성/만족…`)은 에러 메시지를 돕는 보조일 뿐, 게이트는 "신호 부재"로 판정한다.

## v2 예시 (status: ready)

```json
{
  "goal_command": "바탕화면 정리 기능 4개가 'AI 제안 → 사용자 승인 → 정리' 플로우로 동작하고 빌드가 통과할 때까지 멈추지 말고 macOS 메뉴바 앱을 구현한다. 각 마일스톤이 끝나면 다음을 실행해 출력에 남긴다: `swift build`가 exit 0; 앱 실행 후 메뉴바 항목 4개(바탕화면/다운로드/스크린샷/중복찾기)가 로그에 표시; 정리 시뮬레이션에서 사용자 승인 없이 이동된 파일 수가 0으로 출력. 제약(불변): 파일 이동·삭제는 반드시 사용자 승인(클릭) 후에만; 화면·집중/클립보드 세트·클라우드 동기화는 구현 안 함. 종료 안전장치: 위가 모두 충족되면 완료, 또는 25턴 후 멈춘다 (or stop after 25 turns), 빌드가 3회 연속 실패하면 자체 수정을 멈추고 사람의 결정을 기다린다.",
  "goal": "사소한 파일 정리를 자동화하는 macOS 메뉴바 앱을 만든다 (첫 핵심: 바탕화면 정리, AI 제안+사용자 승인)",
  "domain": "code",
  "scale": "mvp",
  "success_criteria": [
    "사용자 승인 없이 이동되는 파일 수가 0건으로 출력된다",
    "파일 정리 기능 4개(바탕화면/다운로드/스크린샷/중복찾기)가 각각 메뉴바에서 실행·동작한다",
    "정리 후 `ls ~/Desktop | wc -l` 결과가 사용자 지정 목표치(예: 10) 이하로 출력된다"
  ],
  "done_definition": "Swift+SwiftUI 메뉴바 앱이 `swift build` 통과 후 메뉴바에 상주하고, 4개 기능이 'AI 제안→승인→정리'로 동작함을 직접 실행 출력으로 확인",
  "verification_method": "각 기능을 실행해 결과를 출력에 남기고, 승인 없는 파일 이동이 0건인지 매 반복 확인",
  "risk_tier": "elevated",
  "safety": {
    "permissions_needed": ["풀디스크액세스(바탕화면/다운로드 접근)"],
    "destructive_ops": ["파일 이동", "중복 파일 삭제 후보 처리"],
    "approval_gate": "모든 파일 이동·삭제는 사용자 클릭 승인 후에만 실행",
    "privacy_notes": "바탕화면 파일명·메타데이터를 분류용으로 AI에 전달. 파일 내용 본문은 보내지 않음"
  },
  "constraints": [
    "파일 이동·삭제는 사용자 확인(클릭) 후에만 — 자동 이동 금지",
    "Swift + SwiftUI 네이티브, macOS 메뉴바 앱"
  ],
  "out_of_scope": ["화면·집중 세트", "클립보드 세트", "클라우드 동기화", "앱스토어 출시"],
  "risks": ["중요 파일 오분류·오이동 → 승인 게이트로 완화", "풀디스크액세스 권한 필요", "AI 호출 비용·오분류"],
  "loop_config": {
    "max_iterations": 25,
    "stop_condition": "반복 25회 초과 또는 빌드 실패 3회 연속, 또는 사용자 승인 없는 파일 이동이 1건이라도 발생",
    "checkpoint": "iteration마다 git commit"
  },
  "confidence": "high",
  "status": "ready"
}
```
