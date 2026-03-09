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