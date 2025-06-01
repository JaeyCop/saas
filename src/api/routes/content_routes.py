from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging  # Add this import

# Add logger configuration
logger = logging.getLogger(__name__)

from ...services import content_service # Removed enforce_api_limit import
from ...db.database import get_db
from ...db import models as db_models
from ...schemas.content_schemas import (
    BlogLength,
    TitleRequest,
    TitleResponse,
    SEODescriptionRequest,
    SEODescriptionResponse,
    KeywordsRequest,
    KeywordsResponse,
    TagsRequest,
    TagsResponse,
    BlogIdeasRequest,
    BlogIdeasResponse,
    BlogOutlineRequest,
    BlogOutlineResponse,
    FullBlogPostRequest,
    FullBlogPostResponse,
    SEOFaqsRequest,
    SEOFaqsResponse,
    SocialMediaPostsRequest,
    SocialMediaPostsResponse
)
 
router = APIRouter()

# --- Endpoints ---

@router.post("/generate-title", response_model=TitleResponse, tags=["Content Generation"])
async def generate_title_endpoint(
    request: TitleRequest,
    db: Session = Depends(get_db) # Remove dependency
):
    title = await content_service.generate_title(
        topic=request.topic,
        keywords=request.keywords,
        style=request.style,
        tone=request.tone,
        generation_params=request.generation_params,
        db=db,
        user=None,  # Pass None for user since auth is removed
        request_data=request,
    )
    return {"generated_title": title}

# Note: All content generation endpoints below follow the same pattern
# of removing the enforce_api_limit dependency and passing user=None.
# For brevity, I'll only show the diff for the first one and summarize the rest.
# Remember to apply the same change to all other endpoints.


@router.post(
    "/generate-seo-description",
    response_model=SEODescriptionResponse,
    tags=["Content Generation"]
)
async def generate_seo_description(
    request: SEODescriptionRequest,
    db: Session = Depends(get_db)
):
    try:
        generated_text = await content_service.generate_seo_description(
            text_content=request.text_content,
            db=db
        )
        
        if not generated_text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate SEO description"
            )
            
        # Update this line to match the response model field name
        return {"seo_description": generated_text}
        
    except Exception as e:
        logger.error(f"Error generating SEO description: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/extract-keywords", response_model=KeywordsResponse, tags=["Content Generation"])
async def extract_keywords_endpoint(
    request: KeywordsRequest,
    # db: Session = Depends(get_db), # No database interaction in this function for now
    # current_user: db_models.User = Depends(enforce_api_limit) # No authentication needed
):
    keywords = content_service.extract_keywords(
        text_content=request.text_content,
        num_keywords=request.num_keywords
    )
    return {"extracted_keywords": keywords}


@router.post("/suggest-tags", response_model=TagsResponse, tags=["Content Generation"])
async def suggest_tags_endpoint(
    request: TagsRequest,
    # db: Session = Depends(get_db), # No database interaction in this function
    # current_user: db_models.User = Depends(enforce_api_limit) # No authentication needed
):
    tags = content_service.suggest_tags(
        topic=request.topic,
        extracted_keywords=request.extracted_keywords
    )
    return {"suggested_tags": tags}


@router.post("/generate-blog-ideas", response_model=BlogIdeasResponse, tags=["Content Generation"])
async def generate_blog_ideas_endpoint(
    request: BlogIdeasRequest,
    db: Session = Depends(get_db), # Database interaction
    # current_user: db_models.User = Depends(enforce_api_limit) # No authentication needed
):
    ideas = await content_service.generate_blog_ideas(
        topic=request.topic,
        num_ideas=request.num_ideas,
        target_audience=request.target_audience,
        style=request.style,
        generation_params=request.generation_params,
        db=db,
        user=None, # No user authentication
        request_data=request
    )
    return {"blog_ideas": ideas}


@router.post("/generate-blog-outline", response_model=BlogOutlineResponse, tags=["Content Generation"])
async def generate_blog_outline_endpoint(
    request: BlogOutlineRequest,
    db: Session = Depends(get_db), # Database interaction
    # current_user: db_models.User = Depends(enforce_api_limit) # No authentication needed
):
    outline = await content_service.generate_blog_outline(
        topic=request.topic,
        num_sections=request.num_sections,
        target_audience=request.target_audience,
        style=request.style,
        generation_params=request.generation_params,
        db=db,
        user=None, # No user authentication
        request_data=request
    )
    return {"blog_outline": outline}


