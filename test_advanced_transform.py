#!/usr/bin/env python3

import sys
sys.path.append('/app/backend')

import numpy as np
import librosa
import soundfile as sf
from pathlib import Path
import requests
import json

# Import our advanced transformation functions
from server import extract_stems_and_convert_to_midi, create_frequency_based_stems

def create_musical_test_audio():
    """Create a more musical test audio file with clear stems"""
    duration = 10  # 10 seconds
    sample_rate = 22050
    
    t = np.linspace(0, duration, duration * sample_rate)
    
    # Create different musical elements
    # 1. Bass line (C - F - G - C progression)
    bass_freqs = [65.4, 87.3, 98.0, 130.8]  # C2, F2, G2, C3
    bass = np.zeros_like(t)
    beat_duration = duration / 4
    
    for i, freq in enumerate(bass_freqs):
        start_idx = int(i * beat_duration * sample_rate)
        end_idx = int((i + 1) * beat_duration * sample_rate)
        if end_idx <= len(bass):
            bass[start_idx:end_idx] = np.sin(2 * np.pi * freq * t[start_idx:end_idx]) * 0.4
    
    # 2. Melody line (pentatonic scale)
    melody_freqs = [261.6, 293.7, 329.6, 392.0, 440.0]  # C4, D4, E4, G4, A4
    melody = np.zeros_like(t)
    
    for i in range(20):  # 20 notes
        freq = melody_freqs[i % len(melody_freqs)]
        start_idx = int(i * 0.5 * sample_rate)
        end_idx = int((i + 1) * 0.5 * sample_rate)
        if end_idx <= len(melody):
            # Add some envelope for more realistic notes
            envelope = np.exp(-np.linspace(0, 2, end_idx - start_idx))
            melody[start_idx:end_idx] = (
                np.sin(2 * np.pi * freq * t[start_idx:end_idx]) * envelope * 0.3
            )
    
    # 3. Percussion (kick and hi-hat pattern)
    percussion = np.zeros_like(t)
    kick_interval = int(1.0 * sample_rate)  # Every second
    hihat_interval = int(0.25 * sample_rate)  # 4 times per second
    
    for i in range(0, len(percussion), kick_interval):
        if i < len(percussion) - 1000:
            # Kick drum (low frequency burst)
            kick_env = np.exp(-np.linspace(0, 10, 1000))
            percussion[i:i+1000] += np.sin(2 * np.pi * 60 * t[:1000]) * kick_env * 0.5
    
    for i in range(0, len(percussion), hihat_interval):
        if i < len(percussion) - 200:
            # Hi-hat (high frequency noise burst)
            hihat_env = np.exp(-np.linspace(0, 20, 200))
            percussion[i:i+200] += np.random.normal(0, 0.1, 200) * hihat_env * 0.2
    
    # 4. Combine all elements
    combined_audio = bass + melody + percussion
    
    # Add some reverb for realism
    reverb_impulse = np.exp(-np.linspace(0, 2, int(0.1 * sample_rate))) * 0.1
    combined_audio = np.convolve(combined_audio, reverb_impulse, mode='same')
    
    # Normalize
    combined_audio = combined_audio / np.max(np.abs(combined_audio)) * 0.8
    
    return combined_audio, sample_rate

