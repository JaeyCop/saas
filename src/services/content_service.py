import re
from collections import Counter
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel # For Pydantic schemas if not already imported for other reasons
from datetime import datetime # For Pydantic schemas
import json # For serializing dict/list to string for DB storage
from enum import Enum

from ..db import models as db_models # Import your SQLAlchemy models
from ..schemas.content_schemas import ( # Import all necessary request models from schemas
    TitleRequest,
    SEODescriptionRequest,
    BlogIdeasRequest,
    BlogOutlineRequest,
    FullBlogPostRequest,
    SEOFaqsRequest,
    SocialMediaPostsRequest
)
from .gemini_service import get_gemini_service, GeminiServiceError, Dict, Any # Import new service getter and error

# A basic list of common English stopwords.
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "should", "can", "could", "may", "might", "must",
    "and", "but", "or", "nor", "for", "so", "yet", "in", "on", "at", "by", "from", "to", "with",
    "about", "above", "after", "again", "against", "all", "am", "as", "because", "before",
    "below", "between", "both", "during", "each", "few", "further", "here", "how", "i", "if",
    "into", "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no", "not",
    "now", "of", "off", "once", "only", "other", "our", "ours", "ourselves", "out", "over",
    "own", "same", "she", "he", "him", "her", "his", "hers", "some", "such", "than", "that", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "too", "under", "until", "up", "very", "we", "what", "when", "where", "which",
    "while", "who", "whom", "why", "you", "your", "yours", "yourself", "yourselves"
}

# --- Pydantic Schemas for Content Responses (e.g., for history) ---
class GeneratedContentBase(BaseModel):
    content_type: str
    input_params: Optional[Dict[str, Any]] = None
    generated_text: str
    display_title: Optional[str] = None

