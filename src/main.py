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
import psutil
import math
import json
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
        self.is_mac = platform.system() == "Darwin"
        self.is_windows = platform.system() == "Windows"
        
        if self.is_windows and getattr(sys, "frozen", False) and not is_admin():
            self.withdraw()
            messagebox.showerror("권한 필요", "이 애플리케이션을 실행하려면 관리자 권한이 필요합니다.")
            self.destroy()
            return
        
        self.title("OpenClaw AI Manager Pro")
        self.geometry("750x950")
        
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

        # --- 💻 하드웨어 분석 및 모델 설정 섹션 ---
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.pack(pady=10, padx=20, fill="x")

        # 1. 하드웨어 분석 결과 출력
        hardware_info, recommended_model = self.analyze_hardware()
        self.hw_label = ctk.CTkLabel(self.config_frame, text=f"💻 내 PC: {hardware_info}", font=("Arial", 12))
        self.hw_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="w")
        
        self.rec_label = ctk.CTkLabel(self.config_frame, text=f"💡 권장 설정: {recommended_model}", font=("Arial", 12, "bold"), text_color="#22CC22")
        self.rec_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w")

        # 2. 모델 선택 (로컬 모델 전용 + 직접 입력)
        ctk.CTkLabel(self.config_frame, text="모델 선택:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.model_list = [
            "⭐ Llama 3.2:3b (로컬 - 8GB RAM 최적/추천)",
            "💻 Qwen 2.5 Coder:7b (로컬 - 코딩 특화)",
            "💻 Llama 3.1:8b (로컬 - 마지노선)",
            "✍️ 기타 (직접 입력)"
        ]
        self.model_combo = ctk.CTkComboBox(self.config_frame, values=self.model_list, width=320, command=self.on_model_select)
        self.model_combo.grid(row=2, column=1, padx=10, pady=5)

        # 3. API 키 입력 및 붙여넣기 버튼 (유료 API 직접 입력 대비용 유지)
        ctk.CTkLabel(self.config_frame, text="API 키:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        
        self.api_inner_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        self.api_inner_frame.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        
        self.api_entry = ctk.CTkEntry(self.api_inner_frame, placeholder_text="API 모델 선택 시 필수 입력 (로컬은 비워둠)", width=220, show="*")
        self.api_entry.pack(side="left")
        
        self.paste_btn = ctk.CTkButton(self.api_inner_frame, text="📋 붙여넣기", width=80, command=self.paste_from_clipboard, fg_color="#444444", hover_color="#555555")
        self.paste_btn.pack(side="left", padx=(10, 0))

        # 4. 모델 직접 입력 칸 (초기에는 숨김)
        self.custom_label = ctk.CTkLabel(self.config_frame, text="모델명 입력:", text_color="#22CC22")
        self.custom_model_entry = ctk.CTkEntry(self.config_frame, placeholder_text="예: ollama/mistral 또는 openai/gpt-4o", width=320)

        # 🟢 하드웨어 기반 자동 선택 실행
        self.auto_select_model()

        # 로그 창
        self.log_box = ctk.CTkTextbox(self, width=680, height=250, font=("Consolas", 12))
        self.log_box.pack(pady=10, padx=20)
        self.log_box.configure(state="disabled") 
        
        # --- 🐈 2. 고양이 프로그레스 바 구성 ---
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent", width=680, height=60)
        self.progress_frame.pack(pady=10)
        self.progress_frame.pack_propagate(False)

        self.progress = ctk.CTkProgressBar(self.progress_frame, width=680)
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

    # --- UI 이벤트 및 하드웨어 분석 메서드 ---
    def on_model_select(self, choice):
        if "직접 입력" in choice:
            self.custom_label.grid(row=4, column=0, padx=10, pady=5, sticky="w")
            self.custom_model_entry.grid(row=4, column=1, padx=10, pady=5)
        else:
            self.custom_label.grid_forget()
            self.custom_model_entry.grid_forget()

    def paste_from_clipboard(self):
        try:
            clipboard_text = self.clipboard_get()
            self.api_entry.delete(0, "end")
            self.api_entry.insert(0, clipboard_text)
            self.log("✅ 클립보드에서 API 키를 성공적으로 붙여넣었습니다.")
        except tk.TclError:
            self.log("⚠️ 클립보드에 복사된 텍스트가 없습니다.")

    def analyze_hardware(self):
        try:
            ram_bytes = psutil.virtual_memory().total
            ram_gb = math.ceil(ram_bytes / (1024 ** 3))
            os_name = platform.system()
            cpu_arch = platform.machine()
            hw_string = f"{os_name} ({cpu_arch}) / RAM {ram_gb}GB"
            
            if ram_gb <= 8:
                recommendation = "로컬 3B 모델 권장 (메모리 최적화)"
            elif ram_gb <= 16:
                recommendation = "로컬 8B 이하 모델 권장"
            else:
                recommendation = "로컬 14B 이상 고성능 모델 구동 가능"
                
            return hw_string, recommendation
        except Exception as e:
            return "사양 분석 실패", "알 수 없음"

    def auto_select_model(self):
        try:
            ram_gb = math.ceil(psutil.virtual_memory().total / (1024 ** 3))
            if ram_gb <= 16:
                self.model_combo.set(self.model_list[0]) 
            else:
                self.model_combo.set(self.model_list[1]) 
        except:
            self.model_combo.set(self.model_list[0])
        self.on_model_select(self.model_combo.get())

    # --- 유틸리티 메서드 ---
    def set_cat_progress(self, value):
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
        if not self.is_windows: return True 
        
        self.log("⏳ 도커 엔진 상태 확인 중...")
        info = subprocess.run(["docker", "info"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        
        if info.returncode != 0:
            self.log("🚀 도커 엔진이 잠들어 있습니다. 깨우는 중...")
            docker_exe = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Docker\\Docker\\Docker Desktop.exe")
            if os.path.exists(docker_exe):
                subprocess.Popen([docker_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    # --- 메인 실행 로직 ---
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
                self.log("✅ Ollama 점검 완료.")
            self.set_cat_progress(0.2) 

            if not shutil.which("docker"):
                self.log("❌ Docker가 설치되어 있지 않습니다!")
                if self.is_windows:
                    self.log("⏳ 윈도우용 Docker Desktop 다운로드 및 설치 중... (수 분 소요)")
                    cmd = ["winget", "install", "--id", "Docker.DockerDesktop", "-e", "--source", "winget", "--silent", "--accept-package-agreements", "--accept-source-agreements"]
                    if self.run_with_live_logs(cmd, startupinfo=startupinfo) == 0:
                        self.log("✅ Docker 설치 완료!")
                        messagebox.showinfo("재부팅 필요", "Docker 가상화 엔진(WSL2) 적용을 위해 PC를 재시작한 후 다시 실행해주세요.")
                        self.after(0, self.destroy)
                        return
                    else:
                        self.log("❌ 자동 설치 실패. 브라우저 수동 설치를 유도합니다.")
                        webbrowser.open("https://docs.docker.com/desktop/install/windows-install/")
                        self.start_btn.configure(state="normal")
                        return
                else:
                    self.log("👉 맥 환경입니다. 브라우저에서 Docker Desktop을 설치해주세요.")
                    webbrowser.open("https://docs.docker.com/desktop/install/mac-install/")
                    self.start_btn.configure(state="normal")
                    return
            else:
                self.log("✅ Docker 점검 완료.")
                if not self.start_docker_engine():
                    self.log("❌ 도커 엔진을 켤 수 없습니다. Docker Desktop을 수동으로 실행해주세요.")
                    self.start_btn.configure(state="normal")
                    return
            
            self.set_cat_progress(0.3) 
            self.log(">>> 시스템 점검 통과. 모델 세팅을 시작합니다.")
            self.main_logic()
        except Exception as e:
            self.log(f"❌ 의존성 점검 중 오류 발생: {str(e)}")
            self.start_btn.configure(state="normal")

    def main_logic(self):
        try:
            startupinfo = None
            if self.is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            selected_display = self.model_combo.get()
            api_key = self.api_entry.get().strip()

            if "직접 입력" in selected_display:
                custom_val = self.custom_model_entry.get().strip()
                if not custom_val:
                    self.log("❌ 오류: 모델명(예: ollama/mistral)을 입력해주세요.")
                    self.start_btn.configure(state="normal")
                    self.set_cat_progress(0)
                    return
                
                if "/" in custom_val:
                    provider, target_model_id = custom_val.split("/", 1)
                else:
                    provider = "ollama"
                    target_model_id = custom_val
                
                is_local = (provider == "ollama")
                base_url = "http://host.docker.internal:11434/v1" if is_local else "https://api.openai.com/v1"
                ctx_window = 32000
                target_model_full = f"{provider}/{target_model_id}"
            
            else:
                is_local = True
                model_mapping = {
                    "Llama 3.2:3b": ("ollama", "llama3.2", "http://host.docker.internal:11434/v1", 32000),
                    "Qwen 2.5 Coder:7b": ("ollama", "qwen2.5-coder:7b", "http://host.docker.internal:11434/v1", 32000),
                    "Llama 3.1:8b": ("ollama", "llama3.1", "http://host.docker.internal:11434/v1", 32000)
                }

                provider = "ollama"
                target_model_id = "llama3.2"
                base_url = "http://host.docker.internal:11434/v1"
                ctx_window = 32000

                for key, (prov, mid, url, ctx) in model_mapping.items():
                    if key in selected_display:
                        provider = prov
                        target_model_id = mid
                        base_url = url
                        ctx_window = ctx
                        break

                target_model_full = f"{provider}/{target_model_id}"

            if not is_local and not api_key:
                self.log("⚠️ 주의: 외부 모델 지정 시 API 키가 필요할 수 있습니다.")

            # ---------------------------------------------------------
            if is_local:
                self.log(f">>> [로컬 모드] Ollama 엔진 구동 및 '{target_model_id}' 준비...")
                self.stop_ollama()
                ollama_env = os.environ.copy()
                ollama_env["OLLAMA_HOST"] = "0.0.0.0"

                subprocess.Popen(["ollama", "serve"], env=ollama_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
                
                self.pulling_model = True
                self.log(f"📥 로컬 모델({target_model_id})을 확인/다운로드합니다. (최초 1회, 수 분 소요)")
                pull_status = self.run_with_live_logs(["ollama", "pull", target_model_id], startupinfo=startupinfo)
                if pull_status != 0:
                    raise Exception(f"Ollama pull failed")
                    
                self.log(f"✅ 로컬 모델 다운로드/검증 완료: {target_model_id}")
                self.pulling_model = False
            else:
                self.log(f">>> [API 모드] 외부 접속을 준비합니다.")

            self.set_cat_progress(0.5) 

            # ---------------------------------------------------------
            self.log(">>> [1] 설정 파일(JSON) 동적 생성 중...")
            config_dir = os.path.expanduser("~/.openclaw_data")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "config.json")
            
            if os.path.exists(config_path):
                try: os.remove(config_path)
                except: pass

            config_data = {
                "gateway": { 
                    "mode": "local",
                    "controlUi": { "dangerouslyAllowHostHeaderOriginFallback": True }
                },
                "agents": { "defaults": { "model": { "primary": target_model_full } } },
                "models": { "providers": {} }
            }

            if is_local:
                config_data["models"]["providers"]["ollama"] = {
                    "baseUrl": base_url,
                    "api": "openai-completions",
                    "models": [ { "id": target_model_full, "name": target_model_id, "contextWindow": ctx_window } ]
                }
            else:
                config_data["models"]["providers"][provider] = {
                    "apiKey": api_key,
                    "baseUrl": base_url,   
                    "api": "openai-responses",       
                    "models": [ { "id": target_model_full, "name": target_model_id, "contextWindow": ctx_window } ]
                }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
                
            self.set_cat_progress(0.6) 

            # ---------------------------------------------------------
            self.log(">>> [2] 도커 컨테이너 완전 재부팅...")
            subprocess.run(["docker", "rm", "-f", "openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
            
            image_name = "ghcr.io/openclaw/openclaw:latest"
            subprocess.run(["docker", "pull", image_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)

            env_vars = []
            if not is_local and api_key:
                env_vars.extend(["-e", f"OPENAI_API_KEY={api_key}"])

            run_cmd = [
                "docker", "run", "-d",
                "--name", "openclaw-main",
                "-p", "18789:18789",
                "-p", "18790:18790", 
                "-v", f"{config_dir}:/home/node/.openclaw", 
                "-e", "OPENCLAW_GATEWAY_AUTH_ENABLED=true",
                "-e", "OPENCLAW_GATEWAY_TOKEN=admin123",
                "-e", "OPENCLAW_GATEWAY_MODE=local",
                "-e", f"OPENCLAW_MODEL={target_model_full}",
                "-e", "OPENCLAW_CONFIG_PATH=/home/node/.openclaw/config.json",
            ] + env_vars + [
                image_name, 
                "openclaw", "gateway", "run", 
                "--port", "18789", 
                "--bind", "lan",        
                "--allow-unconfigured",
                "--auth", "token",
                "--token", "admin123"
            ]

            run_result = subprocess.run(run_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
            if run_result.returncode != 0:
                raise Exception("docker run failed")
            
            self.set_cat_progress(0.7)
            
            # ---------------------------------------------------------
            self.log(">>> [3] 백엔드 시스템 로그 분석 중... ")
            success = False
            for i in range(20): 
                try:
                    time.sleep(3)
                    log_check = subprocess.run(["docker", "logs", "openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo, timeout=10)
                    logs = log_check.stdout + log_check.stderr
                    
                    if logs:
                        last_line = logs.strip().splitlines()[-1]
                        self.log(f"[도커 로그] {last_line}")
                    
                    if ("listening on" in logs.lower() or "gateway started" in logs.lower()):
                        self.log(f"🎊 통합 성공! '{target_model_id}' 세팅 완료!")
                        proxy_js = "require('net').createServer(c=>{let s=require('net').connect(18789,'127.0.0.1');c.pipe(s).pipe(c);s.on('error',()=>c.destroy());c.on('error',()=>s.destroy());}).listen(18790,'0.0.0.0')"
                        subprocess.run(["docker", "exec", "-d", "openclaw-main", "node", "-e", proxy_js], startupinfo=startupinfo, timeout=10)
                        success = True
                        break
                    
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
                self.log("🚀 실행 완료! 브라우저에서 대시보드를 확인해주세요.")
            else:
                self.set_cat_progress(0)
                self.log("❌ 실행 실패: 도커 로그를 다시 확인해야 합니다.")

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
            self.log("⚠️ 모델 다운로드 중에는 Ollama를 중지할 수 없습니다.")
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