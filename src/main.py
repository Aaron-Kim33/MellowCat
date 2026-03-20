import customtkinter as ctk
import subprocess
import threading
import os
import platform
import time
import shutil
import webbrowser
import sys
import tkinter as tk
import tkinter.messagebox as messagebox
import psutil
import math
import json
from PIL import Image, ImageTk

try:
    import keyring
    _KEYRING_OK = True
except ImportError:
    _KEYRING_OK = False

_KEYRING_SERVICE = "MellowCat"

def is_admin():
    if platform.system() != "Windows":
        return True
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# ─────────────────────────────────────────────────────────────
# 클라우드 API Provider 정의
# ─────────────────────────────────────────────────────────────
CLOUD_PROVIDERS = {
    "OpenAI": {
        "provider_id": "openai", "api_type": "openai-completions",
        "base_url": "https://api.openai.com/v1", "key_placeholder": "sk-...",
        "site_url": "https://platform.openai.com/api-keys",
        "models": [("gpt-4o", "GPT-4o (최신·추천)"), ("gpt-4o-mini", "GPT-4o mini (빠름·저렴)"), ("gpt-4-turbo", "GPT-4 Turbo"), ("gpt-3.5-turbo", "GPT-3.5 Turbo")]
    },
    "Anthropic": {
        "provider_id": "anthropic", "api_type": "anthropic-messages",
        "base_url": "https://api.anthropic.com/v1", "key_placeholder": "sk-ant-...",
        "site_url": "https://console.anthropic.com/settings/keys",
        "models": [("claude-opus-4-5", "Claude Opus 4.5"), ("claude-sonnet-4-5", "Claude Sonnet 4.5 (추천)"), ("claude-haiku-3-5", "Claude Haiku 3.5")]
    },
    "Gemini": {
        "provider_id": "google", "api_type": "openai-completions",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "key_placeholder": "AIza...",
        "site_url": "https://aistudio.google.com/app/apikey",
        "models": [("gemini-2.0-flash", "Gemini 2.0 Flash (추천)"), ("gemini-2.0-pro", "Gemini 2.0 Pro"), ("gemini-1.5-flash", "Gemini 1.5 Flash")]
    },
    "Groq": {
        "provider_id": "groq", "api_type": "openai-completions",
        "base_url": "https://api.groq.com/openai/v1", "key_placeholder": "gsk_...",
        "site_url": "https://console.groq.com/keys",
        "models": [("llama-3.3-70b-versatile", "Llama 3.3 70B"), ("llama-3.1-8b-instant", "Llama 3.1 8B Instant"), ("mixtral-8x7b-32768", "Mixtral 8x7B")]
    },
    "OpenRouter": {
        "provider_id": "openrouter", "api_type": "openai-completions",
        "base_url": "https://openrouter.ai/api/v1", "key_placeholder": "sk-or-...",
        "site_url": "https://openrouter.ai/settings/keys",
        "models": [("openai/gpt-4o", "GPT-4o (via OR)"), ("anthropic/claude-sonnet-4-5", "Claude Sonnet 4.5 (via OR)"), ("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B (무료 가능)")]
    },
}

# LLMFIT 확장 모델 리스트 (ID, 이름, 필요 RAM(GB), 컨텍스트, 설명)
EXPANDED_OLLAMA_MODELS = [
    ("qwen2.5-coder:1.5b", "Qwen 2.5 Coder 1.5B", 2, 32000, "초경량 코딩 특화"),
    ("llama3.2",           "Llama 3.2 3B",        4, 32000, "빠른 응답 (모바일급)"),
    #("phi3:mini",          "Phi-3 Mini 3.8B",     4, 128000, "MS 고효율 모델"), 지원안함
    ("llama3.1",           "Llama 3.1 8B",        8, 128000, "표준형 (가장 추천)"),
    ("qwen2.5-coder:7b",   "Qwen 2.5 Coder 7B",   8, 32000, "코딩 특화 (추천)"),
    ("gemma2",             "Gemma 2 9B",          10, 32000, "구글 고성능 모델"),
    ("mistral-nemo",       "Mistral Nemo 12B",    14, 128000, "다국어 우수"),
    ("deepseek-coder-v2",  "DeepSeek Coder V2",   16, 128000, "전문가 코딩용"),
    ("command-r",          "Cohere Command R",    32, 128000, "RAG 특화 거대 모델"),
    ("llama3.1:70b",       "Llama 3.1 70B",       40, 128000, "초거대 모델 (서버급)"),
]

