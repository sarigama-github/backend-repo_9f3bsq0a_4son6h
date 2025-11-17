import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests
from typing import Any, Dict, Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


class TokenBody(BaseModel):
    token: str = Field(..., description="Telegram bot token starting with 'XXXX:YYYY'")


class SendMessageBody(BaseModel):
    token: str
    chat_id: str
    text: str
    parse_mode: Optional[str] = None
    disable_web_page_preview: Optional[bool] = None
    disable_notification: Optional[bool] = None


class CallMethodBody(BaseModel):
    token: str
    method: str
    params: Dict[str, Any] = {}


@app.get("/")
def read_root():
    return {"message": "Telegram Bot → App backend is running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


# =============== Telegram Helpers ===============

def tg_call(token: str, method: str, payload: Optional[Dict[str, Any]] = None):
    url = TELEGRAM_API_BASE.format(token=token, method=method)
    try:
        r = requests.post(url, json=payload or {}, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok", False):
            raise HTTPException(status_code=400, detail=data)
        return data
    except requests.exceptions.HTTPError as e:
        # Try to parse JSON error if available
        try:
            return_data = r.json()
        except Exception:
            return_data = {"description": str(e)}
        raise HTTPException(status_code=r.status_code if 'r' in locals() else 500, detail=return_data)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail={"description": str(e)})


# =============== Telegram Routes ===============

@app.post("/api/telegram/validate")
def validate_bot(body: TokenBody):
    """Validate a Telegram bot token and return bot info (getMe)."""
    data = tg_call(body.token, "getMe")
    return data


@app.post("/api/telegram/commands")
def get_my_commands(body: TokenBody):
    """Fetch bot commands using getMyCommands."""
    data = tg_call(body.token, "getMyCommands")
    return data


@app.post("/api/telegram/send")
def send_message(body: SendMessageBody):
    """Send a message via sendMessage."""
    payload = {
        "chat_id": body.chat_id,
        "text": body.text,
    }
    if body.parse_mode is not None:
        payload["parse_mode"] = body.parse_mode
    if body.disable_web_page_preview is not None:
        payload["disable_web_page_preview"] = body.disable_web_page_preview
    if body.disable_notification is not None:
        payload["disable_notification"] = body.disable_notification

    data = tg_call(body.token, "sendMessage", payload)
    return data


@app.post("/api/telegram/call")
def call_method(body: CallMethodBody):
    """Generic Telegram API passthrough for advanced users."""
    data = tg_call(body.token, body.method, body.params)
    return data


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
