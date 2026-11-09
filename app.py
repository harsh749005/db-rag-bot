"""
Web app for the QA bot, with Supabase for login, files, vectors and chats.

Run:
    python -m uvicorn app:app
Then open http://127.0.0.1:8000
"""

import os
import shutil
import threading
import uuid

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from langchain_anthropic import ChatAnthropic
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel

import qa_bot  # our bot from before (this also loads the .env file)
import database

for name in ("SUPABASE_URL", "SUPABASE_ANON_KEY"):
    if not os.environ.get(name):
        raise SystemExit(f"Please add {name} to your .env file.")

app = FastAPI()
llm = ChatAnthropic(model=qa_bot.MODEL_NAME)
embeddings = HuggingFaceEmbeddings(model_name=qa_bot.EMBEDDING_MODEL)  # loaded once

HERE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(HERE, "uploads")  # temporary copies while we process
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_TYPES = [".pdf", ".docx"] + qa_bot.IMAGE_TYPES + qa_bot.VIDEO_TYPES

# What we are doing right now for each file being processed (lost if the server stops)
jobs = {}


class Login(BaseModel):
    email: str
    password: str


class Question(BaseModel):
    document_id: str
    question: str


# ---------- Helpers ----------

def current_user(authorization: str = Header(default="")):
    # Every request must carry the token we gave at login
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Please log in.")
    try:
        user_id = database.get_user_id(token)
    except Exception:
        raise HTTPException(401, "Your session ended. Please log in again.")
    return {"token": token, "user_id": user_id}


def get_file_type(extension):
    if extension == ".pdf":
        return "pdf"
    if extension == ".docx":
        return "docx"
    if extension in qa_bot.IMAGE_TYPES:
        return "image"
    return "video"


def get_sources(rows):
    # Make short labels like "Page 3" or "Video 01:30"
    sources = []
    for row in rows:
        if row.get("page") is not None:
            sources.append(f"Page {row['page']}")
        if row.get("start_seconds") is not None:
            sources.append(f"Video {qa_bot.format_time(row['start_seconds'])}")
    return list(dict.fromkeys(sources))  # remove repeats, keep order


def find_document(user, document_id):
    document = database.get_document(user["token"], document_id)
    if not document:
        raise HTTPException(404, "File not found.")
    return document


def process_file(token, document_id, path, storage_path):
    # Runs in the background. "stage" tells the web page what we are doing now.
    job = jobs[document_id]
    try:
        job["stage"] = "uploading"
        database.upload_file(token, storage_path, path)

        extension = os.path.splitext(path)[1].lower()
        if extension in qa_bot.VIDEO_TYPES:
            job["stage"] = "speech"
            documents = qa_bot.load_video_speech(path)
            job["stage"] = "frames"
            documents += qa_bot.load_video_frames(path, llm)
        else:
            job["stage"] = "reading"
            documents = qa_bot.load_file(path, llm)

        job["stage"] = "splitting"
        chunks = qa_bot.split_into_chunks(documents)
        if not chunks:
            raise ValueError("No text found in this file.")

        job["stage"] = "indexing"
        vectors = embeddings.embed_documents([chunk.page_content for chunk in chunks])
        database.save_chunks(token, document_id, chunks, vectors)

        database.update_document(token, document_id, "ready")
        job["stage"] = "ready"
    except Exception as error:
        job["stage"] = "failed"
        job["error"] = str(error)
        try:
            database.update_document(token, document_id, "failed", str(error))
        except Exception:
            pass
    finally:
        os.remove(path)  # the file is safe in Supabase Storage now


# ---------- Pages and login ----------

@app.get("/")
def home():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


@app.post("/signup")
def signup(body: Login):
    try:
        session = database.sign_up(body.email, body.password)
    except Exception as error:
        print("Signup error:", error)
        raise HTTPException(400, str(error))
    if session is None:
        return {"message": "Check your email to confirm your account, then log in."}
    return {"access_token": session.access_token}


@app.post("/login")
def login(body: Login):
    try:
        session = database.sign_in(body.email, body.password)
    except Exception as error:
        print("Login error:", error)
        raise HTTPException(401, str(error))
    return {"access_token": session.access_token}


# ---------- Files ----------

@app.get("/documents")
def documents(user: dict = Depends(current_user)):
    return {"documents": database.list_documents(user["token"])}


@app.delete("/documents/{document_id}")
def remove_document(document_id: str, user: dict = Depends(current_user)):
    document = find_document(user, document_id)
    database.delete_document(user["token"], document_id, document["storage_path"])
    jobs.pop(document_id, None)
    return {"deleted": True}


@app.post("/upload")
def upload(file: UploadFile = File(...), user: dict = Depends(current_user)):
    extension = os.path.splitext(file.filename)[1].lower()
    if extension not in ALLOWED_TYPES:
        raise HTTPException(400, f"{extension or 'This'} file type is not supported.")

    document_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_FOLDER, document_id + extension)
    with open(path, "wb") as saved_file:
        shutil.copyfileobj(file.file, saved_file)

    # Files are stored as <user id>/<document id>.<extension>, as our storage rule expects
    storage_path = f"{user['user_id']}/{document_id}{extension}"
    database.create_document(
        user["token"], document_id, user["user_id"], file.filename,
        get_file_type(extension), storage_path, os.path.getsize(path),
    )

    jobs[document_id] = {"stage": "uploading", "error": None}
    threading.Thread(
        target=process_file, args=(user["token"], document_id, path, storage_path), daemon=True
    ).start()
    return {"document_id": document_id}


@app.get("/status/{document_id}")
def status(document_id: str, user: dict = Depends(current_user)):
    job = jobs.get(document_id)
    if job:
        return {"stage": job["stage"], "error": job["error"]}

    # Not in memory (the server was restarted), so use what the database says
    document = find_document(user, document_id)
    if document["status"] == "ready":
        return {"stage": "ready", "error": None}
    if document["status"] == "failed":
        return {"stage": "failed", "error": document["error"]}
    return {"stage": "failed", "error": "Processing was interrupted. Please upload the file again."}


# ---------- Chat ----------

@app.get("/chat/{document_id}")
def chat(document_id: str, user: dict = Depends(current_user)):
    find_document(user, document_id)
    chat_id = database.get_or_create_chat(user["token"], user["user_id"], document_id)
    return {"messages": database.get_messages(user["token"], chat_id)}


@app.post("/ask")
def ask(body: Question, user: dict = Depends(current_user)):
    token = user["token"]
    document = find_document(user, body.document_id)
    if document["status"] != "ready":
        raise HTTPException(400, "The file is not ready yet.")

    chat_id = database.get_or_create_chat(token, user["user_id"], body.document_id)
    database.save_message(token, chat_id, "user", body.question)

    # Find the closest chunks, then let Claude answer from them
    question_vector = embeddings.embed_query(body.question)
    rows = database.search_chunks(token, body.document_id, question_vector, qa_bot.CHUNKS_TO_USE)
    context = "\n\n".join(row["content"] for row in rows)
    messages = qa_bot.PROMPT.invoke({"context": context, "question": body.question})
    answer = qa_bot.get_text(llm.invoke(messages))

    sources = get_sources(rows)
    database.save_message(token, chat_id, "assistant", answer, sources)
    return {"answer": answer, "sources": sources}