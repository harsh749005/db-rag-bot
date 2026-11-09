"""
Simple Supabase helpers for the QA bot.

Every function takes the logged-in user's token. Supabase then applies the
row level security rules, so a user can only see their own rows.
"""

import mimetypes
import os

from supabase import ClientOptions, create_client


def get_client(token=None):
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    if token is None:
        return create_client(url, key)
    # With a token, every request is made "as this user"
    options = ClientOptions(headers={"Authorization": f"Bearer {token}"})
    return create_client(url, key, options=options)


# ---------- Login ----------

def sign_up(email, password):
    result = get_client().auth.sign_up({"email": email, "password": password})
    return result.session  # None when the email must be confirmed first


def sign_in(email, password):
    result = get_client().auth.sign_in_with_password({"email": email, "password": password})
    return result.session


def get_user_id(token):
    # Ask Supabase who this token belongs to (it also checks the token is valid)
    return get_client().auth.get_user(token).user.id


# ---------- Files ----------

def create_document(token, document_id, user_id, file_name, file_type, storage_path, size_bytes):
    row = {
        "id": document_id,
        "user_id": user_id,
        "file_name": file_name,
        "file_type": file_type,
        "storage_path": storage_path,
        "size_bytes": size_bytes,
    }
    get_client(token).table("documents").insert(row).execute()


def get_document(token, document_id):
    result = get_client(token).table("documents").select("*").eq("id", document_id).limit(1).execute()
    return result.data[0] if result.data else None


def list_documents(token):
    result = (
        get_client(token)
        .table("documents")
        .select("id, file_name, file_type, status, error")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


def update_document(token, document_id, status, error=None):
    row = {"status": status, "error": error}
    get_client(token).table("documents").update(row).eq("id", document_id).execute()


def delete_document(token, document_id, storage_path):
    client = get_client(token)
    try:
        client.storage.from_("uploads").remove([storage_path])
    except Exception as error:
        print("Could not remove the stored file:", error)  # still remove the database rows
    # Chunks, chats and messages are removed too ("on delete cascade" in schema.sql)
    client.table("documents").delete().eq("id", document_id).execute()


def upload_file(token, storage_path, local_path):
    mime_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    with open(local_path, "rb") as file:
        get_client(token).storage.from_("uploads").upload(
            storage_path, file.read(), {"content-type": mime_type}
        )


# ---------- Chunks and vectors ----------

def save_chunks(token, document_id, chunks, vectors):
    rows = []
    for chunk, vector in zip(chunks, vectors):
        info = chunk.metadata
        rows.append({
            "document_id": document_id,
            "content": chunk.page_content,
            "kind": info.get("kind", "text"),
            "page": info["page"] + 1 if "page" in info else None,  # PDF pages start at 0
            "start_seconds": info.get("start"),
            "embedding": vector,
        })

    # Save in small batches so each request stays small
    client = get_client(token)
    for start in range(0, len(rows), 100):
        client.table("chunks").insert(rows[start:start + 100]).execute()


def search_chunks(token, document_id, question_vector, count):
    # match_chunks is the search function we created in schema.sql
    params = {"query_embedding": question_vector, "doc_id": document_id, "match_count": count}
    return get_client(token).rpc("match_chunks", params).execute().data


# ---------- Chats ----------

def get_or_create_chat(token, user_id, document_id):
    client = get_client(token)
    found = client.table("chats").select("id").eq("document_id", document_id).limit(1).execute()
    if found.data:
        return found.data[0]["id"]

    created = client.table("chats").insert({"user_id": user_id, "document_id": document_id}).execute()
    return created.data[0]["id"]


def save_message(token, chat_id, role, content, sources=None):
    row = {"chat_id": chat_id, "role": role, "content": content, "sources": sources or []}
    get_client(token).table("messages").insert(row).execute()


def get_messages(token, chat_id):
    result = (
        get_client(token)
        .table("messages")
        .select("role, content, sources")
        .eq("chat_id", chat_id)
        .order("created_at")
        .execute()
    )
    return result.data