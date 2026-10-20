import os
from dotenv import load_dotenv
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from models import Category, Priority
#from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
#is_loaded = load_dotenv(override=True)
load_dotenv()
DATABASE_PATH = Path(
    os.getenv(
        "SUPPORT_DATABASE_PATH",
        str(Path(__file__).with_name("support_requests.db")),
    )
).expanduser()
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
MAX_TOTAL_ATTACHMENT_SIZE = 25 * 1024 * 1024
MAX_ATTACHMENTS = 10
ADMIN_EMAIL = "abhaysingh480shiv@gmail.com"
admin_security = HTTPBasic()


@contextmanager
def database_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS priorities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            [(category.value,) for category in Category],
        )
        connection.executemany(
            "INSERT OR IGNORE INTO priorities (name) VALUES (?)",
            [(priority.value,) for priority in Priority],
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS support_requests (
                id TEXT PRIMARY KEY,
                book TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                category_id INTEGER NOT NULL REFERENCES categories(id),
                priority_id INTEGER NOT NULL REFERENCES priorities(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        request_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(support_requests)")
        }
        if "category_id" not in request_columns:
            connection.execute(
                """
                ALTER TABLE support_requests
                ADD COLUMN category_id INTEGER REFERENCES categories(id)
                """
            )
        if "priority_id" not in request_columns:
            connection.execute(
                """
                ALTER TABLE support_requests
                ADD COLUMN priority_id INTEGER REFERENCES priorities(id)
                """
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS support_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL REFERENCES support_requests(id)
                    ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content BLOB NOT NULL
            )
            """
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173","https://leaf-books.onrender.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,
)


class TextClassification(BaseModel):
    category: Category = Field(
        description="The primary category of the plain text context."
    )
    priority: Priority = Field(
        description="The priority level based on the urgency of the text."
    )
    tags: List[str] = Field(
        description="A list of 2-3 keyword tags representing the topic."
    )
    summary: str = Field(
        description="A short 1-sentence summary of the text content."
    )

sample_context = """
Royality & Payment:
BookLeaf follows an 80/20 royalty split: 80% of the net profit per  author.
20% to Bookleaf.

Net profit = MRP minus printing cost, platform commission (Amazon/Flipkart), and shipping charges.
Royalties are calculated quarterly and paid within 45 days of the quarter ending.
Minimum payout threshold: 1,000. If accumulated royalties are below this, they roll over to the next
quarter.
Payouts are made via bank transfer to the account linked in the authors dashboard.
Authors can view a detailed royalty breakdown in their dashboard, showing sales figures per
platform.
ISBN Policy
• Every book published through BookLeaf receives a unique ISBN assigned by BookLeaf.
• ISBNs are registered under BookLeaf’s publisher imprint. If an author wants an ISBN under their
own imprint, they need to obtain it independently.
• If an author reports an ISBN error (duplicate, wrong book linked), it is treated as a high-priority issue
and escalated to the production team.
Printing & Quality
• In-house printing handles most orders. Overflow or specific format requirements go to Repro India
or Epitome Books.
• Standard print turnaround: 5–7 business days from order confirmation.
• If an author reports a quality issue (misprints, binding defects, color inconsistency), BookLeaf
arranges a free reprint after verification. The author may need to share photos of the defective copy.
Distribution & Availability
• Books are listed on Amazon India, Flipkart, Amazon US, Amazon UK, and the BookLeaf Store.
• New listings typically go live within 7–10 business days after publication is complete.
• If a book is showing as unavailable on a platform, it usually indicates a stock sync issue—
BookLeaf’s team can trigger a re-sync within 24–48 hours.
"""
prompt_template = ChatPromptTemplate.from_messages([
    (
        "system",
        "Classify the support request using the available categories and priorities. "
        "Use 'none' for category or priority when it cannot be determined or does not apply. "
        "Use this Bookleaf policy as context:\n" + sample_context,
    ),
    (
        "human",
        "Book or account: {book}\nSubject: {subject}\nDescription: {description}",
    ),
])

llm = ChatGoogleGenerativeAI(
    model=os.getenv("MODEL","gemini-3.8-flash"),
    temperature=0.2,
    api_key=os.getenv("GEMINI_API_KEY"),
)
classifier_chain = prompt_template | llm.with_structured_output(
    TextClassification
)
@app.get("/api/priorities")
async def get_priorities():
    with database_connection() as connection:
        rows = connection.execute(
            "SELECT id, name FROM priorities ORDER BY name"
        ).fetchall()

    return JSONResponse(
        content=[{"id": row[0], "name": row[1]} for row in rows]
    )

@app.get("/api/categories")
async def get_categories():
    with database_connection() as connection:
        rows = connection.execute(
            "SELECT id, name FROM categories ORDER BY name"
        ).fetchall()

    return JSONResponse(
        content=[{"id": row[0], "name": row[1]} for row in rows]
    )


@app.get("/api/support-requests")
async def get_support_requests():
    with database_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                support_requests.id,
                support_requests.book,
                support_requests.subject,
                support_requests.description,
                categories.name AS category,
                priorities.name AS priority,
                support_requests.created_at
            FROM support_requests
            JOIN categories ON support_requests.category_id = categories.id
            JOIN priorities ON support_requests.priority_id = priorities.id
            ORDER BY support_requests.created_at DESC, support_requests.id
            """
        ).fetchall()

    return JSONResponse(
        content=[
            {
                "id": row[0],
                "book": row[1],
                "subject": row[2],
                "description": row[3],
                "category": row[4],
                "priority": row[5],
                "created_at": row[6],
            }
            for row in rows
        ]
    )


@app.post("/api/support-requests", status_code=201)
async def create_support_request(
    book: str = Form(..., min_length=1, max_length=200),
    subject: str = Form(..., min_length=1, max_length=200),
    description: str = Form(..., min_length=1, max_length=10000),
    attachments: list[UploadFile] = File(default=[]),
    #author: dict = Depends(require_current_author),
):
    book = book.strip()
    subject = subject.strip()
    description = description.strip()
    print(f"book: {book}, subject: {subject}, description: {description}")
    if not book or not subject or not description:
        raise HTTPException(status_code=422, detail="All request fields are required.")
    if len(attachments) > MAX_ATTACHMENTS:
        raise HTTPException(
            status_code=413,
            detail=f"You can attach up to {MAX_ATTACHMENTS} files.",
        )

    uploaded_files = []
    total_size = 0
    for attachment in attachments:
        content = await attachment.read(MAX_ATTACHMENT_SIZE + 1)
        if len(content) > MAX_ATTACHMENT_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"{attachment.filename} exceeds the 10 MB file limit.",
            )
        total_size += len(content)
        if total_size > MAX_TOTAL_ATTACHMENT_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Attachments must total no more than 25 MB.",
            )
        uploaded_files.append(
            (
                (attachment.filename or "attachment")
                .replace("\\", "/")
                .rsplit("/", 1)[-1],
                attachment.content_type or "application/octet-stream",
                content,
            )
        )

    result: TextClassification = await classifier_chain.ainvoke(
        {
            "book": book,
            "subject": subject,
            "description": description,
        }
    )
    print(f"category: {result.category} priority: {result.priority}")

    request_id = str(uuid.uuid4())

    with database_connection() as connection:
        category_id = connection.execute(
            "SELECT id FROM categories WHERE name = ?",
            (result.category.value,),
        ).fetchone()
        priority_id = connection.execute(
            "SELECT id FROM priorities WHERE name = ?",
            (result.priority.value,),
        ).fetchone()
        if category_id is None or priority_id is None:
            raise RuntimeError("Classification lookup values were not initialized.")

        connection.execute(
            """
            INSERT INTO support_requests (
                id, book, subject, description, category_id, priority_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                book,
                subject,
                description,
                category_id[0],
                priority_id[0],
            ),
        )
        connection.executemany(
            """
            INSERT INTO support_attachments
                (request_id, filename, content_type, content)
            VALUES (?, ?, ?, ?)
            """,
            [
                (request_id, filename, content_type, content)
                for filename, content_type, content in uploaded_files
            ],
        )

    return JSONResponse(
        status_code=201,
        content={
            "request_id": request_id,
            "message": "Your support request was submitted.",
            #"classification": {
            "category": result.category,
            "priority": result.priority,
            #"tags": result.tags,
            #"summary": result.summary,
       # },
    }
    )
    
