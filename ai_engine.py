import os
import logging
from pydub import AudioSegment

def generate_script(anthropic_client, model, article_text, target_length_minutes):
    """
    Generates a conversational podcast script using Anthropic's Claude.
    
    Args:
        anthropic_client: The Anthropic API client.
        model (str): The model ID to use.
        article_text (str): The source text to summarize.
        target_length_minutes (int): Desired podcast length.
        
    Returns:
        str: The generated script text.
    """
    system_prompt = (
        "You are writing a conversational podcast script for two hosts based on the provided article. "
        "Host A is the explainer — synthesizes and contextualizes from the article. "
        "Host B is the skeptic/questioner — pushes back, asks clarifying questions, highlights tension. "
        "The script should NOT read the article aloud. It should discuss, argue, and synthesize. "
        "Quotes from the original should be paraphrased unless a short exact quote meaningfully adds to the conversation. "
        "Lines MUST be prefixed strictly with 'HOST_A:' or 'HOST_B:'. Do not include sound effects or other staging instructions. "
        f"The target length for this podcast is approximately {target_length_minutes} minutes, so aim for a proportional word count (around {target_length_minutes * 150} words)."
    )
    
    try:
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Here is the article text:\n\n{article_text[:20000]}"}
            ]
        )
        return response.content[0].text
    except Exception as e:
        logging.error(f"Failed to generate script: {e}")
        return None

def parse_script(script_text):
    """
    Parses the raw script text into a list of (host, dialogue) pairs.
    """
    lines = script_text.split('\n')
    parsed = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('HOST_A:'):
            parsed.append(('HOST_A', line[len('HOST_A:'):].strip()))
        elif line.startswith('HOST_B:'):
            parsed.append(('HOST_B', line[len('HOST_B:'):].strip()))
        elif line.startswith('**HOST_A:**'):
            parsed.append(('HOST_A', line[len('**HOST_A:**'):].strip()))
        elif line.startswith('**HOST_B:**'):
            parsed.append(('HOST_B', line[len('**HOST_B:**'):].strip()))
    return parsed

def generate_audio_for_lines(openai_client, lines, model, host_a_voice, host_b_voice, temp_dir):
    """
    Generates audio files for each line of dialogue using OpenAI's TTS.
    """
    audio_files = []
    for idx, (host, text) in enumerate(lines):
        if not text:
            continue
        voice = host_a_voice if host == 'HOST_A' else host_b_voice
        filename = os.path.join(temp_dir, f"{idx:04d}_{host}.mp3")
        try:
            response = openai_client.audio.speech.create(
                model=model,
                voice=voice,
                input=text
            )
            response.stream_to_file(filename)
            audio_files.append(filename)
        except Exception as e:
            logging.error(f"Failed to generate audio for line {idx}: {e}")
            raise e
    return audio_files

def stitch_audio(audio_files, output_filename, tags=None):
    """
    Merges multiple audio files and exports with ID3 metadata.
    """
    try:
        combined = AudioSegment.empty()
        for file in audio_files:
            segment = AudioSegment.from_mp3(file)
            combined += segment
        
        export_kwargs = {"format": "mp3", "bitrate": "64k"}
        if tags:
            export_kwargs["tags"] = tags
            
        combined.export(output_filename, **export_kwargs)
        return True
    except Exception as e:
        logging.error(f"Failed to stitch audio: {e}")
        return False
