import subprocess
from pathlib import Path

def download_model():
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    model_path = model_dir / "qwen2.5-7b-instruct-q4_K_M.gguf"

    if model_path.exists():
        print(f"Model already exists at {model_path}")
        return

    print("Downloading Qwen2.5-7B-Instruct Q4_K_M (4.5 GB)...")
    url = "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf"

    cmd = ["curl", "-L", url, "-o", str(model_path)]
    subprocess.run(cmd, check=True)
    print("Download complete.")

if __name__ == "__main__":
    download_model()
    print("\nSetup finished. Edit .env if needed, then run: python run.py")
