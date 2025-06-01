from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

# --- Request and Response Models for Content Generation ---

class TitleRequest(BaseModel):
    topic: str
    keywords: Optional[List[str]] = None
    style: str = "informative"
    tone: Optional[str] = None
    generation_params: Optional[Dict[str, Any]] = None

class TitleResponse(BaseModel):
    generated_title: str

class SEODescriptionRequest(BaseModel):
    text_content: str
    keywords: Optional[List[str]] = None
    max_length: int = 160
    generation_params: Optional[Dict[str, Any]] = None

class SEODescriptionResponse(BaseModel):
    seo_description: str

class KeywordsRequest(BaseModel):
    text_content: str
    num_keywords: int = 5

class KeywordsResponse(BaseModel):
    extracted_keywords: List[str]

class TagsRequest(BaseModel):
    topic: str
    extracted_keywords: List[str]

class TagsResponse(BaseModel):
    suggested_tags: List[str]

class BlogIdeasRequest(BaseModel):
    topic: str
    num_ideas: int = 5
    target_audience: Optional[str] = None
    style: Optional[str] = None
    generation_params: Optional[Dict[str, Any]] = None

class BlogIdeasResponse(BaseModel):
    blog_ideas: List[str]

class BlogOutlineRequest(BaseModel):
    topic: str
    num_sections: int = 5
    target_audience: Optional[str] = None
    style: Optional[str] = None
    generation_params: Optional[Dict[str, Any]] = None

class BlogOutlineResponse(BaseModel):
    blog_outline: Dict[str, List[str]] # Or a more structured Pydantic model for outline sections

class BlogLength(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"

class FullBlogPostRequest(BaseModel):
    topic: str
    target_audience: Optional[str] = None
    style: Optional[str] = None
    blog_length: BlogLength = BlogLength.MEDIUM
    generation_params: Optional[Dict[str, Any]] = None

class FullBlogPostResponse(BaseModel):
    full_blog_post: str

class SEOFaqItem(BaseModel): # This can stay here or move to a more general schema file if used elsewhere
    question: str
    answer: str

class SEOFaqsRequest(BaseModel):
    topic: str
    num_faqs: int = 3
    content_snippet: Optional[str] = None
    style: Optional[str] = None
    generation_params: Optional[Dict[str, Any]] = None

class SEOFaqsResponse(BaseModel):
    faqs: List[SEOFaqItem]

class SocialMediaPostsRequest(BaseModel):
    topic: Optional[str] = None
    content_snippet: Optional[str] = None
    platform: str = "General"
    num_posts: int = 3
    tone: Optional[str] = None
    call_to_action: Optional[str] = None
    include_hashtags: bool = True
    generation_params: Optional[Dict[str, Any]] = None

class SocialMediaPostsResponse(BaseModel):
    social_media_posts: List[str]