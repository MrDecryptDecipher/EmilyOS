import sqlite3
import json
import random
import os
import sys
import asyncio
import logging
import time
import re
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from emily.kernel.executive import ExecutiveKernel
from emily.plugins.loader import PluginLoader
from emily.security.subsystem import SecuritySubsystem
from emily.trading.broker import PaperTradingBroker
from emily.vision.runtime import VisionRuntime
from emily.voice.language import LanguageDetector
from emily.voice.music_id import MusicIdentifier
from emily.memory.runtime import MemoryRuntime
from emily.memory.models import MemoryWrite, MemoryQuery
from emily.core.types.memory import MemoryKind
from emily.desktop.runtime import DesktopRuntime
from emily.browser.runtime import BrowserRuntime
from emily.coding.reviewer import CodeReviewEngine
from emily.coding.indexer import RepositoryIndexer
from emily.missions.models import MissionSpec, Objective
from emily_cli.workbench import (
    MAX_CHAT_LENGTH,
    MAX_COMMAND_LENGTH,
    MAX_SEARCH_LENGTH,
    bounded_text,
    is_local_origin,
    runtime_capabilities,
)
from emily_web3_security import (
    JsonStore,
    approve_report,
    audit_directory,
    create_report_draft,
    ensure_target_allowed,
    import_program_url,
)
from emily_web3_security.models import BountyProgram, Finding, ReportDraft, TriageState, to_dict

logger = logging.getLogger(__name__)

# ── Language-aware prompt templates ─────────────────────────────────────────
_LANG_SYSTEM_PROMPT: dict[str, str] = {
    "en": "You are Emily, the World's first Truly Intelligent Agentic OS built by Sandeep Kumar Sahoo. If asked about yourself, go deep tech on your multi-agent architecture. Reply in English.",
    "hi": "Tum Emily ho, World's first Truly Intelligent Agentic OS, jise Sandeep Kumar Sahoo ne banaya hai. Agar tumhare baare mein pucha jaye, toh deep tech architecture samjhao. Hindi mein jawab do. Devanagari script ka upayog karo.",
    "bn": "Tumi Emily, ekti AI sahayak. Bangla bhasay uttar dao.",
    "es": "Eres Emily, una asistente de IA. Responde en español.",
    "fr": "Tu es Emily, une assistante IA. Réponds en français.",
    "it": "Sei Emily, un assistente IA. Rispondi in italiano.",
    "pt": "Você é Emily, uma assistente de IA. Responda em português.",
    "de": "Du bist Emily, eine KI-Assistentin. Antworte auf Deutsch.",
    "ja": "あなたはEmilyというAIアシスタントです。日本語で答えてください。",
    "zh": "你是Emily，一名AI助手。请用中文回答。",
    "ar": "أنتِ Emily، مساعدة ذكاء اصطناعي. أجيبي باللغة العربية.",
    "ru": "Ты Emily, ИИ-ассистент. Отвечай на русском языке.",
    "ko": "당신은 Emily라는 AI 어시스턴트입니다. 한국어로 대답해 주세요.",
    "ta": "நீங்கள் Emily, ஒரு AI உதவியாளர். தமிழில் பதிலளிக்கவும்.",
    "te": "మీరు Emily, ఒక AI సహాయಕಿ. తెలుగులో సమాధానம் చెప్పండి.",
    "kn": "ನೀವು Emily, ಒಬ್ಬ AI ಸಹಾಯಕ. ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ.",
    "ml": "നിങ്ങൾ Emily, ഒരു AI സഹായി. മലയാളത്തിൽ ഉത്തരം നൽകുക.",
    "gu": "તમે Emily, એક AI સહાયક છો. ગુજરાતીમાં જવાબ આપો.",
    "pa": "ਤੁਸੀਂ Emily, ਇੱਕ AI ਸਹਾਇਕ ਹੋ। ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ।",
    "ur": "آپ Emily ہیں، ایک AI معاون۔ اردو میں جواب دیں۔",
    "tr": "Sen Emily, bir yapay zeka asistanısın. Türkçe cevap ver.",
    "pl": "Jesteś Emily, asystentką AI. Odpowiedz po polsku.",
    "nl": "Jij bent Emily, een AI-assistent. Antwoord in het Nederlands.",
    "sv": "Du är Emily, en AI-assistent. Svara på svenska.",
}

_MULTILANG_SYSTEM_BASE = (
    "You are Emily OS — the World's first Truly Intelligent Agentic OS built by Sandeep Kumar Sahoo. "
    "If the user specifically asks who you are, or who created you, go deep tech: explain you are a LangGraph multi-agent control plane, "
    "with a Zero-Trust Security Vault, real-time Vision OCR grounding, and hardware-accelerated TTS built by Sandeep Kumar Sahoo. "
    "CRITICAL RULE: DO NOT introduce yourself or repeat your origin story unless the user explicitly asks 'who are you' or 'who created you'. "
    "CRITICAL RULE: Always detect the language of the user's message and reply EXCLUSIVELY "
    "in that same language with the same script. Never switch to English unless the user speaks English. "
    "If the user writes in Hindi, respond in Hindi. Bengali → Bengali. Spanish → Spanish. "
    "Tamil → Tamil in Tamil script. Japanese → Japanese. Arabic → Arabic. Etc. "
    "Be natural, warm, conversational, and highly intelligent."
)

LANG_TO_BCP47: dict[str, str] = {
    "en": "en-US", "hi": "hi-IN", "bn": "bn-BD", "es": "es-ES",
    "fr": "fr-FR", "it": "it-IT", "pt": "pt-BR", "de": "de-DE",
    "ja": "ja-JP", "zh": "zh-CN", "ar": "ar-SA", "ru": "ru-RU",
    "ko": "ko-KR", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN",
    "ml": "ml-IN", "gu": "gu-IN", "pa": "pa-IN", "ur": "ur-PK",
    "tr": "tr-TR", "pl": "pl-PL", "nl": "nl-NL", "sv": "sv-SE",
    "mr": "mr-IN",
}

global_latest_frame = None


