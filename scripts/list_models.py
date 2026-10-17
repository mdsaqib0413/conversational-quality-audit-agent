"""List Google Gemini models available for the configured API key that support generateContent."""

import os
import sys
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv(override=True)

def list_supported_models():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[!] Error: GEMINI_API_KEY is not set in environment or .env file.")
        print("Please add your key to .env:")
        print("  GEMINI_API_KEY=AIzaSy...")
        sys.exit(1)

    print(f"[*] Querying available Gemini models for API key ({api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else ''})...\n")

    # Try modern google-genai SDK first
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        supported = []
        try:
            for model in client.models.list():
                actions = getattr(model, "supported_actions", None) or getattr(model, "supported_generation_methods", None) or []
                model_name = getattr(model, "name", str(model))
                display_name = getattr(model, "display_name", "") or ""
                
                is_generate_content = False
                if actions:
                    is_generate_content = any("generateContent" in str(act) for act in actions)
                else:
                    is_generate_content = "gemini" in model_name.lower()

                if is_generate_content:
                    supported.append((model_name, display_name, actions))

            if not supported:
                print("No models with generateContent capability found.")
                return

            print(f"[+] Found {len(supported)} models supporting generateContent:\n")
            print(f"{'Model Identifier (for GEMINI_MODEL)':<42} | {'Display Name'}")
            print("-" * 80)
            for m_name, d_name, _ in supported:
                clean_name = m_name.replace("models/", "")
                print(f"{clean_name:<42} | {d_name}")

            print("\nRecommendation: Pick a model above (e.g. gemini-2.0-flash or gemini-2.5-flash) and set it in .env:")
            print("   GEMINI_MODEL=gemini-2.0-flash")
            return

        except Exception as e:
            err_msg = str(e)
            if "400" in err_msg and "INVALID_ARGUMENT" in err_msg:
                print(f"[!] Error: Gemini API rejected the key as INVALID.")
                print(f"Details: {err_msg}")
                print("\nPlease check your API key at: https://aistudio.google.com/app/apikey")
                sys.exit(1)
            raise e

    except ImportError:
        pass

    # Fallback to legacy google.generativeai
    try:
        import google.generativeai as legacy_genai
        legacy_genai.configure(api_key=api_key)
        
        supported = []
        for m in legacy_genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                supported.append((m.name.replace("models/", ""), m.display_name))

        print(f"[+] Found {len(supported)} models supporting generateContent:\n")
        print(f"{'Model Identifier (for GEMINI_MODEL)':<42} | {'Display Name'}")
        print("-" * 80)
        for m_name, d_name in supported:
            print(f"{m_name:<42} | {d_name}")

    except Exception as e:
        print(f"[!] Error fetching models: {e}")
        sys.exit(1)

if __name__ == "__main__":
    list_supported_models()
