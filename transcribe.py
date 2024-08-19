import pyaudio
import numpy as np
import whisper
import torch

# Audio recording parameters
RATE = 16000  # Sample rate
CHUNK = 4096  # Buffer size

# Load the Whisper model
model = whisper.load_model("small")  # Choose "tiny", "base", "small", "medium", or "large"

# Initialize PyAudio
p = pyaudio.PyAudio()

def open_stream():
    return p.open(format=pyaudio.paInt16,
                  channels=1,
                  rate=RATE,
                  input=True,
                  frames_per_buffer=CHUNK)

# Open an audio stream for recording
stream = open_stream()

print("Listening... Press Ctrl+C to stop.")

try:
    while True:
        try:
            # Read audio data from the stream
            data = stream.read(CHUNK, exception_on_overflow=False)
            
            # Convert the audio data to a NumPy array and make it writable
            audio_data = np.frombuffer(data, dtype=np.int16).copy()
            
            # Convert the NumPy array to a floating-point tensor
            audio_tensor = torch.from_numpy(audio_data).float() / 32768.0  # Normalize to [-1, 1]
            
            # Compute the log-mel spectrogram
            mel = whisper.log_mel_spectrogram(audio_tensor).to(model.device)
    
            # Transcribe the audio chunk
            result = model.transcribe(mel, language="en")
            
            # Print the transcribed text
            print("You said:", result["text"])

        except IOError as e:
            # Handle stream overflow
            if e.errno == -9981:
                print(f"Input overflowed: {e}")
            elif e.errno == -9988:
                print(f"Stream closed, reopening...")
                stream.stop_stream()
                stream.close()
                stream = open_stream()
            continue

except KeyboardInterrupt:
    print("Stopped.")
    
    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    
    # Terminate PyAudio
    p.terminate()
