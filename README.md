# goalgoal

> 막연한 한 줄 아이디어를, 자율 루프가 헛돌지 않고 돌릴 수 있는 **검증 가능한 목표(`goal.json`)** 로 바꿔주는 Claude Code / Codex 스킬.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

"쇼핑몰 만들어줘", "내 맥 좀 정리되게 해줘" 같은 한 줄은 사람에겐 통해도 **자율 반복 루프(Claude Code `/goal`)에는 미완성 입력**입니다. 성공 기준도, 완료 정의도, 멈출 조건도 없으면 루프는 무한 반복하거나 엉뚱한 방향으로 수렴하죠. goalgoal은 선택지 최대 4개짜리 질문으로 짧게 인터뷰해서 그 모호함을 걷어내고, `/goal`이 그대로 물고 돌릴 수 있는 `goal.json`(특히 **`goal_command` 완료조건**)을 만들어 바로 핸드오프합니다.

---

## ⚡ 한 줄 설치

```bash
curl -fsSL https://raw.githubusercontent.com/NewTurn2017/goalgoal/main/install.sh | bash
```

Claude Code(`~/.claude/skills`)와 Codex(`~/.codex/skills`)를 자동 감지해 **있는 곳마다 모두** 설치합니다. 재실행하면 업데이트(`git pull`)만 하므로 안전합니다(idempotent).

설치 확인:

```bash
ls -l ~/.claude/skills/goalgoal/SKILL.md   # 파일이 보이면 성공
```

