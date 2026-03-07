import customtkinter as ctk
import subprocess
import threading
import os
import platform
import time
import socket
from tkinter import messagebox

class OpenClawLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OpenClaw AI Manager Pro")
        self.geometry("700x900")
        
        # --- UI 구성 ---
        self.label = ctk.CTkLabel(self, text="OpenClaw AI Manager", font=("Arial", 28, "bold"))
        self.label.pack(pady=20)

        # 1. 상태 모니터링 섹션
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.pack(pady=10, padx=20, fill="x")
        self.create_status_row("Docker (OpenClaw)", "docker_status", self.stop_docker)
        self.create_status_row("Ollama Engine", "ollama_status", self.stop_ollama)

        # 2. 모델 설정 섹션
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(self.config_frame, text="모델 선택:").grid(row=0, column=0, padx=10, pady=10)
        self.model_list = ["llama3.1", "qwen2.5-coder", "claude-3-5-sonnet", "[직접 입력]"]
        self.model_combo = ctk.CTkComboBox(self.config_frame, values=self.model_list, width=250)
        self.model_combo.set("llama3.1")
        self.model_combo.grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(self.config_frame, text="API 키:").grid(row=1, column=0, padx=10, pady=5)
        self.api_entry = ctk.CTkEntry(self.config_frame, placeholder_text="API 키 (선택사항)", width=250, show="*")
        self.api_entry.grid(row=1, column=1, padx=10, pady=5)

        # 3. 로그 창 및 진행바
        self.log_box = ctk.CTkTextbox(self, width=640, height=300, font=("Consolas", 12))
        self.log_box.pack(pady=10, padx=20)
        self.log_box.configure(state="disabled") 
        
        self.progress = ctk.CTkProgressBar(self, width=640)
        self.progress.pack(pady=10)
        self.progress.set(0)

        # 4. 실행 버튼
        self.start_btn = ctk.CTkButton(self, text=" 설치 및 통합 실행", command=self.start_thread, height=55, font=("Arial", 20, "bold"))
        self.start_btn.pack(pady=20)

        self.update_status_loop()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_status_row(self, name, attr_name, stop_cmd):
        row = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        row.pack(pady=5, padx=10, fill="x")
        ctk.CTkLabel(row, text=name, width=150, anchor="w").pack(side="left")
        status_indicator = ctk.CTkLabel(row, text="확인 중...", text_color="gray")
        status_indicator.pack(side="left", padx=20)
        setattr(self, attr_name, status_indicator)
        ctk.CTkButton(row, text="종료", width=60, fg_color="#CC3333", command=stop_cmd).pack(side="right")

    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")
        self.update_idletasks()

    def update_status_loop(self):
        threading.Thread(target=self._check_services, daemon=True).start()
        self.after(10000, self.update_status_loop)

    def _check_services(self):
        try:
            d_check = subprocess.run(["docker", "ps", "--filter", "name=openclaw-main", "-q"], capture_output=True, text=True)
            is_docker_on = bool(d_check.stdout.strip())
            self.docker_status.configure(text="● 실행 중" if is_docker_on else "○ 중지됨",
                                         text_color="#22CC22" if is_docker_on else "#CC2222")
            
            o_cmd = ["pgrep", "ollama"] if platform.system() == "Darwin" else ["tasklist", "/FI", "IMAGENAME eq ollama.exe"]
            o_check = subprocess.run(o_cmd, capture_output=True, text=True)
            is_ollama_on = "ollama" in o_check.stdout.lower() or o_check.returncode == 0
            self.ollama_status.configure(text="● 실행 중" if is_ollama_on else "○ 중지됨",
                                         text_color="#22CC22" if is_ollama_on else "#CC2222")
        except:
            pass

    def start_thread(self):
        self.start_btn.configure(state="disabled")
        threading.Thread(target=self.main_logic, daemon=True).start()

    def main_logic(self):
        current_os = platform.system()
        
        self.log(">>> [1] 기존 충돌 프로세스 및 포트 청소...")
        subprocess.run(["docker", "rm", "-f", "openclaw-main"], capture_output=True)
        # 🔥 팀킬을 유발하는 lsof kill 명령어를 아예 삭제했습니다!
        self.log(">>> [순정 모드] 안전 실행 및 우회 프록시 포트(18790) 개방...")
        
        # 🔥 변경 1: -p 18790:18790 포트를 추가하고, 에러를 내던 옵션을 지웠습니다.
        run_cmd = [
            "docker", "run", "-d",
            "--name", "openclaw-main",
            "-p", "18789:18789",
            "-p", "18790:18790", 
            "-e", "OPENCLAW_GATEWAY_AUTH_ENABLED=false",
            "-e", "OPENCLAW_GATEWAY_TOKEN=admin123",  # 🔥 우리가 직접 암호를 admin123으로 고정해버립니다!
            "-e", "OPENCLAW_MODEL=ollama/llama3.2:latest",
            "-e", "OLLAMA_HOST=http://host.docker.internal:11434",
            "openclaw:local",
            "openclaw", "gateway", "--port", "18789", "--allow-unconfigured" 
        ]

        self.log(">>> [2] 엔진 가동 시도...")
        result = subprocess.run(run_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            self.log(f"❌ 도커 실행 자체 실패: {result.stderr}")
            self.start_btn.configure(state="normal")
            return
        else:
            self.log(f"✅ 도커 실행 명령 전달! (ID: {result.stdout.strip()[:8]})")
            
        time.sleep(2)
        crash_check = subprocess.run(["docker", "ps", "-q", "-f", "name=openclaw-main"], capture_output=True, text=True)
        
        if not crash_check.stdout.strip():
            logs = subprocess.run(["docker", "logs", "openclaw-main"], capture_output=True, text=True)
            self.log("🚨 컨테이너가 실행 직후 종료되었습니다!")
            self.log(f"🔍 사망 원인: {logs.stderr or logs.stdout}")
            self.start_btn.configure(state="normal")
            return 
        else:
            self.log(">>> [대기] 엔진 정상 작동 중, 예열 대기 (최대 1분)...")

        success = False
        for i in range(20): 
            time.sleep(5)
            check = subprocess.run(
                ["docker", "exec", "openclaw-main", "curl", "-s", "http://127.0.0.1:18789/__openclaw__/canvas/"], 
                capture_output=True, text=True
            )
            
            if "OpenClaw Canvas" in check.stdout:
                self.log("✅ 엔진 내부 렌더링 완료! 우회 프록시 통로를 개척합니다.")
                
                # 🔥 변경 2: 무적의 꼼수! 컨테이너 내부에 Node.js TCP 프록시를 실행합니다.
                proxy_js = "require('net').createServer(c=>{let s=require('net').connect(18789,'127.0.0.1');c.pipe(s).pipe(c);s.on('error',()=>c.destroy());c.on('error',()=>s.destroy());}).listen(18790,'0.0.0.0')"
                proxy_cmd = ["docker", "exec", "-d", "openclaw-main", "node", "-e", proxy_js]
                subprocess.run(proxy_cmd)
                
                time.sleep(1) # 프록시가 켜질 시간 1초 대기
                success = True
                break
            
            curr_log = subprocess.run(["docker", "logs", "--tail", "1", "openclaw-main"], capture_output=True, text=True).stdout.strip()
            if curr_log:
                self.log(f"📋 엔진 상태: {curr_log[:50]}...")
            
            self.log(f"응답 대기 중... ({i*5+5}초 / 100초)")

        if success:
            # 🔥 변경 3: 사파리가 접속할 주소를 우회 포트인 18790으로 변경합니다.
            # 기존: url = "http://127.0.0.1:18790/"
            # 🔥 변경: 주소 뒤에 마스터키(토큰)를 달아서 자동 로그인 시킵니다!
            url = "http://127.0.0.1:18790/?token=admin123" 

            if current_os == "Darwin":
                subprocess.run(["open", "-a", "Safari", url])
                self.log("🚀 사파리 실행 완료! 프록시를 통해 우회/토큰 자동 로그인 접속했습니다.")
        else:
            self.log("❌ 엔진이 응답을 주지 않습니다. 다시 시도하거나 로그를 확인해주세요.")

        self.start_btn.configure(state="normal")

    def stop_docker(self):
        subprocess.run(["docker", "rm", "-f", "openclaw-main"])
        self._check_services()
        self.log("Docker 컨테이너를 중지했습니다.")

    def stop_ollama(self):
        cmd = ["pkill", "ollama"] if platform.system() == "Darwin" else ["taskkill", "/f", "/im", "ollama.exe"]
        subprocess.run(cmd)
        self._check_services()
        self.log("Ollama 엔진을 종료했습니다.")

    def on_closing(self):
        self.destroy()

if __name__ == "__main__":
    app = OpenClawLauncher()
    app.mainloop()