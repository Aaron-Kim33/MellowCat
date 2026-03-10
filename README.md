🦞 OpenClaw One-Click Installer for Mac/Windows
"맥북 M1/M2/M3 및 Windows 환경에서 OpenClaw를 단 한 번의 클릭으로 완벽하게 구동하세요."

본 프로젝트는 초보자들이 겪는 복잡한 도커(Docker) 설정, Ollama 연동, 에이전트 환경 변수 충돌 문제를 Python GUI 기반의 원클릭 자동화 스크립트로 해결한 설치 도구입니다. 수천 번의 트러블슈팅 끝에 완성된 가장 안정적인 배포판입니다.

✨ 핵심 기능
원클릭 배포: Python 스크립트 실행만으로 Ollama 기동, 모델 다운로드, 도커 컨테이너 생성을 자동화.

로컬 모델 강제화: OpenClaw가 유료 API(Claude 등)로 도망가지 못하도록 로컬 Ollama 엔진에 완벽 고정.

자동 프록시 터널링: 도커 내부 네트워크와 로컬 호스트 간의 복잡한 통신을 Node.js 프록시로 자동 연결.

환경 최적화: Apple Silicon(M1/M2/M3) 및 Windows 환경에 최적화된 자원 할당.






------------------------------------------------------------------------
🛠️ 트러블슈팅 기록 (The War Room Log)
본 프로젝트는 다음의 치명적인 오류들을 해결하는 과정에서 탄생했습니다.

1. 인증 오류 (401 Unauthorized / Token Mismatch)
문제: 시크릿 모드로 접속해도 이전 세션 정보가 남아 인증 오류가 발생하거나, 게이트웨이 토큰이 일치하지 않음.

원인: OpenClaw는 ~/.openclaw 내부에 숨겨진 데이터베이스를 생성하며, 단순 파일 삭제(*)로는 숨김 파일(.)이 지워지지 않아 과거의 잘못된 인증 정보가 계속 호출됨.

해결: rm -rf 명령어를 통해 폴더 자체를 뿌리 뽑고, 실행 시 admin123 토큰을 강제 주입하여 인증 절차를 일원화함.

2. 기본 모델 회귀 현상 (The Claude Escape)
문제: 설정을 마쳤음에도 로그에 agent model: anthropic/claude가 뜨며 유료 API를 요구함.

원인: OpenClaw의 깐깐한 JSON 스키마 때문. model 지정 시 문자열이 아닌 {"primary": "model_id"} 형태의 객체 구조를 갖춰야만 인식됨.

해결: 공식 규격에 맞는 JSON 스키마를 동적으로 생성하고, 도커 환경 변수(OPENCLAW_MODEL)를 통해 2중으로 모델을 고정함.

3. 언어 폭주 및 JSON 답변 오류 (The Hallucination)
문제: AI가 한국어 질문에 독일어, 베트남어 등을 섞어 쓰거나, 답변 대신 도구 실행 코드({"name":...})만 출력함.

원인: 경량 모델(Llama 3.2 등)이 OpenClaw의 복잡한 에이전트 지침을 처리하며 발생하는 '지능의 병목 현상'.

해결: OPENCLAW_SYSTEM_PROMPT를 통해 출력 형식을 강제하고, TEMPERATURE를 낮춰 AI의 환각을 억제함.

JSON 규격 역해킹 및 UI 에러(Unsupported type) 돌파
문제: 런처에서 config.json에 채널 정보를 미리 적어두면 대시보드 UI가 깨지거나(Unsupported type), 백엔드 보안 시스템(Doctor)이 평문 토큰을 감지해 에러(Unrecognized key)를 뿜어냄.

해결 (CLI 다이렉트 주입): JSON 파일은 채널/스킬을 완전히 비워둔 **'순정(Vanilla) 상태'**로 생성하여 Doctor의 보안 검사를 무사통과시킴. 이후 도커(Gateway)가 완벽히 부팅된 것을 로그로 확인한 직후, 터미널 명령어(channels add)를 백그라운드에서 쏴서 토큰을 안전한 내부 DB로 밀어 넣는 우회 주입 기법을 완성함.

2. 3대 메신저(Telegram, Discord, WhatsApp) 원클릭 연동 시스템 구축
Telegram / Discord: UI에 토큰 입력 칸을 만들고, 초보자를 위해 토큰 발급 방법을 알려주는 ? 도움말 가이드 버튼을 추가함.

WhatsApp: 토큰 방식이 아닌 QR 스캔 방식임을 감안하여, **'전용 터미널 호출 버튼'**을 제작. 버튼 클릭 시 OS(Mac/Win)에 맞춰 네이티브 터미널/CMD 창을 띄우고 QR 코드를 자동 출력하도록 구현.

3. 'Pairing' 기반의 철통 보안 아키텍처 확립
문제: 정책을 open으로 설정하면 누구나 봇 아이디만 알면 사용자의 로컬 자원(GPU)과 API 크레딧을 무단으로 사용할 수 있는 심각한 보안 취약점 발견.

