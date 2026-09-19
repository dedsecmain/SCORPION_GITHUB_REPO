from __future__ import annotations

import threading
import time
import traceback
from collections.abc import Callable

from .actions import (
    execute_preflighted_action,
    execute_windows_action,
    focus_windows_target,
    preflight_windows_action,
    resolve_app_id,
)
from .adaptive import AdaptiveStore
from .app_trust import AppTrustRegistry
from .audit_log import AuditLog
from .camera import CameraService
from .cloud_ai import CloudAI, CloudUnavailableError
from .cloud_gate import CloudApprovalError, CloudGate
from .commands import CommandKind, parse_command
from .config import Mode, Settings
from .context_engine import analyze_context
from .handoff import ChatGPTHandoff, HandoffResult
from .hud import THEME, SystemPanelModel, VoiceVisualState
from .improvement_advisor import ImprovementAdvisor
from .hardware import HardwareProfiler
from .listener import ContinuousWakeListener
from .local_ai import OllamaLocalAI
from .local_audio import LocalAudioService
from .local_vision import LocalVision
from .model_manager import ModelManager
from .model_router import ModelRouter, TaskKind
from .memory import ConversationMemory
from .long_term_memory import LongTermMemoryStore
from .router import AssistantRouter, RouteStatus
from .screen import ScreenService
from .screen_context import ScreenContextMonitor
from .updater import Updater, UpdateVerificationError
from . import __version__
from .update_helper import apply_update
from .wake_matcher import WakeMatcher


