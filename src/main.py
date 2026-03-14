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

# keyring: OS 내장 키체인(Windows Credential Manager / macOS Keychain) 사용
# 설치 안 된 경우 파일 폴백(fallback)으로 자동 전환됩니다.
try:
    import keyring
    _KEYRING_OK = True
except ImportError:
    _KEYRING_OK = False

_KEYRING_SERVICE = "MellowCat"

# ─────────────────────────────────────────────────────────────
# 플랫폼별 관리자 권한 체크 (Windows 전용)
# ─────────────────────────────────────────────────────────────
def is_admin():
    """Windows 전용. Mac/Linux 는 항상 True."""
    if platform.system() != "Windows":
        return True
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def resource_path(relative_path):
    """PyInstaller 패키징 및 개발 환경 모두에서 올바른 경로 반환."""
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
        "provider_id": "openai",
        "api_type": "openai-completions",
        "base_url": "https://api.openai.com/v1",
        "key_placeholder": "sk-...",
        "site_url": "https://platform.openai.com/api-keys",
        "models": [
            ("gpt-4o",         "GPT-4o (최신·추천)"),
            ("gpt-4o-mini",    "GPT-4o mini (빠름·저렴)"),
            ("gpt-4-turbo",    "GPT-4 Turbo"),
            ("gpt-3.5-turbo",  "GPT-3.5 Turbo (가장 저렴)"),
        ],
    },
    "Anthropic (Claude)": {
        "provider_id": "anthropic",
        "api_type": "anthropic-messages",
        "base_url": "https://api.anthropic.com/v1",
        "key_placeholder": "sk-ant-...",
        "site_url": "https://console.anthropic.com/settings/keys",
        "models": [
            ("claude-opus-4-5",   "Claude Opus 4.5 (최고성능)"),
            ("claude-sonnet-4-5", "Claude Sonnet 4.5 (균형·추천)"),
            ("claude-haiku-3-5",  "Claude Haiku 3.5 (빠름·경제적)"),
        ],
    },
    "Google Gemini": {
        "provider_id": "google",
        "api_type": "openai-completions",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_placeholder": "AIza...",
        "site_url": "https://aistudio.google.com/app/apikey",
        "models": [
            ("gemini-2.0-flash", "Gemini 2.0 Flash (최신·추천)"),
            ("gemini-2.0-pro",   "Gemini 2.0 Pro"),
            ("gemini-1.5-flash", "Gemini 1.5 Flash (경제적)"),
            ("gemini-1.5-pro",   "Gemini 1.5 Pro"),
        ],
    },
    "Groq (초고속)": {
        "provider_id": "groq",
        "api_type": "openai-completions",
        "base_url": "https://api.groq.com/openai/v1",
        "key_placeholder": "gsk_...",
        "site_url": "https://console.groq.com/keys",
        "models": [
            ("llama-3.3-70b-versatile", "Llama 3.3 70B (추천)"),
            ("llama-3.1-8b-instant",    "Llama 3.1 8B Instant (초고속)"),
            ("mixtral-8x7b-32768",      "Mixtral 8x7B"),
            ("gemma2-9b-it",            "Gemma 2 9B"),
        ],
    },
    "OpenRouter": {
        "provider_id": "openrouter",
        "api_type": "openai-completions",
        "base_url": "https://openrouter.ai/api/v1",
        "key_placeholder": "sk-or-...",
        "site_url": "https://openrouter.ai/settings/keys",
        "models": [
            ("openai/gpt-4o",                    "GPT-4o (via OpenRouter)"),
            ("anthropic/claude-sonnet-4-5",      "Claude Sonnet 4.5 (via OpenRouter)"),
            ("google/gemini-2.0-flash",          "Gemini 2.0 Flash (via OpenRouter)"),
            ("meta-llama/llama-3.3-70b-instruct","Llama 3.3 70B (무료 가능)"),
        ],
    },
}

