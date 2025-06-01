import os
from typing import Optional, Dict, Any # Ensure Dict and Any are imported
import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai.types import GenerationConfig # Import GenerationConfig
from fastapi import HTTPException
from functools import lru_cache

class GeminiServiceError(Exception):
    """Custom exception for Gemini service errors"""
    pass

class GeminiService:
    def __init__(self):
        load_dotenv()
        self.api_key = self._validate_api_key()
        self._configure_gemini()
        self.model = self._get_model()

    @staticmethod
    def _validate_api_key() -> str:
        """Validate Gemini API key existence and format"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiServiceError("Gemini API key not found in environment variables")
        if not isinstance(api_key, str) or len(api_key) < 10:
            raise GeminiServiceError("Invalid Gemini API key format")
        return api_key

    def _configure_gemini(self) -> None:
        """Configure Gemini API with validated key"""
        try:
            genai.configure(api_key=self.api_key)
        except Exception as e:
            raise GeminiServiceError(f"Failed to configure Gemini API: {str(e)}")

    def _get_model(self) -> Any:
        """Initialize and return Gemini model"""
        try:
            return genai.GenerativeModel('gemini-1.5-flash-latest') # Use a more specific/current model
        except Exception as e:
            raise GeminiServiceError(f"Failed to initialize Gemini model: {str(e)}")

    async def generate_content(self, prompt: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate content using Gemini API
        
        Args:
            prompt: The input prompt for content generation
            params: Optional parameters for generation (temperature, max_tokens, etc.)
        
        Returns:
            Generated content as string
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty")

        default_params = {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 2048,
        }

        generation_params = {**default_params, **(params or {})}

        config = GenerationConfig(**generation_params) # Create GenerationConfig object

        try:
            response = await self.model.generate_content_async(
                prompt, generation_config=config # Pass the GenerationConfig object
            )
            return response.text
        except Exception as e:
            raise GeminiServiceError(f"Content generation failed: {str(e)}")

    async def is_api_healthy(self) -> bool:
        """Check if the Gemini API is responsive and properly configured"""
        try:
            response = await self.generate_content("Test connection")
            return bool(response)
        except Exception:
            return False

@lru_cache()
def get_gemini_service() -> GeminiService:
    """Singleton instance of GeminiService"""
    try:
        return GeminiService()
    except GeminiServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))