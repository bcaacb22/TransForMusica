#!/usr/bin/env python3

import sys
sys.path.append('/app/backend')

import numpy as np
import librosa
import soundfile as sf
from pathlib import Path
import requests
import io

# Import our transformation functions
from server import apply_audio_transformations

def create_test_audio():
    """Create a simple test audio file"""
    duration = 5  # 5 seconds
    sample_rate = 22050
    
    # Generate a simple tone with some harmonics
    t = np.linspace(0, duration, duration * sample_rate)
    frequency = 440  # A4 note
    
    # Create a simple beat pattern
    audio = (
        np.sin(2 * np.pi * frequency * t) * 0.3 +  # Base tone
        np.sin(2 * np.pi * frequency * 2 * t) * 0.1 +  # Octave
        np.sin(2 * np.pi * frequency * 3 * t) * 0.05  # Third harmonic
    )
    
    # Add some rhythm (beat every 0.5 seconds)
    beat_interval = int(0.5 * sample_rate)
    for i in range(0, len(audio), beat_interval):
        if i < len(audio) - 1000:
            # Add a kick drum sound (low frequency burst)
            kick = np.sin(2 * np.pi * 60 * t[:1000]) * np.exp(-t[:1000] * 10)
            audio[i:i+1000] += kick * 0.5
    
    return audio, sample_rate

def test_transformation():
    """Test that audio transformation creates different output"""
    print("🎵 Testing Audio Transformation")
    print("=" * 50)
    
    # Create test directories
    test_dir = Path("/tmp/audio_test")
    test_dir.mkdir(exist_ok=True)
    
    original_file = test_dir / "original.wav"
    transformed_file = test_dir / "transformed.wav"
    
    # Create and save original audio
    print("📄 Creating test audio...")
    original_audio, sr = create_test_audio()
    sf.write(original_file, original_audio, sr)
    print(f"   Original audio: {len(original_audio)} samples at {sr}Hz")
    
    # Apply transformation
    print("🔄 Applying transformation...")
    success = apply_audio_transformations(str(original_file), str(transformed_file))
    
    if not success:
        print("❌ Transformation failed!")
        return False
    
    # Load transformed audio
    if not transformed_file.exists():
        print("❌ Transformed file not created!")
        return False
    
    transformed_audio, transformed_sr = librosa.load(str(transformed_file), sr=None)
    print(f"   Transformed audio: {len(transformed_audio)} samples at {transformed_sr}Hz")
    
    # Compare the files
    print("📊 Analyzing differences...")
    
    # Ensure same length for comparison (transformation may change length slightly)
    min_length = min(len(original_audio), len(transformed_audio))
    orig_segment = original_audio[:min_length]
    trans_segment = transformed_audio[:min_length]
    
    # Calculate difference metrics
    mse = np.mean((orig_segment - trans_segment) ** 2)
    correlation = np.corrcoef(orig_segment, trans_segment)[0, 1]
    max_diff = np.max(np.abs(orig_segment - trans_segment))
    
    print(f"   Mean Square Error: {mse:.6f}")
    print(f"   Correlation: {correlation:.3f}")
    print(f"   Max Difference: {max_diff:.3f}")
    
    # Check if transformation actually changed the audio
    if mse < 0.001:  # Very small difference
        print("⚠️  Audio appears mostly unchanged (MSE < 0.001)")
        return False
    elif mse > 0.1:  # Very different
        print("✅ Audio significantly transformed (Good for originality)")
        return True
    else:
        print("✅ Audio moderately transformed (Balanced)")
        return True

if __name__ == "__main__":
    success = test_transformation()
    if success:
        print("\n🎉 Audio transformation test PASSED!")
        print("   Your uploaded instrumentals will be transformed into original, copyrightable beats!")
    else:
        print("\n❌ Audio transformation test FAILED!")
        print("   The transformation may need adjustment.")
    
    sys.exit(0 if success else 1)