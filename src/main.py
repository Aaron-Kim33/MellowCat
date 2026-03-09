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
        
        # 🟢 맥북 에어 화면에 쏙 들어가도록 세로 길이를 850으로 압축했습니다.
        self.title("MellowCat")
        self.geometry("780x850") 
        
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

        self.ram_gb = math.ceil(psutil.virtual_memory().total / (1024 ** 3))
        os_name = platform.system()
        cpu_arch = platform.machine()

        # 여백(pady)들을 최소화하여 공간을 확보합니다.
        self.label = ctk.CTkLabel(self, text="MellowCat", font=("Arial", 32, "bold"))
        self.label.pack(pady=5)

        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.pack(pady=5, padx=20, fill="x")
        self.create_status_row("Docker (MellowCat)", "docker_status", self.stop_docker)
        self.create_status_row("Ollama Engine", "ollama_status", self.stop_ollama)

        # ---------------------------------------------------------
        # 1. 시스템 및 모델 설정 섹션
        # ---------------------------------------------------------
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.pack(pady=5, padx=20, fill="x")

        self.hw_label = ctk.CTkLabel(self.config_frame, text=f"💻 시스템: {os_name} ({cpu_arch})", font=("Arial", 12))
        self.hw_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(5, 0), sticky="w")
        
        self.ram_label = ctk.CTkLabel(self.config_frame, text=f"🔥 내 PC RAM: {self.ram_gb}GB", font=("Arial", 14, "bold"), text_color="#3399FF")
        self.ram_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="w")

        ctk.CTkLabel(self.config_frame, text="모델 선택:").grid(row=2, column=0, padx=10, pady=2, sticky="w")
        
        self.model_list = []
        base_models = [
            ("Llama 3.2:3b", 8, "가장 빠름"),
            ("Qwen 2.5 Coder:7b", 8, "코딩 특화"),
            ("Llama 3.1:8b", 16, "표준형"),
            ("Gemma 2:9b", 16, "고성능"),
            ("DeepSeek Coder V2 Lite", 32, "전문가용")
        ]

        for name, req_ram, desc in base_models:
            if self.ram_gb >= req_ram:
                self.model_list.append(f"🟢 [원활] {name} (권장 {req_ram}GB) - {desc}")
            else:
                self.model_list.append(f"🔴 [경고] {name} (권장 {req_ram}GB) - 램 부족")
        
        self.model_list.append("✍️ 기타 (직접 입력)")

        self.model_combo = ctk.CTkComboBox(self.config_frame, values=self.model_list, width=380, command=self.on_model_select)
        self.model_combo.grid(row=2, column=1, padx=10, pady=2, sticky="w")

        self.ram_warning_label = ctk.CTkLabel(self.config_frame, text="", font=("Arial", 12, "bold"))
        self.ram_warning_label.grid(row=3, column=1, padx=10, pady=(0, 2), sticky="w")

        self.custom_label = ctk.CTkLabel(self.config_frame, text="모델명 입력:", text_color="#22CC22")
        self.custom_model_entry = ctk.CTkEntry(self.config_frame, placeholder_text="예: ollama/mistral", width=320)

        # ---------------------------------------------------------
        # 2. 채널(Channels) 토큰 입력 섹션
        # ---------------------------------------------------------
        self.channel_frame = ctk.CTkFrame(self)
        self.channel_frame.pack(pady=5, padx=20, fill="x")
        
        ctk.CTkLabel(self.channel_frame, text="[ 메신저 채널 연동 (선택) ]", font=("Arial", 13, "bold")).grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(self.channel_frame, text="Telegram:").grid(row=1, column=0, padx=10, pady=2, sticky="w")
        self.tg_entry = ctk.CTkEntry(self.channel_frame, placeholder_text="봇 토큰 입력 (예: 12345:ABCDE...)", width=410, show="*")
        self.tg_entry.grid(row=1, column=1, padx=(10, 5), pady=2, sticky="w")
        ctk.CTkButton(self.channel_frame, text="?", width=30, command=self.show_telegram_help, fg_color="#555555", hover_color="#777777").grid(row=1, column=2, padx=(0, 10), pady=2, sticky="w")

        ctk.CTkLabel(self.channel_frame, text="Discord:").grid(row=2, column=0, padx=10, pady=2, sticky="w")
        self.dc_entry = ctk.CTkEntry(self.channel_frame, placeholder_text="봇 토큰 입력 (예: MTEyMz...)", width=410, show="*")
        self.dc_entry.grid(row=2, column=1, padx=(10, 5), pady=2, sticky="w")
        ctk.CTkButton(self.channel_frame, text="?", width=30, command=self.show_discord_help, fg_color="#555555", hover_color="#777777").grid(row=2, column=2, padx=(0, 10), pady=2, sticky="w")
        
        self.wa_btn = ctk.CTkButton(self.channel_frame, text="📱 WhatsApp 연동하기 (QR코드 띄우기)", fg_color="#25D366", hover_color="#128C7E", text_color="white", font=("Arial", 13, "bold"), command=self.open_whatsapp_qr)
        self.wa_btn.grid(row=3, column=0, columnspan=3, padx=10, pady=(5, 5), sticky="w")

        # ---------------------------------------------------------
        # 3. 보안 및 기기 승인 (Pairing) 섹션
        # ---------------------------------------------------------
        self.pairing_frame = ctk.CTkFrame(self)
        self.pairing_frame.pack(pady=5, padx=20, fill="x")
        
        ctk.CTkLabel(self.pairing_frame, text="[ 🔐 봇 사용 권한 승인 (Pairing) ]", font=("Arial", 13, "bold"), text_color="#FFB347").grid(row=0, column=0, columnspan=4, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(self.pairing_frame, text="메신저에서 보낸 코드 입력:").grid(row=1, column=0, padx=10, pady=2, sticky="w")
        
        self.pairing_ch_combo = ctk.CTkComboBox(self.pairing_frame, values=["telegram", "whatsapp", "discord"], width=100)
        self.pairing_ch_combo.grid(row=1, column=1, padx=(5, 5), pady=2, sticky="w")
        
        self.pairing_entry = ctk.CTkEntry(self.pairing_frame, placeholder_text="예: J46PG7YA", width=110)
        self.pairing_entry.grid(row=1, column=2, padx=(5, 5), pady=2, sticky="w")
        
        self.pairing_btn = ctk.CTkButton(self.pairing_frame, text="✅ 승인", width=60, command=self.approve_pairing)
        self.pairing_btn.grid(row=1, column=3, padx=(5, 10), pady=2, sticky="w")

        # ---------------------------------------------------------

        self.auto_select_model()

        # 🟢 로그 박스 높이를 180 -> 100으로 줄여서 공간을 대폭 확보했습니다.
        self.log_box = ctk.CTkTextbox(self, width=680, height=100, font=("Consolas", 12))
        self.log_box.pack(pady=5, padx=20)
        self.log_box.configure(state="disabled") 
        
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent", width=680, height=50)
        self.progress_frame.pack(pady=5)
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

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=(5, 10))

        self.start_btn = ctk.CTkButton(self.btn_frame, text=" 원클릭 자동 설치 및 실행 ", command=self.start_thread, height=50, font=("Arial", 18, "bold"))
        self.start_btn.pack(side="left", padx=10)

        self.exit_btn = ctk.CTkButton(self.btn_frame, text=" 런처 종료 ", command=self.on_closing, height=50, font=("Arial", 18, "bold"), fg_color="#CC3333", hover_color="#AA2222")
        self.exit_btn.pack(side="left", padx=10)

        self.update_status_loop()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_model_select(self, choice):
        if "🔴" in choice:
            self.ram_warning_label.configure(text="⚠️ 권장 RAM 부족! 구동 시 시스템이 멈출 수 있습니다.", text_color="#FF3333")
        elif "🟢" in choice:
            self.ram_warning_label.configure(text="✅ 현재 PC 환경에서 원활하게 구동 가능합니다.", text_color="#22CC22")
        else:
            self.ram_warning_label.configure(text="")

        if "직접 입력" in choice:
            self.custom_label.grid(row=4, column=0, padx=10, pady=2, sticky="w")
            self.custom_model_entry.grid(row=4, column=1, padx=10, pady=2, sticky="w")
        else:
            self.custom_label.grid_forget()
            self.custom_model_entry.grid_forget()

    def show_telegram_help(self):
        help_text = [
            "--------------------------------------------------",
            "📘 [텔레그램(Telegram) 봇 토큰 받는 법]",
            "텔레그램은 'BotFather'라는 공식 계정을 통해 아주 쉽게 토큰을 만들 수 있습니다.",
            "1. BotFather 찾기: 텔레그램 앱 검색창에 @BotFather를 검색하고 공식 인증 마크(파란 체크)가 있는 계정을 선택합니다.",
            "2. 봇 생성 시작: 대화창에 /newbot을 입력합니다.",
            "3. 이름 설정: 봇의 이름(예: MyOpenClawBot)을 입력합니다.",
            "4. 사용자명 설정: 봇의 아이디를 입력합니다. 반드시 끝이 _bot으로 끝나야 합니다 (예: openclaw_test_bot).",
            "5. 토큰 복사: 생성이 완료되면 **HTTP API token**이라는 이름으로 긴 문자열이 나옵니다. 이것이 토큰입니다.",
            "--------------------------------------------------"
        ]
        for line in help_text:
            self.log(line)

    def show_discord_help(self):
        help_text = [
            "--------------------------------------------------",
            "🎮 [디스코드(Discord) 봇 토큰 받는 법]",
            "디스코드는 개발자 포털을 통해 애플리케이션을 생성해야 합니다.",
            "1. 디스코드 개발자 포털 접속: Discord Developer Portal에 로그인합니다.",
            "2. 새 애플리케이션 생성: 우측 상단의 [New Application]을 누르고 이름을 입력합니다.",
            "3. 봇 설정: 왼쪽 메뉴에서 [Bot] 탭을 클릭합니다.",
            "4. 토큰 확인: 'Build-a-Bot' 섹션의 [Reset Token] 또는 [Copy Token] 버튼을 눌러 복사합니다.",
            "5. 권한 설정(중요): 아래 'Privileged Gateway Intents' 항목에서 Message Content Intent를 활성화(ON)해야 합니다.",
            "--------------------------------------------------"
        ]
        for line in help_text:
            self.log(line)

    def open_whatsapp_qr(self):
        check = subprocess.run(["docker", "ps", "-q", "-f", "name=openclaw-main"], capture_output=True, text=True)
        if not check.stdout.strip():
            self.log("⚠️ 앗! 먼저 하단의 '원클릭 자동 설치 및 실행'을 눌러서 시스템을 켜주세요!")
            return
        
        self.log("📱 WhatsApp QR 코드 창을 엽니다. 스마트폰으로 스캔해주세요!")
        if self.is_mac:
            cmd = 'tell application "Terminal" to do script "docker exec -it openclaw-main openclaw channels login --channel whatsapp"'
            subprocess.run(['osascript', '-e', cmd])
        elif self.is_windows:
            subprocess.Popen(['start', 'cmd', '/k', 'docker exec -it openclaw-main openclaw channels login --channel whatsapp'], shell=True)

    def approve_pairing(self):
        channel = self.pairing_ch_combo.get()
        code = self.pairing_entry.get().strip()
        
        if not code:
            self.log("⚠️ 봇이 메신저로 보내준 8자리 페어링 코드를 입력해주세요.")
            return
            
        check = subprocess.run(["docker", "ps", "-q", "-f", "name=openclaw-main"], capture_output=True, text=True)
        if not check.stdout.strip():
            self.log("⚠️ 시스템이 아직 실행되지 않았습니다.")
            return

        self.log(f"🔐 [{channel}] 페어링 코드({code}) 승인을 시도합니다...")
        cmd = ["docker", "exec", "openclaw-main", "openclaw", "pairing", "approve", channel, code]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        output = res.stdout.strip() + res.stderr.strip()
        self.log(f"[승인 결과] {output}")
        
        if res.returncode == 0 and "error" not in output.lower():
            self.log("🎉 기기 승인이 완료되었습니다! 이제 메신저에서 봇과 대화할 수 있습니다.")
            self.pairing_entry.delete(0, 'end')
        else:
            self.log("❌ 승인 실패. 채널과 코드가 정확한지 확인해주세요.")

    def auto_select_model(self):
        try:
            if self.ram_gb <= 8:
                self.model_combo.set(self.model_list[0]) 
            elif self.ram_gb <= 16:
                self.model_combo.set(self.model_list[2]) 
            else:
                self.model_combo.set(self.model_list[4]) 
        except:
            self.model_combo.set(self.model_list[0])
        self.on_model_select(self.model_combo.get())

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

            config_dir = os.path.expanduser("~/.openclaw_data")
            config_path = os.path.join(config_dir, "config.json")

            selected_display = self.model_combo.get()
            
            # UI에서 가져온 데이터
            tg_token = self.tg_entry.get().strip()
            dc_token = self.dc_entry.get().strip()

            if "직접 입력" in selected_display:
                custom_val = self.custom_model_entry.get().strip()
                if not custom_val:
                    self.log("❌ 오류: 모델명을 입력해주세요.")
                    self.start_btn.configure(state="normal")
                    self.set_cat_progress(0)
                    return
                provider, target_model_id = custom_val.split("/", 1) if "/" in custom_val else ("ollama", custom_val)
                is_local = (provider == "ollama")
                base_url = "http://host.docker.internal:11434/v1" if is_local else "https://api.openai.com/v1"
                ctx_window = 32000
            else:
                is_local = True
                model_mapping = {
                    "Llama 3.2:3b": ("ollama", "llama3.2", "http://host.docker.internal:11434/v1", 32000),
                    "Qwen 2.5 Coder:7b": ("ollama", "qwen2.5-coder:7b", "http://host.docker.internal:11434/v1", 32000),
                    "Llama 3.1:8b": ("ollama", "llama3.1", "http://host.docker.internal:11434/v1", 128000),
                    "Gemma 2:9b": ("ollama", "gemma2", "http://host.docker.internal:11434/v1", 8192),
                    "DeepSeek Coder V2 Lite": ("ollama", "deepseek-coder-v2", "http://host.docker.internal:11434/v1", 128000)
                }
                for key, (prov, mid, url, ctx) in model_mapping.items():
                    if key in selected_display:
                        provider, target_model_id, base_url, ctx_window = prov, mid, url, ctx
                        break
            
            target_model_full = f"{provider}/{target_model_id}"

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

            self.set_cat_progress(0.4) 

            # 도커 정지 및 딥클린
            self.log(">>> [1] 도커 컨테이너 정지 및 락 해제 중...")
            subprocess.run(["docker", "rm", "-f", "openclaw-main"], capture_output=True, startupinfo=startupinfo)

            self.log(">>> [2] 데이터 폴더 '딥 클린' 중...")
            if os.path.exists(config_dir):
                try:
                    shutil.rmtree(config_dir) 
                    self.log("✅ 이전 세션 및 DB 찌꺼기를 완전히 청소했습니다.")
                except Exception as e:
                    self.log(f"⚠️ 폴더 삭제 오류: {e}")
            os.makedirs(config_dir, exist_ok=True)

            self.set_cat_progress(0.5)

            # 🟢 [핵심] JSON 파일 생성 (보안 Pairing 모드 유지, 토큰 미포함)
            self.log(">>> [3] 보안 설정(Pairing) 기반 설정 파일 생성 중...")
            
            channels_config = {
                "whatsapp": { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist", "debounceMs": 0, "mediaMaxMb": 50 }
            }
            
            if tg_token:
                channels_config["telegram"] = { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist", "streaming": "partial" }
                self.log("✅ Telegram 채널 활성화 (토큰은 부팅 후 안전하게 주입됩니다)")
            else:
                channels_config["telegram"] = { "enabled": False, "dmPolicy": "pairing", "groupPolicy": "allowlist", "streaming": "partial" }
                
            if dc_token:
                channels_config["discord"] = { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist", "streaming": "off" }
                self.log("✅ Discord 채널 활성화 (토큰은 부팅 후 안전하게 주입됩니다)")
            else:
                channels_config["discord"] = { "enabled": False, "groupPolicy": "allowlist", "streaming": "off" }

            config_data = {
                "models": { "providers": {} },
                "agents": { "defaults": { "model": { "primary": target_model_full } } },
                "commands": { "native": "auto", "nativeSkills": "auto", "restart": True, "ownerDisplay": "raw" },
                "channels": channels_config,
                "gateway": { "mode": "local", "controlUi": { "dangerouslyAllowHostHeaderOriginFallback": True } },
                "skills": {}, 
                "meta": { "lastTouchedVersion": "2026.3.8", "lastTouchedAt": time.strftime('%Y-%m-%dT%H:%M:%S.%fZ') }
            }

            if is_local:
                config_data["models"]["providers"]["ollama"] = {
                    "baseUrl": base_url, "api": "openai-completions",
                    "models": [ { "id": target_model_full, "name": target_model_id, "contextWindow": ctx_window } ]
                }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
                
            self.set_cat_progress(0.6) 

            # 도커 실행
            self.log(">>> [4] 도커 컨테이너 실행 중...")
            image_name = "ghcr.io/openclaw/openclaw:latest"
            subprocess.run(["docker", "pull", image_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)

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
                image_name, "openclaw", "gateway", "run", "--port", "18789", "--bind", "lan", "--allow-unconfigured", "--auth", "token", "--token", "admin123"
            ]

            if subprocess.run(run_cmd, capture_output=True, text=True, startupinfo=startupinfo).returncode != 0:
                raise Exception("docker run failed")
            
            # ---------------------------------------------------------
            self.log(">>> [5] 백엔드 시스템(Gateway) 부팅 대기 중... ")
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
                    
                    self.set_cat_progress(0.6 + (i * 0.01)) 
                except subprocess.TimeoutExpired:
                    continue
                except Exception as e:
                    self.log(f"⚠️ 로그 분석 오류: {str(e)}")
                    break

            # 🟢 [핵심] 게이트웨이가 완전히 켜진 후 토큰 주입
            if success:
                self.set_cat_progress(0.9)
                
                if tg_token or dc_token:
                    self.log(">>> [6] 자동 채널 연동 (보안 토큰 주입) 진행 중...")
                    time.sleep(2) # 게이트웨이 안정화 대기
                    if tg_token:
                        self.log("📡 Telegram 토큰을 내부 시스템에 안전하게 등록합니다...")
                        tg_res = subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "channels", "add", "--channel", "telegram", "--token", tg_token], capture_output=True, text=True)
                        self.log(f"[CLI 결과] {tg_res.stdout.strip() or tg_res.stderr.strip()}")
                        
                    if dc_token:
                        self.log("📡 Discord 토큰을 내부 시스템에 안전하게 등록합니다...")
                        dc_res = subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "channels", "add", "--channel", "discord", "--token", dc_token], capture_output=True, text=True)
                        self.log(f"[CLI 결과] {dc_res.stdout.strip() or dc_res.stderr.strip()}")

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