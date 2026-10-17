"""Check system and environment setup for ShopEase QA Audit Agent."""

import os
import sys
import shutil
from pathlib import Path
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load environment with override=True to ensure .env takes precedence over OS session variables
env_path = REPO_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)


from typing import Optional

def check_setup(model_override: Optional[str] = None) -> int:
    print("=" * 65)
    print("📋 SHOPEASE AUDIT AGENT: SYSTEM & ENVIRONMENT SETUP CHECK")
    print("=" * 65)

    checklist = []
    overall_pass = True

    # 1. .env exists
    if env_path.exists():
        checklist.append(("1. Configuration file (.env)", True, f"Found at {env_path.name}"))
    else:
        checklist.append(("1. Configuration file (.env)", False, "Missing .env file. Copy from .env.example"))
        overall_pass = False

    # 2. GEMINI_API_KEY set
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key and api_key != "your_gemini_api_key_here":
        checklist.append(("2. GEMINI_API_KEY configured", True, f"Set ({api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else ''})"))
    else:
        checklist.append(("2. GEMINI_API_KEY configured", False, "GEMINI_API_KEY is missing or using placeholder in .env"))
        overall_pass = False

    # 3. Required Python packages import
    required_pkgs = [
        ("google.genai", "google-genai"),
        ("pydantic", "pydantic"),
        ("yaml", "pyyaml"),
        ("pydub", "pydub"),
        ("edge_tts", "edge-tts"),
        ("sentence_transformers", "sentence-transformers"),
        ("chromadb", "chromadb"),
        ("streamlit", "streamlit"),
        ("plotly", "plotly"),
        ("jinja2", "jinja2"),
        ("xhtml2pdf", "xhtml2pdf")
    ]
    missing_pkgs = []
    for mod_name, pkg_name in required_pkgs:
        try:
            __import__(mod_name)
        except ImportError:
            missing_pkgs.append(pkg_name)

    if not missing_pkgs:
        checklist.append(("3. Required Python packages", True, f"All {len(required_pkgs)} packages imported successfully"))
    else:
        checklist.append(("3. Required Python packages", False, f"Missing: {', '.join(missing_pkgs)}. Run 'pip install -r requirements.txt'"))
        overall_pass = False

    # 4. FFmpeg on PATH
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        checklist.append(("4. FFmpeg executable on PATH", True, f"Found: {ffmpeg_bin}"))
    else:
        checklist.append(("4. FFmpeg executable on PATH", False, "FFmpeg not found. Install via 'winget install Gyan.FFmpeg' and add bin to PATH."))
        overall_pass = False

    # 5. Gemini Models Query & GEMINI_MODEL validation
    target_model = (model_override or os.getenv("GEMINI_MODEL", "")).strip()
    available_model_names = []
    available_flash_models = []
    models_api_ok = False
    model_check_msg = ""

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            models = list(client.models.list())
            for m in models:
                raw_name = getattr(m, "name", str(m))
                clean_name = raw_name.replace("models/", "")
                available_model_names.append(clean_name)
                if "flash" in clean_name.lower():
                    available_flash_models.append(clean_name)

            models_api_ok = True
        except Exception as e:
            models_api_ok = False
            model_check_msg = f"API error connecting with key: {e}"

    if not api_key:
        checklist.append(("5. GEMINI_MODEL available", False, "Skipped because GEMINI_API_KEY is not set."))
        overall_pass = False
    elif not models_api_ok:
        checklist.append(("5. GEMINI_MODEL available", False, f"Failed to query models from Google API: {model_check_msg}"))
        overall_pass = False
    else:
        # Check target model
        if not target_model:
            checklist.append(("5. GEMINI_MODEL available", False, f"GEMINI_MODEL is not set in .env. Recommended flash models: {available_flash_models[:4]}"))
            overall_pass = False
        elif target_model in available_model_names:
            checklist.append(("5. GEMINI_MODEL available", True, f"'{target_model}' is available and supports generateContent"))
        else:
            checklist.append((
                "5. GEMINI_MODEL available",
                False,
                f"Model '{target_model}' is not in available models list.\n"
                f"      Available flash models for your key:\n"
                f"      " + ", ".join(available_flash_models[:6])
            ))
            overall_pass = False

    # 6. One tiny real test call works (Structured Output with Pydantic Schema)
    if api_key and models_api_ok and target_model and (target_model in available_model_names):
        try:
            from pydantic import BaseModel
            from src.audit.llm import gemini_gateway

            class TinySetupTest(BaseModel):
                status: str
                message: str

            if target_model:
                gemini_gateway.model_name = target_model
                gemini_gateway._init_client()

            test_result = gemini_gateway.generate_structured(
                prompt="Respond with status 'ready' and message 'ShopEase audit setup OK'",
                schema=TinySetupTest,
                temperature=0.0,
                max_output_tokens=1000
            )
            checklist.append((
                "6. Structured output test call",
                True,
                f"Success (status='{test_result.status}', message='{test_result.message}')"
            ))
        except Exception as e:
            checklist.append(("6. Structured output test call", False, f"Structured output test failed: {e}"))
            overall_pass = False
    else:
        checklist.append(("6. Structured output test call", False, "Skipped due to API key or model issues above."))
        overall_pass = False

    # Print checklist results
    for title, passed, detail in checklist:
        status_badge = "[PASS]" if passed else "[FAIL]"
        print(f"{status_badge:<7} | {title:<32} | {detail}")

    print("=" * 65)
    if overall_pass:
        print("🎉 ALL CHECKS PASSED: Environment and Gemini API are fully operational!\n")
        return 0
    else:
        print("❌ SETUP CHECK FAILED: Resolve the items marked [FAIL] above before running generation.\n")
        return 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Check system and environment setup for ShopEase QA Audit Agent.")
    parser.add_argument("--model", type=str, default=None, help="Override GEMINI_MODEL for check")
    cli_args = parser.parse_args()
    code = check_setup(model_override=cli_args.model)
    sys.exit(code)
