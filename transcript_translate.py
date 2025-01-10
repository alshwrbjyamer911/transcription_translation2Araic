import os
from pydub import AudioSegment
import speech_recognition as sr
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from googletrans import Translator  # Install with `pip install googletrans==4.0.0-rc1`


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
            return recognizer.recognize_google(audio)
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


def generate_srt_files(chunks, translations, total_audio_duration, output_prefix="subtitles"):
    """
    Generates two SRT files: one for the original text (English) and one for the translated text (Arabic).
    """
    chunk_duration = total_audio_duration / len(chunks)
    
    # Generate English SRT file
    english_output_file = f"{output_prefix}_en.srt"
    with open(english_output_file, "w", encoding="utf-8") as srt_file:
        for idx, chunk in enumerate(chunks):
            start_time = timedelta(seconds=idx * chunk_duration)
            end_time = timedelta(seconds=(idx + 1) * chunk_duration)
            srt_file.write(f"{idx + 1}\n")
            srt_file.write(f"{str(start_time)[:-3]} --> {str(end_time)[:-3]}\n")
            srt_file.write(f"{chunk}\n\n")  # Original text (English)
    print(f"English SRT file generated: {english_output_file}")

    # Generate Arabic SRT file
    arabic_output_file = f"{output_prefix}_ar.srt"
    with open(arabic_output_file, "w", encoding="utf-8") as srt_file:
        for idx, translation in enumerate(translations):
            start_time = timedelta(seconds=idx * chunk_duration)
            end_time = timedelta(seconds=(idx + 1) * chunk_duration)
            srt_file.write(f"{idx + 1}\n")
            srt_file.write(f"{str(start_time)[:-3]} --> {str(end_time)[:-3]}\n")
            srt_file.write(f"{translation}\n\n")  # Translated text (Arabic)
    print(f"Arabic SRT file generated: {arabic_output_file}")


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

    # Translate transcriptions to Arabic
    print("Translating transcriptions to Arabic...")
    translator = Translator()
    translations = [translator.translate(text, src="en", dest="ar").text for text in transcriptions]

    # Generate SRT files for English and Arabic
    generate_srt_files(transcriptions, translations, total_audio_duration)

    # Cleanup temporary files
    for chunk_file in chunk_files:
        os.remove(chunk_file)
    os.remove(wav_file)  # Remove the temporary WAV file


if __name__ == "__main__":
    # Replace 'video.mp4' with your input video or audio file
    video_path = "video.mp4"
    main(video_path)