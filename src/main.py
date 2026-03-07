import customtkinter as ctk
import subprocess
import threading
import os
import platform
import time
import shutil
import re
from tkinter import messagebox

class OpenClawLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OpenClaw AI Manager Pro")
        self.geometry("750x950")
        
        # macOS PATH 보정 (Homebrew 경로 강제 추가)
        if platform.system() == "Darwin":
            os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin" + os.pathsep + "/usr/local/bin"

        # --- UI 레이아웃 ---
        self.label = ctk.CTkLabel(self, text="OpenClaw AI Manager", font=("Arial", 28, "bold"))
        self.label.pack(pady=20)

        # 1. 서비스 상태 모니터링 섹션
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.pack(pady=10, padx=20, fill="x")
        self.create_status_row("Docker Engine", "docker_status", self.stop_docker)
        self.create_status_row("Ollama Engine", "ollama_status", self.stop_ollama)

        # 2. 모델 및 API 설정 구역
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(self.config_frame, text="설정 모드:", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=10, pady=10)
        self.model_list = ["llama3.1 (로컬 무료)", "qwen2.5-coder (로컬)", "[직접 입력] 유료 API 사용"]
        self.model_combo = ctk.CTkComboBox(self.config_frame, values=self.model_list, width=250, command=self.on_model_change)
        self.model_combo.set("llama3.1 (로컬 무료)")
        self.model_combo.grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(self.config_frame, text="모델 이름:").grid(row=1, column=0, padx=10, pady=5)
        self.custom_model_entry = ctk.CTkEntry(self.config_frame, placeholder_text="예: claude-3-5-sonnet-latest", width=250, state="disabled")
        self.custom_model_entry.grid(row=1, column=1, padx=10, pady=5)

        ctk.CTkLabel(self.config_frame, text="API 키:").grid(row=2, column=0, padx=10, pady=5)
        self.api_entry = ctk.CTkEntry(self.config_frame, placeholder_text="sk-...", width=250, show="*", state="disabled")
        self.api_entry.grid(row=2, column=1, padx=10, pady=5)

        # 3. 로그 창 및 진행바
        self.log_box = ctk.CTkTextbox(self, width=680, height=300, font=("Consolas", 12))
        self.log_box.pack(pady=10, padx=20)
        self.progress = ctk.CTkProgressBar(self, width=680)
        self.progress.pack(pady=10)
        self.progress.set(0)

        # 4. 메인 버튼
        self.start_btn = ctk.CTkButton(self, text="🚀 원클릭 설치 및 실행", command=self.start_thread, height=55, font=("Arial", 20, "bold"))
        self.start_btn.pack(pady=20)

        self.update_status_loop()

    # --- 유틸리티 함수 ---
    def log(self, text):
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_box.see("end")

    def create_status_row(self, name, attr_name, stop_cmd):
        row = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        row.pack(pady=5, padx=10, fill="x")
        ctk.CTkLabel(row, text=name, width=150, anchor="w").pack(side="left")
        status_indicator = ctk.CTkLabel(row, text="⭕ 확인 중...", text_color="gray")
        status_indicator.pack(side="left", padx=20)
        setattr(self, attr_name, status_indicator)
        ctk.CTkButton(row, text="종료", width=60, fg_color="#CC3333", command=stop_cmd).pack(side="right")

    def on_model_change(self, choice):
        state = "normal" if "[직접 입력]" in choice else "disabled"
        self.custom_model_entry.configure(state=state)
        self.api_entry.configure(state=state)

    # --- 핵심 로직: 서비스 체크 ---
    def update_status_loop(self):
        threading.Thread(target=self._check_services, daemon=True).start()
        self.after(5000, self.update_status_loop) # 5초마다 체크

    def _check_services(self):
        # Docker 엔진 가동 여부 확인 (명령어 존재 여부가 아닌 데몬 응답 확인)
        d_check = subprocess.run("docker info", shell=True, capture_output=True, text=True)
        is_docker_up = d_check.returncode == 0
        self.docker_status.configure(text="✅ 실행 중" if is_docker_up else "❌ 중지됨",
                                     text_color="#22CC22" if is_docker_up else "#CC2222")

        # Ollama 체크
        o_cmd = "tasklist /FI \"IMAGENAME eq ollama.exe\"" if platform.system() == "Windows" else "pgrep ollama"
        o_check = subprocess.run(o_cmd, shell=True, capture_output=True, text=True)
        is_ollama_up = "ollama" in o_check.stdout.lower() or o_check.returncode == 0
        self.ollama_status.configure(text="✅ 실행 중" if is_ollama_up else "❌ 중지됨",
                                     text_color="#22CC22" if is_ollama_up else "#CC2222")

    # --- 핵심 로직: 환경변수 업데이트 ---
    def update_env_file(self, env_path, updates):
        """ .env 파일을 한 줄씩 읽어 안전하게 업데이트 """
        if not os.path.exists(env_path):
            if os.path.exists(env_path + ".example"):
                shutil.copy(env_path + ".example", env_path)
            else:
                with open(env_path, "w") as f: f.write("")

        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        applied_keys = set()

        for line in lines:
            match = re.match(r"^([A-Z_]+)=", line)
            if match:
                key = match.group(1)
                if key in updates:
                    new_lines.append(f'{key}="{updates[key]}"\n')
                    applied_keys.add(key)
                    continue
            new_lines.append(line)

        for key, value in updates.items():
            if key not in applied_keys:
                new_lines.append(f'{key}="{value}"\n')

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    # --- 메인 실행 프로세스 ---
    def start_thread(self):
        self.start_btn.configure(state="disabled", text="처리 중...")
        threading.Thread(target=self.main_logic, daemon=True).start()

    def main_logic(self):
        current_os = platform.system()
        base_path = os.path.join(os.path.expanduser("~"), "OpenClawProject")
        if not os.path.exists(base_path): os.makedirs(base_path)
        os.chdir(base_path)

        # 1. Docker 실행 확인 및 강제 구동 시도
        self.log("🔎 Docker 상태 점검 중...")
        if subprocess.run("docker info", shell=True, capture_output=True).returncode != 0:
            self.log("⚠️ Docker가 꺼져 있습니다. 실행을 시도합니다...")
            if current_os == "Windows":
                subprocess.Popen(["C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"])
            else:
                subprocess.run("open /Applications/Docker.app", shell=True)
            self.log("💡 Docker Desktop이 완전히 켜질 때까지 기다려주세요 (약 30초).")
            time.sleep(20)

        # 2. 필수 도구 설치 (winget / brew)
        self.log("🛠️ 필수 도구 설치 확인...")
        self.progress.set(0.2)
        
        if current_os == "Windows":
            # 관리자 권한 체크 생략(winget이 자체 요청), 필요 도구 리스트
            tools = {"git": "Git.Git", "ollama": "Ollama.Ollama", "docker": "Docker.DockerDesktop"}
            for cmd, target in tools.items():
                if shutil.which(cmd) is None:
                    self.log(f"📦 {cmd} 설치 중...")
                    subprocess.run(f"winget install --id {target} -e --accept-package-agreements --accept-source-agreements", shell=True)
        else:
            if shutil.which("brew") is None:
                self.log("📦 Homebrew 설치 중...")
                subprocess.run('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"', shell=True)
            
            for tool in ["git", "ollama", "docker"]:
                if shutil.which(tool) is None:
                    target = "docker --cask" if tool == "docker" else tool
                    subprocess.run(f"brew install {target}", shell=True)

        # 3. 소스 코드 다운로드 및 설정
        self.progress.set(0.5)
        if not os.path.exists("openclaw"):
            self.log("📥 OpenClaw 소스 다운로드...")
            subprocess.run("git clone https://github.com/openclaw/openclaw.git", shell=True)
        
        os.chdir("openclaw")
        env_path = os.path.abspath(".env")
        
        # 설정 업데이트 데이터 준비
        full_choice = self.model_combo.get()
        selected_model = full_choice.split(" ")[0] if "[직접 입력]" not in full_choice else self.custom_model_entry.get().strip()
        api_key = self.api_entry.get().strip()

        updates = {}
        if "[직접 입력]" in full_choice:
            key_name = "ANTHROPIC_API_KEY" if "sk-ant" in api_key else "OPENAI_API_KEY"
            updates = {key_name: api_key, "OPENCLAW_MODEL": selected_model}
        else:
            updates = {
                "OLLAMA_BASE_URL": "http://host.docker.internal:11434",
                "ANTHROPIC_API_KEY": "ollama-local",
                "OPENCLAW_MODEL": selected_model
            }
            # Ollama 모델 미리 받기
            self.log(f"🦙 모델 다운로드 중 ({selected_model})...")
            subprocess.run(f"ollama pull {selected_model}", shell=True)

        self.update_env_file(env_path, updates)
        self.log("📝 환경 설정(.env) 업데이트 완료")

        # 4. 실행
        self.progress.set(0.8)
        self.log("🚀 Docker 컨테이너 가동...")
        subprocess.run("docker-compose up -d", shell=True)
        
        self.progress.set(1.0)
        self.log("✨ 모든 준비가 끝났습니다! 5초 후 브라우저를 엽니다.")
        time.sleep(5)
        
        url = "http://localhost:3000"
        if current_os == "Windows": os.startfile(url)
        else: subprocess.run(f"open {url}", shell=True)
        
        self.start_btn.configure(state="normal", text="✅ 실행 중 (대시보드 다시 열기)")

    def stop_docker(self):
        if messagebox.askyesno("확인", "서비스를 중지하시겠습니까?"):
            os.chdir(os.path.join(os.path.expanduser("~"), "OpenClawProject", "openclaw"))
            subprocess.run("docker-compose down", shell=True)
            self.log("🛑 서비스가 중지되었습니다.")

    def stop_ollama(self):
        cmd = "taskkill /f /im ollama.exe" if platform.system() == "Windows" else "pkill ollama"
        subprocess.run(cmd, shell=True)
        self.log("🛑 Ollama 엔진을 종료했습니다.")

if __name__ == "__main__":
    app = OpenClawLauncher()
    app.mainloop()