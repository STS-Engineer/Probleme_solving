# server.py
from typing import Optional, List
from datetime import datetime, timezone
import os

from fastapi import FastAPI, HTTPException, Query, Path, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, constr
from dotenv import load_dotenv

from db import get_connection

load_dotenv()

APP_NAME = "Conversation Logger API"
APP_VER  = "1.2.0"
API_KEY  = os.getenv("API_KEY")  # si défini, alors x-api-key requis

app = FastAPI(
    title=APP_NAME,
    version=APP_VER,
    description="API pour enregistrer, rechercher et exporter des conversations dans PostgreSQL (Azure)."
)

# CORS (ouvre par défaut, à restreindre selon besoin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Sécurité API Key (optionnelle) ----------
def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------- Schémas Pydantic (alignés avec ton OpenAPI) ----------
class ConversationIn(BaseModel):
    user_name: constr(min_length=1, max_length=200) = Field(..., description="Nom d'utilisateur de la session")
    conversation: constr(min_length=1) = Field(..., description="Transcript complet au format plat")
    date_conversation: Optional[datetime] = Field(
        None,
        description="Horodatage ISO 8601 (UTC recommandé). Si absent, défini par le serveur."
    )

class ConversationOut(BaseModel):
    id: int
    status: str = "ok"

class ConversationSummary(BaseModel):
    id: int
    user_name: str
    date_conversation: datetime
    preview: str

class ConversationDetail(BaseModel):
    id: int
    user_name: str
    date_conversation: datetime
    conversation: str

class Health(BaseModel):
    status: str = "up"


# ---------------------------
# Health
# ---------------------------
@app.get("/health", response_model=Health)
def health():
    return Health(status="up")


# ---------------------------
# Save conversation
# ---------------------------
@app.post("/save-conversation", response_model=ConversationOut, dependencies=[require_api_key] if API_KEY else [])
def save_conversation(payload: ConversationIn):
    try:
        conn = get_connection()
        cur = conn.cursor()
        date_conv = payload.date_conversation or datetime.now(timezone.utc)

        cur.execute(
            """
            INSERT INTO conversations (user_name, conversation, date_conversation)
            VALUES (%s, %s, %s)
            RETURNING id;
            """,
            (payload.user_name.strip(), payload.conversation, date_conv),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close(); conn.close()
        return ConversationOut(id=new_id, status="ok")
    except Exception as e:
        # log e si besoin
        raise HTTPException(status_code=500, detail=f"Insertion échouée: {e}")


# ---------------------------
# List conversations
# ---------------------------
@app.get("/conversations", dependencies=[require_api_key] if API_KEY else [])
def list_conversations(
    date: Optional[str] = Query(None, description="YYYY-MM-DD (UTC)"),
    user_name: Optional[str] = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    try:
        conn = get_connection()
        cur = conn.cursor()

        where, params = [], []
        if date:
            # match sur la partie date en UTC
            where.append("DATE(date_conversation AT TIME ZONE 'UTC') = %s")
            params.append(date)
        if user_name:
            where.append("LOWER(user_name) LIKE %s")
            params.append(f"%{user_name.lower()}%")

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        cur.execute(
            f"""
            SELECT id, user_name, date_conversation, conversation
            FROM conversations
            {where_sql}
            ORDER BY date_conversation DESC, id DESC
            LIMIT %s OFFSET %s;
            """,
            (*params, limit, offset),
        )
        rows = cur.fetchall()

        cur.execute(f"SELECT COUNT(*) FROM conversations {where_sql};", tuple(params))
        total = cur.fetchone()[0]

        items: List[ConversationSummary] = []
        for (cid, uname, dconv, conv) in rows:
            # aperçu: début du champ conversation (plat) – coupe propre
            preview = (conv[:160] + "…") if len(conv) > 160 else conv
            items.append(ConversationSummary(
                id=cid, user_name=uname, date_conversation=dconv, preview=preview
            ))

        cur.close(); conn.close()
        return {"items": [i.model_json_schema() and i.dict() for i in items], "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")


# ---------------------------
# Get conversation by id
# ---------------------------
@app.get("/conversations/{id}", response_model=ConversationDetail, dependencies=[require_api_key] if API_KEY else [])
def get_conversation_by_id(id: int = Path(..., ge=1)):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_name, date_conversation, conversation
            FROM conversations WHERE id=%s;
            """,
            (id,),
        )
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationDetail(id=row[0], user_name=row[1], date_conversation=row[2], conversation=row[3])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")


# ---------------------------
# Export TXT
# ---------------------------
from fastapi.responses import PlainTextResponse

@app.get("/conversations/{id}/export.txt", response_class=PlainTextResponse,
         dependencies=[require_api_key] if API_KEY else [])
def export_conversation_txt(id: int = Path(..., ge=1)):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT conversation FROM conversations WHERE id=%s;", (id,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Remplace le séparateur " , " par des retours à la ligne pour un rendu lisible
        txt = row[0].replace(" , ", "\n")
        return PlainTextResponse(content=txt, media_type="text/plain")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")
