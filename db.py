# db.py
import os
from typing import Tuple
import psycopg2
from psycopg2 import sql
from psycopg2.extras import register_default_jsonb  # noqa: F401
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ---- Configuration via variables d'environnement (sécurisé pour Azure) ----
PG_HOST = os.getenv("PGHOST", "avo-adb-001.postgres.database.azure.com")
PG_PORT = int(os.getenv("PGPORT", "5432"))
PG_DB   = os.getenv("PGDATABASE", "Problem_solving")  # << demandé
PG_USER = os.getenv("PGUSER", "adminavo")
PG_PASS = os.getenv("PGPASSWORD", "")
PG_SSL  = os.getenv("PGSSLMODE", "require")

def get_connection():
    """
    Établit une connexion sécurisée avec PostgreSQL (Azure).
    Utilise des variables d'environnement. Exemple de configuration Azure App Settings:
      - PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD, PGSSLMODE=require
    """
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        database=PG_DB,
        user=PG_USER,
        password=PG_PASS,
        sslmode=PG_SSL
    )