class ScorpionController:
    def __init__(
        self,
        settings: Settings,
        *,
        approval_callback: Callable[[str], bool] | None = None,
        action_approval_callback: Callable[[str], bool] | None = None,
        local_ai=None,
        local_audio=None,
        cloud_ai=None,
        handoff=None,
        text_model: str | None = None,
        vision_model: str | None = None,
        adaptive_store=None,
        hardware_profiler=None,
        model_manager=None,
    ):
        self.settings = settings
        self.mode = settings.mode
        self.memory = ConversationMemory(settings.memory_path)
        self.long_term_memory = LongTermMemoryStore(settings.long_term_memory_path)
        self.hardware_profile = None
        self.adaptive = adaptive_store or AdaptiveStore(settings.adaptive_path)
        self.improvement_advisor = ImprovementAdvisor(
            settings.adaptive_path.with_name("improvements.json")
        )
        self.hardware_profiler = hardware_profiler or HardwareProfiler()
        self.model_manager = model_manager or ModelManager()

        bootstrap_model = settings.local_model or "gemma3:4b"
        self.local_ai = local_ai or OllamaLocalAI(settings.ollama_url, bootstrap_model)
        if text_model or vision_model:
            self.text_model = text_model or bootstrap_model
            self.vision_model = vision_model or self.text_model
        elif settings.local_model:
            self.text_model = settings.local_model
            self.vision_model = settings.local_model
        else:
            self.text_model, self.vision_model = self._auto_select_models()

        self.audio = local_audio or LocalAudioService(
            settings.whisper_model,
            wake_whisper_model=settings.wake_whisper_model,
            command_whisper_model=settings.command_whisper_model,
            vad_aggressiveness=settings.vad_aggressiveness,
            natural_voice=settings.natural_voice,
            natural_voice_rate=settings.natural_voice_rate,
            natural_voice_pitch=settings.natural_voice_pitch,
            natural_voice_enabled=settings.natural_voice_enabled,
        )
        self.cloud_gate = CloudGate(approval_callback or (lambda _reason: False))
        self.cloud_ai = cloud_ai or CloudAI(self.cloud_gate, settings.api_key, settings.model)
        self.action_approval_callback = action_approval_callback or (lambda _reason: False)
        self.app_trust = AppTrustRegistry(settings.app_trust_path)
        self.audit = AuditLog()
        self.handoff = handoff or ChatGPTHandoff()
        self.router = AssistantRouter(self.local_ai)
        try:
            installed_models = set(self.local_ai.available_models())
        except Exception:
            installed_models = set()
        if self.hardware_profile is None:
            try:
                self.hardware_profile = self.hardware_profiler.profile()
            except Exception:
                self.hardware_profile = None
        routing_profile = self.hardware_profile or "low"
        self.model_router = ModelRouter(
            model_manager=self.model_manager,
            hardware_profile=routing_profile,
            installed_models=installed_models,
            adaptive_store=self.adaptive,
        )
        self.camera = CameraService()
        self.screen = ScreenService()
        self.screen_context = ScreenContextMonitor(interval_ms=settings.screen_context_interval_ms)
        self.local_vision = LocalVision(self.local_ai, model=self.vision_model)
        self.last_user_text = ""
        self.last_image_bytes: bytes | None = None
        self.last_context = analyze_context("")
        self.last_memory_hits = 0
        self.last_route_model = "AUTO"
        self.last_route_reason = "AUTO"
        self._ollama_failures = 0
        self._language_mismatch_count = 0


    def _auto_select_models(self) -> tuple[str, str]:
        saved_text = self.adaptive.get("text_model")
        saved_vision = self.adaptive.get("vision_model")
        if saved_text and saved_vision:
            return str(saved_text), str(saved_vision)
        try:
            profile = self.hardware_profiler.profile()
            self.hardware_profile = profile
        except Exception:
            profile = "low"
        try:
            installed = self.local_ai.available_models()
        except Exception:
            installed = set()
        recommendation = self.model_manager.recommend(profile, installed)
        return recommendation.text_model, recommendation.vision_model

    def set_mode(self, mode: Mode | str) -> Mode:
        self.mode = mode if isinstance(mode, Mode) else Mode.from_value(mode)
        return self.mode

    def local_status(self):
        try:
            return self.local_ai.status(self.text_model)
        except TypeError:
            return self.local_ai.status()

    def hardware_summary(self) -> str:
        profile = self.hardware_profile
        if profile is None:
            try:
                profile = self.hardware_profiler.profile()
                self.hardware_profile = profile
            except Exception as exc:
                return f"HARDWARE UNAVAILABLE · {exc}"
        vram = "? VRAM" if profile.vram_gb is None else f"{profile.vram_gb:.0f} GB VRAM"
        return f"{profile.capability.upper()} · {profile.total_ram_gb:.0f} GB RAM · {vram}"

    def speech_status(self) -> str:
        return self.audio.speech_status()

    def _remember_answer(self, text: str, answer: str) -> None:
        self.memory.append("user", text)
        self.memory.append("assistant", answer)

    @staticmethod
    def _task_complexity(text: str) -> float:
        lowered = text.casefold()
        score = min(0.65, len(text) / 1800.0)
        if any(word in lowered for word in ("analysiere", "begründe", "architektur", "debug", "vergleich", "strategie")):
            score += 0.35
        return max(0.0, min(1.0, score))

    @staticmethod
    def _looks_like_english(text: str) -> bool:
        words = {word.strip(".,!?;:()[]{}\"'").casefold() for word in str(text).split()}
        english = len(words & {
            "the", "and", "you", "your", "this", "that", "with", "from",
            "are", "is", "to", "of", "for", "can", "will",
        })
        german = len(words & {
            "der", "die", "das", "und", "du", "dein", "ist", "sind", "mit",
            "von", "für", "ich", "nicht", "kann", "wird", "auf",
        })
        return english >= 5 and english >= german + 3

    @staticmethod
    def _format_memory_context(entries) -> str:
        parts: list[str] = []
        size = 0
        for item in entries:
            line = f"- [{item.category}] {item.title}: {item.content}".strip()
            if size + len(line) > 1600:
                break
            parts.append(line)
            size += len(line)
        return "\n".join(parts)

    def intelligence_status(self) -> dict[str, object]:
        return {
            "context": self.last_context.label,
            "memory_hits": self.last_memory_hits,
            "route_model": self.last_route_model,
            "route_reason": self.last_route_reason,
            "improvements": len(self.improvement_advisor.pending()),
        }

    def _ask_local(self, text: str, image_bytes: bytes | None = None) -> str:
        self.last_user_text = text
        self.last_image_bytes = image_bytes
        history = self.memory.messages()
        context = analyze_context(text, history)
        memories = self.long_term_memory.relevant(
            text,
            limit=4,
            project=context.project,
        )
        memory_context = self._format_memory_context(memories)
        complexity = max(self._task_complexity(text), context.complexity)
        kind = TaskKind.VISION if image_bytes is not None else (
            TaskKind.REASONING if complexity >= 0.75 else TaskKind.CHAT
        )
        route = self.model_router.route(
            kind,
            complexity=complexity,
            priority=context.priority,
        )
        selected_model = route.model or (
            self.vision_model if image_bytes is not None else self.text_model
        )
        self.last_context = context
        self.last_memory_hits = len(memories)
        self.last_route_model = selected_model or "AUTO"
        self.last_route_reason = route.reason

        started = time.monotonic()
        result = self.router.handle_local(
            text,
            history=history,
            image_bytes=image_bytes,
            model=selected_model,
            context=context,
            memory_context=memory_context,
        )

        if (
            result.status is RouteStatus.ANSWER
            and context.response_language == "de-DE"
            and self._looks_like_english(result.text)
        ):
            self._language_mismatch_count += 1
            self.improvement_advisor.diagnose(
                language_mismatch_count=self._language_mismatch_count,
            )
            retry = self.router.handle_local(
                "Antworte ausschließlich auf Hochdeutsch. " + text,
                history=history,
                image_bytes=image_bytes,
                model=selected_model,
                context=context,
                memory_context=memory_context,
            )
            if retry.status is RouteStatus.ANSWER and not self._looks_like_english(retry.text):
                result = retry

        if result.status is RouteStatus.ESCALATION_REQUIRED and "ollama" in result.text.casefold():
            self._ollama_failures += 1
            self.improvement_advisor.diagnose(ollama_failures=self._ollama_failures)

        try:
            if route.model:
                self.model_router.record_result(
                    route,
                    latency_ms=(time.monotonic() - started) * 1000.0,
                    success=result.status is RouteStatus.ANSWER,
                )
            else:
                self.adaptive.record_model_metric(
                    selected_model,
                    latency_s=time.monotonic() - started,
                    success=result.status is RouteStatus.ANSWER,
                )
        except Exception:
            pass
        if result.status is RouteStatus.ANSWER:
            self._remember_answer(text, result.text)
        return result.text

    def _run_app_action(self, action: str, target: str, executor) -> str:
        preflight = preflight_windows_action(
            action,
            target,
            trust_registry=self.app_trust,
        )
        app_id = resolve_app_id(target)
        if not preflight.allowed and app_id is not None:
            approved = self.action_approval_callback(
                f"Erste App-Freigabe: {app_id}. Aktion: {action}. Ziel: {target}."
            )
            if approved:
                self.app_trust.set_trust(app_id, True)
                preflight = preflight_windows_action(
                    action,
                    target,
                    trust_registry=self.app_trust,
                )
        _ok, message = execute_preflighted_action(
            preflight,
            confirm=lambda pf: self.action_approval_callback(
                f"Bestätigung erforderlich. Risiko: {pf.risk.value}. Aktion: {pf.action}. Ziel: {pf.target}."
            ),
            executor=executor,
            audit_log=self.audit,
        )
        return message

    def handle(self, text: str, image_bytes: bytes | None = None) -> str:
        command = parse_command(text)
        if command.kind is CommandKind.OPEN_APP and command.target:
            return self._run_app_action(
                "open_app",
                command.target,
                lambda: execute_windows_action(command.target, trust_registry=self.app_trust),
            )
        if command.kind is CommandKind.FOCUS_APP and command.target:
            return self._run_app_action(
                "focus_window",
                command.target,
                lambda: focus_windows_target(command.target, trust_registry=self.app_trust),
            )
        if command.kind is CommandKind.SCREEN:
            if callable(getattr(self.local_ai, "available_models", None)):
                result = self.local_vision.analyze_current(self.screen_context, text)
                if not result.summary.startswith("Lokale Bildanalyse nicht verfügbar:"):
                    self._remember_answer(text, result.summary)
                    return result.summary
                return result.summary
            try:
                image_bytes = self.screen.capture_jpeg()
            except Exception as exc:
                return f"Bildschirmaufnahme fehlgeschlagen: {exc}"
            return self._ask_local(text, image_bytes=image_bytes)
        if command.kind is CommandKind.CAMERA and image_bytes is None:
            return "Kamera bereit. Nutze CAM und stell mir direkt eine Frage zum Bild."
        return self._ask_local(text, image_bytes=image_bytes)

    def request_cloud_once(
        self,
        reason: str,
        text: str,
        image_bytes: bytes | None = None,
    ) -> str:
        if self.mode is Mode.LOCAL:
            return "OPENAI LOCKED 🔒 · Im LOCAL-Modus sind direkte OpenAI-API-Aufrufe gesperrt."

        token = self.cloud_gate.request_approval(reason)
        if token is None:
            return "OpenAI wurde für diese Anfrage nicht freigegeben. Es wurden keine API-Credits verwendet."

        try:
            answer = self.cloud_ai.respond(
                token,
                text,
                history=self.memory.messages(),
                image_bytes=image_bytes,
            )
        except (CloudApprovalError, CloudUnavailableError) as exc:
            return str(exc)
        except Exception as exc:
            return f"OpenAI-Anfrage fehlgeschlagen. Für einen neuen Versuch ist eine neue Freigabe nötig: {exc}"

        self._remember_answer(text, answer)
        return answer

    def prepare_chatgpt_handoff(
        self,
        text: str,
        image_bytes: bytes | None = None,
    ) -> HandoffResult:
        prompt = self.handoff.build_prompt(
            text,
            history=self.memory.messages(),
            image_attached=image_bytes is not None,
        )
        return self.handoff.copy_and_open(prompt)

    def import_chatgpt_answer(self, text: str) -> None:
        text = text.strip()
        if text:
            self.memory.append("assistant", text)

    def listen_once(self) -> tuple[str | None, str]:
        wav = self.audio.record_wav(self.settings.mic_seconds)
        method = getattr(self.audio, "transcribe_command", None) or getattr(self.audio, "transcribe")
        transcript = method(wav).strip()
        if not transcript:
            return None, "Nichts verstanden."
        match = WakeMatcher(self.settings.wake_word).match(transcript)
        if match is not None:
            return match.trailing_text.strip(), transcript
        return transcript, transcript

    def create_wake_listener(self, on_command, on_status=None, on_state=None) -> ContinuousWakeListener:
        aliases = set(self.adaptive.get("accepted_wake_aliases", []) or [])
        return ContinuousWakeListener(
            audio=self.audio,
            wake_word=self.settings.wake_word,
            chunk_seconds=self.settings.wake_listener_seconds,
            on_command=on_command,
            on_status=on_status,
            on_state=on_state,
            wait_seconds=self.settings.wake_wait_seconds,
            end_silence_ms=self.settings.command_end_silence_ms,
            max_command_seconds=self.settings.command_max_seconds,
            aliases=aliases or None,
        )


