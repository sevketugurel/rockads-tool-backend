#!/usr/bin/env python3
"""
Enhanced Audio Processing Setup Verification Script
Checks all dependencies and capabilities for the enhanced localization system.
"""

import sys
import subprocess
import importlib
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class AudioSetupVerifier:
    """Comprehensive setup verification for enhanced audio processing"""

    def __init__(self):
        self.results = {
            'python_packages': {},
            'system_tools': {},
            'audio_capabilities': {},
            'overall_status': False
        }

    def check_python_package(self, package_name: str, import_name: str = None, required: bool = True) -> bool:
        """Check if a Python package is installed and importable"""
        import_name = import_name or package_name
        try:
            module = importlib.import_module(import_name)
            version = getattr(module, '__version__', 'unknown')
            self.results['python_packages'][package_name] = {
                'status': 'installed',
                'version': version,
                'required': required
            }
            logger.info(f"✅ {package_name} {version} - installed")
            return True
        except ImportError:
            self.results['python_packages'][package_name] = {
                'status': 'missing',
                'version': None,
                'required': required
            }
            status_icon = "❌" if required else "⚠️"
            requirement = "required" if required else "optional"
            logger.warning(f"{status_icon} {package_name} - not installed ({requirement})")
            return False

    def check_system_tool(self, tool_name: str, version_flag: str = '--version', required: bool = True) -> bool:
        """Check if a system tool is available in PATH"""
        try:
            result = subprocess.run(
                [tool_name, version_flag],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version_info = result.stdout.strip().split('\n')[0]
                self.results['system_tools'][tool_name] = {
                    'status': 'available',
                    'version': version_info,
                    'required': required
                }
                logger.info(f"✅ {tool_name} - {version_info}")
                return True
            else:
                raise subprocess.CalledProcessError(result.returncode, tool_name)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            self.results['system_tools'][tool_name] = {
                'status': 'missing',
                'version': None,
                'required': required
            }
            status_icon = "❌" if required else "⚠️"
            requirement = "required" if required else "recommended"
            logger.warning(f"{status_icon} {tool_name} - not found in PATH ({requirement})")
            return False

    def test_audio_processing_capability(self) -> bool:
        """Test basic audio processing capabilities"""
        try:
            import librosa
            import numpy as np

            # Test basic audio processing
            logger.info("🔧 Testing audio processing capabilities...")

            # Generate test audio signal
            duration = 1.0  # seconds
            sample_rate = 22050
            frequency = 440  # A4 note

            t = np.linspace(0, duration, int(sample_rate * duration), False)
            test_audio = np.sin(frequency * 2 * np.pi * t)

            # Test various audio operations
            tests = []

            # Test STFT
            stft = librosa.stft(test_audio)
            tests.append(("STFT", stft is not None))

            # Test feature extraction
            mfcc = librosa.feature.mfcc(y=test_audio, sr=sample_rate)
            tests.append(("MFCC extraction", mfcc is not None))

            # Test tempo detection
            tempo, _ = librosa.beat.beat_track(y=test_audio, sr=sample_rate)
            tests.append(("Tempo detection", tempo is not None))

            # Test spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=test_audio, sr=sample_rate)
            tests.append(("Spectral analysis", spectral_centroids is not None))

            success_count = sum(1 for _, success in tests if success)
            total_tests = len(tests)

            self.results['audio_capabilities'] = {
                'basic_processing': f"{success_count}/{total_tests} tests passed",
                'tests': dict(tests)
            }

            if success_count == total_tests:
                logger.info(f"✅ Audio processing capabilities: {success_count}/{total_tests} tests passed")
                return True
            else:
                logger.warning(f"⚠️ Audio processing capabilities: {success_count}/{total_tests} tests passed")
                return False

        except Exception as e:
            logger.error(f"❌ Audio processing test failed: {str(e)}")
            self.results['audio_capabilities'] = {'error': str(e)}
            return False

    def test_enhanced_separation_fallback(self) -> bool:
        """Test enhanced FFmpeg-based separation fallback"""
        try:
            if not self.results['system_tools'].get('ffmpeg', {}).get('status') == 'available':
                logger.warning("⚠️ FFmpeg not available, enhanced separation will be limited")
                return False

            logger.info("🔧 Testing enhanced separation capabilities...")

            # Test FFmpeg complex filter support
            cmd = [
                "ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc2=duration=1:size=320x240:rate=30",
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
                "-filter_complex", "[1:a]pan=stereo|c0=c0-c1|c1=c1-c0[separated]",
                "-map", "[separated]", "-f", "null", "-"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                logger.info("✅ Enhanced FFmpeg separation filters available")
                self.results['audio_capabilities']['enhanced_separation'] = True
                return True
            else:
                logger.warning("⚠️ Enhanced FFmpeg separation filters limited")
                self.results['audio_capabilities']['enhanced_separation'] = False
                return False

        except Exception as e:
            logger.warning(f"⚠️ Enhanced separation test failed: {str(e)}")
            self.results['audio_capabilities']['enhanced_separation'] = False
            return False

    def verify_setup(self) -> Dict:
        """Run complete setup verification"""
        logger.info("🚀 Starting Enhanced Audio Processing Setup Verification\n")

        # Check Python packages
        logger.info("📦 Checking Python packages...")
        required_packages = [
            ('librosa', 'librosa', True),
            ('pydub', 'pydub', True),
            ('soundfile', 'soundfile', True),
            ('audioread', 'audioread', True),
            ('scipy', 'scipy', True),
            ('numpy', 'numpy', True),
            ('numba', 'numba', True),
        ]

        optional_packages = [
            ('spleeter', 'spleeter', False),
            ('torch', 'torch', False),
            ('torchaudio', 'torchaudio', False),
            ('demucs', 'demucs', False),
        ]

        package_results = []
        for pkg_name, import_name, required in required_packages + optional_packages:
            result = self.check_python_package(pkg_name, import_name, required)
            package_results.append(result or not required)

        print()  # Empty line for readability

        # Check system tools
        logger.info("🛠️ Checking system tools...")
        system_tools = [
            ('ffmpeg', '--version', True),
            ('ffprobe', '--version', True),
            ('spleeter', '--help', False),
        ]

        tool_results = []
        for tool_name, version_flag, required in system_tools:
            result = self.check_system_tool(tool_name, version_flag, required)
            tool_results.append(result or not required)

        print()  # Empty line for readability

        # Test audio processing capabilities
        logger.info("🎵 Testing audio processing capabilities...")
        audio_test_result = self.test_audio_processing_capability()

        # Test enhanced separation capabilities
        separation_test_result = self.test_enhanced_separation_fallback()

        # Calculate overall status
        required_packages_ok = all(
            self.results['python_packages'].get(pkg, {}).get('status') == 'installed'
            for pkg, _, required in required_packages if required
        )

        required_tools_ok = all(
            self.results['system_tools'].get(tool, {}).get('status') == 'available'
            for tool, _, required in system_tools if required
        )

        self.results['overall_status'] = (
            required_packages_ok and
            required_tools_ok and
            audio_test_result
        )

        # Print summary
        print("\n" + "="*60)
        logger.info("📋 SETUP VERIFICATION SUMMARY")
        print("="*60)

        if self.results['overall_status']:
            logger.info("🎉 Enhanced audio processing setup is READY!")
            logger.info("✅ All required dependencies are installed")
            logger.info("✅ Basic audio processing capabilities verified")
            if separation_test_result:
                logger.info("✅ Enhanced separation capabilities available")
            else:
                logger.info("⚠️ Enhanced separation limited (will use basic FFmpeg)")
        else:
            logger.error("❌ Setup verification FAILED")
            logger.error("💡 Please install missing required dependencies")

        # Recommendations
        print("\n📝 RECOMMENDATIONS:")

        if not self.results['python_packages'].get('spleeter', {}).get('status') == 'installed':
            print("⚠️ Spleeter not installed - using enhanced FFmpeg fallback")
            print("   For best quality, consider using Demucs instead:")
            print("   pip install demucs torch torchaudio")

        if not self.results['system_tools'].get('ffmpeg', {}).get('status') == 'available':
            print("❌ FFmpeg is required for all audio processing")
            print("   Install with: brew install ffmpeg  # macOS")
            print("               : apt-get install ffmpeg  # Ubuntu")

        missing_packages = [
            name for name, info in self.results['python_packages'].items()
            if info['required'] and info['status'] == 'missing'
        ]

        if missing_packages:
            print(f"❌ Install missing packages: pip install {' '.join(missing_packages)}")

        return self.results


def main():
    """Main verification function"""
    verifier = AudioSetupVerifier()
    results = verifier.verify_setup()

    # Exit with appropriate code
    exit_code = 0 if results['overall_status'] else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()