class GeneratedContentResponse(GeneratedContentBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
# --- End Pydantic Schemas ---

def _clean_text_for_keywords(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    return words

def _save_generated_content(
    db: Session,
    user: db_models.User,
    content_type: str,
    input_params: Dict[str, Any],
    generated_text: str,
    display_title: Optional[str] = None
):
    """Helper function to save generated content to the database."""
    db_content = db_models.GeneratedContent(
        user_id=user.id,
        content_type=content_type,
        input_params=input_params, # This should be the request model dict
        generated_text=generated_text,
        display_title=display_title or (generated_text[:100] + "..." if len(generated_text) > 100 else generated_text) # Basic display title
    )
    db.add(db_content)
    db.commit()
    db.refresh(db_content)
    return db_content

def extract_keywords(text_content: str, num_keywords: int = 5) -> List[str]:
    if not text_content:
        return []
    words = _clean_text_for_keywords(text_content)
    filtered_words = [word for word in words if word not in STOPWORDS and len(word) > 2]
    if not filtered_words:
        return []
    word_counts = Counter(filtered_words)
    return [word for word, count in word_counts.most_common(num_keywords)]

async def generate_title(
    topic: str,
    keywords: Optional[List[str]] = None,
    style: str = "informative",
    tone: Optional[str] = None, # New parameter for tone
    generation_params: Optional[Dict[str, Any]] = None, # New parameter for Gemini settings
    db: Optional[Session] = None, # Add DB session
    user: Optional[db_models.User] = None, # Add current user
    request_data: Optional[TitleRequest] = None # Add original request data
) -> str:
    generated_title = None
    try:
        gemini = get_gemini_service() # This might raise HTTPException if GeminiService init fails
        prompt_parts = [f"Generate a compelling and {style} title for a piece of content about '{topic.strip()}'."]
        if keywords:
            prompt_parts.append(f"Try to naturally incorporate one or more of these keywords if relevant: {', '.join(keywords)}.")
        if tone:
            prompt_parts.append(f"The desired tone for the title is: {tone}.")
        prompt_parts.append("The title should be concise and engaging. Return only the title itself, without any extra conversational text or quotation marks.")
        prompt = " ".join(prompt_parts)
        api_response = await gemini.generate_content(prompt, params=generation_params)
        if api_response:
            generated_title = api_response.strip('"')
            
    except GeminiServiceError as e:
        print(f"Gemini service error during title generation: {e}. Using fallback.")
    except Exception as e: # Catch other potential errors from get_gemini_service or other issues
        print(f"Unexpected error during title generation: {e}. Using fallback.")

    if generated_title:
        if db and user and request_data:
            _save_generated_content(
                db=db,
                user=user,
                content_type="title",
                input_params=request_data.model_dump(),
                generated_text=generated_title,
                display_title=generated_title # For titles, the content itself is a good display title
            )
        return generated_title
    else: # Fallback logic
        topic_title = topic.strip().title()
        primary_keyword = keywords[0].title() if keywords and keywords[0] else ""
        if style == "informative":
            return f"{topic_title}: Understanding {primary_keyword}" if primary_keyword else f"A Comprehensive Guide to {topic_title}"
        return f"Content about: {topic_title}"

async def generate_seo_description(
    text_content: str,
    keywords: Optional[List[str]] = None,
    max_length: int = 160,
    generation_params: Optional[Dict[str, Any]] = None, # New parameter
    db: Optional[Session] = None,
    user: Optional[db_models.User] = None,
    request_data: Optional[SEODescriptionRequest] = None
) -> str:
    if not text_content:
        return "Discover more about this interesting topic."

    generated_desc = None
    try:
        gemini = get_gemini_service()
        # Use a reasonable snippet of text_content for the prompt to avoid overly long prompts
        content_snippet = text_content[:800] # Increased snippet size a bit
        if len(text_content) > 800: # Corrected condition to match snippet logic
            content_snippet += "..."

        prompt_parts = [
            f"Write an engaging SEO meta description for the following content. The description should be approximately {max_length} characters long (but not exceeding it by much)."
        ]
        if keywords:
            prompt_parts.append(f"If possible, naturally include some of these keywords: {', '.join(keywords)}.")
        prompt_parts.append(f"The content is about: '{content_snippet}'.")
        prompt_parts.append("The description should be a single, coherent paragraph. Return only the description itself, without any extra conversational text or quotation marks.")

        prompt = " ".join(prompt_parts)
        api_response = await gemini.generate_content(prompt, params=generation_params)
        if api_response:
            generated_desc = api_response.strip('"')[:max_length]
    except GeminiServiceError as e:
        print(f"Gemini service error during SEO description generation: {e}. Using fallback.")
    except Exception as e:
        print(f"Unexpected error during SEO description generation: {e}. Using fallback.")

    if generated_desc:
        if db and user and request_data:
            _save_generated_content(
                db=db,
                user=user,
                content_type="seo_description",
                input_params=request_data.model_dump(),
                generated_text=generated_desc,
                display_title=f"SEO Desc: {generated_desc[:70]}..." # A short preview for display
            )
        return generated_desc
    else: # Fallback logic
        return text_content[:max_length-3] + "..." if len(text_content) > max_length else text_content

def suggest_tags(topic: str, extracted_keywords: List[str]) -> List[str]:
    tags = set()
    topic_slug = re.sub(r'\s+', '-', topic.lower().strip())
    topic_slug = re.sub(r'[^\w-]', '', topic_slug)
    if topic_slug:
        tags.add(topic_slug)
    for kw in extracted_keywords:
        tags.add(kw.lower().replace(" ", "-"))
    return sorted(list(tags))

async def generate_blog_ideas(
    topic: str,
    num_ideas: int = 5,
    target_audience: Optional[str] = None,
    style: Optional[str] = None, # e.g., "how-to", "listicle", "thought-leadership"
    generation_params: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    user: Optional[db_models.User] = None,
    request_data: Optional[BlogIdeasRequest] = None
) -> List[str]:
    """Generates a list of blog post ideas based on a topic."""
    blog_ideas_list = []
    try:
        gemini = get_gemini_service()
        prompt_parts = [
            f"Generate a list of {num_ideas} engaging blog post ideas about '{topic.strip()}'."
        ]
        if target_audience:
            prompt_parts.append(f"The target audience for these blog posts is: {target_audience}.")
        if style:
            prompt_parts.append(f"The desired style for the blog ideas is: {style} (e.g., 'how-to guides', 'listicles', 'case studies', 'opinion pieces').")
        prompt_parts.append(
            "Each idea should be a concise and compelling title or a short concept suitable for a blog post."
        )
        prompt_parts.append(
            "Please format the output as a numbered list, with each idea on a new line. For example:\n1. First idea\n2. Second idea"
        )
        prompt = " ".join(prompt_parts)

        api_response = await gemini.generate_content(prompt, params=generation_params)

        if api_response:
            # Basic parsing: split by newline and strip numbering/whitespace
            ideas = api_response.strip().split('\n')
            for idea in ideas:
                cleaned_idea = re.sub(r'^\d+\.\s*', '', idea.strip()) # Remove "1. ", "2. ", etc.
                if cleaned_idea: # Avoid empty strings
                    blog_ideas_list.append(cleaned_idea)
    except GeminiServiceError as e:
        print(f"Gemini service error during blog idea generation: {e}. Returning empty list.")
    except Exception as e:
        print(f"Unexpected error during blog idea generation: {e}. Returning empty list.")
    
    # Fallback if no ideas generated or to ensure correct number if parsing is imperfect
    if not blog_ideas_list:
        return [f"Idea about {topic} - Style: {style or 'general'}" for _ in range(num_ideas)]
    
    if db and user and request_data and blog_ideas_list:
        ideas_text = "\n".join(blog_ideas_list)
        _save_generated_content(db, user, "blog_ideas", request_data.model_dump(), ideas_text, f"Blog Ideas: {topic}")
    return blog_ideas_list[:num_ideas] # Ensure we don't return more than requested

def _parse_markdown_outline(markdown_text: str) -> Dict[str, List[str]]:
    """
    Parses a markdown-like outline into a dictionary.
    Assumes section titles start with '## ' and bullet points with '- '.
    """
    outline = {}
    current_section_title = None
    lines = markdown_text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if line.startswith("## "):
            current_section_title = line[3:].strip()
            outline[current_section_title] = []
        elif line.startswith("- ") and current_section_title:
            point = line[2:].strip()
            if point: # Ensure the point is not empty
                outline[current_section_title].append(point)
        elif line and current_section_title and not outline[current_section_title]:
            # If a line under a section isn't a bullet, and no bullets yet, treat it as the first point (less strict)
            # This is a fallback for slightly off formatting from the AI
            outline[current_section_title].append(line)
            
    # Remove sections that ended up empty if any
    return {section: points for section, points in outline.items() if points or section.lower() in ["introduction", "conclusion"]}

async def generate_blog_outline(
    topic: str,
    num_sections: int = 5, # Approximate number of main sections
    target_audience: Optional[str] = None,
    style: Optional[str] = None, # e.g., "Comprehensive Guide", "Quick Tips"
    generation_params: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    user: Optional[db_models.User] = None,
    request_data: Optional[BlogOutlineRequest] = None
) -> Dict[str, List[str]]:
    """Generates a blog post outline for a given topic."""
    parsed_outline = {}
    try:
        gemini = get_gemini_service()
        prompt_parts = [
            f"Generate a detailed blog post outline for the topic: '{topic.strip()}'."
            f"The outline should have approximately {num_sections} main sections, including an introduction and a conclusion.",
            "For each main section, provide a clear title and 2-4 key bullet points or sub-topics to cover within that section."
        ]
        if target_audience:
            prompt_parts.append(f"The target audience is: {target_audience}.")
        if style:
            prompt_parts.append(f"The desired style of the blog post is: {style}.")
        prompt_parts.append(
            "Please format the output clearly. Main section titles should start with '## ' (e.g., '## Introduction'). Bullet points under each section should start with '- ' (e.g., '- Key point 1')."
        )
        prompt = "\n".join(prompt_parts) # Use newline for better prompt structure for the AI
        api_response = await gemini.generate_content(prompt, params=generation_params)
        if api_response:
            parsed_outline = _parse_markdown_outline(api_response)
    except GeminiServiceError as e:
        print(f"Gemini service error during blog outline generation: {e}. Returning empty outline.")
    except Exception as e:
        print(f"Unexpected error during blog outline generation: {e}. Returning empty outline.")
    
    if not parsed_outline: # Fallback
        return {"Introduction": [f"Introduce {topic}"], f"Main Body (Discuss {topic})": ["Point 1", "Point 2"], "Conclusion": [f"Conclude thoughts on {topic}"]}
    
    if db and user and request_data and parsed_outline:
        outline_text = json.dumps(parsed_outline, indent=2)
        _save_generated_content(db, user, "blog_outline", request_data.model_dump(), outline_text, f"Outline: {topic}")
    return parsed_outline

class BlogLength(str, Enum):
    SHORT = "short"      # ~300 words
    MEDIUM = "medium"    # ~600 words
    LONG = "long"       # ~1000 words

async def generate_full_blog_post(
    topic: str,
    target_audience: Optional[str] = None,
    style: Optional[str] = None,
    blog_length: BlogLength = BlogLength.MEDIUM,
    generation_params: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    user: Optional[db_models.User] = None,
    request_data: Optional[FullBlogPostRequest] = None
) -> str:
    """
    Generates a full blog post with specified length using token-based control.
    """
    generation_params = generation_params or {}
    
    # Calculate approximate section lengths based on blog length
    length_info = {
        BlogLength.SHORT: {'sections': 3, 'approx_words': 300},
        BlogLength.MEDIUM: {'sections': 4, 'approx_words': 600},
        BlogLength.LONG: {'sections': 5, 'approx_words': 1000}
    }

    config = length_info[blog_length]
    approx_words = config['approx_words']
    num_sections = config['sections']

    try:
        gemini = get_gemini_service()
        
        prompt = (
            f"Write a {blog_length.value} blog post (~{approx_words} words) about {topic}. "
            f"The post should have {num_sections} main sections including introduction and conclusion. "
        )
        
        if target_audience:
            prompt += f"Target audience: {target_audience}. "
        
        if style:
            prompt += f"Writing style: {style}. "
        
        prompt += (
            "Format the post in Markdown with appropriate headings, "
            "paragraphs, and section breaks. Make it engaging and well-structured."
        )

        response = await gemini.generate_content(
            prompt=prompt,
            params=generation_params
        )

        if not response:
            raise ValueError("Failed to generate blog post content")

        blog_post = response.strip()

        # Save to history if database and user are available
        if db and user and request_data:
            _save_generated_content(
                db=db,
                user=user,
                content_type="full_blog_post",
                input_params=request_data.model_dump(),
                generated_text=blog_post,
                display_title=f"Blog Post: {topic[:50]}..."
            )

        return blog_post

    except Exception as e:
        print(f"Unexpected error during blog post generation: {e}")
        return f"Error generating blog post about {topic}. Please try again."

def _parse_faqs(faq_text: str) -> List[Dict[str, str]]:
    """
    Parses text containing Q&A pairs into a list of dictionaries.
    Assumes questions start with 'Q:' or 'Question:' and answers with 'A:' or 'Answer:'.
    """
    faqs = []
    lines = faq_text.strip().split('\n')
    current_q = None
    current_a = None

    for line in lines:
        line = line.strip()
        if line.lower().startswith("q:") or line.lower().startswith("question:"):
            if current_q and current_a: # Save previous Q&A
                faqs.append({"question": current_q.strip(), "answer": current_a.strip()})
            current_q = re.sub(r'^(q:|question:)\s*', '', line, flags=re.IGNORECASE).strip()
            current_a = "" # Reset answer
        elif line.lower().startswith("a:") or line.lower().startswith("answer:"):
            if current_q: # Only start an answer if there's a current question
                current_a = re.sub(r'^(a:|answer:)\s*', '', line, flags=re.IGNORECASE).strip()
        elif current_a is not None: # Append to current answer if it's multi-line
            current_a += " " + line.strip()
    
    if current_q and current_a: # Save the last Q&A pair
        faqs.append({"question": current_q.strip(), "answer": current_a.strip()})
        
    return faqs

async def generate_seo_faqs(
    topic: str,
    num_faqs: int = 5,
    content_snippet: Optional[str] = None, # Optional existing content to base FAQs on
    generation_params: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    user: Optional[db_models.User] = None,
    request_data: Optional[SEOFaqsRequest] = None
) -> List[Dict[str, str]]:
    """Generates a list of SEO-friendly FAQs (question and answer pairs)."""
    parsed_faqs = []
    try:
        gemini = get_gemini_service()
        prompt_parts = [
            f"Generate a list of {num_faqs} frequently asked questions (FAQs) and their concise answers related to the topic: '{topic.strip()}'."
        ]
        if content_snippet:
            prompt_parts.append(f"Consider the following content snippet for context: \"{content_snippet[:500]}...\"")
        prompt_parts.append("Format each FAQ with 'Q: [Question]' followed by 'A: [Answer]' on new lines. Ensure answers are informative yet brief, suitable for an FAQ section aimed at improving SEO.")
        prompt = "\n".join(prompt_parts)
        api_response = await gemini.generate_content(prompt, params=generation_params)
        if api_response:
            parsed_faqs = _parse_faqs(api_response)
    except GeminiServiceError as e:
        print(f"Gemini service error during FAQ generation: {e}. Returning empty list.")
    except Exception as e:
        print(f"Unexpected error during FAQ generation: {e}. Returning empty list.")
    
    if not parsed_faqs: # Fallback
        return [{"question": f"What is {topic}?", "answer": f"Learn more about {topic} here."} for _ in range(num_faqs)]
    
    if db and user and request_data and parsed_faqs:
        faqs_text = json.dumps(parsed_faqs, indent=2)
        _save_generated_content(db, user, "seo_faqs", request_data.model_dump(), faqs_text, f"FAQs: {topic}")
    return parsed_faqs[:num_faqs]

def _parse_social_media_posts(text_response: str) -> List[str]:
    """
    Parses a block of text containing multiple social media posts.
    Assumes posts are separated by one or more newlines or are numbered.
    """
    posts = []
    # Attempt to split by common delimiters or numbering
    potential_posts = re.split(r'\n\s*\n|^\d+\.\s*', text_response, flags=re.MULTILINE)
    for post_text in potential_posts:
        cleaned_post = post_text.strip()
        if cleaned_post: # Ensure the post is not just whitespace
            posts.append(cleaned_post)
    
    # If the above split doesn't work well and we have a single block,
    # and it looks like a list of items separated by single newlines.
    if len(posts) <= 1 and '\n' in text_response:
        posts = [p.strip() for p in text_response.strip().split('\n') if p.strip()]

    return posts

async def generate_social_media_posts(
    topic: Optional[str] = None,
    content_snippet: Optional[str] = None,
    platform: str = "General", # e.g., "Twitter", "LinkedIn", "Facebook", "Instagram"
    num_posts: int = 3,
    tone: Optional[str] = None, # e.g., "Professional", "Witty", "Inspirational"
    call_to_action: Optional[str] = None,
    include_hashtags: bool = True,
    generation_params: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    user: Optional[db_models.User] = None,
    request_data: Optional[SocialMediaPostsRequest] = None
) -> List[str]:
    """Generates a list of social media posts."""
    if not topic and not content_snippet:
        raise ValueError("Either topic or content_snippet must be provided.")

    generated_posts_list = []
    try:
        gemini = get_gemini_service()
        prompt_parts = [f"Generate {num_posts} engaging social media posts for the {platform} platform."]
        if topic:
            prompt_parts.append(f"The posts should be about the topic: '{topic.strip()}'.")
        if content_snippet:
            prompt_parts.append(f"Base the posts on the following content snippet (extract key messages): \"{content_snippet[:700]}...\"")
        if tone:
            prompt_parts.append(f"The desired tone is: {tone}.")
        if call_to_action:
            prompt_parts.append(f"Each post should ideally include or lead to this call to action: '{call_to_action}'.")
        if include_hashtags:
            prompt_parts.append("Include 2-3 relevant hashtags for each post.")
        prompt_parts.append(f"Ensure each post is concise and suitable for {platform}. Format the output as a list of posts, each on a new line or numbered.")
        prompt = "\n".join(prompt_parts)
        api_response = await gemini.generate_content(prompt, params=generation_params)
        if api_response:
            generated_posts_list = _parse_social_media_posts(api_response)
    except GeminiServiceError as e:
        print(f"Gemini service error during social media post generation: {e}. Returning empty list.")
    except Exception as e:
        print(f"Unexpected error during social media post generation: {e}. Returning empty list.")

    if not generated_posts_list: # Fallback
        base_text = topic or "your amazing content"
        return [f"Check out our latest on {base_text}! #{platform.lower()} #{base_text.replace(' ','').lower()}" for _ in range(num_posts)]
    
    if db and user and request_data and generated_posts_list:
        posts_text = "\n\n---\n\n".join(generated_posts_list)
        display_title = f"Social Posts for {platform}: {topic or 'General Content'}"
        _save_generated_content(db, user, "social_media_posts", request_data.model_dump(), posts_text, display_title)
    return generated_posts_list[:num_posts]

# --- Content History Service Functions ---

def get_user_content_history(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 100
) -> List[GeneratedContentResponse]:
    """
    Retrieves a list of generated content for a specific user with pagination.
    Currently returns all history for testing without auth. Reimplement user-specific history later.
    """
    return db.query(db_models.GeneratedContent) \
        .order_by(db_models.GeneratedContent.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

def get_generated_content_item_by_id(db: Session, item_id: int) -> Optional[db_models.GeneratedContent]:
    """
    Retrieves a single piece of generated content by its ID.
    No user check now, will be added back later.
    """
    return db.query(db_models.GeneratedContent) \
        .filter(db_models.GeneratedContent.id == item_id) \
        .first()


# Example Usage (optional, can be removed or kept for direct testing of this service)
# Note: This __main__ block will need to be run with asyncio if testing async functions directly.
if __name__ == '__main__':
    import asyncio

    async def main_test():
        print("--- Testing Content Service ---")
        # Note: get_gemini_service() might raise HTTPException if GEMINI_API_KEY is not set or invalid
        # This simple test won't handle that gracefully without a running FastAPI app context.
        # For direct script testing, you might need to temporarily adjust how GeminiService is instantiated or mocked.
        sample_text = "FastAPI is a modern, fast web framework for building APIs with Python."
        sample_topic = "FastAPI Framework"
        kws = extract_keywords(sample_text, 3)
        print(f"Keywords: {kws}")
        print(f"Title (informative): {await generate_title(sample_topic, kws, 'informative')}")
        print(f"Title (catchy): {await generate_title(sample_topic, kws, 'very catchy')}")
        print(f"SEO Desc: {await generate_seo_description(sample_text, kws)}")
        print(f"\nBlog Ideas: {await generate_blog_ideas(sample_topic, num_ideas=3, style='listicle')}")
        print(f"\nBlog Outline for '{sample_topic}': {await generate_blog_outline(sample_topic, num_sections=4)}")
        # print(f"\nFull Blog Post for '{sample_topic}':\n{await generate_full_blog_post(sample_topic, style='Informative Tutorial', num_sections_for_outline=3)}") # Commented out for quicker testing
        print(f"\nSEO FAQs for '{sample_topic}': {await generate_seo_faqs(sample_topic, num_faqs=3)}")
        print(f"\nSocial Media Posts for '{sample_topic}' (Twitter): {await generate_social_media_posts(topic=sample_topic, platform='Twitter', num_posts=2, tone='punchy')}")
        print(f"Tags: {suggest_tags(sample_topic, kws)}")

    asyncio.run(main_test())