def run_app() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    import customtkinter as ctk
    import tkinter as tk
    import tempfile
    from pathlib import Path
    from tkinter import messagebox

    settings = Settings.from_env()
    ctk.set_appearance_mode("dark")

    root = ctk.CTk(fg_color=THEME["bg"])
    root.title("SCORPION MK47")
    root.geometry("1400x840")
    root.minsize(1120, 700)
    root.grid_columnconfigure(0, weight=0, minsize=185)
    root.grid_columnconfigure(1, weight=1)
    root.grid_columnconfigure(2, weight=0, minsize=300)
    root.grid_rowconfigure(0, weight=1)

    def clipboard_writer(text: str) -> None:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()

    handoff = ChatGPTHandoff(clipboard_writer=clipboard_writer)
    cloud_status_ref: dict[str, object] = {}

    def approval_callback(reason: str) -> bool:
        done = threading.Event()
        approved = {"value": False}

        def show_dialog() -> None:
            label = cloud_status_ref.get("label")
            if label is not None:
                label.configure(text="OPENAI APPROVAL PENDING", text_color=THEME["orange"])
            approved["value"] = messagebox.askyesno(
                "OpenAI API · mögliche Kosten",
                "Scorpion möchte OpenAI für genau diese eine Aufgabe verwenden:\n\n"
                f"{reason}\n\n"
                "Dabei können OpenAI-API-Credits verbraucht werden.\n"
                "Die Freigabe gilt nur einmal.\n\nEinmal erlauben?",
            )
            if label is not None:
                label.configure(text="OPENAI LOCKED 🔒", text_color=THEME["success"])
            done.set()

        root.after(0, show_dialog)
        done.wait()
        return approved["value"]

    def action_approval_callback(reason: str) -> bool:
        done = threading.Event()
        approved = {"value": False}

        def show_dialog() -> None:
            approved["value"] = messagebox.askyesno(
                "Scorpion · Aktion bestätigen",
                reason + "\n\nNur mit Ja wird diese konkrete Freigabe erteilt.",
            )
            done.set()

        root.after(0, show_dialog)
        done.wait()
        return approved["value"]

    controller = ScorpionController(
        settings,
        approval_callback=approval_callback,
        action_approval_callback=action_approval_callback,
        handoff=handoff,
    )
    updater = Updater(settings.github_repo)
    wake_listener: ContinuousWakeListener | None = None
    voice_runtime = {"state": "STANDBY", "deadline": None}

    # Left navigation
    rail = ctk.CTkFrame(root, width=185, corner_radius=0, fg_color="#0C1118")
    rail.grid(row=0, column=0, sticky="nsew")
    rail.grid_propagate(False)
    ctk.CTkLabel(
        rail,
        text="SCORPION",
        font=ctk.CTkFont(size=22, weight="bold"),
        text_color=THEME["text"],
    ).pack(anchor="w", padx=16, pady=(24, 0))
    ctk.CTkLabel(
        rail,
        text="MK47 · ADAPTIVE CORE",
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color=THEME["cyan"],
    ).pack(anchor="w", padx=16, pady=(2, 20))

    ctk.CTkLabel(
        rail,
        text="MODE",
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color=THEME["muted"],
    ).pack(anchor="w", padx=16, pady=(0, 6))
    mode_menu = ctk.CTkSegmentedButton(rail, values=["LOCAL", "HYBRID", "CLOUD"], height=34)
    mode_menu.pack(fill="x", padx=12, pady=(0, 18))
    mode_menu.set(controller.mode.value)

    nav = ctk.CTkFrame(rail, fg_color="transparent")
    nav.pack(fill="both", expand=True, padx=10)

    # Center workspace
    center = ctk.CTkFrame(root, corner_radius=0, fg_color=THEME["bg"])
    center.grid(row=0, column=1, sticky="nsew", padx=14, pady=14)
    center.grid_columnconfigure(0, weight=1)
    center.grid_rowconfigure(1, weight=1)

    core_panel = ctk.CTkFrame(
        center,
        height=168,
        corner_radius=22,
        fg_color=THEME["panel"],
        border_width=1,
        border_color=THEME["border"],
    )
    core_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    core_panel.grid_columnconfigure(1, weight=1)

    core_canvas = tk.Canvas(
        core_panel,
        width=130,
        height=130,
        bg=THEME["panel"],
        highlightthickness=0,
    )
    core_canvas.grid(row=0, column=0, rowspan=2, padx=18, pady=18)
    ring_outer = core_canvas.create_oval(12, 12, 118, 118, outline=THEME["cyan_dim"], width=4)
    ring_inner = core_canvas.create_oval(28, 28, 102, 102, fill="#0C2631", outline=THEME["cyan"], width=2)
    core_canvas.create_text(65, 61, text="S", fill=THEME["text"], font=("Segoe UI", 30, "bold"))
    core_canvas.create_text(65, 86, text="CORE", fill=THEME["cyan"], font=("Segoe UI", 8, "bold"))

    voice_state_label = ctk.CTkLabel(
        core_panel,
        text="STANDBY",
        font=ctk.CTkFont(size=25, weight="bold"),
        text_color=THEME["cyan"],
    )
    voice_state_label.grid(row=0, column=1, sticky="sw", padx=(2, 16), pady=(28, 2))
    voice_hint_label = ctk.CTkLabel(
        core_panel,
        text='Sag „Scorpion“',
        font=ctk.CTkFont(size=13),
        text_color=THEME["muted"],
    )
    voice_hint_label.grid(row=1, column=1, sticky="nw", padx=(2, 16), pady=(0, 26))
    countdown_label = ctk.CTkLabel(
        core_panel,
        text="",
        font=ctk.CTkFont(size=30, weight="bold"),
        text_color=THEME["cyan"],
    )
    countdown_label.grid(row=0, column=2, rowspan=2, padx=24)

    conversation = ctk.CTkTextbox(
        center,
        corner_radius=22,
        fg_color=THEME["panel"],
        border_width=1,
        border_color=THEME["border"],
        text_color=THEME["text"],
        font=ctk.CTkFont(size=14),
        wrap="word",
    )
    conversation.grid(row=1, column=0, sticky="nsew")
    conversation.configure(state="disabled")

    input_bar = ctk.CTkFrame(
        center,
        corner_radius=18,
        fg_color=THEME["panel_alt"],
        border_width=1,
        border_color=THEME["border"],
    )
    input_bar.grid(row=2, column=0, sticky="ew", pady=(12, 0))
    input_bar.grid_columnconfigure(0, weight=1)
    entry = ctk.CTkEntry(
        input_bar,
        placeholder_text="Frag Scorpion …",
        height=42,
        corner_radius=12,
        border_width=0,
        fg_color="#0D141C",
        text_color=THEME["text"],
    )
    entry.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=11)

    # Right system panel
    right = ctk.CTkFrame(root, width=300, corner_radius=0, fg_color="#0C1118")
    right.grid(row=0, column=2, sticky="nsew")
    right.grid_propagate(False)
    ctk.CTkLabel(
        right,
        text="SYSTEM CORE",
        font=ctk.CTkFont(size=15, weight="bold"),
        text_color=THEME["text"],
    ).pack(anchor="w", padx=18, pady=(22, 12))

    status_refs: dict[str, object] = {}

    def status_card(title: str, value: str, key: str, accent: str = THEME["cyan"]):
        card = ctk.CTkFrame(
            right,
            corner_radius=14,
            fg_color=THEME["panel"],
            border_width=1,
            border_color=THEME["border"],
        )
        card.pack(fill="x", padx=14, pady=5)
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=THEME["muted"],
        ).pack(anchor="w", padx=12, pady=(9, 1))
        label = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=accent,
            wraplength=250,
            justify="left",
        )
        label.pack(anchor="w", padx=12, pady=(0, 9))
        status_refs[key] = label
        return label

    status_card("VOICE STATE", "STANDBY", "voice")
    status_card("TEXT MODEL", controller.text_model, "text_model")
    status_card("VISION MODEL", controller.vision_model, "vision_model")
    status_card("OLLAMA", "CHECKING", "ollama")
    status_card("SPEECH", "CHECKING", "speech")
    status_card("HARDWARE", "CHECKING", "hardware")
    status_card("ACTIVE APP", "NO ACTIVE APP", "active_app")
    status_card("SCREEN CONTEXT", "LOCAL CONTEXT OFF", "screen_context", THEME["muted"])
    status_card("INTELLIGENCE", "GENERAL · AUTO\nMEMORY 0 · IDEAS 0", "intelligence")
    cloud_label = status_card("CLOUD GUARD", "OPENAI LOCKED 🔒", "cloud", THEME["success"])
    cloud_status_ref["label"] = cloud_label
    status_card("CORE UPDATE", "CHANNEL OFF" if not settings.github_repo else "UP TO DATE", "update", THEME["muted"])

    mic_card = ctk.CTkFrame(
        right,
        corner_radius=14,
        fg_color=THEME["panel"],
        border_width=1,
        border_color=THEME["border"],
    )
    mic_card.pack(fill="x", padx=14, pady=5)
    ctk.CTkLabel(
        mic_card,
        text="MIC LEVEL",
        font=ctk.CTkFont(size=9, weight="bold"),
        text_color=THEME["muted"],
    ).pack(anchor="w", padx=12, pady=(9, 4))
    mic_bar = ctk.CTkProgressBar(mic_card, height=8, progress_color=THEME["cyan"], fg_color="#162330")
    mic_bar.pack(fill="x", padx=12, pady=(0, 11))
    mic_bar.set(0)

    def append_chat(who: str, text: str) -> None:
        conversation.configure(state="normal")
        conversation.insert("end", f"{who}\n{text}\n\n")
        conversation.see("end")
        conversation.configure(state="disabled")

    append_chat(
        "SCORPION",
        "MK47 Core online. Sag „Scorpion“. Ich antworte mit „Ja, Herr Rodriguez.“ und warte bis zu 20 Sekunden auf deinen Befehl.",
    )

    def run_bg(fn) -> None:
        threading.Thread(target=fn, daemon=True).start()

    def set_voice_visual(state, remaining=None) -> None:
        model = SystemPanelModel.from_voice_state(state, remaining=remaining)
        status_refs["voice"].configure(text=model.voice_label)
        voice_state_label.configure(text=model.voice_label)
        palette = {
            VoiceVisualState.STANDBY: (THEME["cyan_dim"], "#0C2631", THEME["cyan"]),
            VoiceVisualState.ACKNOWLEDGED: (THEME["success"], "#113023", THEME["success"]),
            VoiceVisualState.WAITING: (THEME["cyan"], "#102B38", THEME["cyan"]),
            VoiceVisualState.LISTENING: (THEME["cyan"], "#123A46", THEME["cyan"]),
            VoiceVisualState.THINKING: (THEME["orange"], "#392817", THEME["orange"]),
            VoiceVisualState.SPEAKING: (THEME["success"], "#14351F", THEME["success"]),
            VoiceVisualState.ERROR: (THEME["danger"], "#35151A", THEME["danger"]),
        }
        outer, fill, accent = palette[model.core_state]
        core_canvas.itemconfigure(ring_outer, outline=outer)
        core_canvas.itemconfigure(ring_inner, outline=accent, fill=fill)
        voice_state_label.configure(text_color=accent)
        hint_map = {
            "STANDBY": 'Sag „Scorpion“',
            "ACKNOWLEDGED": "Ich habe dich gehört.",
            "WAITING_COMMAND": "Sag jetzt deinen Befehl oder deine Frage.",
            "LISTENING": "Ich höre zu …",
            "THINKING": "Lokale KI verarbeitet …",
            "SPEAKING": "Antwort läuft …",
            "ERROR": "Voice Core Fehler",
        }
        value = str(getattr(state, "value", state))
        voice_hint_label.configure(text=hint_map.get(value, ""))
        countdown_label.configure(
            text=f"{int(round(remaining))}s" if model.countdown_visible and remaining is not None else ""
        )

    def countdown_tick() -> None:
        if voice_runtime["state"] != "WAITING_COMMAND" or voice_runtime["deadline"] is None:
            return
        remaining = max(0.0, voice_runtime["deadline"] - time.monotonic())
        set_voice_visual("WAITING_COMMAND", remaining)
        if remaining > 0:
            root.after(250, countdown_tick)

    def on_voice_state(state, remaining=None) -> None:
        value = str(getattr(state, "value", state))

        def update() -> None:
            voice_runtime["state"] = value
            if value == "WAITING_COMMAND":
                duration = remaining if remaining is not None else settings.wake_wait_seconds
                voice_runtime["deadline"] = time.monotonic() + duration
                countdown_tick()
            else:
                voice_runtime["deadline"] = None
                set_voice_visual(value, remaining)

        root.after(0, update)

    def refresh_intelligence() -> None:
        status = controller.intelligence_status()
        text = (
            f"{status['context']}\n"
            f"MEMORY {status['memory_hits']} · {status['route_model']} · IDEAS {status['improvements']}"
        )
        status_refs["intelligence"].configure(text=text[:110])

    def refresh_status() -> None:
        def work() -> None:
            try:
                local = controller.local_status()
                ollama = local.detail
            except Exception:
                ollama = "OLLAMA OFFLINE"
            try:
                speech = controller.speech_status()
            except Exception:
                speech = "LOCAL SPEECH SETUP"
            hardware = controller.hardware_summary()
            root.after(0, lambda: status_refs["ollama"].configure(text=ollama[:50]))
            root.after(0, lambda: status_refs["speech"].configure(text=speech[:50]))
            root.after(0, lambda: status_refs["hardware"].configure(text=hardware[:58]))
            root.after(0, refresh_intelligence)

        run_bg(work)

    def on_screen_context(context) -> None:
        active = context.active_app or "NO ACTIVE APP"
        root.after(0, lambda: status_refs["active_app"].configure(text=active[:50]))
        root.after(
            0,
            lambda: status_refs["screen_context"].configure(
                text="LOCAL CONTEXT ACTIVE",
                text_color=THEME["success"],
            ),
        )

    def ask(text: str, image_bytes: bytes | None = None, speak: bool = True) -> None:
        text = text.strip()
        if not text:
            return
        append_chat("DU", text)
        entry.delete(0, "end")
        on_voice_state("THINKING")

        def work() -> None:
            try:
                answer = controller.handle(text, image_bytes=image_bytes)
            except Exception as exc:
                traceback.print_exc()
                answer = f"Fehler: {exc}"
            root.after(0, lambda: append_chat("SCORPION", answer))
            root.after(0, refresh_intelligence)
            if speak and answer and not answer.startswith("Fehler:"):
                on_voice_state("SPEAKING")
                controller.audio.speak(answer)
            on_voice_state("STANDBY")

        run_bg(work)

    def on_send() -> None:
        ask(entry.get())

    def on_mode_change(value: str) -> None:
        controller.set_mode(value)
        status_refs["cloud"].configure(text="OPENAI LOCKED 🔒", text_color=THEME["success"])
        append_chat("SYSTEM", f"Modus {value}. OpenAI bleibt pro Anfrage bestätigungspflichtig.")

    mode_menu.configure(command=on_mode_change)

    def on_mic() -> None:
        def work() -> None:
            try:
                on_voice_state("LISTENING")
                command_text, _heard = controller.listen_once()
                if command_text is None:
                    on_voice_state("STANDBY")
                    return
                root.after(0, lambda: ask(command_text))
            except Exception as exc:
                root.after(0, lambda: append_chat("SYSTEM", f"Lokale Sprache nicht verfügbar: {exc}"))
                on_voice_state("ERROR")

        run_bg(work)

    def on_camera() -> None:
        prompt = entry.get().strip() or "Was siehst du auf diesem Kamerabild?"

        def work() -> None:
            try:
                image = controller.camera.capture_jpeg()
                root.after(0, lambda: ask(prompt, image_bytes=image))
            except Exception as exc:
                root.after(0, lambda: append_chat("SYSTEM", f"Kamerafehler: {exc}"))

        run_bg(work)

    def on_screen() -> None:
        ask(entry.get().strip() or "Was siehst du auf meinem Bildschirm?")

    def on_wake_command(command: str, _transcript: str) -> None:
        if command:
            root.after(0, lambda: ask(command))

    def on_wake_status(text: str) -> None:
        if text == "OFF":
            root.after(0, lambda: status_refs["voice"].configure(text="WAKE OFF"))

    def toggle_wake() -> None:
        nonlocal wake_listener
        if wake_listener and wake_listener.running:
            wake_listener.stop()
            wake_listener = None
            on_voice_state("STANDBY")
            append_chat("SYSTEM", "Wake Listener aus.")
            return
        wake_listener = controller.create_wake_listener(
            on_wake_command,
            on_wake_status,
            on_voice_state,
        )
        wake_listener.start()
        append_chat("SYSTEM", "Wake Listener lokal aktiv. Hintergrundsprache ohne Wakeword wird still verworfen.")

    def on_chatgpt() -> None:
        text = entry.get().strip() or controller.last_user_text
        if not text:
            append_chat("SYSTEM", "Schreib zuerst eine Aufgabe für den ChatGPT-Handoff.")
            return
        image = controller.last_image_bytes if text == controller.last_user_text else None
        result = controller.prepare_chatgpt_handoff(text, image_bytes=image)
        if result.copied:
            append_chat("SYSTEM", "Prompt kopiert und ChatGPT geöffnet. Keine Scorpion-API-Credits.")
        else:
            append_chat("SYSTEM", f"Prompt konnte nicht kopiert werden:\n{result.prompt}")

    def on_paste_chatgpt() -> None:
        try:
            text = root.clipboard_get().strip()
        except Exception as exc:
            append_chat("SYSTEM", f"Zwischenablagefehler: {exc}")
            return
        if text:
            controller.import_chatgpt_answer(text)
            append_chat("CHATGPT · EINGEFÜGT", text)

    def on_cloud_once() -> None:
        text = entry.get().strip() or controller.last_user_text
        if not text:
            append_chat("SYSTEM", "Schreib zuerst die Aufgabe für OpenAI.")
            return
        image = controller.last_image_bytes if text == controller.last_user_text else None

        def work() -> None:
            answer = controller.request_cloud_once(
                f"Aufgabe: {text[:180]}",
                text,
                image_bytes=image,
            )
            root.after(0, lambda: append_chat("SCORPION · CLOUD", answer))
            root.after(
                0,
                lambda: status_refs["cloud"].configure(
                    text="OPENAI LOCKED 🔒",
                    text_color=THEME["success"],
                ),
            )

        run_bg(work)

    def show_improvements() -> None:
        items = controller.improvement_advisor.pending()
        if not items:
            append_chat("SCORPION · IDEEN", "Aktuell keine offenen Verbesserungsvorschläge.")
            return
        lines = [
            f"• {item.title} [{item.area}]\n  {item.detail}"
            for item in items[:8]
        ]
        append_chat(
            "SCORPION · IDEEN",
            "\n\n".join(lines)
            + "\n\nVorschläge werden nie automatisch angewendet.",
        )

    def clear_memory() -> None:
        controller.memory.clear()
        append_chat("SYSTEM", "Lokales Gesprächs-Memory geleert.")

    def install_selected_models() -> None:
        def work() -> None:
            try:
                installed = controller.local_ai.available_models()
            except Exception as exc:
                root.after(0, lambda: append_chat("SYSTEM", f"Ollama ist nicht erreichbar: {exc}"))
                return
            missing = sorted({controller.text_model, controller.vision_model} - installed)
            if not missing:
                root.after(0, lambda: append_chat("SYSTEM", "Die ausgewählten lokalen Modelle sind bereits installiert."))
                return

            done = threading.Event()
            approved = {"value": False}
            def confirm() -> None:
                approved["value"] = messagebox.askyesno(
                    "Lokale Modelle herunterladen",
                    "Scorpion möchte folgende Ollama-Modelle herunterladen:\n\n"
                    + "\n".join(missing)
                    + "\n\nDer Download kann mehrere GB groß sein. Jetzt herunterladen?",
                )
                done.set()
            root.after(0, confirm)
            done.wait()
            if not approved["value"]:
                return
            for model in missing:
                code = controller.model_manager.pull(model, confirmed=True)
                if code != 0:
                    root.after(0, lambda m=model: append_chat("SYSTEM", f"Modelldownload fehlgeschlagen: {m}"))
                    return
            root.after(0, lambda: append_chat("SYSTEM", "Lokale KI-Modelle installiert."))
            root.after(0, refresh_status)
        run_bg(work)

    def check_updates(*, automatic: bool = False) -> None:
        if not settings.github_repo:
            if not automatic:
                append_chat("SYSTEM", "Update-Kanal ist noch deaktiviert. Setze später SCORPION_GITHUB_REPO auf das offizielle GitHub-Repository.")
            return

        def work() -> None:
            try:
                info = updater.check(force=not automatic, current_version=__version__)
                if info is None:
                    if not automatic:
                        root.after(0, lambda: append_chat("SYSTEM", "Kein neuer Update-Check nötig bzw. kein Update gemeldet."))
                    return
                root.after(0, lambda: status_refs["update"].configure(text=f"UPDATE {info.version}", text_color=THEME["orange"]))
                if automatic:
                    return

                done = threading.Event()
                approved = {"value": False}
                def confirm() -> None:
                    approved["value"] = messagebox.askyesno(
                        f"Scorpion Update {info.version}",
                        f"{info.notes[:600]}\n\nDownload, Signaturprüfung, Backup und Installation starten?",
                    )
                    done.set()
                root.after(0, confirm)
                done.wait()
                if not approved["value"]:
                    return

                stage = Path(tempfile.mkdtemp(prefix="scorpion_update_stage_"))
                staged_root, manifest = updater.stage_update(info, confirmed=True, destination=stage)
                install_root = Path(__file__).resolve().parents[2]
                apply_update(install_root, staged_root, manifest)
                root.after(0, lambda: status_refs["update"].configure(text=f"INSTALLED {info.version}", text_color=THEME["success"]))
                root.after(0, lambda: messagebox.showinfo("Scorpion Update", "Update installiert und Self-Check bestanden. Bitte Scorpion neu starten."))
            except (UpdateVerificationError, Exception) as exc:
                root.after(0, lambda: append_chat("SYSTEM", f"Update abgebrochen: {exc}"))
                root.after(0, lambda: status_refs["update"].configure(text="UPDATE BLOCKED", text_color=THEME["danger"]))
        run_bg(work)

    def add_nav(text: str, command, *, accent: bool = False) -> None:
        ctk.CTkButton(
            nav,
            text=text,
            height=38,
            corner_radius=10,
            anchor="w",
            command=command,
            fg_color=THEME["cyan_dim"] if accent else "transparent",
            hover_color="#172634",
            border_width=0 if accent else 1,
            border_color=THEME["border"],
            text_color=THEME["text"],
        ).pack(fill="x", pady=4)

    add_nav("◉  WAKE ON / OFF", toggle_wake, accent=True)
    add_nav("🎙  LOCAL VOICE", on_mic)
    add_nav("▣  SCREEN VISION", on_screen)
    add_nav("◌  CAMERA", on_camera)
    add_nav("↗  ASK CHATGPT", on_chatgpt)
    add_nav("↙  PASTE ANSWER", on_paste_chatgpt)
    add_nav("⚡  OPENAI ONCE", on_cloud_once)
    add_nav("⬇  AI MODELS", install_selected_models)
    add_nav("↻  CHECK UPDATES", lambda: check_updates(automatic=False))
    add_nav("💡  IMPROVEMENTS", show_improvements)
    add_nav("⌫  CLEAR MEMORY", clear_memory)

    ctk.CTkButton(
        input_bar,
        text="SEND",
        width=78,
        height=42,
        corner_radius=12,
        command=on_send,
        fg_color=THEME["cyan_dim"],
        hover_color="#15506A",
    ).grid(row=0, column=1, padx=4, pady=11)
    ctk.CTkButton(
        input_bar,
        text="🎙",
        width=48,
        height=42,
        corner_radius=12,
        command=on_mic,
        fg_color="#17212C",
        hover_color="#26384A",
    ).grid(row=0, column=2, padx=(4, 12), pady=11)

    def shutdown() -> None:
        if wake_listener:
            wake_listener.stop()
        controller.screen_context.stop()
        root.destroy()

    entry.bind("<Return>", lambda _event: on_send())
    root.protocol("WM_DELETE_WINDOW", shutdown)
    entry.focus_set()
    refresh_status()
    set_voice_visual("STANDBY")
    if settings.screen_context_enabled:
        controller.screen_context.start(on_screen_context)
    if settings.wake_listener_enabled:
        root.after(700, toggle_wake)
    if settings.github_repo:
        root.after(3500, lambda: check_updates(automatic=True))
    root.mainloop()