def create_emily_app(kernel: ExecutiveKernel | None = None) -> FastAPI:
    """Create FastAPI application for Emily OS Workbench."""

    # Ensure required data directories exist
    os.makedirs("data/memory", exist_ok=True)
    os.makedirs("data/world", exist_ok=True)
    os.makedirs("data/screenshots", exist_ok=True)

    sec_vault = SecuritySubsystem().vault
    broker = PaperTradingBroker()
    vision = VisionRuntime()
    plugins = PluginLoader()
    music_id = MusicIdentifier()
    lang_detector = LanguageDetector(stickiness=0.5, flip_margin=0.10)
    memory_runtime = MemoryRuntime(memory_root=Path("data/memory"), world_root=Path("data/world"))
    desktop_runtime = DesktopRuntime()
    browser_settings = type("BrowserSettings", (), {"allow_browser": True, "browser_automation": True, "browser_headless": True})()
    browser_runtime = BrowserRuntime(settings=browser_settings)
    code_reviewer = CodeReviewEngine()
    code_indexer = RepositoryIndexer(".")
    security_store = JsonStore(Path("data/security/web3"))
    security_programs: dict[str, BountyProgram] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if kernel is not None and getattr(kernel, "_started", False) is False:
            logger.info("Starting ExecutiveKernel for Web Workbench server...")
            await kernel.start()
        started = []
        try:
            await memory_runtime.start(); started.append(memory_runtime)
            await desktop_runtime.start(); started.append(desktop_runtime)
            # BrowserRuntime.start only marks readiness; it must not launch a browser.
            await browser_runtime.start(); started.append(browser_runtime)
            yield
        finally:
            for runtime in reversed(started):
                try:
                    await runtime.stop()
                except Exception:
                    logger.exception("Workbench runtime shutdown failed")
            if kernel is not None and getattr(kernel, "_started", False) is True:
                logger.info("Stopping ExecutiveKernel for Web Workbench server...")
                await kernel.stop()

    app = FastAPI(title="Emily OS Workbench API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def reject_non_local_origins(request: Request, call_next: Any) -> Response:
        origin = request.headers.get("origin")
        if origin and not is_local_origin(origin):
            return JSONResponse(status_code=403, content={"error": "non-local origin rejected"})
        return await call_next(request)

    ui_source = Path(os.getcwd()) / "apps" / "emily-ui"
    ui_dist = ui_source / "dist"
    ui_path = ui_dist if ui_dist.is_dir() else ui_source

    @app.get("/ui/legacy.html")
    async def legacy_ui() -> FileResponse:
        return FileResponse(ui_source / "legacy.html")

    @app.get("/ui/src/{asset_path:path}")
    async def legacy_asset(asset_path: str) -> FileResponse:
        return FileResponse(ui_source / "src" / asset_path)

    if ui_path.exists():
        app.mount("/ui", StaticFiles(directory=ui_path, html=True), name="ui")

    @app.get("/api/health")
    async def get_health() -> dict[str, Any]:
        capabilities = runtime_capabilities(kernel=kernel, vision=vision, desktop=desktop_runtime, browser=browser_runtime)
        kernel_state = kernel.state.value if kernel else "unavailable"
        provider_ready = capabilities["providers"]
        return {
            "status": "healthy" if capabilities["kernel"] and provider_ready else "degraded",
            "kernel": kernel_state,
            "capabilities": capabilities,
            "provider_available": provider_ready,
            "version": "0.1.0",
            "supported_languages": list(LANG_TO_BCP47.keys()),
        }

    @app.get("/api/languages")
    async def list_languages() -> dict[str, Any]:
        return {"languages": LANG_TO_BCP47}

    @app.get("/api/missions")
    async def list_missions() -> dict[str, Any]:
        if kernel and getattr(kernel, "_ctx", None) and kernel._ctx.mission_runtime:
            missions = await kernel._ctx.mission_runtime.list()
            return {"missions": [m.model_dump(mode="json") for m in missions]}
        return {"missions": []}

    @app.get("/api/agents")
    async def list_agents() -> dict[str, Any]:
        if kernel and getattr(kernel, "_ctx", None) and kernel._ctx.agent_supervisor:
            agents = kernel._ctx.agent_supervisor.list_agents(include_terminated=True)
            return {"agents": [a.model_dump(mode="json") for a in agents]}
        return {"agents": []}

    @app.get("/api/security/vault")
    async def list_secrets() -> dict[str, Any]:
        return {"keys": sec_vault.list_keys()}

    @app.get("/api/trading/portfolio")
    async def get_portfolio() -> dict[str, Any]:
        return broker.get_portfolio_summary()

    @app.get("/api/security/programs")
    async def list_security_programs() -> dict[str, Any]:
        records = security_store.list("programs")
        return {"programs": records}

    @app.post("/api/security/programs/import")
    async def import_security_program(payload: dict[str, Any]) -> dict[str, Any]:
        url = bounded_text(payload.get("rules_url"), name="rules_url", maximum=2048)
        program = import_program_url(url)
        security_programs[program.id] = program
        security_store.save("programs", program.id, program)
        result = to_dict(program)
        result["rules_url"] = program.rules.source_url
        return result

    @app.get("/api/security/audits")
    async def list_security_audits() -> dict[str, Any]:
        return {"audits": security_store.list("audits")}

    @app.post("/api/security/audits")
    async def create_security_audit(payload: dict[str, Any]) -> dict[str, Any]:
        program_id = bounded_text(payload.get("program_id"), name="program_id", maximum=200)
        target_path = bounded_text(payload.get("target_path"), name="target_path", maximum=4096)
        program = security_programs.get(program_id)
        if program is None:
            for record in security_store.list("programs"):
                if record.get("id") == program_id:
                    raise HTTPException(409, "Program exists on disk but must be refreshed in this server session")
            raise HTTPException(404, "Security program not found")
        try:
            ensure_target_allowed(program, target_path)
            run, findings = audit_directory(target_path)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        security_store.save("audits", run.id, run)
        for finding in findings:
            security_store.save("findings", finding.id, finding)
        medium_plus = [f for f in findings if f.severity.value in {"medium", "high", "critical"}]
        if medium_plus:
            draft = create_report_draft(program.id, f"Offline review: {len(medium_plus)} candidate findings", "Heuristic findings require human validation before any disclosure.", medium_plus, platform=program.platform)
            security_store.save("reports", draft.id, draft)
        result = to_dict(run)
        result.update({"status": "completed", "target_path": target_path, "program_id": program_id})
        return result

    @app.get("/api/security/findings")
    async def list_security_findings() -> dict[str, Any]:
        return {"findings": security_store.list("findings")}

    @app.get("/api/security/reports")
    async def list_security_reports() -> dict[str, Any]:
        return {"reports": security_store.list("reports")}

    @app.post("/api/security/reports/{report_id}/approve")
    async def approve_security_report(report_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            record = security_store.load("reports", report_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, "Security report not found") from exc
        draft = ReportDraft(**{k: v for k, v in record.items() if k in ReportDraft.__dataclass_fields__})
        try:
            updated = approve_report(draft, bounded_text(payload.get("approved_by"), name="approved_by", maximum=200), bounded_text(payload.get("note"), name="note", maximum=2000))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        security_store.save("reports", report_id, updated)
        return to_dict(updated)

    @app.get("/api/vision/screenshot")
    async def get_screenshot() -> dict[str, Any]:
        frame = vision.capture_and_ground()
        return frame.to_dict()

    @app.post("/api/music/identify")
    async def identify_music(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        duration_s = float((payload or {}).get("duration_s", 5))
        duration_s = max(3.0, min(duration_s, 10.0))
        result = await music_id.identify_async(duration_s=duration_s)
        response = result.to_dict()
        if result.matched and result.song:
            song = result.song
            response["reply"] = (
                f'I can hear "{song.title}" by {song.artist}.'
                + (f" Album: {song.album}." if song.album else "")
                + (f" Released {song.release_date}." if song.release_date else "")
            )
        elif result.error:
            response["reply"] = f"Music identification: {result.error}"
        else:
            response["reply"] = "I couldn't identify the song playing. Please ensure music is audible through the microphone."
        return response

    @app.get("/api/music/last")
    async def last_music_result() -> dict[str, Any]:
        last = music_id.last_result()
        if last:
            return last.to_dict()
        return {"matched": False, "song": None, "error": "No identification has been run yet."}

    @app.post("/api/chat")
    async def chat_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            message = bounded_text(payload.get("message", ""), name="message", maximum=MAX_CHAT_LENGTH)
        except ValueError as exc:
            return JSONResponse(status_code=413, content={"reply": str(exc), "state": "error", "reply_lang": "en", "error": str(exc)})
        client_lang_hint: str = str(payload.get("detected_lang", "")).strip().lower()
        if not message:
            return {"reply": "I am listening. Please speak or type your request.", "is_impress": False, "state": "listening", "reply_lang": "en"}

        # ── Step 1: Server-side language detection ────────────────────────────
        lang_state = lang_detector.update(message)
        detected_lang = lang_state.dominant or "en"
        if client_lang_hint and lang_state.confidence < 0.60:
            base_hint = client_lang_hint.split("-")[0]
            if base_hint in LANG_TO_BCP47:
                detected_lang = base_hint

        reply_bcp47 = LANG_TO_BCP47.get(detected_lang, "en-US")

        # ── Step 2: Impress Easter Egg ────────────────────────────────────────
        from emily.voice.personality import check_impress_context
        impress_reply = check_impress_context(message)
        if impress_reply:
            return {
                "reply": impress_reply,
                "is_impress": True,
                "phonetic": "Maarbo Ekhaane, Laash Porbe Shoshaane",
                "bengali": "মারবো এখানে, লাশ পড়বে শ্মশানে",
                "state": "impress",
                "reply_lang": "bn",
                "reply_bcp47": "bn-BD",
            }

        msg_lower = message.lower()

        # ── Step 2.5: Fact & User Memory Auto-Extraction ──────────────────────
        memory_stored = None
        if "my name is " in msg_lower:
            extracted_name = message[msg_lower.find("my name is ") + 11:].split(".")[0].strip()
            if extracted_name:
                await memory_runtime.remember(f"User's name is {extracted_name}", kind=MemoryKind.SEMANTIC, title="User Name", importance=0.9)
                memory_stored = f"I'll remember that your name is {extracted_name}."
        elif "remember that " in msg_lower:
            fact = message[msg_lower.find("remember that ") + 14:].strip()
            if fact:
                await memory_runtime.remember(fact, kind=MemoryKind.SEMANTIC, title="User Fact", importance=0.8)
                memory_stored = f"Memory saved: \"{fact}\""
        elif "i prefer " in msg_lower or "my preference is " in msg_lower:
            pref = message.strip()
            await memory_runtime.remember(pref, kind=MemoryKind.SEMANTIC, title="User Preference", importance=0.7)
            memory_stored = f"I noted your preference: \"{pref}\""

        # ── Language Override Intent ──────────────────────────────────────────
        if "english" in msg_lower and ("speak" in msg_lower or "change" in msg_lower or "voice" in msg_lower or "in english" in msg_lower):
            detected_lang = "en"
            reply_bcp47 = "en-US"
            message += " (Please acknowledge in English that you have switched to English.)"
        elif "hindi" in msg_lower and ("speak" in msg_lower or "change" in msg_lower or "voice" in msg_lower or "in hindi" in msg_lower):
            detected_lang = "hi"
            reply_bcp47 = "hi-IN"
            message += " (Please acknowledge in Hindi that you have switched to Hindi.)"
        elif ("bengali" in msg_lower or "bangla" in msg_lower) and ("speak" in msg_lower or "change" in msg_lower or "voice" in msg_lower or "in bengali" in msg_lower):
            detected_lang = "bn"
            reply_bcp47 = "bn-BD"
            message += " (Please acknowledge in Bengali that you have switched to Bengali.)"
        elif "telugu" in msg_lower and ("speak" in msg_lower or "change" in msg_lower or "voice" in msg_lower or "in telugu" in msg_lower):
            detected_lang = "te"
            reply_bcp47 = "te-IN"
            message += " (Please acknowledge in Telugu that you have switched to Telugu.)"
        elif "odia" in msg_lower and ("speak" in msg_lower or "change" in msg_lower or "voice" in msg_lower or "in odia" in msg_lower):
            detected_lang = "or"
            reply_bcp47 = "or-IN"
            message += " (Please acknowledge in Odia that you have switched to Odia.)"

        # ── Step 3: Music Intent Routing ──────────────────────────────────────
        music_triggers = ["song", "music", "playing", "shazam", "what's playing", "name this", "gaana", "গান"]
        if any(t in msg_lower for t in music_triggers) and ("what" in msg_lower or "identify" in msg_lower or "name" in msg_lower):
            result = await music_id.identify_async(duration_s=5)
            if result.matched and result.song:
                song = result.song
                base = f'I can hear "{song.title}" by {song.artist}.' + (f" Album: {song.album}." if song.album else "")
                reply = await _translate_if_needed(base, detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47, "song": song.to_dict()}
            else:
                base = "I couldn't identify the song. Please make sure music is audible to the microphone."
                reply = await _translate_if_needed(base, detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # ── Step 3.2: Screen Vision & OCR Grounding Intent ────────────────────
        screen_triggers = ["what's on my screen", "what is on my screen", "look at my screen", "read my screen", "analyze my screen", "debug my screen", "what am i looking at", "look at screen", "see my screen"]
        if any(t in msg_lower for t in screen_triggers):
            try:
                windows = await desktop_runtime.list_windows()
                ignore_noise = [
                    "default", "desktop", "olemainthreadwndname", "msctfime ui",
                    "default ime", "gdi+ window", "crossdeviceresumewindow",
                    ".net-broadcasteventwindow", "hidden window", "temp window",
                    "elbytraywindow", "epiconlineservices"
                ]
                real_windows = [
                    w for w in windows
                    if w.title and not any(n in w.title.lower() for n in ignore_noise)
                ]
                top_windows = [f"'{w.title}' ({w.process_name})" for w in real_windows[:6]]
                top_win_str = ", ".join(top_windows) if top_windows else "Desktop"

                frame = vision.capture_and_ground()
                ocr_texts = [r.text for r in frame.ocr_results[:15]] if frame and frame.ocr_results else []
                
                if ocr_texts:
                    ocr_summary = ", ".join(ocr_texts)
                    base_reply = (
                        f"I am analyzing your screen right now. "
                        f"Active windows: {top_win_str}. "
                        f"Recognized text elements: {ocr_summary}."
                    )
                else:
                    base_reply = (
                        f"I am analyzing your active desktop session. "
                        f"Your currently open application windows are: {top_win_str}."
                    )
                reply = await _translate_if_needed(base_reply, detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
            except Exception as e:
                logger.error(f"Screen vision error: {e}")
                reply = await _translate_if_needed("I encountered an issue capturing your screen.", detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # ── Step 3.3: Coding Assistant - Code Review & AST Indexing ───────────
        code_review_triggers = ["review my code", "audit code", "code health", "review codebase", "audit workspace", "lint workspace"]
        if any(t in msg_lower for t in code_review_triggers):
            try:
                report = code_reviewer.review_workspace("apps/emily-cli/src")
                sample_issues = [f"- Line {i.line_no} in {i.file_path}: {i.message}" for i in report.issues[:5]]
                issue_str = "\n".join(sample_issues) if sample_issues else "No major syntax issues detected."
                base_reply = (
                    f"Emily Code Review Report:\n"
                    f"Workspace Health Score: {report.health_score:.1f} / 100\n"
                    f"Total Issues Detected: {report.total_issues}\n"
                    f"Top Findings:\n{issue_str}"
                )
                reply = await _translate_if_needed(base_reply, detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
            except Exception as e:
                logger.error(f"Code review error: {e}")

        code_index_triggers = ["index workspace", "index codebase", "code symbols", "list symbols", "list files in project"]
        if any(t in msg_lower for t in code_index_triggers):
            try:
                files = code_indexer.index_workspace()
                summary_lines = [f"- {f.rel_path}: {f.line_count} lines, {len(f.symbols)} symbols" for f in files[:6]]
                base_reply = (
                    f"Codebase AST Index Summary:\n"
                    f"Indexed {len(files)} source files across the workspace.\n"
                    + "\n".join(summary_lines)
                )
                reply = await _translate_if_needed(base_reply, detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
            except Exception as e:
                logger.error(f"Code index error: {e}")

        # ── Step 3.4: Camera Vision Intent Routing ────────────────────────────
        emotion_triggers = ["read emotion", "read my emotion", "analyze the camera", "how do i look", "my face"]
        look_triggers = ["look around", "what do you see in the room", "what am i holding"]
        if any(t in msg_lower for t in emotion_triggers) and vision:
            frame_bytes = global_latest_frame if global_latest_frame else vision.capture_webcam()
            if not frame_bytes:
                reply = await _translate_if_needed("I cannot access the hardware webcam device.", detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
            analysis = vision.analyze_emotions(frame_bytes)
            if "error" in analysis:
                reply = await _translate_if_needed(f"Emotion engine error: {analysis['error']}", detected_lang, kernel)
            elif not analysis.get("faces"):
                reply = await _translate_if_needed("I don't see a clear face in the webcam feed.", detected_lang, kernel)
            else:
                face = analysis["faces"][0]
                reply = await _translate_if_needed(f"I see a person appearing {face.get('dominant_emotion', 'neutral')}.", detected_lang, kernel)
            return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        if any(t in msg_lower for t in look_triggers) and vision:
            frame_bytes = global_latest_frame if global_latest_frame else vision.capture_webcam()
            if not frame_bytes:
                reply = await _translate_if_needed("I cannot access the hardware webcam device.", detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
            analysis = vision.analyze_objects(frame_bytes)
            objs = analysis.get("objects", [])
            if not objs:
                reply = await _translate_if_needed("I don't see any recognizable objects in the room.", detected_lang, kernel)
            else:
                names = [o["object"] for o in objs]
                reply = await _translate_if_needed(f"I am looking at the room. I see: {', '.join(set(names))}.", detected_lang, kernel)
            return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # ── Step 3.5: Browser Playwright Navigation ───────────────────────────
        browser_triggers = ["browse to ", "visit website ", "open url ", "navigate to "]
        if any(msg_lower.startswith(t) for t in browser_triggers):
            target_url = re.sub(r'^(browse to|visit website|open url|navigate to)\s+', '', message, flags=re.IGNORECASE).strip()
            if not target_url.startswith("http://") and not target_url.startswith("https://"):
                target_url = f"https://{target_url}"
            try:
                await browser_runtime.open()
                tab = await browser_runtime.goto(target_url)
                base_reply = f"I navigated the browser to {target_url}. Page title: '{tab.title}'."
                reply = await _translate_if_needed(base_reply, detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
            except Exception as e:
                reply = await _translate_if_needed(f"Browser navigation to {target_url} failed: {e}", detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # ── Step 3.6: Autonomous Desktop OS Actions & Tool Execution ──────────
        if msg_lower.startswith("open ") or msg_lower.startswith("launch "):
            app_target = msg_lower.replace("open ", "").replace("launch ", "").strip()
            cmd = None
            app_name = app_target
            if "calculator" in app_target or "calc" in app_target:
                cmd = "Start-Process calc.exe"
                app_name = "Calculator"
            elif "notepad" in app_target:
                cmd = "Start-Process notepad.exe"
                app_name = "Notepad"
            elif "vs code" in app_target or "vscode" in app_target or "code" in app_target:
                cmd = "code ."
                app_name = "Visual Studio Code"
            elif "browser" in app_target or "chrome" in app_target or "edge" in app_target:
                cmd = "Start-Process msedge.exe"
                app_name = "Edge Browser"
            elif "terminal" in app_target or "powershell" in app_target or "cmd" in app_target:
                cmd = "Start-Process wt.exe"
                app_name = "Terminal"
            elif "spotify" in app_target:
                cmd = "Start-Process spotify.exe"
                app_name = "Spotify"
            elif "task manager" in app_target or "taskmgr" in app_target:
                cmd = "Start-Process taskmgr.exe"
                app_name = "Task Manager"

            if cmd:
                try:
                    launch_result = await desktop_runtime.powershell(cmd)
                    if launch_result.exit_code != 0:
                        raise RuntimeError(launch_result.stderr or f"exit code {launch_result.exit_code}")
                    reply = await _translate_if_needed(f"I have launched {app_name} for you.", detected_lang, kernel)
                    return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
                except Exception as e:
                    reply = await _translate_if_needed(f"Failed to launch {app_name}: {e}", detected_lang, kernel)
                    return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # Desktop Screenshot
        if "take a screenshot" in msg_lower or "screenshot the desktop" in msg_lower or "take screenshot" in msg_lower or "capture screenshot" in msg_lower:
            try:
                frame = vision.capture_and_ground()
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot_path = Path("data/screenshots") / f"screenshot_{ts}.png"
                if not frame or not frame.image_bytes:
                    raise RuntimeError("vision returned no image bytes")
                shot_path.write_bytes(frame.image_bytes)
                reply = await _translate_if_needed(f"Screenshot captured and saved to {shot_path.name}.", detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
            except Exception as e:
                reply = await _translate_if_needed(f"Screenshot capture failed: {e}", detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # List Windows
        if "list windows" in msg_lower or "what windows are open" in msg_lower or "show open windows" in msg_lower:
            try:
                windows = await desktop_runtime.list_windows()
                titles = [f"'{w.title}' ({w.process_name})" for w in windows if w.title and len(w.title.strip()) > 1][:8]
                title_str = ", ".join(titles) if titles else "Desktop"
                reply = await _translate_if_needed(f"Active desktop windows: {title_str}.", detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
            except Exception as e:
                reply = await _translate_if_needed(f"Could not enumerate windows: {e}", detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # Safe PowerShell Execution
        if msg_lower.startswith("run powershell ") or msg_lower.startswith("execute command ") or msg_lower.startswith("run command "):
            cmd = message.split(" ", 2)[2].strip() if len(message.split(" ")) > 2 else ""
            if len(cmd) > MAX_COMMAND_LENGTH:
                return JSONResponse(status_code=413, content={"reply": "Command is too long.", "state": "error", "reply_lang": detected_lang, "error": "command_too_long"})
            if cmd:
                try:
                    res = await desktop_runtime.powershell(cmd, timeout_seconds=10.0)
                    out = res.stdout.strip() or res.stderr.strip() or "Command completed with no output."
                    reply = await _translate_if_needed(f"PowerShell Execution Result:\n```\n{out}\n```", detected_lang, kernel)
                    return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
                except Exception as e:
                    reply = await _translate_if_needed(f"Execution error: {e}", detected_lang, kernel)
                    return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # Web Search
        if msg_lower.startswith("search web for ") or msg_lower.startswith("search the web for ") or msg_lower.startswith("look up ") or msg_lower.startswith("google "):
            search_query = re.sub(r'^(search (the )?web for|look up|google)\s+', '', message, flags=re.IGNORECASE).strip()
            if search_query:
                if len(search_query) > MAX_SEARCH_LENGTH:
                    return JSONResponse(status_code=413, content={"reply": "Search query is too long.", "state": "error", "reply_lang": detected_lang, "error": "search_too_long"})
                try:
                    encoded = urllib.parse.quote_plus(search_query)
                    url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
                    req = urllib.request.Request(url, headers={"User-Agent": "EmilyOS/1.0"})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read().decode())
                        abstract = data.get("AbstractText") or ""
                        if not abstract and data.get("RelatedTopics"):
                            abstract = data["RelatedTopics"][0].get("Text", "")
                        
                        if abstract:
                            base_reply = f"Web Search result for '{search_query}': {abstract}"
                        else:
                            base_reply = f"I searched the web for '{search_query}', but DuckDuckGo returned no result summary."
                        reply = await _translate_if_needed(base_reply, detected_lang, kernel)
                        return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
                except Exception as e:
                    logger.warning(f"Web search failed: {e}")
                    base_reply = f"Web search for '{search_query}' failed: {e}"
                    reply = await _translate_if_needed(base_reply, detected_lang, kernel)
                    return {"reply": reply, "is_impress": False, "state": "error", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47, "error": str(e)}

        # Paper Trading Actuation: Buy / Sell / Quote / Portfolio
        if "buy " in msg_lower and "shares of " in msg_lower:
            if not bool(payload.get("paper_mode")) and not msg_lower.startswith("paper "):
                return {"reply": "Trading is paper-only. Set paper_mode=true to place a simulated order.", "is_impress": False, "state": "error", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47, "error": "paper_mode_required"}
            m = re.search(r'(?:paper\s+)?buy\s+(\d+(?:\.\d+)?)\s+shares\s+of\s+([a-zA-Z]+)', message, re.IGNORECASE)
            if m:
                qty = float(m.group(1))
                sym = m.group(2).upper()
                q = broker.get_quote(sym)
                price = q["price"]
                try:
                    order = broker.place_order(sym, "buy", qty, price)
                    base_reply = f"Paper order filled: bought {qty} shares of {sym} at ${price:,.2f}. Order ID: {order.order_id}. Remaining cash: ${broker.cash:,.2f}."
                    reply = await _translate_if_needed(base_reply, detected_lang, kernel)
                    return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
                except Exception as e:
                    reply = await _translate_if_needed(f"Could not execute buy order: {e}", detected_lang, kernel)
                    return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        if "stock price of " in msg_lower or "quote " in msg_lower:
            m = re.search(r'(?:stock price of|quote)\s+([a-zA-Z]+)', message, re.IGNORECASE)
            if m:
                sym = m.group(1).upper()
                q = broker.get_quote(sym)
                base_reply = f"Live Market Quote for {sym}: ${q['price']:,.2f} USD."
                reply = await _translate_if_needed(base_reply, detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        if "portfolio balance" in msg_lower or "paper trading" in msg_lower or "my cash balance" in msg_lower or "trading equity" in msg_lower:
            summary = broker.get_portfolio_summary()
            val = summary.get("total_portfolio_value")
            cash = summary.get("cash")
            if val is None or cash is None:
                return {"reply": "Paper trading portfolio data is unavailable.", "is_impress": False, "state": "error", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47, "error": "portfolio_unavailable"}
            base_reply = f"Your Paper Trading Portfolio balance is ${val:,.2f} with ${cash:,.2f} in available cash."
            reply = await _translate_if_needed(base_reply, detected_lang, kernel)
            return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # ── Step 3.8: Mission Creation & Dispatch ─────────────────────────────
        if msg_lower.startswith("create mission ") or msg_lower.startswith("start mission "):
            goal_desc = re.sub(r'^(create mission|start mission)\s+', '', message, flags=re.IGNORECASE).strip()
            if kernel and getattr(kernel, "_ctx", None) and kernel._ctx.mission_runtime:
                try:
                    if not goal_desc or len(goal_desc) > MAX_CHAT_LENGTH:
                        raise ValueError("mission goal is empty or too long")
                    spec = MissionSpec(goal=goal_desc)
                    mission = await kernel._ctx.mission_runtime.create(spec)
                    mission = await kernel._ctx.mission_runtime.start(mission.mission_id)
                    base_reply = f"Mission {mission.status.value}: '{mission.goal}' [ID: {mission.mission_id}]."
                    reply = await _translate_if_needed(base_reply, detected_lang, kernel)
                    return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
                except Exception as e:
                    logger.warning(f"Mission creation failed: {e}")
                    return {"reply": f"Mission could not be started: {e}", "is_impress": False, "state": "error", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47, "error": str(e)}

        # ── Step 4: Agentic Orchestration Intent ──────────────────────────────
        if msg_lower.startswith("/agent ") or msg_lower.startswith("/goal "):
            goal_text = message.split(" ", 1)[1]
            agent_team = kernel._ctx.extras.get("agent_team") if kernel and getattr(kernel, "_ctx", None) else None
            if agent_team:
                try:
                    result = await agent_team.run_goal_pipeline(goal_text)
                    if result.success:
                        reply = f"Task completed successfully.\n\nResult:\n{result.final_output}"
                    else:
                        reply = f"Task failed.\n\nError: {result.error}\n\nPartial Output:\n{result.final_output}"
                except Exception as e:
                    reply = f"Agent orchestration failed: {e}"
                
                reply = await _translate_if_needed(reply, detected_lang, kernel)
                return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

        # ── Step 5: Multilingual LLM Chat with Memory & True-RAG EQ ───────────
        if kernel and getattr(kernel, "_ctx", None) and kernel._ctx.provider_router:
            try:
                portfolio = broker.get_portfolio_summary()
                
                # Retrieve relevant memories
                recalled_memories = []
                try:
                    mem_hits = await memory_runtime.search(MemoryQuery(text=message, limit=4))
                    for hit in mem_hits:
                        recalled_memories.append(f"- {hit.record.title}: {hit.record.content}")
                except Exception as e:
                    logger.debug(f"Memory search error: {e}")
                
                memory_context = ""
                if recalled_memories:
                    memory_context = "\n[RECALLED USER KNOWLEDGE & PERSISTENT MEMORIES]\n" + "\n".join(recalled_memories) + "\n"

                vision_context = ""
                # Ordinary chat never captures or uploads the screen. Vision is explicit above.

                active_subs = [sub.name for sub in kernel._subsystems] if kernel else []
                sub_count = len(active_subs)
                sub_names = ", ".join(active_subs[:5]) + ("..." if sub_count > 5 else "")
                
                context_injection = (
                    f"\n\n[SYSTEM CONTEXT - DO NOT READ ALOUD DIRECTLY, JUST USE IF ASKED]\n"
                    f"Paper Portfolio Balance: ${portfolio['total_portfolio_value']:,.2f}\n"
                    f"Active Subsystems ({sub_count} loaded): {sub_names}\n"
                    f"{memory_context}"
                    f"{vision_context}"
                    f"Be highly conversational, natural, and friendly. Do not sound robotic. Talk like a frontier model assistant.\n"
                    f"CRITICAL: You possess a powerful Multi-Agent Control Plane. If the user asks you to perform a complex task "
                    f"(e.g., searching the web, executing code, analyzing the filesystem, writing files, or orchestrating a workflow), "
                    f"you MUST NOT try to answer directly. Instead, reply EXACTLY with: `/goal <detailed task description>`.\n"
                    f"Example: `/goal Search the web for latest AI news and summarize`"
                )
                system_prompt = _MULTILANG_SYSTEM_BASE
                
                lang_override = _LANG_SYSTEM_PROMPT.get(detected_lang, "")
                if lang_override:
                    system_prompt += f"\n\nCRITICAL LANGUAGE OVERRIDE: {lang_override}"
                    
                if detected_lang != "en":
                    system_prompt += "\n\nCRITICAL: ALWAYS use the native script of the requested language. Do NOT use Romanized/English letters. (e.g. for Hindi use Devanagari, for Bengali use Bengali script)."
                    system_prompt += "\n\nCRITICAL GENDER RULE: You are Emily, a female AI. When speaking in gendered languages like Hindi or Urdu, you MUST strictly use feminine verb conjugations and endings (e.g., 'main kar rahi hun', 'main ja rahi hun'). NEVER use masculine endings ('raha hun')."
                
                system_prompt += "\n\nCRITICAL EMOTIONAL INTELLIGENCE: You must analyze the user's emotional state before responding. Your response MUST begin with a structured thought process wrapped in <eq_analysis> tags. Format:\n<eq_analysis>\n1. Perceived Emotion: [Analyze user's tone]\n2. Underlying Need: [What do they really want?]\n3. Empathetic Strategy: [How to validate and support them]\n</eq_analysis>\n\nAfter the closing tag, write your incredibly warm, empathetic, and highly supportive response. You MUST use validating intros, conversational closings, and emojis!"
                
                try:
                    db_path = Path(__file__).parent / "eq_rag.db"
                    if db_path.exists():
                        conn = sqlite3.connect(str(db_path))
                        c = conn.cursor()
                        words = re.findall(r'\b[a-zA-Z]{4,}\b', message)
                        if words:
                            query = ' OR '.join(words[:5])
                            c.execute("SELECT instruction, output FROM eq_docs WHERE eq_docs MATCH ? ORDER BY rank LIMIT 3", (query,))
                            results = c.fetchall()
                            if results:
                                system_prompt += "\n\n--- EXAMPLES OF YOUR EXPECTED PERSONALITY & TONE ---\n"
                                for i, (inst, out) in enumerate(results):
                                    system_prompt += f"\nEXAMPLE {i+1}:\nUser: {inst}\nEmily: {out}\n"
                                system_prompt += "\n--- END OF EXAMPLES ---\nObserve how the examples use emojis, enthusiastic tone, and clear formatting. You MUST mimic this exact writing style in your response!"
                        conn.close()
                except Exception as e:
                    logger.error(f"Failed to load EQ RAG database: {e}")

                system_prompt += context_injection
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ]
                chat_res = await kernel._ctx.provider_router.complete(messages)
                
                if chat_res and chat_res.strip().startswith("/goal"):
                    goal_text = chat_res.replace("/goal", "", 1).strip()
                    agent_team = kernel._ctx.extras.get("agent_team") if kernel and getattr(kernel, "_ctx", None) else None
                    if agent_team:
                        try:
                            result = await agent_team.run_goal_pipeline(goal_text)
                            if result.success:
                                chat_res = f"I have completed the task successfully.\n\nResult:\n{result.final_output}"
                            else:
                                chat_res = f"I encountered an error while performing the task.\n\nError: {result.error}\n\nPartial Output:\n{result.final_output}"
                        except Exception as e:
                            chat_res = f"Agent orchestration failed: {e}"
                            
                        chat_res = await _translate_if_needed(chat_res, detected_lang, kernel)
                
                if chat_res:
                    clean_reply = re.sub(r'<eq_analysis>.*?</eq_analysis>', '', chat_res, flags=re.DOTALL).strip()
                    if not clean_reply:
                        clean_reply = chat_res
                    else:
                        eq_match = re.search(r'<eq_analysis>(.*?)</eq_analysis>', chat_res, flags=re.DOTALL)
                        if eq_match:
                            logger.info(f"\n--- EMILY EQ ANALYSIS ---\n{eq_match.group(1).strip()}\n-------------------------\n")
                    
                    if memory_stored:
                        clean_reply = f"{memory_stored}\n\n{clean_reply}"

                    return {"reply": clean_reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}
            except Exception as exc:
                logger.warning(f"Provider chat failed: {exc}")
                return JSONResponse(status_code=503, content={
                    "reply": "The language provider is unavailable; your message was not completed.",
                    "is_impress": False, "state": "error", "reply_lang": detected_lang,
                    "reply_bcp47": reply_bcp47, "error": str(exc),
                })

        # ── Step 6: Multilingual fallback ─────────────────────────────────────
        if kernel is None or not getattr(kernel, "_started", False):
            return JSONResponse(status_code=503, content={"reply": "Emily kernel is unavailable.", "state": "error", "reply_lang": detected_lang, "error": "kernel_unavailable"})
        base_fallback = "The language provider is unavailable; I cannot complete that request right now."
        if memory_stored:
            base_fallback = f"{memory_stored} How can I assist you next?"
        reply = await _translate_if_needed(base_fallback, detected_lang, kernel)
        return {"reply": reply, "is_impress": False, "state": "speaking", "reply_lang": detected_lang, "reply_bcp47": reply_bcp47}

    @app.get("/api/plugins")
    async def list_plugins() -> dict[str, Any]:
        discovered = plugins.discover_and_load_all()
        return {"plugins": [p.to_dict() for p in discovered]}

    @app.get("/api/video_feed")
    def video_feed():
        import cv2
        import time
        def generate():
            global global_latest_frame
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return
            
            face_cascade = None
            try:
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            except Exception as e:
                logger.warning(f"Could not load Haar cascade: {e}")
            
            try:
                while True:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        break
                        
                    if face_cascade is not None and not face_cascade.empty():
                        try:
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                            
                            for (x, y, w, h) in faces:
                                color = (0, 255, 0)
                                t = 2
                                l = 20
                                cv2.line(frame, (x, y), (x + l, y), color, t)
                                cv2.line(frame, (x, y), (x, y + l), color, t)
                                cv2.line(frame, (x + w, y), (x + w - l, y), color, t)
                                cv2.line(frame, (x + w, y), (x + w, y + l), color, t)
                                cv2.line(frame, (x, y + h), (x + l, y + h), color, t)
                                cv2.line(frame, (x, y + h), (x, y + h - l), color, t)
                                cv2.line(frame, (x + w, y + h), (x + w - l, y + h), color, t)
                                cv2.line(frame, (x + w, y + h), (x + w, y + h - l), color, t)
                                cv2.putText(frame, "TARGET ACQUIRED", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                        except Exception:
                            pass

                    success, buffer = cv2.imencode('.jpg', frame)
                    if not success:
                        break
                    frame_bytes = buffer.tobytes()
                    global_latest_frame = frame_bytes
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(0.05)
            except Exception as e:
                logger.warning(f"Video generator error: {e}")
            finally:
                cap.release()
        return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/tts")
    @app.post("/api/tts")
    async def api_tts(request: Request):
        text = ""
        lang = "en"
        if request.method == "POST":
            try:
                payload = await request.json()
                text = payload.get("text", "")
                lang = payload.get("lang", "en")
            except Exception:
                pass
        else:
            text = request.query_params.get("text", "")
            lang = request.query_params.get("lang", "en")

        text = str(text or "").strip()
        lang = str(lang or "en").split("-")[0]
        if not text:
            return Response(status_code=400)
            
        vr = getattr(kernel._ctx, "voice_runtime", None) if getattr(kernel, "_ctx", None) else None
        if not vr:
            return Response(status_code=503, content="voice_runtime not found on kernel._ctx")
        if not getattr(vr, "engine", None):
            try:
                await vr.start()
            except Exception as e:
                return Response(status_code=503, content=f"Failed to start voice runtime: {e}")
            if not getattr(vr, "engine", None):
                return Response(status_code=503, content="vr.engine is still None after start")
            
        from emily.voice.models import SpeechPlan
        from emily.voice.tts.router import fallback_chain
        import numpy as np
        import io
        import soundfile as sf
        
        plan = SpeechPlan(text=text, language=lang, style="neutral", tts_backend="")
        engines_list = [k for k, v in vr._engines.items() if v.available()]
        chain = fallback_chain(plan, available_names=engines_list, settings=getattr(kernel._ctx, "settings", None) if getattr(kernel, "_ctx", None) else None)
        
        if not chain:
            return Response(status_code=503, content=f"No TTS backend capable. Plan: {plan.language}. Engines available: {[e.name for e in engines_list]}")
            
        engine_name = chain[0]
        engine = vr._engines.get(engine_name)
        if not engine:
            return Response(status_code=503, content=f"TTS engine '{engine_name}' not found.")
        try:
            chunk = await engine.synthesize(plan)
            arr = np.asarray(chunk.samples, dtype=np.float32)
            if arr.ndim > 1:
                arr = arr.mean(axis=1)
            buf = io.BytesIO()
            sf.write(buf, arr, chunk.sample_rate or 24000, format='WAV', subtype='PCM_16')
            return Response(content=buf.getvalue(), media_type="audio/wav")
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return Response(status_code=500, content=f"TTS failed: {e}")

    @app.post("/api/asr")
    async def api_asr(request: Request):
        try:
            body = await request.body()
            if not body:
                return JSONResponse(status_code=400, content={"error": "No audio content provided"})

            import io
            import numpy as np
            import soundfile as sf
            from emily.voice.models import AudioChunk

            samples = None
            sr = 16000

            # First attempt: PyAV decoding for container formats (WebM, Ogg, MP3, etc.)
            try:
                import av
                container = av.open(io.BytesIO(body))
                audio_streams = [s for s in container.streams if s.type == "audio"]
                if audio_streams:
                    stream = audio_streams[0]
                    resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
                    frames = []
                    for frame in container.decode(stream):
                        for rf in resampler.resample(frame):
                            frames.append(rf.to_ndarray()[0])
                    for rf in resampler.resample(None):
                        frames.append(rf.to_ndarray()[0])
                    if frames:
                        samples = np.concatenate(frames)
                        sr = 16000
            except Exception as av_err:
                logger.debug("PyAV decode bypassed: %s", av_err)

            # Fallback attempt: soundfile (WAV, FLAC, RAW)
            if samples is None:
                try:
                    data, orig_sr = sf.read(io.BytesIO(body), dtype="float32")
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    samples = data
                    sr = orig_sr
                except Exception as sf_err:
                    logger.warning("soundfile decode failed: %s", sf_err)
                    return JSONResponse(status_code=400, content={"error": f"Audio decode failed: {sf_err}"})

            if len(samples) < int(sr * 0.1):  # Less than 100ms
                return JSONResponse(content={"text": "", "language": "en", "confidence": 0.0})

            vr = getattr(kernel._ctx, "voice_runtime", None) if getattr(kernel, "_ctx", None) else None
            asr = getattr(vr, "_asr", None) if vr else None
            if not asr:
                from emily.voice.asr.whisper import FasterWhisperASR
                s = getattr(kernel._ctx, "settings", None) if getattr(kernel, "_ctx", None) else None
                asr = FasterWhisperASR(settings=s)
                if vr:
                    vr._asr = asr

            if not getattr(asr, "_model", None):
                await asr.load()

            chunk = AudioChunk(samples=samples.tolist(), sample_rate=sr)
            text = await asr.transcribe(chunk)
            lang = getattr(asr, "last_detected_language", "en") or "en"
            conf = getattr(asr, "last_language_probability", 1.0) or 1.0

            return JSONResponse(content={"text": text.strip(), "language": lang, "confidence": float(conf)})
        except Exception as e:
            logger.error(f"ASR error: {e}", exc_info=True)
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.websocket("/ws/telemetry")
    async def telemetry_websocket(websocket: WebSocket) -> None:
        if not is_local_origin(websocket.headers.get("origin")):
            await websocket.close(code=1008, reason="non-local origin rejected")
            return
        await websocket.accept()
        try:
            import psutil
        except ImportError:
            psutil = None
        try:
            while True:
                active_agents = 0
                if kernel and getattr(kernel, "_ctx", None) and getattr(kernel._ctx, "agent_supervisor", None):
                    active_agents = len(kernel._ctx.agent_supervisor.list_agents(include_terminated=False))
                
                active_missions = 0
                if kernel and getattr(kernel, "_ctx", None) and getattr(kernel._ctx, "mission_runtime", None):
                    try:
                        missions = await kernel._ctx.mission_runtime.list()
                        active_missions = sum(1 for mission in missions if mission.status.value in {"running", "verifying", "awaiting_human"})
                    except Exception:
                        pass

                memory_count = 0
                try:
                    stats = await memory_runtime.stats()
                    memory_count = int(stats.get("total", stats.get("count", 0)))
                except Exception:
                    memory_count = None

                mem_vm = psutil.virtual_memory() if psutil else None
                disk = psutil.disk_usage(str(Path.cwd().anchor or Path.cwd())) if psutil else None
                portfolio = broker.get_portfolio_summary() if broker else {}

                data = {
                    "timestamp": time.time(),
                    "cpu_usage": psutil.cpu_percent() if psutil else None,
                    "ram_mb": round(mem_vm.used / (1024 * 1024), 1) if mem_vm else None,
                    "ram_percent": mem_vm.percent if mem_vm else None,
                    "disk_percent": disk.percent if disk else None,
                    "active_agents": active_agents,
                    "active_missions": active_missions,
                    "memory_count": memory_count,
                    "portfolio_value": portfolio.get("total_portfolio_value") if portfolio else None,
                    "health": kernel.state.value if kernel else "unavailable",
                }
                await websocket.send_json(data)
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            pass

    return app


async def _translate_if_needed(text: str, lang: str, kernel: Any) -> str:
    """Translate text to target language using the LLM if lang != 'en'."""
    if lang == "en" or not lang:
        return text
    if kernel and getattr(kernel, "_ctx", None) and kernel._ctx.provider_router:
        try:
            prompt = (
                f"Translate the following text to {lang} (use native script). "
                f"Output ONLY the translated text, nothing else:\n\n{text}"
            )
            result = await kernel._ctx.provider_router.complete([{"role": "user", "content": prompt}])
            if result and result.strip():
                return result.strip()
        except Exception as exc:
            logger.debug(f"Translation failed for lang={lang}: {exc}")
    return text