> Windows는 아래 [수동 설치](#수동-설치)를 사용하세요(현재 PowerShell 부트스트랩은 제공하지 않습니다).

---

## 🚀 사용법

설치 후 Claude Code나 Codex에서 한 문장만 던지면 됩니다.

```
목표 잡아줘 — 매일 쓰는 사소한 일을 자동화하는 macOS 메뉴바 앱
```

그러면 goalgoal이:

1. 아이디어의 **명확도를 스코어링**하고 도메인·위험도를 분류합니다.
2. 한 문장에서 **추론 가능한 건 먼저 추정**하고, 답할 수 없는 핵심(성공기준·종료조건)만 **4개씩 묶어** 묻습니다(보통 4~8개, "잘 모르겠어요" 항상 제공).
3. 답을 모아 **`goal.json`** 을 만들고, **자체 검증**을 통과해야만 `ready`로 내보냅니다.
4. 마지막에 바로 이어 돌릴 명령을 추천합니다 — **`goal_command` 산문을 복붙하는 형태**입니다:

```
✅ goal.json 준비 완료. 아래 줄을 통째로 복사해 Claude Code에 붙여넣으세요:

  /goal <goal_command 전문>
```

`/goal`은 이 조건을 완료조건으로 삼아, 매 턴이 끝날 때마다 충족 여부를 평가하며 자동으로 반복합니다. (`/goal`은 자연어 조건만 받습니다 — `@goal.json` 같은 파일 문법은 공식 지원이 아니라서, JSON 전문이 아니라 `goal_command` 산문만 넣습니다. goal.json 파일은 기록·재검증·재개용으로 함께 남습니다.)

완성된 결과물 예시는 [`examples/goal.example.json`](./examples/goal.example.json)을 보세요.

---

## 🧠 어떻게 모호함을 없애나 (동작 원리)

goalgoal의 핵심은 인터뷰가 아니라 **"나쁜 목표는 통과시키지 않는다"는 게이트**입니다.

| 장치 | 내용 |
|------|------|
| **Iron Law (코드로 강제)** | 측정 불가능하거나 종료 조건이 없는 목표는 절대 `status: "ready"`로 못 나갑니다. `scripts/validate_goal.py`가 단일 진실 원천(SSOT)이며, 차단 이슈가 있으면 상태를 강제로 `needs_review`로 내립니다. |
| **Demonstrable-in-conversation** | `/goal` 평가자는 도구를 못 돌리고 파일을 못 읽습니다 — **대화에 드러난 출력만으로** 판정합니다. 그래서 모든 성공 기준은 "Claude가 출력으로 증명할 수 있는 것"이어야 합니다. (❌ "사용자가 만족" → ✅ "`swift build` exit 0", "`ls ~/Desktop \| wc -l` ≤ 10") |
| **측정가능성 양성 규칙** | 각 성공 기준은 숫자·%·통과/실패·동작/표시 같은 **관찰 신호를 반드시 포함**해야 통과합니다. |
| **risk_tier + safety** | 파일 변경·시스템 접근·콘텐츠 읽기·외부 전송이 있으면 `risk_tier: elevated`로 분류되고, 권한·파괴적작업·승인게이트·프라이버시를 담은 `safety` 블록이 **필수**가 됩니다. |
| **턴 바운드** | `goal_command`에 `"또는 N턴 후 멈춘다 (or stop after N turns)"`가 들어가야 무한 반복을 막습니다. |
| **재개점 = 산출물** | 인터뷰를 중간에 멈춰도 별도 세션 파일 없이, `needs_review` + `open_questions`로 저장된 `goal.json`에서 이어갑니다. |

---

## 📦 goal.json 스키마 (요약)

전체 정의와 좋은/나쁜 예시는 [`references/goal-schema.md`](./references/goal-schema.md) 참고.

| 필드 | 필수 | 설명 |
|------|:---:|------|
| `goal_command` | ✅ | `/goal`에 그대로 넣는 ≤4,000자 산문 완료조건 (측정가능 종료상태 + 대화로 증명되는 체크 + 제약 + 턴바운드) |
| `goal` | ✅ | 한 문장 목표 |
| `domain` | ✅ | code · data · infra · automation · creative · analysis |
| `scale` | ✅ | spike · mvp · production |
| `success_criteria` | ✅ | 관찰 가능 신호를 포함한 성공 기준(1개 이상) |
| `done_definition` | ✅ | 성공적으로 완료된 상태 |
| `verification_method` | ✅ | 각 반복 결과를 대화 출력으로 증명하는 방법 |
| `risk_tier` | ✅ | none · low · elevated |
| `safety` | ⚠️ | `risk_tier: elevated`면 필수 |
| `loop_config` | ✅ | `max_iterations`(>0) + `stop_condition`(강제중단) |
| `confidence` | ✅ | high · medium · low |
| `status` | ✅ | ready · needs_review |

---

## 🔍 검증기 직접 돌리기

`goal.json`이 `/goal`에 투입 가능한지 표준 라이브러리만으로 검사합니다(설치된 경우 `jsonschema`로 2차 검사).

```bash
python3 scripts/validate_goal.py examples/goal.example.json
# 통과 시 종료코드 0, {"pass": true, ...}
```

엄격 모드(경고도 실패 처리):

```bash
python3 scripts/validate_goal.py path/to/goal.json --strict
```

---

## 🗂 레포 구조

```
LICENSE
SKILL.md                      # 스킬 워크플로우 (스코어링→추정→인터뷰→생성→검증 9단계 + Iron Law)
install.sh                    # 한 줄 설치 스크립트
assets/goal.schema.json       # 참조용 JSON 스키마
examples/goal.example.json    # 완성된 goal.json 예시
evals/
  evals.json                  # 산출물 품질 테스트 케이스 3종 + 어서션
  trigger-eval.json           # description 트리거 정확도 평가 쿼리 20개
references/
  goal-schema.md              # goal.json 필드 정의 + 측정가능성 가이드
  loop-formats.md             # /goal 공식 계약 + 핸드오프 형식 + goal_command 템플릿
  question-pool.md            # 20개 마스터 질문 풀 + 추정(infer_first)/가지치기/조기종료
scripts/
  validate_goal.py            # 하드게이트 검증기 (SSOT)
  test_validate_goal.py       # 검증기 회귀 테스트 (14 픽스처)
```

---

## 🛠 설치 상세

### `install.sh`가 하는 일

1. `git` 설치 여부를 확인합니다(없으면 중단).
2. 설치 대상 디렉터리를 수집합니다 — `~/.claude/skills`, `~/.codex/skills`(존재할 때), 그리고 `$AGENT_SKILLS_DIR`(설정 시).
3. 아무것도 못 찾으면 `~/.claude/skills`를 기본값으로 사용합니다.
4. 각 위치에 이미 설치돼 있으면 `git pull`로 업데이트하고, 없으면 `git clone --depth 1`로 설치합니다.

### 환경 변수

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `GOALGOAL_REPO` | `https://github.com/NewTurn2017/goalgoal.git` | 포크 등 다른 소스에서 설치 |
| `AGENT_SKILLS_DIR` | (없음) | 추가 설치 위치를 직접 지정 |

### 수동 설치

```bash
git clone https://github.com/NewTurn2017/goalgoal.git ~/.claude/skills/goalgoal
# Codex도 쓴다면:
git clone https://github.com/NewTurn2017/goalgoal.git ~/.codex/skills/goalgoal
```

### 업데이트 / 제거

```bash
# 업데이트: 설치 스크립트 재실행 (또는)
git -C ~/.claude/skills/goalgoal pull

# 제거
rm -rf ~/.claude/skills/goalgoal ~/.codex/skills/goalgoal
```

---

## 📄 라이선스

[MIT](./LICENSE) © 2026 NewTurn2017
