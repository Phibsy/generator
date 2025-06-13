# backend/app/services/content_generation.py
"""
🤖 REELS GENERATOR - Content Generation Service
OpenAI GPT-4 integration for automated script generation and content optimization
"""

import openai
from typing import List, Dict, Any, Optional
import json
import re
from datetime import datetime
import logging

from ..config import settings
from ..schemas import ContentGenerationRequest, ContentGenerationResponse

logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai.api_key = settings.OPENAI_API_KEY

class ContentGenerationService:
    """Service for AI-powered content generation"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
    # ========================================================================
    # STORY GENERATION
    # ========================================================================
    
    async def generate_story(self, request: ContentGenerationRequest) -> ContentGenerationResponse:
        """Generate complete video script with GPT-4"""
        
        try:
            # Build the prompt for GPT-4
            prompt = self._build_story_prompt(request)
            
            # Call GPT-4
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            content_data = json.loads(response.choices[0].message.content)
            
            # Validate and clean the script
            script = self._validate_script(content_data.get("script", ""), request.duration)
            
            # Generate hashtags if not provided
            hashtags = content_data.get("hashtags", [])
            if not hashtags:
                hashtags = await self.generate_hashtags(request.topic, request.target_audience)
            
            # Calculate content score
            content_score = self._calculate_content_score(script, hashtags, request)
            
            return ContentGenerationResponse(
                script=script,
                hashtags=hashtags[:30],  # Limit to 30 hashtags
                suggested_title=content_data.get("title", self._generate_title(request.topic)),
                estimated_duration=self._estimate_duration(script),
                content_score=content_score
            )
            
        except Exception as e:
            logger.error(f"💥 Content generation failed: {e}")
            raise
    
    # ========================================================================
    # HASHTAG GENERATION
    # ========================================================================
    
    async def generate_hashtags(self, topic: str, target_audience: str) -> List[str]:
        """Generate optimized hashtags for social media"""
        
        try:
            prompt = f"""
            Generate 30 viral hashtags for a video about "{topic}" targeting {target_audience}.
            
            Include:
            - 10 high-volume hashtags (1M+ posts)
            - 10 medium-volume hashtags (100K-1M posts)
            - 10 niche hashtags (under 100K posts)
            
            Format: Return as JSON array of hashtags without #
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a social media expert specializing in hashtag optimization."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            hashtag_data = json.loads(response.choices[0].message.content)
            hashtags = hashtag_data.get("hashtags", [])
            
            # Clean and validate hashtags
            cleaned_hashtags = []
            for tag in hashtags:
                clean_tag = re.sub(r'[^a-zA-Z0-9]', '', tag)
                if clean_tag and len(clean_tag) <= 30:
                    cleaned_hashtags.append(clean_tag.lower())
            
            return cleaned_hashtags[:30]
            
        except Exception as e:
            logger.error(f"💥 Hashtag generation failed: {e}")
            # Return fallback hashtags
            return ["viral", "fyp", "trending", "shorts", "reels"]
    
    # ========================================================================
    # CONTENT QUALITY ANALYZER
    # ========================================================================
    
    async def analyze_content_quality(self, script: str, topic: str) -> Dict[str, Any]:
        """Analyze content quality and provide improvement suggestions"""
        
        try:
            prompt = f"""
            Analyze this video script for quality and virality potential:
            
            Topic: {topic}
            Script: {script}
            
            Provide analysis in JSON format with:
            - engagement_score (0-1)
            - hook_strength (0-1)
            - clarity_score (0-1)
            - emotion_score (0-1)
            - cta_effectiveness (0-1)
            - improvement_suggestions (array of strings)
            - viral_potential (low/medium/high)
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a content strategist analyzing video scripts for maximum engagement."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            return analysis
            
        except Exception as e:
            logger.error(f"💥 Content analysis failed: {e}")
            return {
                "engagement_score": 0.5,
                "hook_strength": 0.5,
                "clarity_score": 0.5,
                "emotion_score": 0.5,
                "cta_effectiveness": 0.5,
                "improvement_suggestions": [],
                "viral_potential": "medium"
            }
    
    # ========================================================================
    # CONTENT VARIATIONS
    # ========================================================================
    
    async def generate_variations(self, original_script: str, num_variations: int = 3) -> List[str]:
        """Generate variations of a script for A/B testing"""
        
        variations = []
        
        for i in range(num_variations):
            try:
                prompt = f"""
                Create a variation of this video script maintaining the core message but with:
                - Different hook (first 3 seconds)
                - Slightly different tone
                - Alternative call-to-action
                
                Original script: {original_script}
                
                Return only the new script.
                """
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a creative copywriter specializing in short-form video content."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.9,
                    max_tokens=800
                )
                
                variations.append(response.choices[0].message.content)
                
            except Exception as e:
                logger.error(f"💥 Variation generation failed: {e}")
                continue
        
        return variations
    
    # ========================================================================
    # TREND INTEGRATION
    # ========================================================================
    
    async def integrate_trends(self, script: str, platform: str) -> str:
        """Update script to include current trends"""
        
        try:
            prompt = f"""
            Update this script to incorporate current {platform} trends while maintaining the message:
            
            Original script: {script}
            
            Consider:
            - Trending sounds/music references
            - Popular phrases or memes
            - Current events (if relevant)
            - Platform-specific features
            
            Return the updated script.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a {platform} content expert who stays current with trends."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"💥 Trend integration failed: {e}")
            return script  # Return original if fails
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for content generation"""
        return """
        You are an expert viral content creator specializing in short-form video scripts.
        You create engaging, concise content optimized for YouTube Shorts, Instagram Reels, and TikTok.
        
        Your scripts always:
        - Start with a strong hook in the first 3 seconds
        - Use simple, conversational language
        - Include emotional triggers
        - End with a clear call-to-action
        - Are perfectly timed for the requested duration
        
        You understand platform algorithms and create content that maximizes engagement.
        """
    
    def _build_story_prompt(self, request: ContentGenerationRequest) -> str:
        """Build the prompt for story generation"""
        return f"""
        Create a {request.duration}-second video script about "{request.topic}" for {request.target_audience}.
        
        Style: {request.video_style}
        Tone: {request.tone}
        Include CTA: {request.include_call_to_action}
        
        Requirements:
        1. Hook viewers in first 3 seconds
        2. Maintain high energy throughout
        3. Use natural speech patterns
        4. Include 1-2 emotional peaks
        5. End with clear next step
        
        Return as JSON with:
        {{
            "title": "Catchy video title",
            "script": "The complete script with timing markers",
            "hashtags": ["relevant", "hashtags", "without", "hash"]
        }}
        """
    
    def _validate_script(self, script: str, target_duration: int) -> str:
        """Validate and adjust script for target duration"""
        
        # Remove extra whitespace
        script = re.sub(r'\s+', ' ', script).strip()
        
        # Estimate current duration (average 2.5 words per second)
        word_count = len(script.split())
        estimated_duration = word_count / 2.5
        
        # Adjust if needed
        if estimated_duration > target_duration + 5:
            # Script too long - trim
            target_words = int(target_duration * 2.5)
            words = script.split()[:target_words]
            script = ' '.join(words) + "..."
        
        return script
    
    def _estimate_duration(self, script: str) -> int:
        """Estimate script duration in seconds"""
        word_count = len(script.split())
        return int(word_count / 2.5)  # Average speaking rate
    
    def _calculate_content_score(self, script: str, hashtags: List[str], request: ContentGenerationRequest) -> float:
        """Calculate overall content quality score"""
        
        score = 0.0
        
        # Hook strength (check first sentence)
        first_sentence = script.split('.')[0]
        if any(word in first_sentence.lower() for word in ['you', 'your', 'stop', 'wait', 'look']):
            score += 0.2
        
        # Emotional words
        emotional_words = ['amazing', 'incredible', 'shocking', 'unbelievable', 'secret', 'never', 'always']
        emotional_count = sum(1 for word in emotional_words if word in script.lower())
        score += min(0.2, emotional_count * 0.05)
        
        # Question usage
        if '?' in script:
            score += 0.1
        
        # CTA presence
        cta_phrases = ['comment', 'share', 'follow', 'like', 'subscribe', 'click', 'swipe']
        if any(phrase in script.lower() for phrase in cta_phrases):
            score += 0.2
        
        # Hashtag quality
        if len(hashtags) >= 20:
            score += 0.1
        if len(hashtags) >= 25:
            score += 0.1
        
        # Length appropriateness
        word_count = len(script.split())
        target_words = request.duration * 2.5
        if abs(word_count - target_words) < 20:
            score += 0.1
        
        return min(1.0, score)
    
    def _generate_title(self, topic: str) -> str:
        """Generate a fallback title"""
        return f"Amazing Facts About {topic.title()} You Need to Know!"

# ============================================================================
# CONTENT TEMPLATES
# ============================================================================

class ContentTemplates:
    """Pre-defined templates for different content types"""
    
    EDUCATIONAL = {
        "intro": "Did you know that {topic}? Here's what you need to know...",
        "body": "First, {point1}. Second, {point2}. Finally, {point3}.",
        "outro": "Follow for more {topic} tips! What surprised you most? Comment below!"
    }
    
    ENTERTAINMENT = {
        "intro": "POV: You just discovered {topic} and your mind is blown 🤯",
        "body": "Imagine {scenario}. But wait, it gets better... {twist}",
        "outro": "Wait for part 2! Share this with someone who needs to see it!"
    }
    
    GAMING = {
        "intro": "This {topic} trick will change your game forever!",
        "body": "Step 1: {action1}. Step 2: {action2}. Watch what happens next...",
        "outro": "GG! Drop a 🔥 if this helped you! More tips coming tomorrow!"
    }

# Initialize service
content_service = ContentGenerationService()
