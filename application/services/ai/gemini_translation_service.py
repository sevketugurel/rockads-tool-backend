import os
import asyncio
import time
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

import google.generativeai as genai
from moviepy.editor import VideoFileClip
from PIL import Image

from application.services.ai.translation_service import TranslationService
from application.services.ai.elevenlabs_tts_service import ElevenLabsTTSService
from application.services.video.video_processing_service import VideoProcessingService
from domain.entities.translation import (
    Translation,
    TranslationSegment,
    TranslationStatus,
    VideoSceneContext,
    CulturalAdaptation
)
from domain.entities.country import Country
from core.config.settings import settings

logger = logging.getLogger(__name__)


class GeminiTranslationService(TranslationService):
    """Google Gemini implementation of sophisticated translation service"""

    def __init__(self):
        """Initialize Gemini client with TTS and video processing"""
        if not settings.gemini_api_key or settings.gemini_api_key == "your-gemini-api-key-here":
            raise ValueError("Gemini API key not configured. Please set GEMINI_API_KEY in your .env file")

        genai.configure(api_key=settings.gemini_api_key, transport="rest")
        # Use a single configurable model to avoid mixed quotas
        self.model = genai.GenerativeModel(settings.gemini_model)
        self.vision_model = genai.GenerativeModel(settings.gemini_model)

        # Initialize TTS and video processing services
        # Initialize preferred TTS (ElevenLabs), then fallback to local OS TTS
        try:
            self.tts_service = ElevenLabsTTSService()
        except ValueError as e:
            logger.warning(f"ElevenLabs TTS not available: {e}")
            try:
                from application.services.ai.local_tts_service import LocalTTSService
                self.tts_service = LocalTTSService()
            except Exception as e2:
                logger.warning(f"Local TTS not available: {e2}")
                self.tts_service = None

        self.video_service = VideoProcessingService(
            temp_dir=settings.temp_dir,
            output_dir=settings.output_dir
        )

    async def analyze_video_context(
        self,
        video_path: str,
        transcription_text: str,
        target_country: Country
    ) -> Dict[str, Any]:
        """
        Analyze video content holistically including visual and audio elements
        """
        try:
            logger.info(f"Starting comprehensive video analysis for {video_path}")

            # Upload video to Gemini
            video_file = genai.upload_file(path=video_path)

            # Wait for processing
            while video_file.state.name == "PROCESSING":
                await asyncio.sleep(3)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED":
                raise Exception(f"Video processing failed: {video_file.state}")

            # Create comprehensive analysis prompt
            analysis_prompt = self._create_video_analysis_prompt(
                transcription_text,
                target_country
            )

            logger.info("Generating comprehensive video analysis...")
            # Small delay to respect free-tier RPM
            await asyncio.sleep(2)
            response = self.model.generate_content([video_file, analysis_prompt])

            # Parse the analysis response
            analysis_result = self._parse_video_analysis(response.text)

            # Clean up
            genai.delete_file(video_file.name)

            logger.info("Video analysis completed successfully")
            return analysis_result

        except Exception as e:
            logger.error(f"Video analysis failed: {str(e)}")
            return {
                "error": str(e),
                "advertising_elements": {},
                "visual_context": {},
                "emotional_tone": {},
                "brand_analysis": {},
                "cultural_considerations": {}
            }

    async def translate_with_context(
        self,
        video_path: str,
        transcription: str,
        target_country: Country,
        video_analysis: Dict[str, Any]
    ) -> Translation:
        """
        Translate content with full video and cultural context awareness
        """
        start_time = time.time()

        try:
            logger.info(f"Starting context-aware translation to {target_country.country_name}")

            # Create translation object
            translation = Translation(
                video_id=0,  # Will be set by calling code
                transcription_id=0,  # Will be set by calling code
                country_id=target_country.id or 0,
                source_language="auto",  # Will be detected
                target_language=target_country.language_code,
                country_code=target_country.country_code,
                status=TranslationStatus.ANALYZING_CONTEXT,
                video_analysis=video_analysis,
                model_used=settings.gemini_model
            )

            # Extract scenes for context
            translation.status = TranslationStatus.TRANSLATING
            scenes = await self.extract_video_scenes(video_path)

            # Create sophisticated translation prompt
            translation_prompt = self._create_context_aware_translation_prompt(
                transcription,
                target_country,
                video_analysis,
                scenes
            )

            # Generate translation
            logger.info("Generating culturally-aware translation...")
            await asyncio.sleep(2)
            response = self.model.generate_content(translation_prompt)

            if not response.text:
                raise Exception("No translation generated")

            # Parse translation response
            translation_result = self._parse_translation_response(response.text, scenes)

            # Update translation object
            translation.segments = translation_result["segments"]
            translation.full_translated_text = translation_result["full_text"]
            translation.cultural_adaptation = translation_result["cultural_adaptation"]
            translation.overall_confidence = translation_result["confidence"]

            # Perform cultural appropriateness assessment
            translation.status = TranslationStatus.CULTURAL_ADAPTATION
            appropriateness_assessment = await self.assess_cultural_appropriateness(
                translation, target_country, video_analysis
            )

            translation.cultural_appropriateness_score = appropriateness_assessment.get("score", 0.8)
            translation.warnings = appropriateness_assessment.get("warnings", [])

            # Optimize for advertising effectiveness
            translation = await self.optimize_for_advertising_effectiveness(
                translation,
                target_country,
                video_analysis.get("advertising_elements", {})
            )

            # Final status update
            translation.status = TranslationStatus.COMPLETED
            translation.processing_time = time.time() - start_time

            logger.info(f"Context-aware translation completed in {translation.processing_time:.2f}s")
            return translation

        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            translation.status = TranslationStatus.FAILED
            translation.error_message = str(e)
            translation.processing_time = time.time() - start_time
            return translation

    async def extract_video_scenes(
        self,
        video_path: str,
        interval_seconds: float = 10.0
    ) -> List[VideoSceneContext]:
        """
        Extract scene contexts from video at regular intervals
        """
        scenes = []

        try:
            video = VideoFileClip(video_path)
            duration = video.duration

            # Extract frames at intervals
            current_time = 0
            while current_time < duration:
                try:
                    # Extract frame
                    frame = video.get_frame(current_time)

                    # Convert to PIL Image
                    pil_image = Image.fromarray(frame.astype('uint8'))

                    # Analyze this frame with Gemini Vision
                    scene_analysis = await self._analyze_frame(pil_image, current_time)

                    scene_context = VideoSceneContext(
                        timestamp=current_time,
                        visual_elements=scene_analysis.get("visual_elements", []),
                        emotions=scene_analysis.get("emotions", []),
                        actions=scene_analysis.get("actions", []),
                        setting_type=scene_analysis.get("setting_type", "unknown"),
                        brand_elements=scene_analysis.get("brand_elements", []),
                        text_overlays=scene_analysis.get("text_overlays", []),
                        color_palette=scene_analysis.get("color_palette", [])
                    )

                    scenes.append(scene_context)

                except Exception as e:
                    logger.warning(f"Failed to analyze frame at {current_time}s: {str(e)}")

                current_time += interval_seconds

            video.close()

        except Exception as e:
            logger.error(f"Scene extraction failed: {str(e)}")

        return scenes

    async def direct_localize_video(
        self,
        video_path: str,
        target_country: Country,
        force_local_tts: bool = False,
        music_only_background: bool = False,
        skip_tts: bool = False,
        precomputed_segments: Optional[List[TranslationSegment]] = None,
        precomputed_duration: Optional[float] = None,
        output_suffix: Optional[str] = None,
    ) -> Translation:
        """
        Complete video localization: video → translation → TTS → final video with new audio.
        Does not require a prior transcription; uses the video file as context.
        """
        start_time = time.time()

        translation = Translation(
            video_id=0,
            transcription_id=0,
            country_id=target_country.id or 0,
            source_language="auto",
            target_language=target_country.language_code,
            country_code=target_country.country_code,
            status=TranslationStatus.ANALYZING_CONTEXT,
            model_used=settings.gemini_model
        )

        try:
            logger.info(f"Starting complete video localization for {target_country.country_name}")

            if precomputed_segments is None:
                # Step 1: Upload and analyze video
                video_file = genai.upload_file(path=video_path)
                while video_file.state.name == "PROCESSING":
                    await asyncio.sleep(2)
                    video_file = genai.get_file(video_file.name)
                if video_file.state.name == "FAILED":
                    raise Exception(f"Video processing failed: {video_file.state}")

                # Step 2: Generate translation with precise timing
                translation.status = TranslationStatus.TRANSLATING
                prompt = f"""
            You are a senior localization expert for advertising videos.
            Watch and listen to this video and produce a localized script for {target_country.country_name}
            in {target_country.language_name}. Focus on preserving ADVERTISING INTENT and scene timing.

            Country cultural context:
            - Communication style: {target_country.cultural_context.communication_style}
            - Marketing preferences: {target_country.cultural_context.marketing_preferences}
            - Cultural values: {target_country.cultural_context.cultural_values}
            - Taboo topics: {target_country.cultural_context.taboo_topics}
            - Dialect: {target_country.dialect_info.primary_dialect}

            CRITICAL: Provide PRECISE timing for each speech segment. Analyze the video carefully for:
            - When exactly speech starts and ends
            - Pauses between sentences
            - Scene transitions
            - Audio-visual synchronization points

            Return STRICT JSON with keys:
            {{
              "video_duration": float,
              "full_translated_text": str,
              "segments": [{{
                  "start_time": float,
                  "end_time": float,
                  "original_text": str,
                  "translated_text": str,
                  "confidence_score": float,
                  "context_used": [str],
                  "cultural_adaptations": [str],
                  "speech_speed": str,
                  "emotional_tone": str
              }}],
              "cultural_adaptation": {{
                  "original_concept": str,
                  "adapted_concept": str,
                  "changes_made": [str],
                  "cultural_reasoning": str,
                  "risk_assessment": str,
                  "effectiveness_score": float
              }},
              "advertising_context": {{
                "primary_message": str,
                "call_to_action": str,
                "target_audience": str,
                "emotional_appeal": str
              }}
            }}
            """

                await asyncio.sleep(2)
                response = self.model.generate_content([video_file, prompt])

                if not response.text:
                    raise Exception("No response generated from Gemini")

                parsed = self._parse_translation_response(response.text, [])

                translation.segments = parsed["segments"]
                translation.full_translated_text = parsed["full_text"]
                translation.cultural_adaptation = parsed["cultural_adaptation"]
                translation.advertising_context = parsed.get("advertising_context", {})
                translation.overall_confidence = parsed["confidence"]

                # Get video duration for processing
                try:
                    from moviepy.editor import VideoFileClip
                    with VideoFileClip(video_path) as video_clip:
                        translation.video_duration = video_clip.duration
                except Exception as e:
                    logger.warning(f"Could not get video duration: {str(e)}")
                    translation.video_duration = 30.0  # Default fallback

                # Cleanup Gemini resources
                genai.delete_file(video_file.name)
            else:
                translation.status = TranslationStatus.TRANSLATING
                translation.segments = precomputed_segments
                translation.video_duration = precomputed_duration
                translation.full_translated_text = (
                    "\n".join([seg.translated_text for seg in (precomputed_segments or [])])
                    if precomputed_segments
                    else None
                )

            if skip_tts:
                translation.status = TranslationStatus.COMPLETED
                translation.processing_time = time.time() - start_time
                return translation

            # Step 3: Generate speech with ElevenLabs if available
            # TTS generation (with optional force-local fallback)
            if translation.segments:
                if force_local_tts:
                    try:
                        from application.services.ai.local_tts_service import LocalTTSService
                        logger.info("Force using Local TTS backend...")
                        tts_impl = LocalTTSService()
                        self.tts_service = tts_impl
                    except Exception as e:
                        logger.warning(f"Local TTS unavailable: {e}")

                if not self.tts_service:
                    try:
                        from application.services.ai.local_tts_service import LocalTTSService
                        self.tts_service = LocalTTSService()
                    except Exception:
                        self.tts_service = None

            if self.tts_service and translation.segments:
                translation.status = TranslationStatus.GENERATING_AUDIO

                # Create unique output directory for this translation
                import uuid
                session_id = str(uuid.uuid4())[:8]
                audio_output_dir = self.video_service.temp_dir / f"audio_{session_id}"

                logger.info("Generating speech for segments...")
                audio_segments = await self.tts_service.generate_speech_for_segments(
                    segments=translation.segments,
                    target_language=target_country.language_code,
                    country_code=target_country.country_code,
                    output_dir=str(audio_output_dir)
                )

                # If preferred backend failed, try local fallback once
                if not audio_segments:
                    try:
                        from application.services.ai.local_tts_service import LocalTTSService
                        logger.info("Falling back to Local TTS backend...")
                        local_tts = LocalTTSService()
                        audio_segments = await local_tts.generate_speech_for_segments(
                            segments=translation.segments,
                            target_language=target_country.language_code,
                            country_code=target_country.country_code,
                            output_dir=str(audio_output_dir)
                        )
                    except Exception as e3:
                        logger.warning(f"Local TTS fallback also failed: {e3}")

                if audio_segments:
                    # Step 4: Create final video with new audio
                    translation.status = TranslationStatus.PROCESSING_VIDEO

                    # Generate output filename
                    from pathlib import Path
                    original_filename = Path(video_path).stem
                    suffix = f"_{output_suffix}" if output_suffix else ""
                    output_filename = f"{original_filename}_{target_country.country_code}{suffix}_{session_id}.mp4"
                    final_video_path = self.video_service.output_dir / output_filename

                    logger.info("Creating final video with synchronized audio...")

                    # Analyze scene transitions for better synchronization
                    enhanced_segments = await self.video_service.analyze_scene_transitions(
                        video_path, audio_segments
                    )

                    # Create the final video
                    result_video_path = await self.video_service.create_synchronized_video_with_segments(
                        original_video_path=video_path,
                        audio_segments=enhanced_segments,
                        output_video_path=str(final_video_path),
                        background_audio_volume=0.05,  # Keep minimal background audio
                        isolate_music=bool(music_only_background)
                    )

                    if result_video_path:
                        # Store the final video path in translation
                        translation.final_video_path = result_video_path
                        translation.audio_segments = audio_segments
                        logger.info(f"Complete video localization successful: {result_video_path}")
                    else:
                        logger.warning("Video processing failed, but translation is available")

                    # Clean up temporary audio files
                    import shutil
                    if audio_output_dir.exists():
                        shutil.rmtree(audio_output_dir)

                else:
                    logger.warning("TTS generation failed, returning text-only translation")
            else:
                logger.info("TTS service not available, returning text-only translation")

            translation.status = TranslationStatus.COMPLETED
            translation.processing_time = time.time() - start_time

            return translation

        except Exception as e:
            logger.error(f"Complete video localization failed: {str(e)}")
            translation.status = TranslationStatus.FAILED
            translation.error_message = str(e)
            translation.processing_time = time.time() - start_time
            return translation

    async def assess_cultural_appropriateness(
        self,
        translation: Translation,
        target_country: Country,
        video_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess cultural appropriateness of the translation
        """
        try:
            assessment_prompt = self._create_cultural_assessment_prompt(
                translation, target_country, video_analysis
            )

            await asyncio.sleep(2)
            response = self.model.generate_content(assessment_prompt)
            assessment_result = self._parse_assessment_response(response.text)

            return assessment_result

        except Exception as e:
            logger.error(f"Cultural assessment failed: {str(e)}")
            return {
                "score": 0.7,
                "warnings": [f"Assessment failed: {str(e)}"],
                "recommendations": []
            }

    async def optimize_for_advertising_effectiveness(
        self,
        translation: Translation,
        target_country: Country,
        original_intent: Dict[str, Any]
    ) -> Translation:
        """
        Optimize translation to maintain advertising effectiveness
        """
        try:
            optimization_prompt = self._create_optimization_prompt(
                translation, target_country, original_intent
            )

            response = self.model.generate_content(optimization_prompt)
            optimization_result = self._parse_optimization_response(response.text)

            # Update translation with optimizations
            if optimization_result.get("optimized_segments"):
                translation.segments = optimization_result["optimized_segments"]
                translation.full_translated_text = " ".join([
                    seg.translated_text for seg in translation.segments
                ])

            translation.effectiveness_prediction = optimization_result.get("effectiveness_score", 0.8)
            translation.brand_consistency_score = optimization_result.get("brand_consistency", 0.8)

            return translation

        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}")
            return translation

    async def _analyze_frame(self, image: Image.Image, timestamp: float) -> Dict[str, Any]:
        """Analyze a single frame using Gemini Vision"""
        try:
            prompt = """
            Analyze this video frame and identify:
            1. Visual elements (objects, people, settings)
            2. Emotions visible in faces or body language
            3. Actions taking place
            4. Setting type (indoor/outdoor/office/home/etc)
            5. Brand elements (logos, products, colors)
            6. Any text overlays or graphics
            7. Dominant color palette

            Return as JSON format.
            """

            # Simple backoff loop for rate limit handling
            last_error = None
            for attempt in range(3):
                try:
                    await asyncio.sleep(2)  # throttle free-tier RPM
                    response = self.vision_model.generate_content([image, prompt])
                    break
                except Exception as e:
                    last_error = e
                    # If 429 or quota in message, wait a bit and retry
                    msg = str(e)
                    if "429" in msg or "quota" in msg.lower() or "rate" in msg.lower():
                        await asyncio.sleep(8 * (attempt + 1))
                        continue
                    raise
            else:
                raise last_error

            try:
                return json.loads(response.text)
            except:
                # If JSON parsing fails, return basic structure
                return {
                    "visual_elements": [],
                    "emotions": [],
                    "actions": [],
                    "setting_type": "unknown",
                    "brand_elements": [],
                    "text_overlays": [],
                    "color_palette": []
                }

        except Exception as e:
            logger.warning(f"Frame analysis failed for timestamp {timestamp}: {str(e)}")
            return {}

    def _create_video_analysis_prompt(self, transcription: str, target_country: Country) -> str:
        """Create prompt for comprehensive video analysis"""
        return f"""
        Analyze this video comprehensively for translation to {target_country.country_name} ({target_country.country_code}).

        The transcription is: "{transcription}"

        Target cultural context:
        - Communication style: {target_country.cultural_context.communication_style}
        - Marketing preferences: {target_country.cultural_context.marketing_preferences}
        - Cultural values: {target_country.cultural_context.cultural_values}
        - Taboo topics: {target_country.cultural_context.taboo_topics}

        Please analyze:
        1. ADVERTISING ELEMENTS:
           - Main product/service being advertised
           - Key selling points and benefits
           - Call-to-action phrases
           - Target audience indicators
           - Emotional appeals used
           - Urgency/scarcity tactics

        2. VISUAL CONTEXT:
           - Scene settings and environments
           - People demographics and emotions
           - Brand colors and visual identity
           - Text overlays and graphics
           - Product demonstrations

        3. EMOTIONAL TONE:
           - Primary emotional appeal
           - Mood and atmosphere
           - Voice tone and delivery style
           - Music and sound effects impact

        4. BRAND ANALYSIS:
           - Brand positioning strategy
           - Brand personality traits
           - Consistency with brand values
           - Competitive differentiation

        5. CULTURAL CONSIDERATIONS for {target_country.country_name}:
           - Potential cultural conflicts
           - Required adaptations
           - Local market preferences
           - Communication style alignment

        Return detailed analysis in JSON format.
        """

    def _create_context_aware_translation_prompt(
        self,
        transcription: str,
        target_country: Country,
        video_analysis: Dict[str, Any],
        scenes: List[VideoSceneContext]
    ) -> str:
        """Create sophisticated translation prompt with full context"""
        return f"""
        Translate the following advertising content to {target_country.language_name} for {target_country.country_name},
        taking into account the complete video context and cultural nuances.

        ORIGINAL TRANSCRIPTION:
        "{transcription}"

        VIDEO ANALYSIS CONTEXT:
        {json.dumps(video_analysis, indent=2)}

        TARGET COUNTRY CULTURAL CONTEXT:
        - Dialect: {target_country.dialect_info.primary_dialect}
        - Communication Style: {target_country.cultural_context.communication_style}
        - Humor Style: {target_country.cultural_context.humor_style}
        - Marketing Preferences: {target_country.cultural_context.marketing_preferences}
        - Call-to-Action Style: {target_country.cultural_context.call_to_action_style}
        - Trust Building Elements: {target_country.cultural_context.trust_building_elements}
        - Common Phrases: {target_country.dialect_info.common_phrases}
        - Formality Level: {target_country.dialect_info.formality_level}

        TRANSLATION REQUIREMENTS:
        1. Preserve advertising effectiveness and persuasive power
        2. Adapt to local cultural preferences and communication style
        3. Maintain brand consistency while localizing appropriately
        4. Use culturally appropriate humor and emotional appeals
        5. Adapt call-to-action phrases for maximum local impact
        6. Consider visual context when translating text overlays
        7. Ensure cultural sensitivity and avoid taboo topics: {target_country.cultural_context.taboo_topics}

        PROVIDE:
        1. Segment-by-segment translation with timestamps
        2. Full translated text
        3. Cultural adaptations made and reasoning
        4. Confidence score for each segment
        5. Overall translation confidence
        6. Effectiveness prediction for target market

        Format as detailed JSON response.
        """

    def _parse_video_analysis(self, response_text: str) -> Dict[str, Any]:
        """Parse video analysis response from Gemini"""
        try:
            return json.loads(response_text)
        except:
            # Fallback parsing for non-JSON responses
            return {
                "advertising_elements": {"main_product": "unknown"},
                "visual_context": {"setting": "unknown"},
                "emotional_tone": {"primary_appeal": "unknown"},
                "brand_analysis": {"positioning": "unknown"},
                "cultural_considerations": {"adaptations_needed": []}
            }

    def _parse_translation_response(
        self,
        response_text: str,
        scenes: List[VideoSceneContext] = None
    ) -> Dict[str, Any]:
        """Parse translation response from Gemini"""
        if scenes is None:
            scenes = []

        try:
            # Clean response text - sometimes Gemini adds markdown formatting
            clean_text = response_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

            result = json.loads(clean_text)

            # Convert to TranslationSegment objects
            segments = []
            if "segments" in result and isinstance(result["segments"], list):
                for seg_data in result["segments"]:
                    if not isinstance(seg_data, dict):
                        continue

                    segment = TranslationSegment(
                        start_time=float(seg_data.get("start_time", 0)),
                        end_time=float(seg_data.get("end_time", 0)),
                        original_text=str(seg_data.get("original_text", "")),
                        translated_text=str(seg_data.get("translated_text", "")),
                        confidence_score=float(seg_data.get("confidence_score", 0.8)),
                        context_used=seg_data.get("context_used", []) if isinstance(seg_data.get("context_used"), list) else [],
                        cultural_adaptations=seg_data.get("cultural_adaptations", []) if isinstance(seg_data.get("cultural_adaptations"), list) else []
                    )
                    segments.append(segment)

            # Create cultural adaptation object
            cultural_adaptation = None
            if "cultural_adaptation" in result and isinstance(result["cultural_adaptation"], dict):
                ca_data = result["cultural_adaptation"]
                cultural_adaptation = CulturalAdaptation(
                    original_concept=str(ca_data.get("original_concept", "")),
                    adapted_concept=str(ca_data.get("adapted_concept", "")),
                    changes_made=ca_data.get("changes_made", []) if isinstance(ca_data.get("changes_made"), list) else [],
                    cultural_reasoning=str(ca_data.get("cultural_reasoning", "")),
                    risk_assessment=str(ca_data.get("risk_assessment", "")),
                    effectiveness_score=float(ca_data.get("effectiveness_score", 0.8))
                )

            return {
                "segments": segments,
                "full_text": str(result.get("full_translated_text", "")),
                "cultural_adaptation": cultural_adaptation,
                "confidence": float(result.get("overall_confidence", 0.8))
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {str(e)}. Response: {response_text[:200]}...")
            # Try to extract some basic text
            fallback_text = self._extract_fallback_text(response_text)
            return {
                "segments": [TranslationSegment(
                    start_time=0.0,
                    end_time=30.0,  # Default 30 seconds
                    original_text="Original text",
                    translated_text=fallback_text,
                    confidence_score=0.5,
                    context_used=[],
                    cultural_adaptations=[]
                )] if fallback_text else [],
                "full_text": fallback_text,
                "cultural_adaptation": None,
                "confidence": 0.5
            }
        except Exception as e:
            logger.error(f"Failed to parse translation response: {str(e)}")
            return {
                "segments": [],
                "full_text": response_text[:500] if response_text else "",  # Fallback to raw text
                "cultural_adaptation": None,
                "confidence": 0.5
            }

    def _extract_fallback_text(self, response_text: str) -> str:
        """Extract fallback translated text from malformed response"""
        try:
            # Look for translated text patterns
            lines = response_text.split('\n')
            for line in lines:
                line = line.strip()
                if any(indicator in line.lower() for indicator in ['translated_text', 'translation:', 'localized:']):
                    # Try to extract text after colon or quotes
                    if ':' in line:
                        text = line.split(':', 1)[1].strip()
                        if text.startswith('"') and text.endswith('"'):
                            return text[1:-1]
                        return text

            # If no pattern found, return first non-empty line
            for line in lines:
                line = line.strip()
                if line and not line.startswith('{') and not line.startswith('['):
                    return line[:200]  # Limit length

            return ""
        except:
            return ""

    def _create_cultural_assessment_prompt(
        self,
        translation: Translation,
        target_country: Country,
        video_analysis: Dict[str, Any]
    ) -> str:
        """Create prompt for cultural appropriateness assessment"""
        return f"""
        Assess the cultural appropriateness of this translation for {target_country.country_name}:

        TRANSLATED CONTENT:
        "{translation.full_translated_text}"

        CULTURAL CONTEXT:
        - Cultural Values: {target_country.cultural_context.cultural_values}
        - Taboo Topics: {target_country.cultural_context.taboo_topics}
        - Communication Style: {target_country.cultural_context.communication_style}
        - Marketing Preferences: {target_country.cultural_context.marketing_preferences}

        VIDEO ANALYSIS:
        {json.dumps(video_analysis, indent=2)}

        Evaluate:
        1. Cultural sensitivity (0-1 score)
        2. Potential offensive content
        3. Alignment with local values
        4. Marketing effectiveness for local market
        5. Any required modifications

        Return JSON with score, warnings, and recommendations.
        """

    def _create_optimization_prompt(
        self,
        translation: Translation,
        target_country: Country,
        original_intent: Dict[str, Any]
    ) -> str:
        """Create prompt for advertising effectiveness optimization"""
        return f"""
        Optimize this translation to maximize advertising effectiveness for {target_country.country_name}:

        CURRENT TRANSLATION:
        "{translation.full_translated_text}"

        ORIGINAL ADVERTISING INTENT:
        {json.dumps(original_intent, indent=2)}

        TARGET MARKET PREFERENCES:
        - Call-to-Action Style: {target_country.cultural_context.call_to_action_style}
        - Trust Building: {target_country.cultural_context.trust_building_elements}
        - Urgency Indicators: {target_country.cultural_context.urgency_indicators}
        - Marketing Preferences: {target_country.cultural_context.marketing_preferences}

        Optimize for:
        1. Maximum persuasive impact
        2. Local market resonance
        3. Brand consistency
        4. Cultural appropriateness
        5. Call-to-action effectiveness

        Return optimized translation with effectiveness prediction.
        """

    def _parse_assessment_response(self, response_text: str) -> Dict[str, Any]:
        """Parse cultural assessment response"""
        try:
            return json.loads(response_text)
        except:
            return {
                "score": 0.7,
                "warnings": ["Assessment parsing failed"],
                "recommendations": []
            }

    def _parse_optimization_response(self, response_text: str) -> Dict[str, Any]:
        """Parse optimization response"""
        try:
            return json.loads(response_text)
        except:
            return {
                "effectiveness_score": 0.8,
                "brand_consistency": 0.8,
                "optimized_segments": []
            }