@router.post("/generate-full-blog-post", response_model=FullBlogPostResponse, tags=["Content Generation"])
async def generate_full_blog_post_endpoint(
    request: FullBlogPostRequest,
    db: Session = Depends(get_db)
):
    # Map blog length to approximate token counts instead of word counts
    length_mapping = {
        BlogLength.SHORT: {'max_output_tokens': 500},  # ~300 words
        BlogLength.MEDIUM: {'max_output_tokens': 1000},  # ~600 words
        BlogLength.LONG: {'max_output_tokens': 1700}   # ~1000 words
    }

    # Add the configuration to generation params
    generation_params = request.generation_params or {}
    generation_params.update(length_mapping[request.blog_length])

    blog_post = await content_service.generate_full_blog_post(
        topic=request.topic,
        target_audience=request.target_audience,
        style=request.style,
        blog_length=request.blog_length,  # Pass the blog_length enum
        generation_params=generation_params,
        db=db,
        user=None,
        request_data=request
    )
    return {"full_blog_post": blog_post}


@router.post("/generate-seo-faqs", response_model=SEOFaqsResponse, tags=["Content Generation"])
async def generate_seo_faqs_endpoint(
    request: SEOFaqsRequest,
    db: Session = Depends(get_db), # Database interaction
    # current_user: db_models.User = Depends(enforce_api_limit) # No authentication needed
):
    faqs_list = await content_service.generate_seo_faqs(
        topic=request.topic,
        num_faqs=request.num_faqs,
        content_snippet=request.content_snippet,
        style=request.style,
        generation_params=request.generation_params,
        db=db,
        user=None, # No user authentication
        request_data=request
    )
    return {"faqs": faqs_list}


@router.post("/generate-social-media-posts", response_model=SocialMediaPostsResponse, tags=["Content Generation"])
async def generate_social_media_posts_endpoint(
    request: SocialMediaPostsRequest,
    db: Session = Depends(get_db), # Database interaction
    # current_user: db_models.User = Depends(enforce_api_limit) # No authentication needed
):
    if not request.topic and not request.content_snippet:
        raise HTTPException(status_code=400, detail="Either 'topic' or 'content_snippet' must be provided.")
    
    posts = await content_service.generate_social_media_posts(
        topic=request.topic,
        content_snippet=request.content_snippet,
        platform=request.platform,
        num_posts=request.num_posts,
        tone=request.tone,
        call_to_action=request.call_to_action,
        include_hashtags=request.include_hashtags,
        generation_params=request.generation_params,
        db=db,
        user=None, # No user authentication
        request_data=request
    )
    return {"social_media_posts": posts}

# --- History Endpoints (Require user ID for retrieval, but no longer enforced by auth) ---

@router.get("/history", response_model=List[content_service.GeneratedContentResponse], tags=["Content Generation", "History"])
async def read_user_content_history(
    skip: int = 0,
    limit: int = 20, # Default to 20 items per page
    db: Session = Depends(get_db),
    # current_user: db_models.User = Depends(get_current_user)  # No authentication needed
):
    """
    Retrieve (all) generated content history (currently unprotected).
    """
    if limit > 100: # Optional: cap the limit
        limit = 100
    # Pass a placeholder user ID (or retrieve a default user)
    #  Remember to re-implement proper user-specific history when auth is back!
    history_items = content_service.get_user_content_history(db=db, user_id=1, skip=skip, limit=limit)
    return history_items

@router.get("/history/{item_id}", response_model=content_service.GeneratedContentResponse, tags=["Content Generation", "History"])
async def read_user_content_item(
    item_id: int,
    db: Session = Depends(get_db),
    # current_user: db_models.User = Depends(get_current_user)  # No authentication needed
):
    # Pass a placeholder user ID (or retrieve a default user)
    #  Remember to re-implement proper user-specific history when auth is back!
    history_item = content_service.get_generated_content_item_by_id(db=db, item_id=item_id) # Removed user_id since it's no longer filtering by user.
    if not history_item:
        raise HTTPException(status_code=404, detail="Content item not found") # Removed "or access denied"
    return history_item