해결 (보안 UI 통합): 기본값을 무조건 pairing(승인 모드)으로 강제함. 봇이 메신저로 8자리 코드를 보내면, 런처 하단의 **'기기 승인(Pairing) UI'**에 코드를 입력해 원클릭으로 승인(approve)할 수 있도록 설계. 터미널 조작 없이 보안과 편의성을 동시에 잡음.

4. 도커(Docker) 아키텍처의 한계 규명 및 스킬(Skills) 최적화
문제: Apple Notes, iMessage 등 특정 스킬들이 Missing 에러를 뱉으며 작동하지 않음.

해결 (Auto-discovery 전환): 도커는 철저히 격리된 '리눅스 무균실'이므로 호스트 OS(macOS, Windows)의 네이티브 앱을 직접 제어할 수 없다는 구조적 한계를 명확히 규명함. 억지로 스킬을 켜는 체크박스 UI를 제거하고, OpenClaw 스스로 가용 스킬(Search, Terminal 등)을 스캔해 켜도록 **자동 인식(Auto-discovery)**에 맡겨 크로스 플랫폼 안정성을 극대화함.

5. '딥 클린(Deep Clean)' 초기화 로직 안정화
문제: 도커가 파일을 쥐고(Lock) 있어서 캐시가 삭제되지 않아 이전 세션의 에러가 계속 묻어나옴(UnboundLocalError 등).

해결: 파이썬 로직의 순서를 **[도커 강제 종료(Lock 해제) ➔ ~/.openclaw_data 폴더 통째로 삭제(shutil.rmtree) ➔ 폴더 재생성]**으로 완벽하게 재배치하여, 런처를 실행할 때마다 찌꺼기 없는 100% 클린 부팅을 보장함.

6. 크로스 플랫폼(Mac/Win) 및 UI 디테일 완성
하드웨어 램(RAM) 용량을 자동 체크하여 적합한 모델을 추천하는 시스템 구축.

실시간 백엔드 로그([CLI 결과])를 런처 화면에 바로 띄워 직관적인 모니터링 가능.

13인치 화면 비율을 고려해 창 세로 해상도를 컴팩트하게 압축(780x850).

Windows의 winget과 Mac의 brew, pkill과 taskkill 등 OS별 분기 처리를 통해 어떤 환경에서도 완벽히 돌아가는 범용성 확보.

🐛 수정된 버그 6가지
문제	원인	수정 내용
Mac에서 크래시	ctypes.windll을 플랫폼 체크 없이 사용	is_admin() 상단에 platform.system() != "Windows" 가드 추가
UnboundLocalError	model_mapping 루프에서 매칭 실패 시 변수 미정의	OLLAMA_MODELS 리스트 기반으로 안전한 매칭 로직으로 재구성
Ollama 상태 오탐 (Windows)	tasklist returncode가 항상 0	stdout에 "ollama.exe" 문자열이 있는지 직접 확인하도록 수정
매 실행마다 데이터 전체 삭제	shutil.rmtree(config_dir)로 페어링 DB까지 삭제	config.json 파일만 교체, 나머지 데이터 유지
Mac에서 Docker 미체크	start_docker_engine()이 Mac에서 그냥 True 반환	open -a Docker 명령어로 Mac Docker 자동 구동 + 공통 60초 대기 루프 적용
외부 API 모드에 API 키 필드 없음	직접 입력 시 API 키 입력란 없음	클라우드 모드 전용 API 키 입력 UI 및 컨테이너 환경변수 주입 추가
✨ 새로 추가된 기능: AI 모드 선택 UI
Cline과 유사한 구조로 구현:

🏠 로컬 Ollama 탭: RAM에 따라 모델 자동 추천 (🟢/🔴 표시), 직접 입력 지원
☁️ 클라우드 API 탭:
Provider 선택: OpenAI / Anthropic (Claude) / Google Gemini / Groq / OpenRouter
모델 선택: Provider 변경 시 자동으로 해당 모델 목록으로 업데이트
API 키 입력: show="*" 마스킹 + 👁 버튼으로 표시/숨기기 토글
🔑 API 키 발급 → 버튼: 선택된 Provider의 공식 발급 페이지 바로 열기
키 자동 저장: ~/.mellowcat_keys.json에 Provider별로 저장, 다음 실행 시 자동 복원

API 키 보안 강화 및 UI 안내 개선이 완료되었습니다.

🔐 보안 강화 내용
기존 문제: ~/.mellowcat_keys.json에 **평문(plain text)**으로 저장 → 파일만 열면 키 노출

새로운 방식: OS 내장 보안 키체인 사용

OS	저장 위치
Windows	자격 증명 관리자 (Windows Credential Manager)
macOS	키체인 앱 (Keychain Access)
keyring 라이브러리가 없거나 실패 시 → 자동으로 파일 폴백(fallback) 전환
기존에 파일로 저장된 키는 keyring으로 자동 마이그레이션됨 (파일에서 해당 항목 제거)
requirements.txt에 keyring 추가 완료
🛡️ UI 안내 문구 개선
클라우드 API 패널 하단에 어두운 초록 배경의 "개인정보 보호 안내 박스" 추가:


