from app.core.supabase import supabase

def get_or_create_submission(ingested_data: dict,mode: str) -> dict:
    """
    Store an ingested input or return existing cached submission
    """
    input_type = ingested_data["input_type"]
    query = supabase.table("submissions").select("*").eq("mode",mode)
    if input_type == "text":
        query = query.eq("text_hash",ingested_data["text_hash"])
    elif input_type == "video_url":
        query = query.eq("raw_url",ingested_data["raw_url"])
    else:
        query = query.eq("content_hash",ingested_data["content_hash"])

    exisiting = query.limit(1).execute().data or []
    if exisiting:
        return {
            "submission":exisiting[0],
            "cache_hit":True
        }

    row = {
        "input_type":input_type,
        "mode": mode,
        "raw_url": ingested_data.get("raw_url"),
        "content_hash":ingested_data.get("content_hash"),
        "raw_text":ingested_data.get("raw_text"),
        "text_hash":ingested_data.get("text_hash"),
        "status":"pending",
    }
    result = supabase.table("submissions").insert(row).execute()
    return {
        "submission":result.data[0],
        "cache_hit":False
    }
    