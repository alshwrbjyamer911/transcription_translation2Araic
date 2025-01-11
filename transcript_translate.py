import os
from pydub import AudioSegment
import speech_recognition as sr
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from googletrans import Translator  # Install with `pip install googletrans==4.0.0-rc1`
from langdetect import detect  # Install with `pip install langdetect`


def convert_to_wav(file_path):
    """
    Converts audio/video file to WAV format.
    """
    output_path = "temp_audio.wav"
    audio = AudioSegment.from_file(file_path)
    audio = audio.set_channels(1)  # Mono for better recognition
    audio.export(output_path, format="wav")
    return output_path


def transcribe_chunk(chunk_file, recognizer):
    """
    Transcribes an audio chunk using SpeechRecognition.
    """
    try:
        with sr.AudioFile(chunk_file) as source:
            audio = recognizer.record(source)
            return recognizer.recognize_google(audio, language="auto")  # Auto-detect language
    except Exception as e:
        print(f"Error during transcription for {chunk_file}: {e}")
        return None


def split_audio_into_chunks(audio, chunk_duration_ms, overlap_ms, temp_dir="chunks"):
    """
    Splits audio into overlapping chunks and saves them as temporary files.
    """
    os.makedirs(temp_dir, exist_ok=True)
    chunk_files = []
    start = 0
    while start < len(audio):
        end = start + chunk_duration_ms
        chunk = audio[start:end + overlap_ms]
        chunk_file = os.path.join(temp_dir, f"chunk_{len(chunk_files)}.wav")
        chunk.export(chunk_file, format="wav")
        chunk_files.append(chunk_file)
        start += chunk_duration_ms  # Move by chunk duration (not overlap)
    return chunk_files


def detect_language(text):
    """
    Detects the language of the given text using langdetect.
    """
    try:
        return detect(text)
    except:
        return "en"  # Default to English if detection fails


def generate_srt_files(chunks, translations, total_audio_duration, output_prefix="subtitles", output_language="ar"):
    """
    Generates two SRT files: one for the original text and one for the translated text.
    """
    chunk_duration = total_audio_duration / len(chunks)
    
    # Generate Original Language SRT file
    original_output_file = f"{output_prefix}_original.srt"
    with open(original_output_file, "w", encoding="utf-8") as srt_file:
        for idx, chunk in enumerate(chunks):
            start_time = timedelta(seconds=idx * chunk_duration)
            end_time = timedelta(seconds=(idx + 1) * chunk_duration)
            srt_file.write(f"{idx + 1}\n")
            srt_file.write(f"{str(start_time)[:-3]} --> {str(end_time)[:-3]}\n")
            srt_file.write(f"{chunk}\n\n")  # Original text
    print(f"Original SRT file generated: {original_output_file}")

    # Generate Translated SRT file
    translated_output_file = f"{output_prefix}_{output_language}.srt"
    with open(translated_output_file, "w", encoding="utf-8") as srt_file:
        for idx, translation in enumerate(translations):
            start_time = timedelta(seconds=idx * chunk_duration)
            end_time = timedelta(seconds=(idx + 1) * chunk_duration)
            srt_file.write(f"{idx + 1}\n")
            srt_file.write(f"{str(start_time)[:-3]} --> {str(end_time)[:-3]}\n")
            srt_file.write(f"{translation}\n\n")  # Translated text
    print(f"Translated SRT file generated: {translated_output_file}")


def main(video_path, chunk_duration=5, overlap=1):
    # Convert video/audio file to WAV
    wav_file = convert_to_wav(video_path)
    print(f"Audio extracted: {wav_file}")

    # Load audio file
    audio = AudioSegment.from_wav(wav_file)
    total_audio_duration = len(audio) // 1000  # Convert to seconds

    # Split audio into overlapping chunks
    chunk_duration_ms = chunk_duration * 1000  # Convert to milliseconds
    overlap_ms = overlap * 1000  # Convert to milliseconds
    chunk_files = split_audio_into_chunks(audio, chunk_duration_ms, overlap_ms)

    # Initialize SpeechRecognition
    recognizer = sr.Recognizer()

    # Transcribe each chunk using multithreading
    print("Transcribing audio in chunks...")
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(transcribe_chunk, chunk, recognizer): chunk for chunk in chunk_files}
        transcriptions = [future.result() for future in futures]

    # Remove None values (failed transcriptions)
    transcriptions = [text for text in transcriptions if text]

    if not transcriptions:
        print("Failed to transcribe audio. Exiting.")
        return

    # Detect the input language from the transcribed text
    combined_text = " ".join(transcriptions)
    input_language = detect_language(combined_text)
    print(f"Detected input language: {input_language}")

    # Ask user for output language
    print("Select the output language:")
    print("1. German")
    print("2. Arabic")
    output_language_choice = int(input("Enter the number corresponding to the output language: "))
    
    output_languages = {
        1: "de",
        2: "ar"
    }
    output_language = output_languages.get(output_language_choice, "ar")  # Default to Arabic if invalid choice

    # Translate transcriptions to the selected output language
    print(f"Translating transcriptions to {output_language}...")
    translator = Translator()
    translations = [translator.translate(text, src=input_language, dest=output_language).text for text in transcriptions]

    # Generate SRT files for the original and translated text
    generate_srt_files(transcriptions, translations, total_audio_duration, output_language=output_language)

    # Cleanup temporary files
    for chunk_file in chunk_files:
        os.remove(chunk_file)
    os.remove(wav_file)  # Remove the temporary WAV file


if __name__ == "__main__":
    # Replace 'video.mp4' with your input video or audio file
    video_path = "video.mp4"
    main(video_path)
