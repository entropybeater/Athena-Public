import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    import athena
    print("✅ Libraries found.")
except ImportError as e:
    print(f"❌ Missing library: {e}")
    sys.exit(1)

# Load .env
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

def verify():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ API Key not found in .env file.")
        return

    # Safe way to show key existence without indexing errors
    display_key = str(api_key)
    print(f"✅ Key loaded successfully (Length: {len(display_key)})")
    print(f"✅ Athena location: {athena.__file__}")
    print("\n🚀 Everything is green! You are ready to start Athena.")

if __name__ == "__main__":
    verify()