// Gemini 2.5 Flash
client<llm> Gemini2_5Flash {
  provider "google-ai"
  options {
    api_key env.GOOGLE_API_KEY
    model "gemini-2.5-flash"
    generationConfig: {
      thinkingConfig: {
        thinkingBudget: 0
      }
      // maxOutputTokens: 10000
      temperature 0
      topP 0.1
      topK 1
    }
  }
}

// Gemini 2.5 Flash Lite
client<llm> Gemini2_5FlashLite {
  provider "google-ai"
  options {
    api_key env.GOOGLE_API_KEY
    model "gemini-2.5-flash-lite"
    generationConfig: {
      thinkingConfig: {
        thinkingBudget: 0
      }
      // maxOutputTokens: 10000
      temperature 0
      topP 0.1
      topK 1
    }
  }
}

// Gemini 3 Pro Preview
client<llm> Gemini3Pro {
  provider "google-ai"
  options {
    api_key env.GOOGLE_API_KEY
    model "gemini-3-pro-preview"
    generationConfig: {
      thinkingConfig: {
        thinkingBudget: 500
      }
      // maxOutputTokens: 10000
      temperature 0.2
      topP 0.5
      topK 5
    }
  }
}