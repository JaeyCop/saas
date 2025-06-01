from fastapi import FastAPI
from .api.routes import auth_routes, content_routes, users, subscription_routes # Added subscription_routes
from .db.database import create_db_and_tables # Import the function
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

app = FastAPI(
    title="SaaS Content Generator API", # Added title here
    description="API for generating various types of content using AI.",
    version="0.1.0"
)

# CORS Middleware Configuration
# Adjust allow_origins to be more restrictive in production
origins = [
    "http://localhost",         # Allow requests from localhost (any port)
    "http://localhost:5173",    # Specifically for your Vite frontend dev server
    "http://127.0.0.1",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # or ["*"] for development, but be more specific for production
    allow_credentials=True,
    allow_methods=["*"],    # Allows all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],    # Allows all headers
)

# # Create database tables on startup (Now handled by Alembic)
# @app.on_event("startup")
# async def on_startup():
#     print("Database schema management is now handled by Alembic.")
#     # create_db_and_tables() # This line is commented out or removed
#     # print("Database tables created (if they didn't exist).")

# Include routers
# app.include_router(auth_routes.router, prefix="/auth", tags=["Authentication"])  # Removed auth router
app.include_router(content_routes.router, prefix="/content", tags=["Content Generation"])
app.include_router(users.router, prefix="/users", tags=["Users"]) # Use the corrected users module
app.include_router(subscription_routes.router, prefix="/subscriptions", tags=["Subscriptions"])

@app.get("/")
async def read_root():
    return {"message": "Welcome to the SaaS Content Generator API!"}