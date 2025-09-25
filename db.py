# db.py
import os
from datetime import datetime
import psycopg2
from dotenv import load_dotenv

def get_connection():
 
    return psycopg2.connect(
        host="avo-adb-001.postgres.database.azure.com",
        port=5432,
        database="Problem_solving",
        user="adminavo",  # utilisateur PostgreSQL, pas le compte Azure
        password="$#fKcdXPg4@ue8AW",  # mot de passe de l'utilisateur PostgreSQL
        sslmode="require"  # obligatoire sur Azure
    )
