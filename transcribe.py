#!/usr/bin/env python3.12

import argparse
import os
import numpy as np
import speech_recognition as sr
from datetime import datetime, timedelta
from queue import Queue
from time import sleep
from sys import platform

def list_audio_devices():
    """Lists the available audio input devices and their indices."""
    print("Available audio devices:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"Device Index: {index} - Device Name: {name}")

def get_device_index(target_name):
    """Returns the device index for the given device name."""
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        if target_name in name:
            return index
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--energy_threshold", default=500,
                        help="Energy level for mic to detect.", type=int)
    parser.add_argument("--record_timeout", default=2,
                        help="How real-time the recording is in seconds.", type=float)
    parser.add_argument("--phrase_timeout", default=3,
                        help="How much empty space between recordings before we "
                             "consider it a new line in the transcription.", type=float)
    parser.add_argument("--output_file", default="/home/jason/light-control/transcription.txt", help="File to write transcriptions to.", type=str)
    parser.add_argument("--device_index", default=None, type=int,
                        help="Device index of the microphone to use. Default is None to automatically select HyperX SoloCast.")

    args = parser.parse_args()

    # List audio devices on boot
    list_audio_devices()

    # Automatically set the device index for HyperX SoloCast if not provided
    if args.device_index is None:
        args.device_index = get_device_index("HyperX")
        if args.device_index is None:
            print("HyperX SoloCast not found. Please connect the device or specify another device index.")
            return

    print(f"Using device index {args.device_index} for HyperX SoloCast.")

    # The last time a recording was retrieved from the queue.
    phrase_time = None
    # Thread-safe Queue for passing data from the threaded recording callback.
    data_queue = Queue()
    # We use SpeechRecognition to record our audio because it has a nice feature where it can detect when speech ends.
    recorder = sr.Recognizer()
    recorder.energy_threshold = args.energy_threshold
    # Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to a point where the SpeechRecognizer never stops recording.
    recorder.dynamic_energy_threshold = False

    # Use the specified device index
    source = sr.Microphone(sample_rate=44100, device_index=args.device_index)

    record_timeout = args.record_timeout
    phrase_timeout = args.phrase_timeout

    transcription = ['']

    with source:
        recorder.adjust_for_ambient_noise(source)

    def record_callback(_, audio: sr.AudioData) -> None:
        """
        Threaded callback function to receive audio data when recordings finish.
        audio: An AudioData containing the recorded bytes.
        """
        # Grab the raw bytes and push them into the thread-safe queue.
        data = audio.get_raw_data()
        data_queue.put(audio)

    # Create a background thread that will pass us raw audio bytes.
    # We could do this manually but SpeechRecognition provides a nice helper.
    recorder.listen_in_background(source, record_callback, phrase_time_limit=record_timeout)

    # Cue the user that we're ready to go.
    print("Model loaded.\n")

    # Open the output file in append mode
    with open(args.output_file, "a") as f:
        while True:
            try:
                now = datetime.utcnow()
                # Pull recorded audio from the queue.
                if not data_queue.empty():
                    phrase_complete = False
                    # If enough time has passed between recordings, consider the phrase complete.
                    # Clear the current working audio buffer to start over with the new data.
                    if phrase_time and now - phrase_time > timedelta(seconds=phrase_timeout):
                        phrase_complete = True
                    # This is the last time we received new audio data from the queue.
                    phrase_time = now
                    
                    # Get audio data from queue
                    audio = data_queue.get()
                    
                    # Recognize speech using Google Web Speech API
                    try:
                        text = recorder.recognize_google(audio).strip()
                    except sr.UnknownValueError:
                        text = ""
                    except sr.RequestError as e:
                        print(f"Could not request results; {e}")
                        continue

                    # If we detected a pause between recordings, add a new item to our transcription.
                    # Otherwise, edit the existing one.
                    if phrase_complete:
                        transcription.append(text)
                    else:
                        transcription[-1] = text

                    # Write the updated transcription to the file
                    f.write(f"{text}\n")
                    f.flush()  # Ensure it's written to disk immediately

                    # Clear the console to reprint the updated transcription.
                    os.system('cls' if os.name == 'nt' else 'clear')
                    for line in transcription:
                        print(line)
                    # Flush stdout.
                    print('', end='', flush=True)
                else:
                    # Infinite loops are bad for processors, must sleep.
                    sleep(0.25)
            except KeyboardInterrupt:
                break

    print("\n\nTranscription:")
    for line in transcription:
        print(line)

if __name__ == "__main__":
    main()
