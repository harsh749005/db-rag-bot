# Multimodal RAG-Based Question Answering System

A Python-based Retrieval-Augmented Generation (RAG) chatbot that lets
users upload their own content and ask questions about it. The
application extracts text from supported files, indexes the extracted
content, retrieves relevant passages for a question, and uses Claude to
generate an answer grounded in those passages.

> **Project:** Multimodal RAG-Based Question Answering System\
> **Institution:** Lakehead University\
> **Developers:** Harsh Patel and Sparsh Bhatt

------------------------------------------------------------------------

## Table of Contents

-   [Overview](#overview)
-   [Key Features](#key-features)
-   [Supported Content](#supported-content)
-   [How It Works](#how-it-works)
-   [Technology Stack](#technology-stack)
-   [Project Structure](#project-structure)
-   [Getting Started](#getting-started)
-   [Environment Configuration](#environment-configuration)
-   [Running the Application](#running-the-application)
-   [How Question Answering Works](#how-question-answering-works)
-   [API Overview](#api-overview)
-   [Important Notes and Limitations](#important-notes-and-limitations)
-   [Future Improvements](#future-improvements)
-   [Contributors](#contributors)

## Overview

Finding a specific answer across multiple documents, images, and
recorded content can be time-consuming. This project addresses that
problem with a document-focused conversational interface.

Instead of sending an entire collection of files to an LLM every time a
user asks a question, the application:

1.  Extracts text from an uploaded file.
2.  Splits the extracted text into smaller chunks.
3.  Converts chunks into vector embeddings.
4.  Stores the chunks and their embeddings in Supabase.
5.  Retrieves the most relevant chunks when the user asks a question.
6.  Sends the question and retrieved context to Claude.
7.  Returns an answer with source information.

This approach makes it possible to ask questions about user-provided
content while keeping the retrieved evidence connected to its source.

## Key Features

-   **Document question answering:** Ask questions about uploaded files
    using natural language.
-   **PDF processing:** Extract text from PDF documents.
-   **Word document processing:** Extract text from `.docx` files.
-   **Image text extraction:** Use OCR to turn text visible in images
    into searchable text.
-   **Video transcription:** Use Faster-Whisper to convert spoken audio
    into text for retrieval.
-   **Semantic search:** Retrieve relevant chunks using sentence
    embeddings rather than relying only on exact keyword matches.
-   **Context-grounded responses:** Provide Claude with the question and
    retrieved passages to generate an answer.
-   **Source information:** Return source metadata associated with the
    retrieved content.
-   **User-aware document access:** The API uses authenticated user
    information when finding documents and creating or retrieving chats.
-   **Persistent storage:** Use Supabase for document, chunk, chat, and
    message data.

## Supported Content

  -----------------------------------------------------------------------
  Content type            Processing approach     Result used by RAG
  ----------------------- ----------------------- -----------------------
  PDF                     Extract text with       Document text
                          `pypdf`                 

  Word (`.docx`)          Extract text with       Document text
                          `docx2txt`              

  Images                  OCR / text recognition  Recognized text

  Videos                  Extract/process audio   Speech transcript
                          and transcribe with     
                          Faster-Whisper; media   
                          handling can use PyAV   
                          and OpenCV              
  -----------------------------------------------------------------------

**Important:** The RAG retrieval pipeline is text-based. Images and
video become searchable after their text has been extracted. This does
not, by itself, mean the system understands every visual detail in an
image or video. Scanned PDFs that do not contain an embedded text layer
need an OCR step before their content can be indexed.

## How It Works

The application has two main phases.

### Phase 1: File ingestion and indexing

This phase runs when a file is uploaded.

``` text
User uploads a file
        |
        v
File type detection
        |
        v
Text extraction
(PDF / DOCX / image OCR / video transcription)
        |
        v
Text splitting
        |
        v
Sentence embeddings
        |
        v
Store chunks and vectors in Supabase
```

### Phase 2: Question answering

This phase runs for each question.

``` text
User asks a question
        |
        v
Create query embedding
        |
        v
Search relevant chunks in Supabase
        |
        v
Build context from retrieved chunks
        |
        v
Send question + context to Claude
        |
        v
Generate answer
        |
        v
Return answer and source information
```

The current question-answering route shown in the application retrieves
a configured number of chunks using `qa_bot.CHUNKS_TO_USE`. The
screenshot of the implementation shows the question embedding, chunk
search, context construction, Claude invocation, and source collection
in the `/ask` endpoint.

## Technology Stack

  -----------------------------------------------------------------------
  Area                                Libraries / Services
  ----------------------------------- -----------------------------------
  Language                            Python

  API backend                         FastAPI, Uvicorn

  Request/file handling               `python-multipart`

  RAG orchestration                   `langchain-core`,
                                      `langchain-community`,
                                      `langchain-text-splitters`

  LLM integration                     `langchain-anthropic`

  Embeddings                          `langchain-huggingface`,
                                      `sentence-transformers`

  PDF extraction                      `pypdf`

  Word extraction                     `docx2txt`

  Speech-to-text                      `faster-whisper`

  Video / media processing            PyAV (`av`), OpenCV
                                      (`opencv-python-headless`)

  Database / vector storage           Supabase

  Configuration                       `python-dotenv`
  -----------------------------------------------------------------------

## Project Structure

The visible project structure is organized as follows. Additional files
or modules may exist as the implementation evolves.

``` text
db-rag/
├── static/
│   └── index.html          # Web interface
├── uploads/                # Uploaded files (if stored locally)
├── app.py                  # FastAPI application and API routes
├── database.py             # Supabase and database operations
├── qa_bot.py               # RAG prompt, LLM and answer utilities
├── requirements.txt        # Python dependencies
├── .env                    # Local environment variables (do not commit)
└── .gitignore
```

### Main modules

-   **`app.py`** --- Defines the FastAPI application and routes. The
    `/ask` route checks the authenticated user and document status, gets
    or creates a chat, embeds the question, retrieves matching chunks,
    invokes the LLM, stores the conversation, and returns the answer and
    sources.
-   **`database.py`** --- Contains database operations such as document
    lookup, chunk search, chat creation, and message storage.
-   **`qa_bot.py`** --- Contains RAG-related configuration and helper
    functions, including the prompt, chunk-selection setting, and answer
    text extraction.
-   **`static/index.html`** --- Provides the browser-based user
    interface.
-   **`uploads/`** --- Local upload directory, if used by the current
    configuration.

## Getting Started

### Prerequisites

-   Python installed on your system.
-   A Supabase project with the database schema and vector-search
    functionality expected by `database.py`.
-   An Anthropic API key for Claude.
-   The required Python dependencies.
-   Any additional OCR executable or library required by the OCR
    implementation in your code.

### 1. Clone the repository

``` bash
git clone <YOUR_REPOSITORY_URL>
cd db-rag
```

If you already have the project locally, open a terminal in the project
directory.

### 2. Create and activate a virtual environment

**Windows PowerShell**

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux**

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If your `requirements.txt` does not yet contain all dependencies, add
the packages used by your current implementation before installing.

### 4. Configure environment variables

Create a `.env` file in the project root. Add the variable names
expected by your code, for example:

``` env
ANTHROPIC_API_KEY=your_anthropic_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_key
```

The names above are common examples. **Check `app.py` and `database.py`
and use the exact environment-variable names referenced by your
implementation.** Do not commit your `.env` file or expose API keys in
screenshots, logs, or source control.

### 5. Configure Supabase

Set up the tables, relationships, access policies, and vector-search
function required by the SQL queries in `database.py`.

The database needs to support the data used by your application, such
as:

-   User and document records.
-   Extracted text chunks.
-   Chunk embeddings / vectors.
-   Chat sessions.
-   User and assistant messages.
-   Source metadata used to identify the original document or location.

The exact schema and SQL function names must match the queries in your
`database.py` file.

## Running the Application

Start the FastAPI development server from the project root:

``` bash
python -m uvicorn app:app --reload
```

By default, Uvicorn serves the application locally at:

``` text
http://127.0.0.1:8000
```

If FastAPI's automatic API documentation is enabled, it is generally
available at:

``` text
http://127.0.0.1:8000/docs
```

Open the application in your browser using the route configured to serve
the frontend. The exact URL depends on the routes defined in `app.py`.

For deployment, run Uvicorn without `--reload` and configure
production-grade secrets, HTTPS, storage, logging, and access controls.

## How Question Answering Works

The `/ask` endpoint in the current implementation follows this general
sequence:

1.  Receives the question and document identifier.
2.  Gets the authenticated user's token and user information.
3.  Looks up the document and checks that its processing status is
    `ready`.
4.  Gets or creates a chat associated with the user and document.
5.  Saves the user's question.
6.  Generates an embedding for the question using
    `embeddings.embed_query(...)`.
7.  Searches Supabase for the closest chunks for that document.
8.  Joins the retrieved chunk text into a context string.
9.  Sends the context and question to the configured RAG prompt and
    Claude model.
10. Extracts the answer text and collects source information.
11. Saves the assistant's response and returns the answer and sources.

This keeps the LLM focused on the most relevant retrieved text instead
of requiring the entire file to be included in every question.

## API Overview

The following endpoint is visible in the provided application
screenshot.

  -----------------------------------------------------------------------
  Method                  Endpoint                Purpose
  ----------------------- ----------------------- -----------------------
  `POST`                  `/ask`                  Ask a question about a
                                                  document and receive an
                                                  answer with sources

  -----------------------------------------------------------------------

The `/ask` route expects the request model and authentication dependency
defined in `app.py`. Consult that file for the exact request fields,
headers, and response schema.

Example response shape based on the visible route:

``` json
{
  "answer": "Generated answer based on the retrieved context.",
  "sources": []
}
```

The actual `sources` array contains the source objects produced by the
application's `get_sources(...)` function.

## Important Notes and Limitations

-   **OCR quality:** OCR results depend on image resolution,
    orientation, contrast, and text clarity.
-   **Scanned PDFs:** A PDF without a text layer needs OCR processing. A
    normal PDF text extractor alone cannot read text embedded only as
    page images.
-   **Transcription quality:** Background noise, accents, multiple
    speakers, and recording quality can affect speech-to-text accuracy.
-   **Retrieval quality:** Chunk size, overlap, embedding model,
    similarity search, and the number of retrieved chunks affect answer
    quality.
-   **LLM limitations:** RAG can reduce unsupported answers by providing
    relevant evidence, but it does not guarantee that every answer is
    correct.
-   **Source accuracy:** Reliable citations depend on retaining useful
    metadata such as filename, page number, and video timestamp during
    ingestion.
-   **Privacy and security:** Uploaded files and API credentials should
    be protected with suitable authentication, authorization, storage
    policies, and secret management.

## Future Improvements

Potential extensions include:

-   Add OCR support for scanned PDF pages.
-   Preserve page numbers and video timestamps in source citations.
-   Add support for additional file formats.
-   Add document previews and processing-status indicators.
-   Improve retrieval with hybrid keyword and vector search, reranking,
    and configurable top-k.
-   Add conversation history and follow-up question support.
-   Add file-size limits, validation, and clearer upload error messages.
-   Add automated tests, logging, and production deployment
    configuration.

## Contributors

**Harsh Patel**\
Lakehead University

**Sparsh Bhatt**\
Lakehead University

------------------------------------------------------------------------

## Acknowledgements and References

-   Lewis et al. (2020), [Retrieval-Augmented Generation for
    Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401).
-   [LangChain Documentation](https://docs.langchain.com/).
-   [Anthropic Documentation](https://docs.anthropic.com/).
-   [Sentence Transformers Documentation](https://www.sbert.net/).
-   [Supabase Documentation](https://supabase.com/docs).
-   [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper).
-   [PyAV Documentation](https://pyav.org/docs/).
-   [OpenCV Documentation](https://docs.opencv.org/).
