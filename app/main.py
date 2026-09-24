from fastapi import FastAPI
from app.core.supabase import supabase

app = FastAPI(
    title="Factchecker API",
    description="backend api for factchecker app"
)

@app.get("/")
def root():
    return {
        "message":"Factchecker API is running"
    }

@app.get("/health")
def health_check():
    return {
        "status":"healthy"
    }

@app.get("/health/supabase")
def health_check_supabase():
    try:
        response = (
            supabase.table("submissions").select("id").limit(1).execute()
        )
        return {
            "status":"healthy",
            "supabase":"connected"
        }
    except Exception as e:
        return {
            "status":"error",
            "supabase":"connection failed",
            "detail": str(e)
        }