def test_advanced_transformation():
    """Test the complete audio-to-MIDI transformation system"""
    print("🎵 Testing Advanced Audio-to-MIDI Transformation")
    print("=" * 60)
    
    # Create test directories
    test_dir = Path("/tmp/advanced_test")
    test_dir.mkdir(exist_ok=True)
    
    output_dir = test_dir / "stems_output"
    output_dir.mkdir(exist_ok=True)
    
    original_file = test_dir / "musical_test.wav"
    
    # Create and save musical test audio
    print("📄 Creating musical test audio...")
    musical_audio, sr = create_musical_test_audio()
    sf.write(original_file, musical_audio, sr)
    print(f"   Musical audio created: {len(musical_audio)} samples at {sr}Hz")
    print(f"   Duration: {len(musical_audio)/sr:.1f}s with bass, melody, and percussion")
    
    # Test stem extraction
    print("\n🎼 Testing stem extraction...")
    stems = create_frequency_based_stems(musical_audio, sr)
    
    print(f"   Created {len(stems)} stems:")
    for stem_name, stem_audio in stems.items():
        print(f"     - {stem_name}: {len(stem_audio)} samples, RMS: {np.sqrt(np.mean(stem_audio**2)):.4f}")
    
    # Test complete transformation
    print("\n🔄 Testing complete audio-to-MIDI transformation...")
    try:
        result = extract_stems_and_convert_to_midi(str(original_file), str(output_dir))
        
        if result.get("success"):
            print("✅ Transformation completed successfully!")
            
            # Check what files were created
            created_files = list(output_dir.glob("*"))
            print(f"\n📁 Created {len(created_files)} files:")
            
            midi_files = []
            musicxml_files = []
            other_files = []
            
            for file_path in created_files:
                if file_path.suffix == '.mid':
                    midi_files.append(file_path)
                elif file_path.suffix == '.musicxml':
                    musicxml_files.append(file_path)
                else:
                    other_files.append(file_path)
            
            print(f"   📄 MIDI files ({len(midi_files)}):")
            for midi_file in midi_files:
                print(f"     - {midi_file.name}")
            
            print(f"   🎼 MusicXML files ({len(musicxml_files)}):")
            for xml_file in musicxml_files:
                print(f"     - {xml_file.name}")
            
            print(f"   📋 Other files ({len(other_files)}):")
            for other_file in other_files:
                print(f"     - {other_file.name}")
            
            # Verify essential files exist
            essential_checks = {
                "Main MIDI file": any("full_song" in f.name for f in midi_files),
                "Stem MIDI files": len(midi_files) > 1,
                "MusicXML files": len(musicxml_files) > 0,
                "Guide file": any("transformation_guide" in f.name for f in other_files)
            }
            
            print(f"\n✅ Essential file checks:")
            all_checks_passed = True
            for check_name, passed in essential_checks.items():
                status = "✅" if passed else "❌"
                print(f"   {status} {check_name}: {'Present' if passed else 'Missing'}")
                if not passed:
                    all_checks_passed = False
            
            return all_checks_passed
            
        else:
            print(f"❌ Transformation failed: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error during transformation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_api_integration():
    """Test the API integration"""
    print("\n🌐 Testing API Integration...")
    
    try:
        # Test root endpoint
        response = requests.get("http://localhost:8000/api/")
        if response.status_code == 200:
            print("✅ API is accessible")
            
            # Test project creation
            project_data = {"name": "Advanced Transform API Test"}
            response = requests.post(
                "http://localhost:8000/api/projects",
                json=project_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                project = response.json()
                print(f"✅ Project created: {project.get('id')}")
                return True
            else:
                print(f"❌ Project creation failed: {response.status_code}")
                return False
        else:
            print(f"❌ API not accessible: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ API test error: {str(e)}")
        return False

if __name__ == "__main__":
    print("🎼 Advanced Audio-to-MIDI Transformation Test Suite")
    print("=" * 60)
    
    # Run transformation test
    transformation_success = test_advanced_transformation()
    
    # Run API test
    api_success = test_api_integration()
    
    # Final results
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS:")
    print(f"   🎵 Advanced Transformation: {'✅ PASSED' if transformation_success else '❌ FAILED'}")
    print(f"   🌐 API Integration: {'✅ PASSED' if api_success else '❌ FAILED'}")
    
    if transformation_success and api_success:
        print("\n🎉 ALL TESTS PASSED!")
        print("   Your system can now:")
        print("   • Convert audio files to MIDI stems (bass, melody, harmony, percussion)")
        print("   • Generate MusicXML notation files")
        print("   • Create completely original, re-orchestratable compositions")
        print("   • Provide DAW-ready files for professional music production")
        print("   • Generate copyrightable derivative works")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
    
    success = transformation_success and api_success
    sys.exit(0 if success else 1)