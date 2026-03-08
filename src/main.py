import customtkinter as ctk
import subprocess
import threading
import os
import platform
import time
import shutil
import webbrowser
import ctypes
import tkinter.messagebox as messagebox

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class OpenClawLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        # OS 확인 (must come before any attribute access)
        self.is_mac = platform.system() == "Darwin"
        self.is_windows = platform.system() == "Windows"
        # When packaged as an executable we need admin rights on Windows;
        # running the script directly from the interpreter should not fail.
        import sys
        if self.is_windows and getattr(sys, "frozen", False) and not is_admin():
            messagebox.showerror("권한 필요", "이 애플리케이션을 실행하려면 관리자 권한이 필요합니다.")
            self.destroy()
            return
        
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
        self.model_list = ["llama3.2", "llama3.2:1b", "qwen2.5-coder:1.5b", "llama3.1"]
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
        # Thread-safe logging: delegate to main thread
        def update_log():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
            self.log_box.configure(state="disabled")
            self.log_box.see("end")
        self.after(0, update_log)

    def update_status_loop(self):
        threading.Thread(target=self._check_services, daemon=True).start()
        self.after(10000, self.update_status_loop)

    def _check_services(self):
        try:
            d_check = subprocess.run(["docker", "ps", "--filter", "name=openclaw-main", "-q"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            # if docker daemon isn't running, stdout may be empty or stderr contain text
            if d_check.returncode != 0:
                self.log(f"⚠️ Docker 상태 조회 실패: {d_check.stderr.strip()}")
            is_docker_on = bool(d_check.stdout.strip())
            self.docker_status.configure(text="● 실행 중" if is_docker_on else "○ 중지됨",
                                         text_color="#22CC22" if is_docker_on else "#CC2222")
        except Exception as e:
            self.log(f"⚠️ Docker 서비스 확인 중 오류: {e}")
            self.docker_status.configure(text="○ 중지됨", text_color="#CC2222")
        try:
            o_cmd = ["pgrep", "ollama"] if self.is_mac else ["tasklist", "/FI", "IMAGENAME eq ollama.exe"]
            o_check = subprocess.run(o_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            is_ollama_on = "ollama" in o_check.stdout.lower() or o_check.returncode == 0
            self.ollama_status.configure(text="● 실행 중" if is_ollama_on else "○ 중지됨",
                                         text_color="#22CC22" if is_ollama_on else "#CC2222")
        except Exception as e:
            self.log(f"⚠️ Ollama 상태 확인 중 오류: {e}")
            self.ollama_status.configure(text="○ 중지됨", text_color="#CC2222")

    def start_thread(self):
        self.start_btn.configure(state="disabled")
        self.progress.set(0)
        # 모델 다운로드 중인지 표시
        self.pulling_model = False
        # 메인 로직 전에 환경 검사부터 별도 스레드로 실행합니다.
        threading.Thread(target=self.check_and_install_dependencies, daemon=True).start()

    def run_winget(self, package_id):
        """윈도우용 조용한 백그라운드 설치 명령어"""
        cmd = [
            "winget", "install", "--id", package_id, 
            "-e", "--source", "winget", "--silent", 
            "--accept-package-agreements", "--accept-source-agreements"
        ]
        startupinfo = None
        if self.is_windows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        try:
            subprocess.run(cmd, check=True, startupinfo=startupinfo)
            return True
        except subprocess.CalledProcessError:
            return False

    def check_and_install_dependencies(self):
        try:
            self.log(">>> [0] 시스템 필수 환경 점검 시작...")
            self.progress.set(0.1)

            # 1. Ollama 체크 및 설치
            if not shutil.which("ollama"):
                self.log("⚠️ Ollama가 없습니다. 자동 설치를 시도합니다...")
                if self.is_windows:
                    if self.run_winget("Ollama.Ollama"):
                        self.log("✅ Ollama 설치 완료!")
                    else:
                        self.log("❌ Ollama 자동 설치 실패. 수동으로 설치해주세요.")
                        self.start_btn.configure(state="normal")
                        return
                elif self.is_mac:
                    try:
                        self.log("⏳ macOS에서 Ollama 설치 중...")
                        result = subprocess.run(["brew", "install", "ollama"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
                        if result.returncode == 0:
                            self.log("✅ Ollama 설치 완료!")
                        else:
                            self.log(f"❌ Ollama 설치 실패: {result.stderr}")
                            self.start_btn.configure(state="normal")
                            return
                    except subprocess.TimeoutExpired:
                        self.log("❌ Ollama 설치 타임아웃.")
                        self.start_btn.configure(state="normal")
                        return
                    except Exception as e:
                        self.log(f"❌ Ollama 설치 오류: {str(e)}")
                        self.start_btn.configure(state="normal")
                        return
                else:
                    self.log("❌ 지원되지 않는 OS입니다.")
                    self.start_btn.configure(state="normal")
                    return
            else:
                self.log("✅ Ollama가 이미 설치되어 있습니다.")
            self.progress.set(0.2)

            # 2. Docker 체크
            if not shutil.which("docker"):
                self.log("❌ Docker가 설치되어 있지 않습니다!")
                if self.is_windows:
                    self.log("⚠️ 윈도우는 Docker 설치 시 재부팅이 필수이므로 자동 설치가 위험합니다.")
                    self.log("👉 브라우저를 열어 다운로드 페이지로 이동합니다...")
                    webbrowser.open("https://docs.docker.com/desktop/install/windows-install/")
                else:
                    self.log("👉 브라우저를 열어 다운로드 페이지로 이동합니다...")
                    webbrowser.open("https://docs.docker.com/desktop/install/mac-install/")
                self.start_btn.configure(state="normal")
                return
            else:
                self.log("✅ Docker가 이미 설치되어 있습니다.")
            self.progress.set(0.3)

            # 필수 점검을 통과하면 기존 메인 로직으로 넘어갑니다.
            self.log(">>> 시스템 점검 완료. 메인 로직으로 진입합니다.")
            self.main_logic()
        except Exception as e:
            self.log(f"❌ 의존성 점검 중 오류 발생: {str(e)}")
            self.start_btn.configure(state="normal")

    def main_logic(self):
        try:
            import json

            self.log(">>> [긴급 복구] Ollama 엔진 및 모델 체크...")
            self.stop_ollama()
            ollama_env = os.environ.copy()
            ollama_env["OLLAMA_HOST"] = "0.0.0.0"
            
            # 윈도우 환경에서 콘솔창 숨기기
            startupinfo = None
            if self.is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            subprocess.Popen(["ollama", "serve"], env=ollama_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
            
            selected_model = self.model_combo.get()
            clean_model_id = selected_model.replace("ollama/", "")
            target_model = f"ollama/{clean_model_id}"
            
            # 모델 다운로드 시작 표시 및 progress bar 방어
            self.pulling_model = True
            self.log(f"⏳ '{clean_model_id}' 모델을 준비 중입니다. (처음엔 오래 걸릴 수 있습니다)")
            result = subprocess.run(["ollama", "pull", clean_model_id], startupinfo=startupinfo, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            # pull 명령의 stdout/err를 로그에 남겨 문제를 진단할 수 있도록
            if result.stdout:
                self.log(result.stdout.strip())
            if result.stderr:
                self.log(result.stderr.strip())
            if result.returncode != 0:
                raise Exception(f"Ollama pull failed (exit {result.returncode})")
            self.log(f"✅ 모델 준비 완료: {target_model}")
            self.progress.set(0.5)
            self.pulling_model = False

            # ---------------------------------------------------------
            self.log(">>> [1] 설정 파일(JSON) 재생성...")
            config_dir = os.path.expanduser("~/.openclaw_data")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "config.json")
            
            config_data = {
                "gateway": { "mode": "local" },
                "agents": { "defaults": { "model": { "primary": target_model } } },
                "models": {
                    "providers": {
                        "ollama": {
                            "baseUrl": "http://host.docker.internal:11434/v1",
                            "apiKey": "ollama-local",
                            "api": "openai-completions",
                            "models": [
                                {
                                    "id": target_model,
                                    "name": clean_model_id,
                                    "contextWindow": 32000
                                }
                            ]
                        }
                    }
                }
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            self.progress.set(0.6)

            # ---------------------------------------------------------
            # ---------------------------------------------------------
            self.log(">>> [2] 도커 컨테이너 완전 재부팅...")
            # make sure docker daemon is available
            info = subprocess.run(["docker", "info"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if info.returncode != 0:
                self.log(f"❌ Docker 데몬이 실행 중이 아닙니다: {info.stderr.strip()}")
                raise Exception("Docker daemon not running")
            
            subprocess.run(["docker", "rm", "-f", "openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
            
            # 👇 여기서부터가 핵심입니다!
            image_name = "aaronkim33/openclaw:latest" # 변수를 위로 빼서 통일합니다.

            # ensure image exists (이제 공식 이미지를 검사합니다)
            img_check = subprocess.run(["docker", "image", "inspect", image_name], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if img_check.returncode != 0:
                self.log(f"⚠️ 이미지 '{image_name}'을 찾을 수 없습니다. 다운로드를 시작합니다 (네트워크에 따라 수 분 소요)...")
                pull_result = subprocess.run(["docker", "pull", image_name], capture_output=True, text=True, encoding="utf-8", errors="replace")
                
                if pull_result.returncode != 0:
                    self.log(f"❌ 이미지 풀 실패: {pull_result.stderr.strip()}")
                    self.log("이미지를 레지스트리에서 가져올 수 없습니다. aaronkim33 계정에 이미지가 Push되어 있는지 확인하세요.")
                    raise Exception("image missing")
                else:
                    self.log(f"✅ 이미지 '{image_name}' 다운로드 완료!")

            run_cmd = [
                "docker", "run", "-d",
                "--name", "openclaw-main",
                "-p", "18789:18789",
                "-p", "18790:18790", 
                "-v", f"{config_dir}:/home/node/.openclaw", 
                "-e", "OPENCLAW_GATEWAY_AUTH_ENABLED=true",
                "-e", "OPENCLAW_GATEWAY_TOKEN=admin123",
                "-e", "OPENCLAW_GATEWAY_MODE=local",
                "-e", f"OPENCLAW_MODEL={target_model}",
                "-e", "OPENCLAW_CONFIG_PATH=/home/node/.openclaw/config.json",
                image_name,  # <--- 원래 "openclaw:latest" 였던 부분을 변수로 완벽 교체!
                "openclaw", "gateway", "run", 
                "--port", "18789", 
                "--allow-unconfigured",
                "--auth", "token",
                "--token", "admin123"
            ]

            run_result = subprocess.run(run_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
            # 👆 여기까지 교체하시면 됩니다! (아래 코드는 기존과 동일)
            if run_result.returncode != 0:
                self.log(f"❌ 도커 컨테이너 실행 실패 (exit {run_result.returncode}): {run_result.stderr.strip()}")
                raise Exception("docker run failed")
            else:
                # log first few lines of stdout for transparency
                if run_result.stdout:
                    outlines = run_result.stdout.strip().splitlines()
                    for line in outlines[:3]:
                        self.log(f"[docker run] {line}")
                # confirm container exists
                ps_check = subprocess.run(["docker", "ps", "-q", "--filter", "name=openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace")
                if not ps_check.stdout.strip():
                    self.log("❌ 컨테이너가 생성되지 않았습니다. 도커 데몬 로그를 확인하세요.")
                    raise Exception("container not created")
            self.progress.set(0.7)
            
            # ---------------------------------------------------------
            self.log(">>> [3] 로그 분석 중... (제발 Ollama!)")
            success = False
            max_attempts = 20
            for i in range(max_attempts): 
                try:
                    time.sleep(3)
                    log_check = subprocess.run(["docker", "logs", "openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo, timeout=10)
                    logs = log_check.stdout + log_check.stderr
                    # print most recent log line for debugging
                    if logs:
                        last_line = logs.strip().splitlines()[-1]
                        self.log(f"[도커 로그] {last_line}")
                    else:
                        self.log("[도커 로그] <empty output>")
                    
                    # Improved success detection: check for model and gateway listening
                    if target_model in logs and ("listening on" in logs.lower() or "gateway started" in logs.lower()):
                        self.log(f"🎊 복구 성공! '{target_model}' 인식 확인!")
                        proxy_js = "require('net').createServer(c=>{let s=require('net').connect(18789,'127.0.0.1');c.pipe(s).pipe(c);s.on('error',()=>c.destroy());c.on('error',()=>s.destroy());}).listen(18790,'0.0.0.0')"
                        subprocess.run(["docker", "exec", "-d", "openclaw-main", "node", "-e", proxy_js], startupinfo=startupinfo, timeout=10)
                        success = True
                        break
                    
                    if "anthropic" in logs.lower():
                        self.log("⚠️ 경고: 아직 Claude가 잡혀있습니다. 재시도 중...")
                        
                    self.log(f"엔진 부팅 대기 중... ({i*3+3}초)")
                    # 대기 시간에 따라 프로그레스 바를 조금씩 채워줍니다.
                    self.progress.set(0.7 + (i * 0.015))
                except subprocess.TimeoutExpired:
                    self.log(f"⚠️ 로그 확인 타임아웃 ({i+1}/{max_attempts})")
                    continue
                except Exception as e:
                    self.log(f"⚠️ 로그 분석 오류: {str(e)}")
                    break

            if success:
                self.progress.set(1.0)
                url = "http://127.0.0.1:18790/?token=admin123" 
                
                # [변경점] 사파리 강제 지정이 아닌 OS 기본 브라우저 열기 모듈 사용
                webbrowser.open(url)
                self.log("🚀 복구 완료! 브라우저에서 OpenClaw 대시보드를 확인해주세요.")
            else:
                self.progress.set(0)
                self.log("❌ 복구 실패: 로그를 다시 확인해야 합니다.")

            self.start_btn.configure(state="normal")
        except Exception as e:
            self.log(f"❌ 메인 로직 오류: {str(e)}")
            self.start_btn.configure(state="normal")

    def stop_docker(self):
        startupinfo = None
        if self.is_windows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(["docker", "rm", "-f", "openclaw-main"], startupinfo=startupinfo)
        self._check_services()
        self.log("Docker 컨테이너를 중지했습니다.")

    def stop_ollama(self):
        # 모델을 당기고 있는 중이면 중단하지 않습니다.
        if getattr(self, "pulling_model", False):
            self.log("⚠️ 모델 준비 중에는 Ollama를 중지할 수 없습니다.")
            return
        startupinfo = None
        if self.is_windows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            cmd = ["taskkill", "/f", "/im", "ollama.exe"]
        else:
            cmd = ["pkill", "ollama"]
            
        subprocess.run(cmd, startupinfo=startupinfo)
        self._check_services()
        self.log("Ollama 엔진을 종료했습니다.")

    def on_closing(self):
        self.destroy()

if __name__ == "__main__":
    app = OpenClawLauncher()
    app.mainloop()