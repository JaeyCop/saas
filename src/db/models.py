from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship, declarative_base # Updated import
from sqlalchemy.sql import func # For default datetime
from datetime import timezone # For timezone-aware datetimes
from ..core.config import settings # To get default tier

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True) # Can be nullable if Supabase is primary
    hashed_password = Column(String(128), nullable=True) # Nullable for Supabase social logins
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    subscription_tier = Column(String(50), default=settings.DEFAULT_SUBSCRIPTION_TIER, nullable=False)

    # API Usage Tracking Fields
    api_call_count = Column(Integer, default=0, nullable=False)
    monthly_api_limit = Column(Integer, default=1000, nullable=False) # Default limit
    api_limit_reset_at = Column(DateTime(timezone=True), nullable=True)
    # Email Verification Fields
    is_email_verified = Column(Boolean, default=False, nullable=True) # Supabase might handle this
    email_verification_token = Column(String, unique=True, index=True, nullable=True) # May become obsolete
    email_verification_token_expires_at = Column(DateTime(timezone=True), nullable=True) # May become obsolete
    # Password Reset Fields
    password_reset_token = Column(String, unique=True, index=True, nullable=True) # May become obsolete
    password_reset_token_expires_at = Column(DateTime(timezone=True), nullable=True) # May become obsolete

    # Supabase Integration
    supabase_user_id = Column(String, unique=True, index=True, nullable=True)
    
    # Relationship to Content model
    generated_contents = relationship("GeneratedContent", back_populates="owner")

class GeneratedContent(Base): # Renamed from Content for clarity
    __tablename__ = 'generated_content'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    content_type = Column(String(50), index=True, nullable=False) # e.g., "title", "seo_description", "blog_post"
    
    input_params = Column(JSON, nullable=True) # Store the request parameters (topic, keywords, style, etc.)
    generated_text = Column(Text, nullable=False) # The actual generated content
    
    # Optional: Store a short title or summary for easier display in lists
    display_title = Column(String(255), nullable=True) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="generated_contents")