OLLAMA_MODELS = [
    ("llama3.2",           "Llama 3.2 3B",           8,  "가장 빠름",   32000),
    ("qwen2.5-coder:7b",   "Qwen 2.5 Coder 7B",      8,  "코딩 특화",   32000),
    ("llama3.1",           "Llama 3.1 8B",           16,  "표준형",     128000),
    ("gemma2",             "Gemma 2 9B",             16,  "고성능",      32000),
    ("deepseek-coder-v2",  "DeepSeek Coder V2 Lite", 32,  "전문가용",   128000),
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
            # Mac에서 주로 사용하는 패키지 관리자 경로들을 모아둡니다.
            extra_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
            current_path = os.environ.get("PATH", "")
            
            # 현재 PATH에 위 경로들이 없다면 맨 앞에 강제로 이어 붙여줍니다.
            for p in extra_paths:
                if os.path.exists(p) and p not in current_path:
                    current_path = f"{p}:{current_path}"
            
            os.environ["PATH"] = current_path
        
        if self.is_windows and getattr(sys, "frozen", False) and not is_admin():
            self.withdraw()
            messagebox.showerror("권한 필요", "이 애플리케이션을 실행하려면 관리자 권한이 필요합니다.")
            self.destroy()
            return

        self.title("MellowCat")

        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = min(820, screen_w - 80)
        win_h = min(820, screen_h - 80)
        pos_x = (screen_w - win_w) // 2
        pos_y = (screen_h - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.minsize(680, 520)
        self.resizable(True, True)

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

        self.ram_gb  = math.ceil(psutil.virtual_memory().total / (1024 ** 3))
        os_name      = platform.system()
        cpu_arch     = platform.machine()

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(side="bottom", pady=(5, 12))

        self.start_btn = ctk.CTkButton(
            self.btn_frame, text=" 원클릭 자동 설치 및 실행 ",
            command=self.start_thread, height=48, font=("Arial", 17, "bold")
        )
        self.start_btn.pack(side="left", padx=10)

        self.exit_btn = ctk.CTkButton(
            self.btn_frame, text=" 런처 종료 ",
            command=self.on_closing, height=48, font=("Arial", 17, "bold"),
            fg_color="#CC3333", hover_color="#AA2222"
        )
        self.exit_btn.pack(side="left", padx=10)

        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent", height=50)
        self.progress_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 4))
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

        self.log_box = ctk.CTkTextbox(self, height=100, font=("Consolas", 11))
        self.log_box.pack(side="bottom", fill="x", padx=20, pady=(0, 4))
        self.log_box.configure(state="disabled")

        ctk.CTkLabel(self, text="MellowCat", font=("Arial", 30, "bold")).pack(side="top", pady=(8, 0))

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(side="top", fill="both", expand=True, padx=10, pady=4)

        self._build_status_section()
        self._build_ai_mode_section(os_name, cpu_arch)

        self.update_status_loop()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _build_status_section(self):
        self.status_frame = ctk.CTkFrame(self.scroll_frame)
        self.status_frame.pack(pady=(4, 4), padx=4, fill="x")
        self.create_status_row("Docker (MellowCat)", "docker_status", self.stop_docker)
        self.create_status_row("Ollama Engine",       "ollama_status", self.stop_ollama)

    def _build_ai_mode_section(self, os_name, cpu_arch):
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(pady=4, padx=4, fill="x")

        ctk.CTkLabel(frame, text="[ 🤖 AI 모드 선택 ]", font=("Arial", 13, "bold")).grid(row=0, column=0, columnspan=4, padx=10, pady=(8, 2), sticky="w")
        ctk.CTkLabel(frame, text=f"💻 {os_name} ({cpu_arch})   |   🔥 RAM {self.ram_gb} GB", font=("Arial", 12), text_color="#AAAAAA").grid(row=1, column=0, columnspan=4, padx=10, pady=(0, 6), sticky="w")

        self.ai_mode_var = ctk.StringVar(value="local")
        self.mode_seg = ctk.CTkSegmentedButton(
            frame,
            values=["🏠  로컬 Ollama (무료·프라이빗)", "☁️  클라우드 API (GPT·Claude 등)"],
            command=self._on_mode_change,
        )
        self.mode_seg.set("🏠  로컬 Ollama (무료·프라이빗)")
        self.mode_seg.grid(row=2, column=0, columnspan=4, padx=10, pady=(0, 8), sticky="ew")
        frame.columnconfigure(0, weight=1)

        self.local_panel = ctk.CTkFrame(frame, fg_color="transparent")
        self.local_panel.grid(row=3, column=0, columnspan=4, padx=0, pady=0, sticky="ew")
        self.local_panel.columnconfigure(1, weight=1)

        ctk.CTkLabel(self.local_panel, text="모델 선택:", width=100, anchor="w").grid(row=0, column=0, padx=10, pady=4, sticky="w")

        self.ollama_model_list = []
        for _mid, name, req_ram, desc, _ctx in OLLAMA_MODELS:
            if self.ram_gb >= req_ram:
                self.ollama_model_list.append(f"🟢 {name}  (권장 {req_ram}GB) — {desc}")
            else:
                self.ollama_model_list.append(f"🔴 {name}  (권장 {req_ram}GB) — RAM 부족")
        self.ollama_model_list.append("✍️  직접 입력 (ollama run 모델명)")

        self.ollama_combo = ctk.CTkComboBox(self.local_panel, values=self.ollama_model_list, command=self._on_ollama_model_select)
        self.ollama_combo.grid(row=0, column=1, padx=10, pady=4, sticky="ew")

        self.ollama_warn_label = ctk.CTkLabel(self.local_panel, text="", font=("Arial", 12, "bold"))
        self.ollama_warn_label.grid(row=1, column=1, padx=10, pady=(0, 2), sticky="w")

        self.ollama_custom_label = ctk.CTkLabel(self.local_panel, text="모델명 직접 입력:", text_color="#22CC22")
        self.ollama_custom_entry = ctk.CTkEntry(self.local_panel, placeholder_text="예: phi3   또는   mistral:latest")

        self._auto_select_ollama_model()

        self.cloud_panel = ctk.CTkFrame(frame, fg_color="transparent")
        self.cloud_panel.columnconfigure(1, weight=1)

        ctk.CTkLabel(self.cloud_panel, text="Provider:", width=100, anchor="w").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.provider_combo = ctk.CTkComboBox(self.cloud_panel, values=list(CLOUD_PROVIDERS.keys()), width=220, command=self._on_provider_change)
        self.provider_combo.set(list(CLOUD_PROVIDERS.keys())[0])
        self.provider_combo.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        self.provider_link_btn = ctk.CTkButton(self.cloud_panel, text="🔑 API 키 발급 →", width=130, fg_color="#3A3A5C", hover_color="#55558A", command=self._open_provider_site)
        self.provider_link_btn.grid(row=0, column=2, padx=(0, 10), pady=5, sticky="w")

        ctk.CTkLabel(self.cloud_panel, text="모델:", width=100, anchor="w").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.cloud_model_combo = ctk.CTkComboBox(self.cloud_panel, values=[])
        self.cloud_model_combo.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(self.cloud_panel, text="API 키:", width=100, anchor="w").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.api_key_entry = ctk.CTkEntry(self.cloud_panel, placeholder_text="API 키를 입력하세요", show="*")
        self.api_key_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        self._api_key_visible = False
        self.eye_btn = ctk.CTkButton(self.cloud_panel, text="👁", width=36, fg_color="#444444", hover_color="#666666", command=self._toggle_api_key_visibility)
        self.eye_btn.grid(row=2, column=2, padx=(0, 10), pady=5, sticky="w")

        security_frame = ctk.CTkFrame(self.cloud_panel, fg_color="#1A2A1A", corner_radius=8)
        security_frame.grid(row=3, column=0, columnspan=3, padx=10, pady=(2, 10), sticky="ew")

        ctk.CTkLabel(security_frame, text="🛡️  개인정보 보호 안내", font=("Arial", 12, "bold"), text_color="#44DD44").grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")

        security_lines = [
            "• MellowCat 은 100% 로컬에서 실행됩니다. 어떤 서버도 운영하지 않습니다.",
            "• API 키는 이 PC의 OS 키체인에만 저장됩니다.",
            "  (Windows: 자격 증명 관리자 / macOS: 키체인 앱)",
            "• 키는 선택하신 AI 서비스(OpenAI 등)에만 직접 전달됩니다.",
            "• MellowCat 개발자는 귀하의 키를 수집하거나 볼 수 없습니다.",
        ]
        for i, line in enumerate(security_lines):
            ctk.CTkLabel(security_frame, text=line, font=("Arial", 11), text_color="#AADDAA", anchor="w", justify="left").grid(row=i + 1, column=0, padx=12, pady=1, sticky="w")
        ctk.CTkLabel(security_frame, text="").grid(row=len(security_lines) + 1, pady=3)

        self._on_provider_change(list(CLOUD_PROVIDERS.keys())[0])

        ch_frame = ctk.CTkFrame(self.scroll_frame)
        ch_frame.pack(pady=4, padx=4, fill="x")
        ch_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(ch_frame, text="[ 💬 메신저 채널 연동 (선택) ]", font=("Arial", 13, "bold")).grid(row=0, column=0, columnspan=3, padx=10, pady=(8, 4), sticky="w")

        ctk.CTkLabel(ch_frame, text="Telegram:", width=100, anchor="w").grid(row=1, column=0, padx=10, pady=3, sticky="w")
        self.tg_entry = ctk.CTkEntry(ch_frame, placeholder_text="봇 토큰 (예: 12345:ABCDE...)", show="*")
        self.tg_entry.grid(row=1, column=1, padx=10, pady=3, sticky="ew")
        ctk.CTkButton(ch_frame, text="?", width=30, fg_color="#555555", hover_color="#777777", command=lambda: self._show_channel_help("telegram")).grid(row=1, column=2, padx=(0, 10), pady=3)

        ctk.CTkLabel(ch_frame, text="Discord:", width=100, anchor="w").grid(row=2, column=0, padx=10, pady=3, sticky="w")
        self.dc_entry = ctk.CTkEntry(ch_frame, placeholder_text="봇 토큰 (예: MTEyMz...)", show="*")
        self.dc_entry.grid(row=2, column=1, padx=10, pady=3, sticky="ew")
        ctk.CTkButton(ch_frame, text="?", width=30, fg_color="#555555", hover_color="#777777", command=lambda: self._show_channel_help("discord")).grid(row=2, column=2, padx=(0, 10), pady=3)

        ctk.CTkLabel(ch_frame, text="Slack Bot:", width=100, anchor="w").grid(row=3, column=0, padx=10, pady=3, sticky="w")
        self.slack_bot_entry = ctk.CTkEntry(ch_frame, placeholder_text="Bot Token (xoxb-...)", show="*")
        self.slack_bot_entry.grid(row=3, column=1, padx=10, pady=3, sticky="ew")
        ctk.CTkButton(ch_frame, text="?", width=30, fg_color="#555555", hover_color="#777777", command=lambda: self._show_channel_help("slack")).grid(row=3, column=2, padx=(0, 10), pady=3)

        ctk.CTkLabel(ch_frame, text="Slack App:", width=100, anchor="w").grid(row=4, column=0, padx=10, pady=3, sticky="w")
        self.slack_app_entry = ctk.CTkEntry(ch_frame, placeholder_text="App Token (xapp-...)", show="*")
        self.slack_app_entry.grid(row=4, column=1, padx=10, pady=3, sticky="ew")

        self.wa_btn = ctk.CTkButton(ch_frame, text="📱 WhatsApp 연동하기 (QR 코드 스캔)", fg_color="#25D366", hover_color="#128C7E", text_color="white", font=("Arial", 13, "bold"), command=self._open_whatsapp_qr)
        self.wa_btn.grid(row=5, column=0, columnspan=3, padx=10, pady=(6, 8), sticky="ew")

        # 🟢 서버 Allowlist 관리 섹션
        allowlist_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#2D2D2D", corner_radius=8)
        allowlist_frame.pack(pady=4, padx=4, fill="x")
        allowlist_frame.columnconfigure(2, weight=1)

        ctk.CTkLabel(allowlist_frame, text="[ 🛡️ 서버/그룹 Allowlist 관리 ]", font=("Arial", 13, "bold"), text_color="#ADD8E6").grid(row=0, column=0, columnspan=4, padx=14, pady=(8, 4), sticky="w")
        
        ctk.CTkLabel(allowlist_frame, text="채널 선택:", width=60, anchor="w").grid(row=1, column=0, padx=(14, 4), pady=(0, 8), sticky="w")
        self.allowlist_ch_combo = ctk.CTkComboBox(allowlist_frame, values=["discord", "telegram", "slack"], width=100)
        self.allowlist_ch_combo.grid(row=1, column=1, padx=4, pady=(0, 8), sticky="w")

        # UI 문구를 조금 명확하게 수정했습니다.
        self.allowlist_id_entry = ctk.CTkEntry(allowlist_frame, placeholder_text="서버(Guild) ID 또는 사용자 ID", width=200)
        self.allowlist_id_entry.grid(row=1, column=2, padx=4, pady=(0, 8), sticky="ew")

        ctk.CTkButton(allowlist_frame, text="➕ 추가", width=60, command=self._add_to_allowlist, fg_color="#3B82F6", hover_color="#2563EB").grid(row=1, column=3, padx=(4, 14), pady=(0, 8), sticky="w")
        # ─────────────────────────────────────────────────────────────

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

    # 🟢 [핵심 변경 1] 공식 문서의 Discord guilds 구조 완벽 대응
    def _add_to_allowlist(self):
        channel = self.allowlist_ch_combo.get()
        target_id = self.allowlist_id_entry.get().strip()
        
        if not target_id:
            self.log("⚠️ 추가할 서버/사용자 ID를 입력해주세요.")
            return

        config_path = os.path.expanduser("~/.openclaw_data/config.json")
        if not os.path.exists(config_path):
            self.log("⚠️ config.json 파일이 없습니다. 먼저 봇을 실행해주세요.")
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            if "channels" not in config_data or channel not in config_data["channels"]:
                self.log(f"⚠️ {channel} 설정이 없습니다. 먼저 토큰을 등록하고 실행해주세요.")
                return

            ch_config = config_data["channels"][channel]

            # Discord는 공식 문서에 따라 guilds 구조를 사용합니다.
            if channel == "discord":
                if "guilds" not in ch_config:
                    ch_config["guilds"] = {}
                
                if target_id in ch_config["guilds"]:
                    self.log(f"ℹ️ 서버 ID({target_id})는 이미 Discord 허용 목록에 있습니다.")
                    return
                
                # 프라이빗 서버용으로 멘션 없이도 대답하도록 requireMention: false 설정
                ch_config["guilds"][target_id] = {
                    "requireMention": False
                }
                self.log(f"✅ Discord 서버({target_id}) 등록 완료! (멘션 없이 응답)")
            
            # 그 외 텔레그램, 슬랙 등은 기존 allowlist 배열 방식 유지
            else:
                if "allowlist" not in ch_config:
                    ch_config["allowlist"] = []

                if target_id in ch_config["allowlist"]:
                    self.log(f"ℹ️ ID({target_id})는 이미 {channel} 허용 목록에 있습니다.")
                    return
                
                ch_config["allowlist"].append(target_id)
                self.log(f"✅ 설정 파일에 ID({target_id}) 추가 완료!")

            # 파일 덮어쓰기
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)

            # Docker 재시작 적용
            check = subprocess.run(["docker", "ps", "-q", "-f", "name=openclaw-main"], capture_output=True, text=True)
            if check.stdout.strip():
                self.log("🔄 변경사항 적용을 위해 시스템을 재시작합니다... (약 5초)")
                si = self._make_si()
                subprocess.run(["docker", "restart", "openclaw-main"], startupinfo=si, capture_output=True)
                time.sleep(5)
                
                proxy_js = "require('net').createServer(c=>{let s=require('net').connect(18789,'127.0.0.1');c.pipe(s).pipe(c);s.on('error',()=>c.destroy());c.on('error',()=>s.destroy());}).listen(18790,'0.0.0.0')"
                subprocess.run(["docker", "exec", "-d", "openclaw-main", "node", "-e", proxy_js], startupinfo=si, capture_output=True)
                self.log("✅ 적용 완료! 봇이 이제 해당 공간에서 응답합니다.")
                
            self.allowlist_id_entry.delete(0, "end")

        except Exception as e:
            self.log(f"❌ Allowlist 추가 중 오류 발생: {e}")

    def _on_mode_change(self, value):
        if "로컬" in value:
            self.ai_mode_var.set("local")
            self.cloud_panel.grid_forget()
            self.local_panel.grid(row=3, column=0, columnspan=4, padx=0, pady=0, sticky="ew")
        else:
            self.ai_mode_var.set("cloud")
            self.local_panel.grid_forget()
            self.cloud_panel.grid(row=3, column=0, columnspan=4, padx=0, pady=0, sticky="ew")

    def _on_ollama_model_select(self, choice):
        if "🔴" in choice:
            self.ollama_warn_label.configure(text="⚠️ 권장 RAM 부족! 시스템이 멈출 수 있습니다.", text_color="#FF3333")
        elif "🟢" in choice:
            self.ollama_warn_label.configure(text="✅ 현재 PC 환경에서 원활하게 구동 가능합니다.", text_color="#22CC22")
        else:
            self.ollama_warn_label.configure(text="")

        if "직접 입력" in choice:
            self.ollama_custom_label.grid(row=2, column=0, padx=10, pady=2, sticky="w")
            self.ollama_custom_entry.grid(row=2, column=1, padx=10, pady=2, sticky="ew")
        else:
            self.ollama_custom_label.grid_forget()
            self.ollama_custom_entry.grid_forget()

    def _auto_select_ollama_model(self):
        try:
            if self.ram_gb <= 8: idx = 0
            elif self.ram_gb <= 16: idx = 2
            else: idx = 4
            self.ollama_combo.set(self.ollama_model_list[idx])
        except Exception:
            self.ollama_combo.set(self.ollama_model_list[0])
        self._on_ollama_model_select(self.ollama_combo.get())

    def _on_provider_change(self, provider_name):
        provider = CLOUD_PROVIDERS.get(provider_name)
        if not provider: return
        model_labels = [f"{mid}  —  {desc}" for mid, desc in provider["models"]]
        self.cloud_model_combo.configure(values=model_labels)
        self.cloud_model_combo.set(model_labels[0] if model_labels else "")

        saved = self._get_saved_key(provider_name)
        self.api_key_entry.delete(0, "end")
        if saved:
            self.api_key_entry.insert(0, saved)

    def _toggle_api_key_visibility(self):
        self._api_key_visible = not self._api_key_visible
        self.api_key_entry.configure(show="" if self._api_key_visible else "*")
        self.eye_btn.configure(text="🙈" if self._api_key_visible else "👁")

    def _open_provider_site(self):
        provider = CLOUD_PROVIDERS.get(self.provider_combo.get())
        url = provider["site_url"] if provider else "https://google.com"
        webbrowser.open(url)

    def _show_channel_help(self, channel):
        if channel == "telegram":
            lines = [
                "─── Telegram 봇 토큰 발급 ───",
                "1. 텔레그램에서 @BotFather 검색 (파란 체크 공식 계정)",
                "2. /newbot 입력 → 봇 이름 → 사용자명(_bot 으로 끝나야 함)",
                "3. 발급된 HTTP API token 복사 후 위 입력란에 붙여넣기",
            ]
        elif channel == "discord":
            lines = [
                "─── Discord 봇 토큰 발급 ───",
                "1. https://discord.com/developers/applications 접속",
                "2. New Application → Bot 탭 → Reset Token 으로 토큰 복사",
                "3. Privileged Gateway Intents → Message Content Intent 활성화 필수",
                "4. OAuth2 → URL Generator → bot 권한으로 서버 초대",
            ]
        elif channel == "slack":
            lines = [
                "─── Slack 봇 토큰 발급 ───",
                "1. https://api.slack.com/apps → Create New App → From scratch",
                "2. Socket Mode 활성화 → App Token 생성 (xapp-...)",
                "3. OAuth & Permissions → Bot Token Scopes 추가 후 Install to Workspace",
                "4. Bot Token (xoxb-...) 복사",
                "※ Bot Token + App Token 두 개 모두 필요합니다.",
            ]
        else: lines = []
        for line in lines: self.log(line)

    def _open_whatsapp_qr(self):
        check = subprocess.run(["docker", "ps", "-q", "-f", "name=openclaw-main"], capture_output=True, text=True)
        if not check.stdout.strip():
            self.log("⚠️ 먼저 '원클릭 자동 설치 및 실행' 버튼을 눌러 시스템을 켜주세요!")
            return
        self.log("📱 WhatsApp QR 코드 창을 엽니다. 스마트폰으로 스캔해주세요!")
        if self.is_windows:
            subprocess.Popen(["cmd", "/k", "docker exec -it openclaw-main openclaw channels login --channel whatsapp"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        elif self.is_mac:
            cmd = 'tell application "Terminal" to do script "docker exec -it openclaw-main openclaw channels login --channel whatsapp"'
            subprocess.run(["osascript", "-e", cmd])

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
        res = subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "pairing", "approve", channel, code], capture_output=True, text=True)
        output = (res.stdout + res.stderr).strip()
        self.log(f"[승인 결과] {output}")
        if res.returncode == 0 and "error" not in output.lower():
            self.log("🎉 기기 승인 완료! 이제 메신저에서 봇과 대화할 수 있습니다.")
            self.pairing_entry.delete(0, "end")
        else:
            self.log("❌ 승인 실패. 채널과 코드를 다시 확인해주세요.")
    
    def _fallback_keys_path(self):
        return os.path.join(os.path.expanduser("~"), ".mellowcat_keys.json")

    def _get_saved_key(self, provider_name):
        if _KEYRING_OK:
            try:
                val = keyring.get_password(_KEYRING_SERVICE, provider_name)
                return val or ""
            except Exception: pass
        try:
            path = self._fallback_keys_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f).get(provider_name, "")
        except Exception: pass
        return ""

    def _save_api_key(self, provider_name, key):
        if _KEYRING_OK:
            try:
                keyring.set_password(_KEYRING_SERVICE, provider_name, key)
                path = self._fallback_keys_path()
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f: data = json.load(f)
                        data.pop(provider_name, None)
                        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
                    except Exception: pass
                return
            except Exception as e:
                self.log(f"⚠️ 키체인 저장 실패, 파일로 대체합니다: {e}")
        try:
            path = self._fallback_keys_path()
            data = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f: data = json.load(f)
            data[provider_name] = key
            with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
        except Exception as e: self.log(f"⚠️ API 키 저장 실패: {e}")

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
                cleaned = line.strip()
                if cleaned: self.log(f"> {cleaned}")
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
        # 1. 무거운 확인 작업은 백그라운드 스레드에서 조용히 처리합니다.
        docker_on = False
        try:
            d = subprocess.run(["docker", "ps", "--filter", "name=openclaw-main", "-q"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=si)
            docker_on = bool(d.stdout.strip()) and d.returncode == 0
        except Exception: 
            pass

        ollama_on = False
        try:
            if self.is_mac or platform.system() == "Linux":
                o = subprocess.run(["pgrep", "-x", "ollama"], capture_output=True, text=True, startupinfo=si)
                ollama_on = (o.returncode == 0)
            else:
                o = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ollama.exe", "/NH"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=si)
                ollama_on = "ollama.exe" in o.stdout.lower()
        except Exception: 
            pass

        # 2. UI 화면을 바꾸는 작업은 메인 스레드에게 안전하게 넘겨줍니다!
        def update_ui():
            self.docker_status.configure(text="● 실행 중" if docker_on else "○ 중지됨", text_color="#22CC22" if docker_on else "#CC2222")
            self.ollama_status.configure(text="● 실행 중" if ollama_on else "○ 중지됨", text_color="#22CC22" if ollama_on else "#CC2222")

        # 화면 멈춤 방지 핵심 코드
        self.after(0, update_ui)

    def start_docker_engine(self):
        self.log("⏳ Docker 엔진 상태 확인 중...")
        info = subprocess.run(["docker", "info"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if info.returncode == 0: return True

        self.log("🚀 Docker 엔진이 꺼져 있습니다. 자동으로 깨우는 중...")
        if self.is_windows:
            docker_exe = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Docker\\Docker\\Docker Desktop.exe")
            if not os.path.exists(docker_exe):
                self.log("❌ Docker Desktop 실행 파일을 찾을 수 없습니다.")
                return False
            subprocess.Popen([docker_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif self.is_mac:
            subprocess.Popen(["open", "-a", "Docker"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for i in range(12):
            time.sleep(5)
            self.log(f"⏳ Docker 가동 대기 중... ({(i+1)*5}초 / 60초)")
            check = subprocess.run(["docker", "info"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if check.returncode == 0:
                self.log("✅ Docker 엔진이 준비되었습니다.")
                return True
        self.log("❌ Docker 엔진 가동 시간 초과.")
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
            si   = self._make_si()
            mode = self.ai_mode_var.get()

            if mode == "local":
                if not shutil.which("ollama"):
                    self.log("⚠️ Ollama 가 없습니다. 설치를 시작합니다...")
                    if self.is_windows:
                        cmd = ["winget", "install", "--id", "Ollama.Ollama", "-e", "--source", "winget", "--silent", "--accept-package-agreements", "--accept-source-agreements"]
                        if self.run_with_live_logs(cmd, startupinfo=si) != 0:
                            self.log("❌ Ollama 자동 설치 실패. 수동으로 설치해주세요.")
                            self.start_btn.configure(state="normal")
                            return
                    elif self.is_mac:
                        # 1. brew가 있는지 검사
                        if not shutil.which("brew"):
                            self.log("⚠️ Homebrew가 없습니다. 터미널을 열어 자동 설치를 진행합니다.")
                            self.log("👉 새로 뜬 터미널 창에서 [엔터]를 누르고, 맥북 비밀번호를 입력해주세요!")
                            
                            # AppleScript를 사용해 새 터미널 창을 열고 brew 설치 명령어 자동 실행
                            brew_cmd = '/bin/bash -c \\"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\\"'
                            apple_script = f'tell application "Terminal" to do script "{brew_cmd}"'
                            subprocess.run(["osascript", "-e", apple_script])
                            
                            self.log("⏳ 터미널에서 설치가 완료되면, 런처를 껐다 켜거나 다시 시작 버튼을 눌러주세요.")
                            self.start_btn.configure(state="normal")
                            return

                        # 2. brew가 있다면 ollama 설치 진행
                        if self.run_with_live_logs(["brew", "install", "ollama"]) != 0:
                            self.log("❌ Ollama 설치 실패. https://ollama.com 에서 수동 설치 후 재시도하세요.")
                            self.start_btn.configure(state="normal")
                            return

            self.set_cat_progress(0.15)

            if not shutil.which("docker"):
                self.log("❌ Docker 가 설치되어 있지 않습니다!")
                if self.is_windows:
                    self.log("⏳ winget 으로 Docker Desktop 설치 중... (수 분 소요)")
                    cmd = ["winget", "install", "--id", "Docker.DockerDesktop", "-e", "--source", "winget", "--silent", "--accept-package-agreements", "--accept-source-agreements"]
                    if self.run_with_live_logs(cmd, startupinfo=si) == 0:
                        self.log("✅ Docker 설치 완료!")
                        messagebox.showinfo("재부팅 필요", "Docker WSL2 적용을 위해 PC 를 재시작한 후 다시 실행해주세요.")
                        self.after(0, self.destroy)
                        return
                    else:
                        webbrowser.open("https://docs.docker.com/desktop/install/windows-install/")
                        self.start_btn.configure(state="normal")
                        return
                else:
                    self.log("👉 Mac 환경: Docker Desktop 을 설치해주세요.")
                    webbrowser.open("https://docs.docker.com/desktop/install/mac-install/")
                    self.start_btn.configure(state="normal")
                    return
            else:
                self.log("✅ Docker 점검 완료.")
                if not self.start_docker_engine():
                    self.log("❌ Docker 엔진을 켤 수 없습니다. Docker Desktop 을 수동으로 실행해주세요.")
                    self.start_btn.configure(state="normal")
                    return

            self.set_cat_progress(0.3)
            self.log(">>> 시스템 점검 완료. 메인 로직을 시작합니다.")
            self.main_logic()
        except Exception as e:
            self.log(f"❌ 의존성 점검 오류: {e}")
            self.start_btn.configure(state="normal")

    def main_logic(self):
        try:
            si          = self._make_si()
            mode        = self.ai_mode_var.get()
            config_dir  = os.path.expanduser("~/.openclaw_data")
            config_path = os.path.join(config_dir, "config.json")

            tg_token       = self.tg_entry.get().strip()
            dc_token       = self.dc_entry.get().strip()
            slack_bot      = self.slack_bot_entry.get().strip()
            slack_app      = self.slack_app_entry.get().strip()

            # ── AI 설정 파싱 ─────────────────────────────────
            if mode == "local":
                is_local = True
                api_key  = ""
                selected = self.ollama_combo.get()

                if "직접 입력" in selected:
                    raw = self.ollama_custom_entry.get().strip()
                    if not raw:
                        self.log("❌ 모델명을 직접 입력해주세요.")
                        self.start_btn.configure(state="normal")
                        self.set_cat_progress(0)
                        return
                    target_model_id = raw
                    ctx_window = 32000
                else:
                    target_model_id = None
                    ctx_window      = 32000
                    for mid, name, _req, _desc, ctx in OLLAMA_MODELS:
                        if name in selected:
                            target_model_id = mid
                            ctx_window      = ctx
                            break
                    if target_model_id is None:
                        self.log("❌ 유효한 Ollama 모델을 선택해주세요.")
                        self.start_btn.configure(state="normal")
                        return

                provider_id       = "ollama"
                base_url          = "http://host.docker.internal:11434/v1"
                target_model_full = f"ollama/{target_model_id}"
                provider_info     = None

            else:
                is_local      = False
                provider_name = self.provider_combo.get()
                provider_info = CLOUD_PROVIDERS.get(provider_name)
                if not provider_info:
                    self.log("❌ 유효한 Provider 를 선택해주세요.")
                    self.start_btn.configure(state="normal")
                    return

                api_key = self.api_key_entry.get().strip()
                if not api_key:
                    self.log("❌ API 키를 입력해주세요.")
                    self.start_btn.configure(state="normal")
                    return

                raw_model         = self.cloud_model_combo.get().split("  —  ")[0].strip()
                target_model_id   = raw_model
                base_url          = provider_info["base_url"]
                
                provider_id       = provider_info["provider_id"]
                api_type          = provider_info["api_type"]
                ctx_window        = 128000

                target_model_full = f"{provider_id}/{target_model_id}"

                self._save_api_key(provider_name, api_key)
                self.log(f"🔑 [{provider_name}] API 키 저장 완료.")

            # ── 로컬 모드: Ollama 준비 ─────────────────────
            if is_local:
                self.log(f">>> [로컬 모드] Ollama 구동 및 '{target_model_id}' 준비 중...")
                self.stop_ollama()
                ollama_env = os.environ.copy()
                ollama_env["OLLAMA_HOST"] = "0.0.0.0"
                subprocess.Popen(["ollama", "serve"], env=ollama_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)
                self.log("⏳ Ollama 엔진 부팅 대기 중... (5초)")
                time.sleep(5)
                self.pulling_model = True
                self.log(f"📥 모델 다운로드/검증 중: {target_model_id}  (최초 1회, 수 분 소요)")
                if self.run_with_live_logs(["ollama", "pull", target_model_id], startupinfo=si) != 0:
                    raise RuntimeError(f"ollama pull {target_model_id} 실패")
                self.log(f"✅ 모델 준비 완료: {target_model_id}")
                self.pulling_model = False
            else:
                self.log(f">>> [클라우드 API 모드] Provider: {provider_name}  |  Model: {target_model_id}")

            self.set_cat_progress(0.4)

            # ── Docker 컨테이너 정리 ─────────────────────────
            self.log(">>> [1] 이전 Docker 컨테이너 정리 중...")
            subprocess.run(["docker", "rm", "-f", "openclaw-main"], capture_output=True, startupinfo=si)

            self.log(">>> [2] 설정 파일 갱신 및 백업 중...")
            os.makedirs(config_dir, exist_ok=True)
            
            # 🟢 [핵심 변경 2] 기존 파일에서 Discord의 guilds 구조도 안전하게 백업
            existing_allowlists = {}
            existing_guilds = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                        for ch_name, ch_data in old_data.get("channels", {}).items():
                            if "allowlist" in ch_data:
                                existing_allowlists[ch_name] = ch_data["allowlist"]
                            if ch_name == "discord" and "guilds" in ch_data:
                                existing_guilds = ch_data["guilds"]
                except Exception:
                    pass
                os.remove(config_path)

            self.set_cat_progress(0.5)

            # ── config.json 생성 ─────────────────────────────
            self.log(">>> [3] OpenClaw 설정 파일 생성 중...")

            channels_config = {
                "whatsapp": { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist", "debounceMs": 0, "mediaMaxMb": 50 }
            }

            if tg_token:
                channels_config["telegram"] = { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist", "streaming": "partial" }
                self.log("✅ Telegram 설정 준비 완료")
            else:
                channels_config["telegram"] = { "enabled": False, "dmPolicy": "pairing", "groupPolicy": "allowlist", "streaming": "partial" }

            if dc_token:
                channels_config["discord"] = { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist", "streaming": "off" }
                self.log("✅ Discord 설정 준비 완료")
            else:
                channels_config["discord"] = { "enabled": False, "groupPolicy": "allowlist", "streaming": "off" }

            if slack_bot and slack_app:
                channels_config["slack"] = { "enabled": True, "dmPolicy": "pairing", "groupPolicy": "allowlist" }
                self.log("✅ Slack 설정 준비 완료")

            # 🟢 [핵심 변경 3] 백업해둔 Discord guilds 정보 원상복구
            for ch_name in channels_config:
                if ch_name in existing_allowlists:
                    channels_config[ch_name]["allowlist"] = existing_allowlists[ch_name]
            
            if "discord" in channels_config and existing_guilds:
                channels_config["discord"]["guilds"] = existing_guilds

            config_data = {
                "models": { "providers": {} },
                "agents": { "defaults": { "model": { "primary": target_model_full } } },
                "commands": { "native": "auto", "nativeSkills": "auto", "restart": True, "ownerDisplay": "raw" },
                "channels": channels_config,
                "gateway": { "mode": "local", "controlUi": { "dangerouslyAllowHostHeaderOriginFallback": True } },
                "skills": {},
                "meta": { "lastTouchedVersion": "2026.3.8", "lastTouchedAt": time.strftime('%Y-%m-%dT%H:%M:%S.000Z') }
            }

            if is_local:
                config_data["models"]["providers"]["ollama"] = {
                    "baseUrl": base_url, "api": "openai-completions",
                    "models": [ { "id": target_model_full, "name": target_model_id, "contextWindow": ctx_window } ]
                }
            else:
                config_data["models"]["providers"][provider_id] = {
                    "baseUrl": base_url, 
                    "api": api_type,
                    "apiKey": api_key,
                    "models": [ { "id": target_model_id, "name": target_model_id, "contextWindow": ctx_window } ]
                }

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            self.log("✅ 설정 파일 생성 완료.")

            self.set_cat_progress(0.6)

            # ── Docker 컨테이너 실행 ─────────────────────────
            self.log(">>> [4] Docker 컨테이너 실행 중...")
            image_name = "ghcr.io/openclaw/openclaw:latest"
            subprocess.run(["docker", "pull", image_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)

            run_cmd = [
                "docker", "run", "-d",
                "--name", "openclaw-main",
                "-p", "18789:18789",
                "-p", "18790:18790",
                "-v", f"{config_dir}:/home/node/.openclaw",
                "--cap-add", "NET_ADMIN",
                "--cap-add", "SYS_PTRACE",
                "-e", "OPENCLAW_GATEWAY_AUTH_ENABLED=true",
                "-e", "OPENCLAW_GATEWAY_TOKEN=admin123",
                "-e", "OPENCLAW_GATEWAY_MODE=local",
                "-e", f"OPENCLAW_MODEL={target_model_full}",
                "-e", "OPENCLAW_CONFIG_PATH=/home/node/.openclaw/config.json",
                "-e", "OPENCLAW_SKILLS_ENABLED=true",
            ]

            if not is_local and api_key:
                run_cmd += ["-e", f"OPENCLAW_API_KEY={api_key}"]

            if not self.is_windows:
                run_cmd += ["--add-host", "host.docker.internal:host-gateway"]

            run_cmd += [
                image_name, "openclaw", "gateway", "run",
                "--port", "18789", "--bind", "lan",
                "--allow-unconfigured", "--auth", "token", "--token", "admin123"
            ]

            result = subprocess.run(run_cmd, capture_output=True, text=True, startupinfo=si)
            if result.returncode != 0:
                raise RuntimeError(f"docker run 실패: {result.stderr.strip()}")

            # ── Gateway 부팅 대기 ────────────────────────────
            self.log(">>> [5] 백엔드 Gateway 부팅 대기 중...")
            success = False
            for i in range(20):
                try:
                    time.sleep(3)
                    log_check = subprocess.run(["docker", "logs", "openclaw-main"], capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=si, timeout=10)
                    logs = log_check.stdout + log_check.stderr
                    if logs:
                        last = logs.strip().splitlines()[-1]
                        self.log(f"[도커 로그] {last}")
                    if "listening on" in logs.lower() or "gateway started" in logs.lower():
                        self.log(f"🎊 통합 성공! '{target_model_id}' 준비 완료!")
                        proxy_js = "require('net').createServer(c=>{let s=require('net').connect(18789,'127.0.0.1');c.pipe(s).pipe(c);s.on('error',()=>c.destroy());c.on('error',()=>s.destroy());}).listen(18790,'0.0.0.0')"
                        subprocess.run(["docker", "exec", "-d", "openclaw-main", "node", "-e", proxy_js], startupinfo=si, timeout=10, capture_output=True)
                        success = True
                        break
                    self.set_cat_progress(0.6 + i * 0.018)
                except subprocess.TimeoutExpired: continue
                except Exception as e:
                    self.log(f"⚠️ 로그 분석 오류: {e}")
                    break

            if success:
                self.set_cat_progress(0.9)

                # ── [6] 채널 토큰 주입 ────────────────────────
                if tg_token or dc_token or (slack_bot and slack_app):
                    self.log(">>> [6] 채널 토큰 주입 중...")
                    time.sleep(3)  # 게이트웨이 안정화 대기

                if tg_token:
                    self.log("📡 Telegram 토큰 등록 중...")
                    res = subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "channels", "add", "--channel", "telegram", "--token", tg_token], capture_output=True, text=True, startupinfo=si)
                    out = (res.stdout + res.stderr).strip()
                    self.log(f"[Telegram] {out or '완료'}")

                if dc_token:
                    self.log("📡 Discord 토큰 등록 중...")
                    res = subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "channels", "add", "--channel", "discord", "--token", dc_token], capture_output=True, text=True, startupinfo=si)
                    out = (res.stdout + res.stderr).strip()
                    self.log(f"[Discord] {out or '완료'}")

                if slack_bot and slack_app:
                    self.log("📡 Slack 토큰 등록 중...")
                    res = subprocess.run(["docker", "exec", "openclaw-main", "openclaw", "channels", "add", "--channel", "slack", "--bot-token", slack_bot, "--app-token", slack_app], capture_output=True, text=True, startupinfo=si)
                    out = (res.stdout + res.stderr).strip()
                    self.log(f"[Slack] {out or '완료'}")

                if tg_token or dc_token or (slack_bot and slack_app):
                    self.log("🔄 토큰 적용을 위해 시스템을 재시작합니다... (약 6초 소요)")
                    subprocess.run(["docker", "restart", "openclaw-main"], startupinfo=si, capture_output=True)
                    time.sleep(6) # 재부팅이 완료될 때까지 대기
                    
                    proxy_js = "require('net').createServer(c=>{let s=require('net').connect(18789,'127.0.0.1');c.pipe(s).pipe(c);s.on('error',()=>c.destroy());c.on('error',()=>s.destroy());}).listen(18790,'0.0.0.0')"
                    subprocess.run(["docker", "exec", "-d", "openclaw-main", "node", "-e", proxy_js], startupinfo=si, capture_output=True)
                    self.log("✅ 시스템 재부팅 및 100% 로드 완료!")

                self.set_cat_progress(1.0)
                url = "http://127.0.0.1:18790/?token=admin123"
                webbrowser.open(url)
                self.log("🚀 실행 완료! WhatsApp 은 런처의 📱 버튼으로 QR 스캔하세요.")
            else:
                self.set_cat_progress(0)
                self.log("❌ 실행 실패: docker logs openclaw-main 으로 오류를 확인하세요.")

            self.start_btn.configure(state="normal")

        except Exception as e:
            self.log(f"❌ 메인 로직 오류: {e}")
            self.start_btn.configure(state="normal")

    # ══════════════════════════════════════════════════════════════
    # 서비스 중지
    # ══════════════════════════════════════════════════════════════

    def stop_docker(self):
        si = self._make_si()
        subprocess.run(["docker", "rm", "-f", "openclaw-main"], startupinfo=si, capture_output=True)
        self.log("Docker 컨테이너(openclaw-main)를 중지했습니다.")

    def stop_ollama(self):
        if getattr(self, "pulling_model", False):
            self.log("⚠️ 모델 다운로드 중에는 Ollama 를 중지할 수 없습니다.")
            return
        si  = self._make_si()
        cmd = ["taskkill", "/f", "/im", "ollama.exe"] if self.is_windows else ["pkill", "ollama"]
        subprocess.run(cmd, startupinfo=si, capture_output=True)
        self.log("Ollama 엔진을 종료했습니다.")

    def on_closing(self):
        answer = messagebox.askyesnocancel(
            "종료 확인",
            "런처를 종료합니다.\n실행 중인 Docker 컨테이너와 Ollama 도 함께 종료하시겠습니까?"
        )
        if answer is True:
            self.stop_docker()
            self.stop_ollama()
            self.destroy()
        elif answer is False:
            self.destroy()

if __name__ == "__main__":
    app = OpenClawLauncher()
    app.mainloop()