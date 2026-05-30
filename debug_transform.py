#!/usr/bin/env python3

import sys
sys.path.append('/app/backend')

import numpy as np
import librosa
import soundfile as sf
from pathlib import Path

def create_simple_test_audio():
    """Create a very simple test audio file"""
    duration = 3  # 3 seconds
    sample_rate = 22050
    
    t = np.linspace(0, duration, duration * sample_rate)
    
    # Simple chord progression
    frequencies = [261.6, 329.6, 392.0]  # C-E-G chord
    audio = sum(np.sin(2 * np.pi * freq * t) * 0.2 for freq in frequencies)
    
    # Add some rhythm
    for i in range(0, len(audio), sample_rate):
        if i < len(audio) - 1000:
            audio[i:i+1000] *= 1.5  # Accent every second
    
    return audio, sample_rate

def test_basic_pitch_directly():
    """Test basic-pitch functionality directly"""
    print("🎵 Testing Basic-Pitch Audio-to-MIDI Conversion")
    print("=" * 50)
    
    # Create test file
    test_dir = Path("/tmp/basic_pitch_test")
    test_dir.mkdir(exist_ok=True)
    
    audio, sr = create_simple_test_audio()
    test_file = test_dir / "simple_test.wav"
    sf.write(test_file, audio, sr)
    print(f"Created test file: {test_file}")
    
    try:
        # Import basic-pitch
        from basic_pitch.inference import predict
        
        print("Running basic-pitch prediction...")
        model_output, midi_data, note_events = predict(str(test_file))
        
        print("✅ Basic-pitch prediction successful!")
        
        # Save MIDI
        midi_file = test_dir / "output.mid" 
        midi_data.write(str(midi_file))
        print(f"✅ MIDI saved to: {midi_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic-pitch error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_stem_extraction():
    """Test the stem extraction function"""
    print("\n🎼 Testing Stem Extraction")
    print("=" * 50)
    
    try:
        from server import create_frequency_based_stems
        
        audio, sr = create_simple_test_audio()
        print(f"Test audio: {len(audio)} samples at {sr}Hz")
        
        stems = create_frequency_based_stems(audio, sr)
        
        print(f"✅ Created {len(stems)} stems:")
        for name, stem_audio in stems.items():
            rms = np.sqrt(np.mean(stem_audio**2))
            print(f"   - {name}: RMS = {rms:.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Stem extraction error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_full_transformation():
    """Test the complete transformation pipeline"""
    print("\n🔄 Testing Complete Transformation Pipeline")
    print("=" * 50)
    
    try:
        from server import extract_stems_and_convert_to_midi
        
        # Create test file
        test_dir = Path("/tmp/full_transform_test")
        test_dir.mkdir(exist_ok=True)
        
        audio, sr = create_simple_test_audio()
        test_file = test_dir / "test_input.wav"
        sf.write(test_file, audio, sr)
        
        output_dir = test_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        print(f"Running full transformation on: {test_file}")
        result = extract_stems_and_convert_to_midi(str(test_file), str(output_dir))
        
        if result.get("success"):
            print("✅ Full transformation successful!")
            
            # Check output files
            output_files = list(output_dir.glob("*"))
            print(f"Generated {len(output_files)} files:")
            for f in sorted(output_files):
                print(f"   - {f.name}")
            
            return True
        else:
            print(f"❌ Transformation failed: {result.get('error', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"❌ Full transformation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 Debug Audio-to-MIDI Transformation System")
    print("=" * 50)
    
    # Test 1: Basic-pitch directly
    basic_pitch_works = test_basic_pitch_directly()
    
    # Test 2: Stem extraction
    stem_extraction_works = test_stem_extraction()
    
    # Test 3: Full pipeline
    full_pipeline_works = test_full_transformation()
    
    print("\n" + "=" * 50)
    print("📊 DEBUG RESULTS:")
    print(f"   Basic-Pitch: {'✅ WORKING' if basic_pitch_works else '❌ BROKEN'}")
    print(f"   Stem Extraction: {'✅ WORKING' if stem_extraction_works else '❌ BROKEN'}")
    print(f"   Full Pipeline: {'✅ WORKING' if full_pipeline_works else '❌ BROKEN'}")
    
    if all([basic_pitch_works, stem_extraction_works, full_pipeline_works]):
        print("\n🎉 ALL SYSTEMS WORKING!")
        print("The issue might be in the API endpoint or database updates.")
    else:
        print("\n⚠️ FOUND ISSUES!")
        print("We need to fix the broken components.")

if __name__ == "__main__":
    main()