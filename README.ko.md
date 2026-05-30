# Agentic Autobiography

## AI가 놓친 맥락을 다시 복구합니다.

Agentic Autobiography는 오늘 해커톤 데모를 위해 만든 로컬 우선 Codex 플러그인입니다. 단순한 챗봇이 아니라, 내 컴퓨터 안의 프로젝트 문서와 최근 작업 흔적을 훑어보고 “오늘 무슨 일이 있었는지”를 출처 기반 저널과 대시보드로 정리합니다.

핵심은 간단합니다.

> AI가 답만 하는 것이 아니라, 왜 그 답이 중요했는지까지 기억하게 만든다.

## 왜 필요한가

해커톤이나 프로젝트 막판에는 대화, 문서, 코드, 메모가 흩어집니다. 사람은 “아까 우리가 뭘 결정했지?”, “다음 액션이 뭐였지?”, “이 판단의 근거 파일이 어디 있었지?”를 자주 잊습니다.

Agentic Autobiography는 Codex가 그 맥락을 다시 찾을 수 있게 해줍니다.

- 최근 24시간의 작업 흐름을 저널로 정리합니다.
- 결정 사항과 할 일을 출처와 함께 뽑아냅니다.
- 타임라인과 최근 파일 활동을 보여줍니다.
- Codex 안에서 MCP 도구로 호출할 수 있습니다.
- 한국어 대시보드로 바로 데모할 수 있습니다.

## 오늘 데모 실행

```bash
python3 scripts/agentic_autobiography.py journal --hours 24
python3 scripts/agentic_autobiography.py render-dashboard --lang ko
python3 scripts/agentic_autobiography.py serve --port 8765 --lang ko
```

브라우저에서 엽니다.

```text
http://127.0.0.1:8765/dashboard/
```

## 데모에서 보여줄 것

1. 대시보드 상단의 한국어 UI를 보여줍니다.
2. “오늘의 저널”에서 24시간 요약을 보여줍니다.
3. 타임라인에서 오늘 실제로 바뀐 파일과 작업 흐름을 보여줍니다.
4. “결정 사항”과 “할 일”이 자동으로 추출된 것을 보여줍니다.
5. “최근 출처”에서 모든 내용이 실제 로컬 파일 경로와 연결되어 있음을 보여줍니다.

## 주요 기능

- 로컬 Markdown, TXT, JSON, CSV, PDF 텍스트를 인덱싱합니다.
- 최근 24시간 파일 활동을 스캔합니다.
- 프로젝트 맥락을 검색합니다.
- 타임라인, 결정 사항, 액션 아이템을 추출합니다.
- 출처 기반 일일 저널을 생성합니다.
- 영어/한국어 대시보드를 렌더링합니다.
- Codex 플러그인과 MCP 서버로 연결됩니다.

## Codex 플러그인 구조

플러그인 매니페스트:

```text
.codex-plugin/plugin.json
```

MCP 설정:

```text
.mcp.json
```

제공 도구:

- `memory.search`: 로컬 맥락 검색
- `memory.timeline`: 관련 타임라인 생성
- `memory.actions`: 할 일 추출
- `memory.summary`: 맥락 요약
- `journal.generate`: 24시간 저널 생성
- `dashboard.render`: 대시보드 렌더링

## 개인정보와 안전

기본 인덱싱 대상은 프로젝트 안의 `docs`, `samples` 폴더입니다. 저널 명령은 `config/activity_roots.json`에 설정된 최근 파일 활동 경로도 확인합니다.

기본 상태에서는 Gmail, Slack, 브라우저 히스토리, Calendar, Messages를 읽지 않습니다. 나중에 별도 커넥터를 명시적으로 추가하고 켰을 때만 그런 소스를 다루도록 설계했습니다.

## 검증 명령

```bash
python3 -m unittest tests/test_agentic_autobiography.py
.venv/bin/python /Users/m5max/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

## 해커톤 포지셔닝

- 트랙: RALPHTHON Track 1 - Codex Plugin
- 한 줄 설명: Codex가 잊어버린 프로젝트 맥락을 로컬 파일과 최근 활동에서 복구해, 하루의 저널과 대시보드로 보여주는 플러그인
- 데모 메시지: “이 플러그인은 AI를 더 똑똑한 답변기가 아니라, 내 작업 맥락을 기억하는 동료로 만든다.”
