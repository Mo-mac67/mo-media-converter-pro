import os
import subprocess

def convert_all_mp4_to_mp3():
    current_folder = os.path.dirname(os.path.abspath(__file__))
    files = os.listdir(current_folder)

    mp4_files = [f for f in files if f.lower().endswith(".mp4")]

    if not mp4_files:
        print("No MP4 files found in this folder.")
        return

    for mp4_file in mp4_files:
        mp4_path = os.path.join(current_folder, mp4_file)
        mp3_file = os.path.splitext(mp4_file)[0] + ".mp3"
        mp3_path = os.path.join(current_folder, mp3_file)

        print(f"Converting: {mp4_file} -> {mp3_file}")

        command = [
            "ffmpeg",
            "-y",
            "-i", mp4_path,
            "-vn",
            "-ab", "320k",
            "-ar", "44100",
            mp3_path
        ]

        try:
            subprocess.run(command, check=True)
            print(f"Done: {mp3_file}")
        except subprocess.CalledProcessError:
            print(f"Failed: {mp4_file}")

    print("All conversions finished.")

if __name__ == "__main__":
    convert_all_mp4_to_mp3()