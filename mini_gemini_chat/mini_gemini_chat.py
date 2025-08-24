from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict,Any,List
from google import genai
from google.genai import types
from google.genai.types import HttpOptions 

client = genai.Client()

DEFAULT_MODEL = "gemini-2.5-flash"

SESSIONS: Dict[str, any] = {}

SESS_DIR = Path("sessions")
SESS_DIR.mkdir(exist_ok=True)

def _session_path(sid: str) -> Path:
    return SESS_DIR / f"{sid}.json"

def _turn_text(turn: types.Content) -> str:
    out = []
    for p in getattr(turn, "parts", []) or []:
        t = getattr(p, "text", None)
        if t:
            out.append(t)
    return "\n".join(out)

def _hist_to_json(history: List[types.Content]) -> List[dict]:
    out = []
    for turn in history or []:
        out.append({"role": turn.role, "text": _turn_text(turn)})
    return out

def _json_to_history(items: List[dict] | None) -> List[types.Content]:
    if not items:
        return []
    return [
        types.Content(role=it.get("role", "user"), parts=[types.Part(text=it.get("text", ""))])
        for it in items
    ]

def load_session_history(session_id: str) -> List[dict] | None:
    p = _session_path(session_id)
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_session_history(session_id: str, chat) -> None:
    p = _session_path(session_id)
    history = chat.get_history()
    with p.open("w", encoding="utf-8") as f:
        json.dump(_hist_to_json(history), f, ensure_ascii=False, indent=2)

app = FastAPI(title="Mini Gemini Chat",version="1.0.0")

class ChatRequest(BaseModel):
    session_id: str
    message: str
    model: str | None = None
    
class ClearRequest(BaseModel):
    session_id: str
    
@app.post("/chat")
def chat(req: ChatRequest):
    model_name = req.model or DEFAULT_MODEL
    
    if req.session_id not in SESSIONS:
        stored = load_session_history(req.session_id)
        history = _json_to_history(stored)
        chat = client.chats.create(model=model_name,history=history)
        SESSIONS[req.session_id]=chat
    else:
        chat = SESSIONS[req.session_id]
        
    resp = chat.send_message(message=req.message)
    
    save_session_history(req.session_id, chat)
    
    turns = [
        {"role":turn.role, " text": _turn_text(turn)}
        for turn in chat.get_history()
    ]

    
    return{
        "session_id": req.session_id,
        "model": model_name,
        "reply": (resp.text or "").strip(),
        "tokens": getattr(resp, "usage_metadata", None),
        "turns": turns
    }

@app.post("/clear")
def clear(req: ClearRequest):
    if req.session_id in SESSIONS:
        del SESSIONS[req.session_id]
    try:
        _session_path(req.session_id).unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True}

def run_cli(session_id: str, model_name: str):
    
    if session_id in SESSIONS:
        chat = SESSIONS[session_id]
    else:
        stored = load_session_history(session_id)
        history = _json_to_history(stored)
        chat = client.chats.create(model=model_name,history=history)
        SESSIONS[session_id]=chat
    
    print(f"Gemini CLI — model: {model_name} — session: {session_id}")
    print("Wpisz pytanie i naciśnij Enter.")
    print("Komendy: :reset (wyczyść sesję), :exit / :q (wyjście)\n")
    
    try:
        while True:
            user = input("Ty: ").strip()
            if not user:
                continue
            if user in (":exit", ":q", ":quit"):
                print("Do zobaczenia!")
                break
            if user in (":reset", ":clear"):
                SESSIONS.pop(session_id,None)
                try:
                    _session_path(session_id).unlink(missing_ok=True)
                except Exception:
                    pass   
                chat = client.chats.create(model=model_name, history=[])
                SESSIONS[session_id] = chat
                print("Sesja wyczyszczona.")
                continue
            
            resp = chat.send_message(message=user)
            
            save_session_history(session_id, chat)
            print("Asystent:", (resp.text or "").strip(), "\n")
    
    except KeyboardInterrupt:
        print("Sesja Przerwana")
    
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mini Gemini Chat — API i/lub CLI")
    parser.add_argument("--cli", action="store_true", help="Uruchom tryb interaktywny w terminalu")
    parser.add_argument("--session", default="local-cli", help="Id sesji dla CLI (domyślnie: local-cli)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Nazwa modelu (domyślnie: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if args.cli:
        run_cli(session_id=args.session, model_name=args.model)