// Gemini 2.5 Flash Lite - Markdown Resume to JSON
client<llm> Gemini2_5FlashLite_ResumeMDtoJSON {
  provider "google-ai"
  options {
    api_key env.GOOGLE_API_KEY
    model "gemini-2.5-flash-lite"
    generationConfig: {
      thinkingConfig: {
        thinkingBudget: 0
      }
      maxOutputTokens: 10000
      temperature 0
      topP 0.1
      topK 1
    }
  }
}

// Gemini 2.5 Flash Lite
client<llm> Gemini3Pro {
  provider "google-ai"
  options {
    api_key env.GOOGLE_API_KEY
    model "gemini-3-pro-preview"
    generationConfig: {
      thinkingConfig: {
        thinkingBudget: 1000
      }
      // maxOutputTokens: 7000
      temperature 0.2
      topP 0.5
      topK 5
    }
  }
}

// Gemini 3 Flash Preview
client<llm> Gemini3FlashPreview {
  provider "google-ai"
  options {
    api_key env.GOOGLE_API_KEY
    model "gemini-3-flash-preview"
    generationConfig: {
      thinkingConfig: {
        thinkingBudget: 2000
      }
      // maxOutputTokens: 5000
      temperature 0
      topP 0.1
      topK 1
    }
  }
}

// Gemini 3 Flash Preview
client<llm> Gemini3FlashPreview_CandidateEvals {
  provider "google-ai"
  options {
    api_key env.GOOGLE_API_KEY
    model "gemini-3-flash-preview"
    generationConfig: {
      thinkingConfig: {
        thinkingBudget: 2000
      }
      // maxOutputTokens: 5000
      temperature 0.7
      topP 1
      topK 10
    }
  }
}
