import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv

# Locate and load the .env file from the project root folder.
# This ensures it resolves correctly regardless of whether the app is run from root or frontend/
backend_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(backend_dir)
env_path = os.path.join(root_dir, ".env")

# Load variables into environment
load_dotenv(dotenv_path=env_path)

# Retrieve the API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def generate_response(user_message: str) -> str:
    """
    Sends a message to Google Gemini API and retrieves the generated response.
    
    Args:
        user_message (str): The chat prompt submitted by the user.
        
    Returns:
        str: The generated response from Gemini.
        
    Raises:
        ValueError: If the user input is empty or the API key is missing.
        ConnectionError: If a network or connectivity issue occurs.
        RuntimeError: If the Gemini API returns an error or is unavailable.
    """
    # 1. Handle Empty Input
    if not user_message or not user_message.strip():
        raise ValueError("User message cannot be empty.")

    # 2. Handle Missing API Key
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is missing. Please ensure you have created a '.env' file "
            "at the project root and added your key, for example:\n"
            "GEMINI_API_KEY=AIzaSy..."
        )

    # 3. Configure Google Generative AI
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        raise RuntimeError(f"Failed to configure Gemini client: {str(e)}")

    # 4. Generate Content via Gemini API
    try:
        # Using the standard lightweight and fast model: gemini-2.5-flash
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(user_message)
        
        # Verify the response object and its text field
        if response and response.text:
            return response.text
        else:
            raise RuntimeError("Received an empty response from the Gemini API.")
            
    except Exception as e:
        error_msg = str(e).lower()
        
        # Categorize the API failure for user friendliness
        if "api_key_invalid" in error_msg or "key not valid" in error_msg:
            raise PermissionError(
                "Invalid API Key. The GEMINI_API_KEY configured in your '.env' file "
                "could not be authorized by Google."
            )
        elif "quota" in error_msg or "limit" in error_msg or "429" in error_msg:
            raise RuntimeError(
                "Gemini API rate limit or quota exceeded. Please wait a moment and try again."
            )
        elif "conn" in error_msg or "dns" in error_msg or "socket" in error_msg or "unreachable" in error_msg:
            raise ConnectionError(
                "Network Error: Unable to reach Google servers. Please check your internet connection."
            )
        else:
            raise RuntimeError(f"Gemini API Error: {str(e)}")
