import customtkinter as ctk
import subprocess
import threading
import os
import platform
import time
import shutil
import webbrowser
import ctypes
import sys
import tkinter as tk
import tkinter.messagebox as messagebox
from PIL import Image, ImageTk

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def resource_path(relative_path):
    """PyInstaller 빌드 및 로컬 테스트 환경 모두에서 안전하게 assets 경로를 찾아줍니다."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

class OpenClawLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        # OS 확인
        self.is_mac = platform.system() == "Darwin"
        self.is_windows = platform.system() == "Windows"
        
        # 권한 체크
        if self.is_windows and getattr(sys, "frozen", False) and not is_admin():
            self.withdraw()
            messagebox.showerror("권한 필요", "이 애플리케이션을 실행하려면 관리자 권한이 필요합니다.")
            self.destroy()
            return
        
        self.title("OpenClaw AI Manager Pro")
        self.geometry("700x900")
        
        # --- 🎨 1. 앱 기본 아이콘 설정 ---
        try:
            if self.is_windows:
                ico_path = resource_path("assets/icon.ico")
                if os.path.exists(ico_path):
                    self.after(200, lambda: self.iconbitmap(ico_path))
            elif self.is_mac:
                png_path = resource_path("assets/icon.png")
                if os.path.exists(png_path):
                    img = tk.PhotoImage(file=png_path)
                    self.wm_iconphoto(True, img)
        except Exception as e:
            print(f"아이콘 로드 실패: {e}")

        # --- UI 구성 ---
        self.label = ctk.CTkLabel(self, text="OpenClaw AI Manager", font=("Arial", 28, "bold"))
        self.label.pack(pady=20)

        # 상태 모니터링 섹션
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.pack(pady=10, padx=20, fill="x")
        self.create_status_row("Docker (OpenClaw)", "docker_status", self.stop_docker)
        self.create_status_row("Ollama Engine", "ollama_status", self.stop_ollama)

        # 모델 설정 섹션
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

        # 로그 창
        self.log_box = ctk.CTkTextbox(self, width=640, height=300, font=("Consolas", 12))
        self.log_box.pack(pady=10, padx=20)
        self.log_box.configure(state="disabled") 
        
        # --- 🐈 2. 고양이 프로그레스 바 구성 ---
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent", width=640, height=60)
        self.progress_frame.pack(pady=10)
        self.progress_frame.pack_propagate(False)

        self.progress = ctk.CTkProgressBar(self.progress_frame, width=640)
        self.progress.place(relx=0.5, rely=0.8, anchor="center")
        self.progress.set(0)

        cat_img_path = resource_path("assets/cat_run.png")
        if os.path.exists(cat_img_path):
            cat_img = ctk.CTkImage(light_image=Image.open(cat_img_path), size=(40, 40))
            self.cat_label = ctk.CTkLabel(self.progress_frame, image=cat_img, text="")
        else:
            self.cat_label = ctk.CTkLabel(self.progress_frame, text="🐈", font=("Arial", 35))
        
        self.cat_label.place(relx=0.0, rely=0.3, anchor="center")

        # 실행 및 종료 버튼
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=20)

        self.start_btn = ctk.CTkButton(self.btn_frame, text=" 설치 및 통합 실행", command=self.start_thread, height=55, font=("Arial", 20, "bold"))
        self.start_btn.pack(side="left", padx=10)

        self.exit_btn = ctk.CTkButton(self.btn_frame, text=" 런처 종료 ", command=self.on_closing, height=55, font=("Arial", 20, "bold"), fg_color="#CC3333", hover_color="#AA2222")
        self.exit_btn.pack(side="left", padx=10)

        self.update_status_loop()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def set_cat_progress(self, value):
        """진행 바를 채우면서 고양이를 이동시킵니다."""
        self.progress.set(value)
        target_x = 0.05 + (value * 0.90)
        self.after(0, lambda: self.cat_label.place(relx=target_x, rely=0.3, anchor="center"))

    def create_status_row(self, name, attr_name, stop_cmd):
        row = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        row.pack(pady=5, padx=10, fill="x")
        ctk.CTkLabel(row, text=name, width=150, anchor="w").pack(side="left")
        status_indicator = ctk.CTkLabel(row, text="확인 중...", text_color="gray")
        status_indicator.pack(side="left", padx=20)
        setattr(self, attr_name, status_indicator)
        ctk.CTkButton(row, text="강제종료", width=60, fg_color="#CC3333", command=stop_cmd).pack(side="right")

    def log(self, text):
        def update_log():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
            self.log_box.configure(state="disabled")
            self.log_box.see("end")
        self.after(0, update_log)

    def run_with_live_logs(self, cmd, startupinfo=None):
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
            for line in process.stdout:
                cleaned_line = line.strip()
                if cleaned_line:
                    self.log(f"> {cleaned_line}")
            process.wait()
            return process.returncode
        except Exception as e:
            self.log(f"⚠️ 프로세스 실행 오류: {e}")
            return 1

    def update_status_loop(self):
        threading.Thread(target=self._check_services, daemon=True).start()
        self.after(10000, self.update_status_loop)

    def _check_services(self):
        try:
            d_check = subprocess.run(["docker", "ps", "--filter", "name=openclaw-main", "-q"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            is_docker_on = bool(d_check.stdout.strip()) and d_check.returncode == 0
            self.docker_status.configure(text="● 실행 중" if is_docker_on else "○ 중지됨", text_color="#22CC22" if is_docker_on else "#CC2222")
        except:
            self.docker_status.configure(text="○ 중지됨", text_color="#CC2222")
            
        try:
            o_cmd = ["pgrep", "ollama"] if self.is_mac else ["tasklist", "/FI", "IMAGENAME eq ollama.exe"]
            o_check = subprocess.run(o_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            is_ollama_on = "ollama" in o_check.stdout.lower() or o_check.returncode == 0
            self.ollama_status.configure(text="● 실행 중" if is_ollama_on else "○ 중지됨", text_color="#22CC22" if is_ollama_on else "#CC2222")
        except:
            self.ollama_status.configure(text="○ 중지됨", text_color="#CC2222")

    def start_docker_engine(self):
        """도커 앱이 설치되어 있지만 엔진이 꺼져 있을 때 자동으로 실행합니다."""
        if not self.is_windows: return True # 맥은 시스템에서 자동화가 더 복잡하므로 일단 패스
        
        self.log("⏳ 도커 엔진 상태 확인 중...")
        # docker info는 엔진이 꺼져있으면 0이 아닌 리턴코드를 줍니다.
        info = subprocess.run(["docker", "info"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        
        if info.returncode != 0:
            self.log("🚀 도커 엔진이 잠들어 있습니다. 깨우는 중...")
            # Docker Desktop 실행 파일 경로 찾기 및 실행
            docker_exe = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Docker\\Docker\\Docker Desktop.exe")
            if os.path.exists(docker_exe):
                subprocess.Popen([docker_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # 엔진이 올라올 때까지 대기 루프 (최대 60초)
                for i in range(12):
                    time.sleep(5)
                    self.log(f"⏳ 도커 엔진 가동 대기 중... ({i*5+5}초/60초)")
                    check = subprocess.run(["docker", "info"], capture_output=True, text=True, encoding="utf-8", errors="replace")
                    if check.returncode == 0:
                        self.log("✅ 도커 엔진이 성공적으로 준비되었습니다.")
                        return True
                self.log("❌ 도커 엔진 가동 시간이 초과되었습니다.")
                return False
            else:
                self.log("❌ Docker Desktop 실행 파일을 찾을 수 없습니다.")
                return False
        return True

    def start_thread(self):
        self.start_btn.configure(state="disabled")
        self.set_cat_progress(0) 
        self.pulling_model = False
        threading.Thread(target=self.check_and_install_dependencies, daemon=True).start()

    def check_and_install_dependencies(self):
        try:
            self.log(">>> [0] 시스템 필수 환경 점검 시작...")
            self.set_cat_progress(0.1) 
            
            startupinfo = None
            if self.is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # 1. Ollama 체크 및 설치
            if not shutil.which("ollama"):
                self.log("⚠️ Ollama가 없습니다. 다운로드 및 설치를 시작합니다...")
                if self.is_windows:
                    cmd = ["winget", "install", "--id", "Ollama.Ollama", "-e", "--source", "winget", "--silent", "--accept-package-agreements", "--accept-source-agreements"]
                    if self.run_with_live_logs(cmd, startupinfo=startupinfo) == 0:
                        self.log("✅ Ollama 설치 완료!")
                    else:
                        self.log("❌ Ollama 자동 설치 실패. 수동으로 설치해주세요.")
                        self.start_btn.configure(state="normal")
                        return
                elif self.is_mac:
                    self.log("⏳ macOS에서 Ollama 설치 중...")
                    if self.run_with_live_logs(["brew", "install", "ollama"]) == 0:
                        self.log("✅ Ollama 설치 완료!")
                    else:
                        self.log("❌ Ollama 설치 실패. 수동으로 설치해주세요.")
                        self.start_btn.configure(state="normal")
                        return
            else:
                self.log("✅ Ollama가 이미 설치되어 있습니다.")
            self.set_cat_progress(0.2) 

            # 2. Docker 체크 및 설치/실행
            if not shutil.which("docker"):
                self.log("❌ Docker가 설치되어 있지 않습니다!")
                if self.is_windows:
                    self.log("⏳ 윈도우용 Docker Desktop 다운로드 및 설치 중... (수 분 소요)")
                    cmd = ["winget", "install", "--id", "Docker.DockerDesktop", "-e", "--source", "winget", "--silent", "--accept-package-agreements", "--accept-source-agreements"]
                    
                    if self.run_with_live_logs(cmd, startupinfo=startupinfo) == 0:
                        self.log("✅ Docker 설치가 완료되었습니다!")
                        messagebox.showinfo("재부팅 필요", "Docker 설치가 성공적으로 완료되었습니다.\n가상화 엔진(WSL2) 적용을 위해 PC를 재시작한 후 런처를 다시 실행해주세요.")
                        self.after(0, self.destroy)
                        return
                    else:
                        self.log("❌ Docker 자동 설치 실패. 브라우저를 열어 수동 설치 유도 중...")
                        webbrowser.open("https://docs.docker.com/desktop/install/windows-install/")
                        self.start_btn.configure(state="normal")
                        return
                else:
                    self.log("👉 맥북은 브라우저를 열어 다운로드 페이지로 이동합니다...")
                    webbrowser.open("https://docs.docker.com/desktop/install/mac-install/")
                    self.start_btn.configure(state="normal")
                    return
            else:
                self.log("✅ Docker가 이미 설치되어 있습니다.")
                # 💡 핵심 추가: 도커가 설치되어 있다면 엔진을 깨웁니다.
                if not self.start_docker_engine():
                    self.log("❌ 도커 엔진을 켤 수 없습니다. Docker Desktop을 수동으로 실행해주세요.")
                    self.start_btn.configure(state="normal")
                    return
            
            self.set_cat_progress(0.3) 
            self.log(">>> 시스템 점검 완료. 메인 로직으로 진입합니다.")
            self.main_logic()
        except Exception as e:
            self.log(f"❌ 의존성 점검 중 오류 발생: {str(e)}")
            self.start_btn.configure(state="normal")

    def main_logic(self):
        try:
            import json
            startupinfo = None
            if self.is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.log(">>> [긴급 복구] Ollama 엔진 및 모델 체크...")
            self.stop_ollama()
            ollama_env = os.environ.copy()
            ollama_env["OLLAMA_HOST"] = "0.0.0.0"

            subprocess.Popen(["ollama", "serve"], env=ollama_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
            
            selected_model = self.model_combo.get()
            clean_model_id = selected_model.replace("ollama/", "")
            target_model = f"ollama/{clean_model_id}"
            
            self.pulling_model = True
            self.log(f"⏳ '{clean_model_id}' 모델을 준비 중입니다. 진행 상황을 확인하세요.")
            
            pull_status = self.run_with_live_logs(["ollama", "pull", clean_model_id], startupinfo=startupinfo)
            if pull_status != 0:
                raise Exception(f"Ollama pull failed (exit {pull_status})")
                
            self.log(f"✅ 모델 준비 완료: {target_model}")
            self.set_cat_progress(0.5) 
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
            self.set_cat_progress(0.6) 

            # ---------------------------------------------------------
            self.log(">>> [2] 도커 컨테이너 완전 재부팅...")
            # 이미 start_docker_engine 단계에서 엔진이 보장되므로 정보 조회 생략 가능
            subprocess.run(["docker", "rm", "-f", "openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
            
            image_name = "aaronkim33/openclaw:latest"

            img_check = subprocess.run(["docker", "image", "inspect", image_name], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
            if img_check.returncode != 0:
                self.log(f"⚠️ 이미지 '{image_name}' 다운로드를 시작합니다...")
                pull_result = self.run_with_live_logs(["docker", "pull", image_name], startupinfo=startupinfo)
                if pull_result != 0:
                    raise Exception("image missing")
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
                image_name, 
                "openclaw", "gateway", "run", 
                "--port", "18789", 
                "--allow-unconfigured",
                "--auth", "token",
                "--token", "admin123"
            ]

            run_result = subprocess.run(run_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
            if run_result.returncode != 0:
                raise Exception("docker run failed")
            
            self.set_cat_progress(0.7) 
            
            # ---------------------------------------------------------
            self.log(">>> [3] 로그 분석 중... ")
            success = False
            max_attempts = 20
            for i in range(max_attempts): 
                try:
                    time.sleep(3)
                    log_check = subprocess.run(["docker", "logs", "openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo, timeout=10)
                    logs = log_check.stdout + log_check.stderr
                    
                    if logs:
                        last_line = logs.strip().splitlines()[-1]
                        self.log(f"[도커 로그] {last_line}")
                    
                    if target_model in logs and ("listening on" in logs.lower() or "gateway started" in logs.lower()):
                        self.log(f"🎊 복구 성공! '{target_model}' 인식 확인!")
                        proxy_js = "require('net').createServer(c=>{let s=require('net').connect(18789,'127.0.0.1');c.pipe(s).pipe(c);s.on('error',()=>c.destroy());c.on('error',()=>s.destroy());}).listen(18790,'0.0.0.0')"
                        subprocess.run(["docker", "exec", "-d", "openclaw-main", "node", "-e", proxy_js], startupinfo=startupinfo, timeout=10)
                        success = True
                        break
                    
                    if "anthropic" in logs.lower():
                        self.log("⚠️ 경고: 아직 Claude가 잡혀있습니다. 재시도 중...")
                        
                    self.set_cat_progress(0.7 + (i * 0.015)) 
                except subprocess.TimeoutExpired:
                    continue
                except Exception as e:
                    self.log(f"⚠️ 로그 분석 오류: {str(e)}")
                    break

            if success:
                self.set_cat_progress(1.0)
                url = "http://127.0.0.1:18790/?token=admin123" 
                webbrowser.open(url)
                self.log("🚀 복구 완료! 브라우저에서 OpenClaw 대시보드를 확인해주세요.")
            else:
                self.set_cat_progress(0)
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
        self.log("Docker 컨테이너(openclaw-main)를 중지했습니다.")

    def stop_ollama(self):
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
        self.log("Ollama 엔진을 종료했습니다.")

    def on_closing(self):
        answer = messagebox.askyesnocancel("종료 확인", "런처를 종료합니다.\n현재 실행 중인 Docker 컨테이너와 Ollama 엔진도 함께 완전 종료하시겠습니까?")
        if answer is True: 
            self.stop_docker()
            self.stop_ollama()
            self.destroy()
        elif answer is False: 
            self.destroy()

if __name__ == "__main__":
    app = OpenClawLauncher()
    app.mainloop()