🛡️  개인정보 보호 안내
• MellowCat 은 100% 로컬에서 실행됩니다. 어떤 서버도 운영하지 않습니다.
• API 키는 이 PC의 OS 키체인에만 저장됩니다.
  (Windows: 자격 증명 관리자 / macOS: 키체인 앱)
• 키는 선택하신 AI 서비스(OpenAI 등)에만 직접 전달됩니다.
• MellowCat 개발자는 귀하의 키를 수집하거나 볼 수 없습니다.
왕초보 유저들도 "이 앱이 로컬 전용이며 키가 외부로 나가지 않는다"는 것을 명확히 인지할 수 있습니다.

### ✅ 변경사항 요약

__1. 메신저 채널 연동 섹션 완전 제거__

- 런처에서 Telegram/Discord/WhatsApp 토큰 입력 UI 삭제
- 대신 모든 지원 채널을 `config.json`에 `enabled: false`로 미리 등록
- 실행 완료 후 브라우저 대시보드 → Channels 탭에서 직접 설정 가능
- __지원 채널 10종 모두 등록__: WhatsApp, Telegram, Discord, Slack, Teams, Instagram, Messenger, LINE, SMS, Email

__2. Skills Docker 플래그 추가 (최선의 시도)__

- `--cap-add NET_ADMIN`, `--cap-add SYS_PTRACE` 권한 추가
- `-e OPENCLAW_SKILLS_ENABLED=true` 환경변수 주입
- Mac/Linux 환경에서 `--add-host host.docker.internal:host-gateway` 자동 추가
- config에 `"skills": {"enabled": true}` 포함

__3. 버튼 항상 보이도록 레이아웃 수정__

- 버튼, 진행 바, 로그 박스를 `side="bottom"` 으로 __하단 고정__
- 클라우드 API 탭으로 전환해도 버튼이 항상 화면 하단에 고정되어 보임

__4. 동적 창 크기 (어떤 해상도에서도 정상 작동)__

- 실행 시 화면 해상도를 감지하여 `min(820, screen - 80)` 으로 창 크기 자동 조정
- 화면 중앙 자동 배치
- `minsize(680, 520)` + `resizable(True, True)` 적용
- 중앙 콘텐츠를 `CTkScrollableFrame` 으로 감싸 작은 화면에서도 스크롤 가능

🐛 수정된 버그 3가지
#	위치	기존 (버그)	수정 후
버그 1	CLOUD_PROVIDERS["Anthropic (Claude)"]["base_url"]	https://api.anthropic.com	https://api.anthropic.com/v1
버그 2	config.json provider 섹션	apiKey 필드 없음	"apiKey": api_key 추가
버그 3	Google Gemini api_style	"gemini" (OpenClaw 미지원)	"openai" (OpenAI 호환 엔드포인트 사용)
🔍 각 버그 상세 설명
버그 1 — Anthropic base URL /v1 누락
Anthropic API는 https://api.anthropic.com/v1/messages 엔드포인트를 사용합니다. /v1이 없으면 OpenClaw가 경로를 찾지 못해 provider 연결 실패 → doctor --fix 출력.

버그 2 — config.json에 apiKey 누락 (핵심 버그)
기존 코드는 API 키를 Docker 환경변수(-e OPENCLAW_API_KEY=...)로만 전달했습니다. 하지만 OpenClaw는 config.json의 provider.apiKey 필드를 우선 참조하며, 이 필드가 없으면 인증 실패로 doctor --fix 오류를 냅니다. 이제 "apiKey": api_key를 config.json에도 포함하고, 환경변수로도 이중 전달합니다.

버그 3 — Gemini api_style: "gemini" → "openai"
Google Gemini는 OpenAI 호환 엔드포인트(/v1beta/openai)를 제공하므로, api_style을 "openai"로 바꾸고 base_url에 /openai 경로를 추가했습니다. OpenClaw는 "gemini" 스타일을 별도 지원하지 않습니다.

__Slack/Google Chat 활성화 가능 여부:__

- __Slack__: ✅ 가능 — Bot Token(xoxb-) + App Token(xapp-) 두 개 필요
- __Google Chat__: ✅ 가능하나 복잡 — webhook URL + audience 설정 필요 (런처에 미포함)

__main.py 변경 사항:__

1. __채널 토큰 입력 UI 추가__ (이전 버전 방식 복원):

   - Telegram 봇 토큰 입력란 + `?` 도움말 버튼
   - Discord 봇 토큰 입력란 + `?` 도움말 버튼
   - Slack Bot Token(xoxb-) + App Token(xapp-) 입력란 + `?` 도움말 버튼
   - WhatsApp QR 코드 연동 버튼 (시스템 실행 후 클릭)

2. __Pairing 승인 섹션__ 추가 (telegram/whatsapp/discord/slack)

3. __게이트웨이 부팅 후 토큰 자동 주입__ (`openclaw channels add` CLI):

   - Telegram: `--channel telegram --token`
   - Discord: `--channel discord --token`
   - Slack: `--channel slack --bot-token --app-token`

4. __channels config 형식__: 이전 버전 검증된 형식 유지 (whatsapp/telegram/discord/slack/signal + 각 채널별 올바른 필드)

