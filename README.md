🦞 OpenClaw One-Click Installer for Mac/Windows
"맥북 M1/M2/M3 및 Windows 환경에서 OpenClaw를 단 한 번의 클릭으로 완벽하게 구동하세요."

본 프로젝트는 초보자들이 겪는 복잡한 도커(Docker) 설정, Ollama 연동, 에이전트 환경 변수 충돌 문제를 Python GUI 기반의 원클릭 자동화 스크립트로 해결한 설치 도구입니다. 수천 번의 트러블슈팅 끝에 완성된 가장 안정적인 배포판입니다.

✨ 핵심 기능
원클릭 배포: Python 스크립트 실행만으로 Ollama 기동, 모델 다운로드, 도커 컨테이너 생성을 자동화.

로컬 모델 강제화: OpenClaw가 유료 API(Claude 등)로 도망가지 못하도록 로컬 Ollama 엔진에 완벽 고정.

자동 프록시 터널링: 도커 내부 네트워크와 로컬 호스트 간의 복잡한 통신을 Node.js 프록시로 자동 연결.

환경 최적화: Apple Silicon(M1/M2/M3) 및 Windows 환경에 최적화된 자원 할당.

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