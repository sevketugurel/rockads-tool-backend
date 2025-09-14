#!/usr/bin/env python3
"""
Setup script for Enhanced Audio Processing Features

This script prepares the system for advanced video localization with audio source separation.
It installs dependencies and downloads necessary AI models.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_ffmpeg():
    """Check if FFmpeg is installed and accessible"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✓ FFmpeg is installed and accessible")
            return True
        else:
            logger.error("✗ FFmpeg is not working properly")
            return False
    except FileNotFoundError:
        logger.error("✗ FFmpeg is not installed or not in PATH")
        return False


def install_spleeter():
    """Install Spleeter and download models"""
    try:
        logger.info("Installing Spleeter and TensorFlow...")

        # Install Spleeter
        subprocess.run([
            sys.executable, '-m', 'pip', 'install',
            'spleeter>=2.4.0',
            'tensorflow>=2.10.0,<2.16.0',
            'tensorflow-io>=0.27.0'
        ], check=True)

        logger.info("✓ Spleeter installation completed")

        # Download Spleeter models
        logger.info("Downloading Spleeter models (this may take a few minutes)...")

        # Create models directory
        models_dir = Path.home() / '.spleeter_models'
        models_dir.mkdir(exist_ok=True)

        # Download models
        for model in ['2stems-16kHz', '4stems-16kHz', '5stems-16kHz']:
            try:
                subprocess.run([
                    'spleeter', 'separate',
                    '--help'  # This will trigger model download
                ], capture_output=True)
                logger.info(f"✓ Model {model} ready")
            except Exception as e:
                logger.warning(f"⚠ Could not pre-download {model}: {e}")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Spleeter installation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error during Spleeter setup: {e}")
        return False


def install_audio_processing_deps():
    """Install additional audio processing dependencies"""
    try:
        logger.info("Installing audio processing libraries...")

        subprocess.run([
            sys.executable, '-m', 'pip', 'install',
            'librosa>=0.9.2',
            'pydub>=0.25.1',
            'soundfile>=0.12.1',
            'scipy>=1.9.0',
            'numpy>=1.21.0',
            'psutil>=5.9.0'
        ], check=True)

        logger.info("✓ Audio processing libraries installed")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Audio processing libraries installation failed: {e}")
        return False


def test_installation():
    """Test the installation by importing key components"""
    try:
        logger.info("Testing installation...")

        # Test Spleeter
        try:
            import spleeter
            logger.info("✓ Spleeter import successful")
        except ImportError:
            logger.error("✗ Spleeter import failed")
            return False

        # Test TensorFlow
        try:
            import tensorflow as tf
            logger.info(f"✓ TensorFlow {tf.__version__} import successful")
        except ImportError:
            logger.error("✗ TensorFlow import failed")
            return False

        # Test audio libraries
        try:
            import librosa
            import pydub
            import soundfile
            logger.info("✓ Audio processing libraries import successful")
        except ImportError as e:
            logger.error(f"✗ Audio library import failed: {e}")
            return False

        return True

    except Exception as e:
        logger.error(f"✗ Installation test failed: {e}")
        return False


def create_config_template():
    """Create configuration template for audio processing"""
    try:
        config_template = '''# Audio Enhancement Configuration Template
# Add these settings to your .env file

# Spleeter Configuration
SPLEETER_MODEL_DIR=~/.spleeter_models
SPLEETER_DEFAULT_MODEL=2stems-16kHz

# Audio Processing Settings
AUDIO_PROCESSING_ENABLED=true
AUDIO_TEMP_DIR=temp/audio
AUDIO_OUTPUT_DIR=output/audio

# Quality Settings
AUDIO_DEFAULT_QUALITY=high
AUDIO_DEFAULT_SAMPLE_RATE=44100
AUDIO_DEFAULT_BITRATE=192k

# Performance Settings
AUDIO_PROCESSING_TIMEOUT=300  # 5 minutes
MAX_CONCURRENT_AUDIO_JOBS=2
CLEANUP_TEMP_FILES_HOURS=24

# Advanced Features
ENABLE_PRECISION_TIMING=true
ENABLE_BACKGROUND_PRESERVATION=true
DEFAULT_BACKGROUND_VOLUME=0.3
DEFAULT_VOICE_VOLUME=1.0
'''

        config_path = Path(__file__).parent / 'audio-enhancement.env.template'
        with open(config_path, 'w') as f:
            f.write(config_template)

        logger.info(f"✓ Configuration template created: {config_path}")
        return True

    except Exception as e:
        logger.error(f"✗ Config template creation failed: {e}")
        return False


def main():
    """Main setup function"""
    logger.info("🎵 Setting up Enhanced Audio Processing for Video Localization")
    logger.info("=" * 60)

    success = True

    # Check prerequisites
    if not check_ffmpeg():
        logger.error("FFmpeg is required but not found. Please install FFmpeg first.")
        logger.info("Installation instructions:")
        logger.info("  macOS: brew install ffmpeg")
        logger.info("  Ubuntu/Debian: sudo apt install ffmpeg")
        logger.info("  Windows: Download from https://ffmpeg.org/download.html")
        success = False

    # Install Spleeter
    if success and not install_spleeter():
        success = False

    # Install audio processing dependencies
    if success and not install_audio_processing_deps():
        success = False

    # Test installation
    if success and not test_installation():
        success = False

    # Create config template
    if success and not create_config_template():
        success = False

    # Final status
    logger.info("=" * 60)
    if success:
        logger.info("🎉 Enhanced Audio Processing setup completed successfully!")
        logger.info("Next steps:")
        logger.info("  1. Review the configuration template: audio-enhancement.env.template")
        logger.info("  2. Add relevant settings to your .env file")
        logger.info("  3. Test the new audio separation endpoints")
        logger.info("  4. Enjoy enhanced video localization with preserved background music!")
    else:
        logger.error("❌ Setup failed. Please review the errors above and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()