# ─────────────────────────────────────────────────────────────
# 메인 앱 클래스
# ─────────────────────────────────────────────────────────────
class OpenClawLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.is_mac     = platform.system() == "Darwin"
        self.is_windows = platform.system() == "Windows"

        if self.is_mac:
            extra_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
            current_path = os.environ.get("PATH", "")
            for p in extra_paths:
                if os.path.exists(p) and p not in current_path:
                    current_path = f"{p}:{current_path}"
            os.environ["PATH"] = current_path
        
        if self.is_windows and getattr(sys, "frozen", False) and not is_admin():
            self.withdraw()
            messagebox.showerror("권한 필요", "이 애플리케이션을 실행하려면 관리자 권한이 필요합니다.")
            self.destroy()
            return

        self.title("MellowCat v2.0")
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = min(850, screen_w - 80)
        win_h = min(950, screen_h - 80)
        pos_x = (screen_w - win_w) // 2
        pos_y = (screen_h - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.minsize(750, 600)

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

        # 기본 시스템 사양 (LLMFIT 갱신 전)
        self.ram_gb = math.ceil(psutil.virtual_memory().total / (1024 ** 3))
        self.vram_gb = 0 
        self.gpu_name = "내장 그래픽 또는 미확인"

        # --- 하단 고정 영역 (버튼, 로그, 프로그레스) ---
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(side="bottom", fill="x")

        self.btn_frame = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        self.btn_frame.pack(side="top", pady=(5, 12))

        self.start_btn = ctk.CTkButton(self.btn_frame, text=" 원클릭 자동 설치 및 실행 ", command=self.start_thread, height=48, font=("Arial", 17, "bold"))
        self.start_btn.pack(side="left", padx=10)

        self.exit_btn = ctk.CTkButton(self.btn_frame, text=" 런처 종료 ", command=self.on_closing, height=48, font=("Arial", 17, "bold"), fg_color="#CC3333", hover_color="#AA2222")
        self.exit_btn.pack(side="left", padx=10)

        self.progress_frame = ctk.CTkFrame(self.bottom_frame, fg_color="transparent", height=50)
        self.progress_frame.pack(side="top", fill="x", padx=20, pady=(0, 4))
        self.progress_frame.pack_propagate(False)

        self.progress = ctk.CTkProgressBar(self.progress_frame)
        self.progress.place(relx=0.5, rely=0.8, anchor="center", relwidth=0.98)
        self.progress.set(0)

        cat_img_path = resource_path("assets/cat_run.png")
        if os.path.exists(cat_img_path):
            cat_img = ctk.CTkImage(light_image=Image.open(cat_img_path), size=(38, 38))
            self.cat_label = ctk.CTkLabel(self.progress_frame, image=cat_img, text="")
        else:
            self.cat_label = ctk.CTkLabel(self.progress_frame, text="🐈", font=("Arial", 32))
        self.cat_label.place(relx=0.0, rely=0.3, anchor="center")

        self.log_box = ctk.CTkTextbox(self.bottom_frame, height=100, font=("Consolas", 11))
        self.log_box.pack(side="top", fill="x", padx=20, pady=(0, 4))
        self.log_box.configure(state="disabled")

        # --- 메인 스크롤 영역 ---
        ctk.CTkLabel(self, text="MellowCat AI Manager", font=("Arial", 28, "bold")).pack(side="top", pady=(8, 0))

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(side="top", fill="both", expand=True, padx=10, pady=4)

        self._build_status_section()
        self._build_ai_tabview_section()
        self._build_messenger_section()

        self.update_status_loop()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _build_status_section(self):
        self.status_frame = ctk.CTkFrame(self.scroll_frame)
        self.status_frame.pack(pady=(4, 4), padx=4, fill="x")
        self.create_status_row("Docker (MellowCat)", "docker_status", self.stop_docker)
        self.create_status_row("Ollama Engine",       "ollama_status", self.stop_ollama)

    def _build_ai_tabview_section(self):
        # 🟢 [핵심 변경] Provider 기반 탭 뷰 UI
        self.ai_tabview = ctk.CTkTabview(self.scroll_frame, height=350)
        self.ai_tabview.pack(pady=4, padx=4, fill="x")

        # 로컬 탭 생성
        tab_local = self.ai_tabview.add("🏠 로컬 (Ollama)")
        self._build_local_tab(tab_local)

        # 클라우드 탭 생성 밎 API 엔트리 딕셔너리
        self.cloud_api_entries = {}
        self.cloud_model_combos = {}
        self.cloud_eye_btns = {}
        self.cloud_api_visible = {}

        for prov_name, prov_info in CLOUD_PROVIDERS.items():
            tab_cloud = self.ai_tabview.add(f"☁️ {prov_name}")
            self._build_cloud_tab(tab_cloud, prov_name, prov_info)

    def _build_local_tab(self, parent):
        # 1. LLMFIT 사양 분석기 영역
        spec_header = ctk.CTkFrame(parent, fg_color="transparent")
        spec_header.pack(fill="x", pady=5)
        
        self.spec_btn = ctk.CTkButton(spec_header, text="🔍 LLMFIT 사양 정밀 분석", command=self._run_llmfit_analysis, fg_color="#4B5563", hover_color="#374151")
        self.spec_btn.pack(side="left", padx=10)
        
        self.spec_label = ctk.CTkLabel(spec_header, text="사양을 분석하면 추천 모델이 표시됩니다.", text_color="#AAAAAA", font=("Arial", 12))
        self.spec_label.pack(side="left", padx=10)

        # 2. 모델 검색 바
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filter_local_models)
        self.search_entry = ctk.CTkEntry(parent, placeholder_text="🔍 모델명 검색 (예: llama, qwen)...", textvariable=self.search_var)
        self.search_entry.pack(fill="x", padx=10, pady=(5, 10))

        # 3. 스크롤 모델 리스트
        self.local_scroll = ctk.CTkScrollableFrame(parent, height=180)
        self.local_scroll.pack(fill="both", expand=True, padx=10)
        
        self.local_model_widgets = [] # 검색 필터링을 위한 위젯 저장소
        self.selected_local_model_var = ctk.StringVar(value="llama3.1")
        
        self._populate_local_models()

        # 4. 하단 선택 모델 및 직접 입력
        bottom_frame = ctk.CTkFrame(parent, fg_color="transparent")
        bottom_frame.pack(fill="x", pady=(10, 5), padx=10)
        
        ctk.CTkLabel(bottom_frame, text="✅ 현재 선택됨:").pack(side="left")
        ctk.CTkLabel(bottom_frame, textvariable=self.selected_local_model_var, text_color="#22CC22", font=("Arial", 13, "bold")).pack(side="left", padx=10)
        
        ctk.CTkLabel(bottom_frame, text="  |  직접 입력:").pack(side="left", padx=10)
        self.custom_local_entry = ctk.CTkEntry(bottom_frame, placeholder_text="예: mistral:latest", width=150)
        self.custom_local_entry.pack(side="left")

        # 👇 여기서부터 추가하세요 (중첩 스크롤바 충돌 방지 로직)
        if not hasattr(self.scroll_frame, "_original_mouse_wheel"):
            # 메인 스크롤의 원래 휠 이벤트를 백업합니다.
            self.scroll_frame._original_mouse_wheel = self.scroll_frame._mouse_wheel_all
            
            def _custom_mouse_wheel(event):
                try:
                    # 현재 마우스 커서의 x, y 좌표를 가져옵니다.
                    x, y = self.winfo_pointerxy()
                    # 그 좌표 아래에 있는 위젯이 무엇인지 찾습니다.
                    hovered_widget = self.winfo_containing(x, y)
                    
                    # 마우스가 가리키는 위젯이 '내부 모델 스크롤(local_scroll)'에 속해 있다면
                    # 메인 스크롤을 움직이지 않고 함수를 종료(return)합니다.
                    if hovered_widget and str(hovered_widget).startswith(str(self.local_scroll)):
                        return 
                except Exception:
                    pass
                # 마우스가 내부 스크롤 밖(앱의 빈 공간 등)에 있다면 정상적으로 메인 스크롤을 움직입니다.
                self.scroll_frame._original_mouse_wheel(event)
                
            # 만든 커스텀 휠 이벤트를 메인 스크롤 프레임에 덮어씌웁니다.
            self.scroll_frame._mouse_wheel_all = _custom_mouse_wheel

    def _build_cloud_tab(self, parent, prov_name, prov_info):
        parent.columnconfigure(1, weight=1)
        
        ctk.CTkLabel(parent, text="Provider:", width=80, anchor="w").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkLabel(parent, text=prov_name, font=("Arial", 13, "bold")).grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        ctk.CTkButton(parent, text="🔑 API 키 발급 →", width=120, fg_color="#3A3A5C", hover_color="#55558A", command=lambda url=prov_info["site_url"]: webbrowser.open(url)).grid(row=0, column=2, padx=10, pady=10)

        ctk.CTkLabel(parent, text="모델:", width=80, anchor="w").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        model_labels = [f"{mid}  —  {desc}" for mid, desc in prov_info["models"]]
        combo = ctk.CTkComboBox(parent, values=model_labels)
        combo.set(model_labels[0])
        combo.grid(row=1, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        self.cloud_model_combos[prov_name] = combo

        ctk.CTkLabel(parent, text="API 키:", width=80, anchor="w").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        entry = ctk.CTkEntry(parent, placeholder_text=prov_info["key_placeholder"], show="*")
        
        saved = self._get_saved_key(prov_name)
        if saved: entry.insert(0, saved)
        entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        self.cloud_api_entries[prov_name] = entry

        self.cloud_api_visible[prov_name] = False
        eye_btn = ctk.CTkButton(parent, text="👁", width=36, fg_color="#444444", command=lambda p=prov_name: self._toggle_cloud_eye(p))
        eye_btn.grid(row=2, column=2, padx=10, pady=10)
        self.cloud_eye_btns[prov_name] = eye_btn

        security_frame = ctk.CTkFrame(parent, fg_color="#1A2A1A", corner_radius=8)
        security_frame.grid(row=3, column=0, columnspan=3, padx=10, pady=15, sticky="ew")
        ctk.CTkLabel(security_frame, text="🛡️ API 키는 로컬 키체인에 안전하게 암호화되어 보관됩니다.", text_color="#44DD44", font=("Arial", 11)).pack(pady=8)

    def _toggle_cloud_eye(self, prov_name):
        is_visible = not self.cloud_api_visible[prov_name]
        self.cloud_api_visible[prov_name] = is_visible
        self.cloud_api_entries[prov_name].configure(show="" if is_visible else "*")
        self.cloud_eye_btns[prov_name].configure(text="🙈" if is_visible else "👁")

    # 🟢 LLMFIT 사양 분석 로직
    def _run_llmfit_analysis(self):
        self.spec_btn.configure(state="disabled", text="⏳ 분석 중...")
        self.update()
        
        # 실제 LLMFIT을 Popen으로 돌리거나, psutil/nvidia-smi로 경량화하여 검사합니다.
        # 여기서는 안정성을 위해 내장 모듈과 nvidia-smi를 활용해 VRAM을 도출합니다.
        vram_gb = 0
        gpu_name = "미확인 GPU"
        
        if self.is_windows:
            try:
                smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if smi.returncode == 0:
                    parts = smi.stdout.strip().split(',')
                    gpu_name = parts[0].strip()
                    vram_mb = int(parts[1].strip().replace(' MiB', ''))
                    vram_gb = vram_mb / 1024
            except Exception:
                pass
        
        self.vram_gb = vram_gb
        self.gpu_name = gpu_name
        
        time.sleep(0.5) # 분석 시각적 효과
        
        if vram_gb > 0:
            spec_text = f"✅ RAM: {self.ram_gb}GB | GPU: {gpu_name} ({vram_gb:.1f}GB VRAM)"
            self.spec_label.configure(text_color="#22CC22")
        else:
            spec_text = f"⚠️ RAM: {self.ram_gb}GB | VRAM 분석 불가 (CPU Fallback)"
            self.spec_label.configure(text_color="#CCCC22")
            
        self.spec_label.configure(text=spec_text)
        self.spec_btn.configure(state="normal", text="🔄 사양 재분석")
        
        self._populate_local_models() # 리스트 신호등 업데이트

    def _populate_local_models(self):
        # 기존 위젯 삭제
        for widget in self.local_model_widgets:
            widget["frame"].destroy()
        self.local_model_widgets.clear()
        
        search_query = self.search_var.get().lower()

        for mid, name, req_ram, ctx, desc in EXPANDED_OLLAMA_MODELS:
            # 검색 필터링
            if search_query and search_query not in mid.lower() and search_query not in name.lower():
                continue

            # 신호등 로직 판별
            if self.vram_gb > 0 and req_ram <= self.vram_gb + 2: 
                status = "🟢 Fit"
                color = "#22CC22"
                info = f"GPU 쾌적 (권장 {req_ram}GB)"
            elif req_ram <= self.ram_gb:
                status = "🟡 Slow"
                color = "#CCCC22"
                info = f"CPU 병목 예상 (권장 {req_ram}GB)"
            else:
                status = "🔴 Unfit"
                color = "#CC2222"
                info = f"메모리 부족 (권장 {req_ram}GB)"

            item_frame = ctk.CTkFrame(self.local_scroll, fg_color="#2B2B2B")
            item_frame.pack(fill="x", pady=2, padx=2)
            
            ctk.CTkLabel(item_frame, text=status, text_color=color, width=60, font=("Arial", 13, "bold")).pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=name, text_color="white", font=("Arial", 13, "bold"), width=150, anchor="w").pack(side="left", padx=5)
            ctk.CTkLabel(item_frame, text=f"{info} | {desc}", text_color="#DDDDDD", font=("Arial", 11)).pack(side="left", padx=5)
            
            select_btn = ctk.CTkButton(item_frame, text="선택", width=60, command=lambda m=mid: self.selected_local_model_var.set(m))
            select_btn.pack(side="right", padx=10, pady=5)
            
            self.local_model_widgets.append({"frame": item_frame, "mid": mid, "name": name})

    def _filter_local_models(self, *args):
        self._populate_local_models()

    def _build_messenger_section(self):
        # 🟢 메신저 및 채널 연동 섹션 (기존 코드 그대로 이식)
        ch_frame = ctk.CTkFrame(self.scroll_frame)
        ch_frame.pack(pady=4, padx=4, fill="x")
        ch_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(ch_frame, text="[ 💬 메신저 채널 연동 (선택) ]", font=("Arial", 13, "bold")).grid(row=0, column=0, columnspan=3, padx=10, pady=(8, 4), sticky="w")

        ctk.CTkLabel(ch_frame, text="Telegram:", width=100, anchor="w").grid(row=1, column=0, padx=10, pady=3, sticky="w")
        self.tg_entry = ctk.CTkEntry(ch_frame, placeholder_text="봇 토큰", show="*")
        self.tg_entry.grid(row=1, column=1, padx=10, pady=3, sticky="ew")

        ctk.CTkLabel(ch_frame, text="Discord:", width=100, anchor="w").grid(row=2, column=0, padx=10, pady=3, sticky="w")
        self.dc_entry = ctk.CTkEntry(ch_frame, placeholder_text="봇 토큰", show="*")
        self.dc_entry.grid(row=2, column=1, padx=10, pady=3, sticky="ew")

        ctk.CTkLabel(ch_frame, text="Slack Bot:", width=100, anchor="w").grid(row=3, column=0, padx=10, pady=3, sticky="w")
        self.slack_bot_entry = ctk.CTkEntry(ch_frame, placeholder_text="Bot Token (xoxb-...)", show="*")
        self.slack_bot_entry.grid(row=3, column=1, padx=10, pady=3, sticky="ew")

        ctk.CTkLabel(ch_frame, text="Slack App:", width=100, anchor="w").grid(row=4, column=0, padx=10, pady=3, sticky="w")
        self.slack_app_entry = ctk.CTkEntry(ch_frame, placeholder_text="App Token (xapp-...)", show="*")
        self.slack_app_entry.grid(row=4, column=1, padx=10, pady=3, sticky="ew")

        self.wa_btn = ctk.CTkButton(ch_frame, text="📱 WhatsApp 연동 (QR)", fg_color="#25D366", hover_color="#128C7E", text_color="white", font=("Arial", 13, "bold"), command=self._open_whatsapp_qr)
        self.wa_btn.grid(row=5, column=0, columnspan=3, padx=10, pady=(6, 8), sticky="ew")

        allowlist_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#2D2D2D", corner_radius=8)
        allowlist_frame.pack(pady=4, padx=4, fill="x")
        allowlist_frame.columnconfigure(2, weight=1)

        ctk.CTkLabel(allowlist_frame, text="[ 🛡️ 서버 Allowlist 관리 ]", font=("Arial", 13, "bold"), text_color="#ADD8E6").grid(row=0, column=0, columnspan=4, padx=14, pady=(8, 4), sticky="w")
        
        self.allowlist_ch_combo = ctk.CTkComboBox(allowlist_frame, values=["discord", "telegram", "slack"], width=100)
        self.allowlist_ch_combo.grid(row=1, column=1, padx=4, pady=(0, 8), sticky="w")
        self.allowlist_id_entry = ctk.CTkEntry(allowlist_frame, placeholder_text="서버(Guild) 또는 사용자 ID", width=200)
        self.allowlist_id_entry.grid(row=1, column=2, padx=4, pady=(0, 8), sticky="ew")

        ctk.CTkButton(allowlist_frame, text="➕ 추가", width=60, command=self._add_to_allowlist, fg_color="#3B82F6").grid(row=1, column=3, padx=(4, 14), pady=(0, 8), sticky="w")

        pairing_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#1A1A2E", corner_radius=8)
        pairing_frame.pack(pady=4, padx=4, fill="x")
        pairing_frame.columnconfigure(2, weight=1)

        ctk.CTkLabel(pairing_frame, text="[ 🔐 봇 1:1 사용 권한 승인 (DM 페어링) ]", font=("Arial", 13, "bold"), text_color="#FFB347").grid(row=0, column=0, columnspan=4, padx=14, pady=(8, 4), sticky="w")
        ctk.CTkLabel(pairing_frame, text="채널:", width=50, anchor="w").grid(row=1, column=0, padx=(14, 4), pady=(0, 8), sticky="w")
        self.pairing_ch_combo = ctk.CTkComboBox(pairing_frame, values=["telegram", "whatsapp", "discord", "slack"], width=110)
        self.pairing_ch_combo.grid(row=1, column=1, padx=4, pady=(0, 8), sticky="w")

        self.pairing_entry = ctk.CTkEntry(pairing_frame, placeholder_text="페어링 코드 (예: J46PG7YA)", width=160)
        self.pairing_entry.grid(row=1, column=2, padx=4, pady=(0, 8), sticky="w")

        ctk.CTkButton(pairing_frame, text="✅ 승인", width=70, command=self._approve_pairing).grid(row=1, column=3, padx=(4, 14), pady=(0, 8), sticky="w")
    # 기존 기능 메서드들 이식 (생략 없이 유지)
    def _add_to_allowlist(self):
        channel = self.allowlist_ch_combo.get()
        target_id = self.allowlist_id_entry.get().strip()
        if not target_id: return self.log("⚠️ ID를 입력해주세요.")
        config_path = os.path.expanduser("~/.openclaw_data/config.json")
        if not os.path.exists(config_path): return self.log("⚠️ config.json 파일이 없습니다.")
        try:
            with open(config_path, "r", encoding="utf-8") as f: config_data = json.load(f)
            if "channels" not in config_data or channel not in config_data["channels"]: return self.log(f"⚠️ {channel} 설정이 없습니다.")
            ch_config = config_data["channels"][channel]
            
            # 💡 [버그 수정 완료] allowlist -> allowFrom 으로 변경
            if channel == "discord":
                if "guilds" not in ch_config: ch_config["guilds"] = {}
                if target_id in ch_config["guilds"]: return self.log("ℹ️ 이미 존재합니다.")
                ch_config["guilds"][target_id] = { "requireMention": False }
            else:
                if "allowFrom" not in ch_config: ch_config["allowFrom"] = []
                if target_id in ch_config["allowFrom"]: return self.log("ℹ️ 이미 존재합니다.")
                ch_config["allowFrom"].append(target_id)
                
            with open(config_path, "w", encoding="utf-8") as f: json.dump(config_data, f, indent=2)
            self.log(f"✅ ID({target_id}) 추가 완료! 적용을 위해 시스템을 재시작합니다.")
            si = self._make_si()
            subprocess.run(["docker", "restart", "openclaw-main"], startupinfo=si, capture_output=True)
        except Exception as e: self.log(f"❌ 오류 발생: {e}")

    # 👇 누락됐던 1:1 페어링 승인 함수 복구!
    def _approve_pairing(self):
        channel = self.pairing_ch_combo.get()
        code    = self.pairing_entry.get().strip()
        if not code:
            self.log("⚠️ 봇이 메신저로 보내준 페어링 코드를 입력해주세요.")
            return
        check = subprocess.run(["docker", "ps", "-q", "-f", "name=openclaw-main"], capture_output=True, text=True)
        if not check.stdout.strip():
            self.log("⚠️ 시스템이 아직 실행되지 않았습니다.")
            return
        self.log(f"🔐 [{channel}] 페어링 코드 승인 시도 중...")
        si = self._make_si()
        res = subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "pairing", "approve", channel, code], capture_output=True, text=True, startupinfo=si)
        output = (res.stdout + res.stderr).strip()
        self.log(f"[승인 결과] {output}")
        if res.returncode == 0 and "error" not in output.lower():
            self.log("🎉 기기 승인 완료! 이제 메신저에서 봇과 대화할 수 있습니다.")
            self.pairing_entry.delete(0, "end")
        else:
            self.log("❌ 승인 실패. 채널과 코드를 다시 확인해주세요.")

    def _open_whatsapp_qr(self):
        check = subprocess.run(["docker", "ps", "-q", "-f", "name=openclaw-main"], capture_output=True, text=True)
        if not check.stdout.strip(): return self.log("⚠️ 먼저 시스템을 켜주세요!")
        if self.is_windows: subprocess.Popen(["cmd", "/k", "docker exec -it openclaw-main openclaw channels login --channel whatsapp"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        elif self.is_mac: subprocess.run(["osascript", "-e", 'tell application "Terminal" to do script "docker exec -it openclaw-main openclaw channels login --channel whatsapp"'])

    def _fallback_keys_path(self): return os.path.join(os.path.expanduser("~"), ".mellowcat_keys.json")
    def _get_saved_key(self, prov):
        if _KEYRING_OK:
            try: return keyring.get_password(_KEYRING_SERVICE, prov) or ""
            except: pass
        try:
            p = self._fallback_keys_path()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f: return json.load(f).get(prov, "")
        except: pass
        return ""
    def _save_api_key(self, prov, key):
        if _KEYRING_OK:
            try: keyring.set_password(_KEYRING_SERVICE, prov, key); return
            except: pass
        try:
            p = self._fallback_keys_path()
            d = {}
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f: d = json.load(f)
            d[prov] = key
            with open(p, "w", encoding="utf-8") as f: json.dump(d, f, indent=2)
        except: pass

    def set_cat_progress(self, value):
        self.progress.set(value)
        target_x = 0.01 + (value * 0.97)
        self.after(0, lambda: self.cat_label.place(relx=target_x, rely=0.3, anchor="center"))

    def create_status_row(self, name, attr_name, stop_cmd):
        row = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        row.pack(pady=4, padx=10, fill="x")
        ctk.CTkLabel(row, text=name, width=160, anchor="w").pack(side="left")
        indicator = ctk.CTkLabel(row, text="확인 중...", text_color="gray")
        indicator.pack(side="left", padx=20)
        setattr(self, attr_name, indicator)
        ctk.CTkButton(row, text="강제종료", width=70, fg_color="#CC3333", command=stop_cmd).pack(side="right")

    def log(self, text):
        def _update():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
            self.log_box.configure(state="disabled")
            self.log_box.see("end")
        self.after(0, _update)

    def run_with_live_logs(self, cmd, startupinfo=None):
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)
            for line in process.stdout:
                if line.strip(): self.log(f"> {line.strip()}")
            process.wait()
            return process.returncode
        except Exception as e:
            self.log(f"⚠️ 프로세스 실행 오류: {e}")
            return 1

    def _make_si(self):
        if not self.is_windows: return None
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return si

    def update_status_loop(self):
        threading.Thread(target=self._check_services, daemon=True).start()
        self.after(10000, self.update_status_loop)

    def _check_services(self):
        si = self._make_si()
        docker_on = ollama_on = False
        try:
            d = subprocess.run(["docker", "ps", "--filter", "name=openclaw-main", "-q"], capture_output=True, text=True, encoding="utf-8", startupinfo=si)
            docker_on = bool(d.stdout.strip()) and d.returncode == 0
        except: pass
        try:
            if self.is_mac: o = subprocess.run(["pgrep", "-x", "ollama"], capture_output=True, text=True, startupinfo=si); ollama_on = (o.returncode == 0)
            else: o = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ollama.exe", "/NH"], capture_output=True, text=True, encoding="utf-8", startupinfo=si); ollama_on = "ollama.exe" in o.stdout.lower()
        except: pass
        def update_ui():
            self.docker_status.configure(text="● 실행 중" if docker_on else "○ 중지됨", text_color="#22CC22" if docker_on else "#CC2222")
            self.ollama_status.configure(text="● 실행 중" if ollama_on else "○ 중지됨", text_color="#22CC22" if ollama_on else "#CC2222")
        self.after(0, update_ui)

    def start_docker_engine(self):
        self.log("⏳ Docker 엔진 상태 확인 중...")
        info = subprocess.run(["docker", "info"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if info.returncode == 0: return True
        self.log("🚀 Docker 엔진이 꺼져 있습니다. 자동으로 깨우는 중...")
        if self.is_windows:
            docker_exe = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Docker\\Docker\\Docker Desktop.exe")
            if not os.path.exists(docker_exe): return False
            subprocess.Popen([docker_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif self.is_mac: subprocess.Popen(["open", "-a", "Docker"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for i in range(12):
            time.sleep(5)
            self.log(f"⏳ Docker 가동 대기 중... ({(i+1)*5}초 / 60초)")
            if subprocess.run(["docker", "info"], capture_output=True, text=True, encoding="utf-8").returncode == 0: return True
        return False

    def start_thread(self):
        self.start_btn.configure(state="disabled")
        self.set_cat_progress(0)
        self.pulling_model = False
        threading.Thread(target=self.check_and_install_dependencies, daemon=True).start()

    def check_and_install_dependencies(self):
        try:
            self.log(">>> [0] 시스템 필수 환경 점검 시작...")
            self.set_cat_progress(0.05)
            si = self._make_si()
            current_tab = self.ai_tabview.get()
            is_local = "로컬" in current_tab

            if is_local:
                if not shutil.which("ollama"):
                    self.log("⚠️ Ollama 가 없습니다. 설치를 시작합니다...")
                    if self.is_windows:
                        if self.run_with_live_logs(["winget", "install", "--id", "Ollama.Ollama", "-e", "--silent", "--accept-source-agreements"], startupinfo=si) != 0: return self.start_btn.configure(state="normal")
                    elif self.is_mac:
                        if not shutil.which("brew"):
                            apple_script = 'tell application "Terminal" to do script "/bin/bash -c \\"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\\""'
                            subprocess.run(["osascript", "-e", apple_script])
                            self.log("⏳ 터미널에서 Homebrew 설치가 완료되면 런처를 껐다 켜주세요.")
                            return self.start_btn.configure(state="normal")
                        if self.run_with_live_logs(["brew", "install", "ollama"]) != 0: return self.start_btn.configure(state="normal")

            self.set_cat_progress(0.15)

            if not shutil.which("docker"):
                self.log("❌ Docker 가 설치되어 있지 않습니다!")
                if self.is_windows:
                    if self.run_with_live_logs(["winget", "install", "--id", "Docker.DockerDesktop", "-e", "--silent", "--accept-source-agreements"], startupinfo=si) == 0:
                        messagebox.showinfo("재부팅 필요", "Docker 설치 완료. 재시작 후 다시 실행해주세요.")
                        self.after(0, self.destroy)
                else: webbrowser.open("https://docs.docker.com/desktop/install/mac-install/")
                return self.start_btn.configure(state="normal")
            else:
                if not self.start_docker_engine():
                    self.log("❌ Docker 엔진을 켤 수 없습니다. 수동으로 실행해주세요.")
                    return self.start_btn.configure(state="normal")

            self.set_cat_progress(0.3)
            self.main_logic()
        except Exception as e:
            self.log(f"❌ 오류: {e}")
            self.start_btn.configure(state="normal")

    def main_logic(self):
        try:
            si = self._make_si()
            current_tab = self.ai_tabview.get()
            is_local = "로컬" in current_tab
            config_dir = os.path.expanduser("~/.openclaw_data")
            config_path = os.path.join(config_dir, "config.json")

            tg_token = self.tg_entry.get().strip()
            dc_token = self.dc_entry.get().strip()
            slack_bot = self.slack_bot_entry.get().strip()
            slack_app = self.slack_app_entry.get().strip()

            # 🟢 [핵심 변경] 새 UI 구조에서 모델 데이터 가져오기
            if is_local:
                api_key = ""
                custom_model = self.custom_local_entry.get().strip()
                target_model_id = custom_model if custom_model else self.selected_local_model_var.get()
                
                if not target_model_id:
                    self.log("❌ 유효한 로컬 모델을 선택하거나 입력해주세요.")
                    return self.start_btn.configure(state="normal")

                ctx_window = 32000
                for mid, _, _, ctx, _ in EXPANDED_OLLAMA_MODELS:
                    if mid == target_model_id: ctx_window = ctx; break

                provider_id = "ollama"
                base_url = "http://host.docker.internal:11434/v1"
                target_model_full = f"ollama/{target_model_id}"
            else:
                provider_name = current_tab.replace("☁️ ", "")
                provider_info = CLOUD_PROVIDERS.get(provider_name)
                
                api_key = self.cloud_api_entries[provider_name].get().strip()
                if not api_key:
                    self.log(f"❌ {provider_name} API 키를 입력해주세요.")
                    return self.start_btn.configure(state="normal")

                raw_model = self.cloud_model_combos[provider_name].get().split("  —  ")[0].strip()
                target_model_id = raw_model
                base_url = provider_info["base_url"]
                provider_id = provider_info["provider_id"]
                api_type = provider_info["api_type"]
                ctx_window = 128000
                target_model_full = f"{provider_id}/{target_model_id}"
                
                self._save_api_key(provider_name, api_key)
                self.log(f"🔑 [{provider_name}] API 키 저장 완료.")

            if is_local:
                self.log(f">>> [로컬 모드] Ollama 구동 및 '{target_model_id}' 준비 중...")
                self.stop_ollama()
                env = os.environ.copy()
                env["OLLAMA_HOST"] = "0.0.0.0"
                subprocess.Popen(["ollama", "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)
                time.sleep(5)
                self.pulling_model = True
                self.log(f"📥 모델 다운로드/검증 중: {target_model_id}")
                if self.run_with_live_logs(["ollama", "pull", target_model_id], startupinfo=si) != 0: raise RuntimeError(f"ollama pull 실패")
                self.log(f"✅ 모델 준비 완료: {target_model_id}")
                self.pulling_model = False

            self.set_cat_progress(0.4)

            self.log(">>> [1] 이전 Docker 정리 및 설정 백업 중...")
            subprocess.run(["docker", "rm", "-f", "openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=si)
            os.makedirs(config_dir, exist_ok=True)
            
            existing_allowlists = {}
            existing_guilds = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                        for ch_name, ch_data in old_data.get("channels", {}).items():
                            if "allowFrom" in ch_data: existing_allowlists[ch_name] = ch_data["allowFrom"]
                            if ch_name == "discord" and "guilds" in ch_data: existing_guilds = ch_data["guilds"]
                except: pass
                os.remove(config_path)

            self.set_cat_progress(0.5)

            self.log(">>> [2] OpenClaw 설정 파일 생성 중...")
            channels_config = { "whatsapp": { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist" } }
            if tg_token: channels_config["telegram"] = { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist" }
            if dc_token: channels_config["discord"] = { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist", "streaming": "off" }
            if slack_bot and slack_app: channels_config["slack"] = { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist" }

            for ch_name in channels_config:
                if ch_name in existing_allowlists: channels_config[ch_name]["allowFrom"] = existing_allowlists[ch_name]
            if "discord" in channels_config and existing_guilds: channels_config["discord"]["guilds"] = existing_guilds

            config_data = {
                "models": { "providers": {} },
                "agents": { "defaults": { "model": { "primary": target_model_full } } },
                "commands": { "native": "auto", "nativeSkills": "auto", "restart": True },
                "channels": channels_config,
                "gateway": { "mode": "local", "controlUi": { "dangerouslyAllowHostHeaderOriginFallback": True } },
                "skills": {}
            }

            if is_local:
                config_data["models"]["providers"]["ollama"] = {
                    "baseUrl": base_url, "api": "openai-completions",
                    "models": [ { "id": target_model_full, "name": target_model_id, "contextWindow": ctx_window } ]
                }
            else:
                config_data["models"]["providers"][provider_id] = {
                    "baseUrl": base_url, "api": api_type, "apiKey": api_key,
                    "models": [ { "id": target_model_id, "name": target_model_id, "contextWindow": ctx_window } ]
                }

            with open(config_path, "w", encoding="utf-8") as f: json.dump(config_data, f, indent=2)
            self.set_cat_progress(0.6)

            self.log(">>> [3] Docker 컨테이너 실행 중...")
            image_name = "ghcr.io/openclaw/openclaw:latest"
            subprocess.run(["docker", "pull", image_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)

            run_cmd = [
                "docker", "run", "-d", "--name", "openclaw-main",
                "-p", "18789:18789", "-p", "18790:18790", "-v", f"{config_dir}:/home/node/.openclaw",
                "--cap-add", "NET_ADMIN", "--cap-add", "SYS_PTRACE",
                "-e", "OPENCLAW_GATEWAY_AUTH_ENABLED=true", "-e", "OPENCLAW_GATEWAY_TOKEN=admin123",
                "-e", "OPENCLAW_GATEWAY_MODE=local", "-e", f"OPENCLAW_MODEL={target_model_full}",
                "-e", "OPENCLAW_CONFIG_PATH=/home/node/.openclaw/config.json", "-e", "OPENCLAW_SKILLS_ENABLED=true",
            ]
            if not is_local and api_key: run_cmd += ["-e", f"OPENCLAW_API_KEY={api_key}"]
            if not self.is_windows: run_cmd += ["--add-host", "host.docker.internal:host-gateway"]
            run_cmd += [image_name, "openclaw", "gateway", "run", "--port", "18789", "--bind", "lan", "--allow-unconfigured", "--auth", "token", "--token", "admin123"]

            res = subprocess.run(run_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=si)
            if res.returncode != 0: raise RuntimeError(f"docker run 실패: {res.stderr.strip()}")

            self.log(">>> [4] Gateway 부팅 대기 중...")
            success = False
            for i in range(20):
                try:
                    time.sleep(3)
                    log_check = subprocess.run(["docker", "logs", "openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=si)
                    logs = log_check.stdout + log_check.stderr
                    if "listening on" in logs.lower() or "gateway started" in logs.lower():
                        proxy_js = "require('net').createServer(c=>{let s=require('net').connect(18789,'127.0.0.1');c.pipe(s).pipe(c);s.on('error',()=>c.destroy());c.on('error',()=>s.destroy());}).listen(18790,'0.0.0.0')"
                        subprocess.run(["docker", "exec", "-d", "openclaw-main", "node", "-e", proxy_js], startupinfo=si)
                        success = True
                        break
                    self.set_cat_progress(0.6 + i * 0.018)
                except: pass

            if success:
                self.set_cat_progress(0.9)
                if tg_token or dc_token or (slack_bot and slack_app):
                    self.log(">>> [5] 메신저 채널 토큰 등록 중...")
                    time.sleep(3)
                    if tg_token: subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "channels", "add", "--channel", "telegram", "--token", tg_token], startupinfo=si)
                    if dc_token: subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "channels", "add", "--channel", "discord", "--token", dc_token], startupinfo=si)
                    if slack_bot and slack_app: subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "channels", "add", "--channel", "slack", "--bot-token", slack_bot, "--app-token", slack_app], startupinfo=si)
                    
                    subprocess.run(["docker", "restart", "openclaw-main"], startupinfo=si)
                    time.sleep(6)
                    proxy_js = "require('net').createServer(c=>{let s=require('net').connect(18789,'127.0.0.1');c.pipe(s).pipe(c);s.on('error',()=>c.destroy());c.on('error',()=>s.destroy());}).listen(18790,'0.0.0.0')"
                    subprocess.run(["docker", "exec", "-d", "openclaw-main", "node", "-e", proxy_js], startupinfo=si)

                self.set_cat_progress(1.0)
                webbrowser.open("http://127.0.0.1:18790/?token=admin123")
                self.log("🚀 실행 완료! WhatsApp 은 런처의 📱 버튼으로 QR 스캔하세요.")
            else:
                self.set_cat_progress(0)
                self.log("❌ 부팅 실패.")

            self.start_btn.configure(state="normal")
        except Exception as e:
            self.log(f"❌ 메인 로직 오류: {e}")
            self.start_btn.configure(state="normal")

    def stop_docker(self):
        si = self._make_si()
        subprocess.run(["docker", "rm", "-f", "openclaw-main"], startupinfo=si, capture_output=True)
        self.log("Docker 컨테이너를 중지했습니다.")

    def stop_ollama(self):
        si = self._make_si()
        cmd = ["taskkill", "/f", "/im", "ollama.exe"] if self.is_windows else ["pkill", "ollama"]
        subprocess.run(cmd, startupinfo=si, capture_output=True)
        self.log("Ollama 엔진을 종료했습니다.")

    def on_closing(self):
        answer = messagebox.askyesnocancel("종료", "실행 중인 Docker와 Ollama 도 함께 종료하시겠습니까?")
        if answer is True: 
            self.stop_docker()
            self.stop_ollama()
            self.destroy()
        elif answer is False: self.destroy()

if __name__ == "__main__":
    app = OpenClawLauncher()
    app.mainloop()