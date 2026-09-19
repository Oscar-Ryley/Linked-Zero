import os
import requests
import json
from dotenv import load_dotenv

# Load your API keys
load_dotenv()
GPTZERO_API_KEY = os.getenv("GPTZERO_API_KEY")
BACKBOARD_API_KEY = os.getenv("BACKBOARD_API_KEY")

# ---------------------------------------------------------
# 1. GPTZERO: The "Slop" Detector
# ---------------------------------------------------------
def analyze_text_for_slop(text):
    print("🔍 Scanning for AI slop with GPTZero...")
    url = "https://api.gptzero.me/v2/predict/text"
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": GPTZERO_API_KEY
    }
    
    payload = {
        "document": text
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        # GPTZero returns a 'completely_generated_prob' (0-1) and detailed sentence-by-sentence analysis
        ai_prob = data['documents'][0]['completely_generated_prob']
        classification = data['documents'][0]['class'] # 'ai', 'human', or 'mixed'
        return ai_prob, classification, data
    else:
        print("GPTZero API Error:", response.text)
        return None, None, None

# ---------------------------------------------------------
# 2. BACKBOARD.IO: The Brain & Investigator
# ---------------------------------------------------------
def investigate_slop_with_backboard(slop_text, ai_probability):
    print(f"🧠 Initiating Backboard.io Investigation (AI Probability: {ai_probability * 100:.2f}%)...")
    
    # Backboard unifies assistants, threads, memory, and 17,000+ models.
    # We are using an HTTP request here for transparency, but you can also use their official SDK!
    
    url = "https://api.backboard.io/v1/chat/completions" # Adjust if you are using their Assistants/Threads endpoint
    
    headers = {
        "Authorization": f"Bearer {BACKBOARD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    You are an investigative AI specializing in detecting hallucinations and misinformation.
    A user has submitted text that was flagged with a {ai_probability * 100}% chance of being AI-generated slop.
    
    Analyze the following text. Tell me:
    1. What the likely prompt was that generated this text.
    2. Any factual hallucinations or bizarre "AIisms" (like 'delve', 'tapestry', etc.) present.
    
    Text: {slop_text}
    """
    
    payload = {
        "model": "claude-3-5-sonnet", # Backboard routes to whatever model you want
        "messages": [{"role": "user", "content": prompt}],
        "memory": True # Turn on Backboard's killer feature: persistent state memory
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        print("Backboard API Error:", response.text)
        return None

# ---------------------------------------------------------
# 3. TYING IT TOGETHER (Hackathon Magic)
# ---------------------------------------------------------
if __name__ == "__main__":
    # Test with some obvious AI-generated content
    suspicious_text = (
        "In today's fast-paced digital landscape, it is crucial to delve into the tapestry of innovation. "
        "Furthermore, as an AI language model, I can tell you that the capital of France is Paris."
    )
    
    # Step 1: Detect
    ai_prob, classification, full_data = analyze_text_for_slop(suspicious_text)
    
    if ai_prob is not None:
        print(f"Verdict: {classification.upper()} (Probability: {ai_prob * 100:.2f}%)")
        
        # Step 2: Investigate if it crosses our threshold
        if ai_prob > 0.50:
            report = investigate_slop_with_backboard(suspicious_text, ai_prob)
            print("\n--- BACKBOARD INVESTIGATIVE REPORT ---")
            print(report)
        else:
            print("This looks like authentic human work. No investigation needed.")