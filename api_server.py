import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Import CORS middleware
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

# Import necessary components
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig # Added import
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel

# Load environment variables (e.g., API keys)
load_dotenv()

app = FastAPI(
    title="Browser Agent API",
    description="API server to interact with the Browser Use agent.",
    version="0.1.0",
)

# --- CORS Middleware ---
# Allow requests from the frontend development server
origins = [
    "http://localhost:3000", # Next.js default dev port
    # Add other origins if needed (e.g., your deployed frontend URL)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"], # Allow all headers
)


# --- Model Instantiation ---
def get_gemini_flash_llm() -> BaseChatModel:
    """Instantiates the Gemini 2.5 Flash model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    # Using the model identifier found in eval/service.py
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-04-17",
        google_api_key=api_key,
        temperature=0.0,
        # Add safety_settings if needed, e.g., to allow harmful content for testing if required
        # safety_settings={
        #     HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        #     HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        #     HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        #     HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        # }
    )

# --- Request and Response Models ---
class TaskRequest(BaseModel):
    task: str
    # Add other potential parameters like session_id if needed later

class TaskResponse(BaseModel):
    result: str | None = None
    error: str | None = None
    # Add other potential response fields like intermediate_steps

# --- API Endpoints ---
@app.post("/run_task", response_model=TaskResponse)
async def run_task_endpoint(request: TaskRequest):
    """
    Receives a task instruction, runs the Browser Use agent, and returns the result.
    """
    task_description = request.task
    print(f"Received task: {task_description}")

    agent = None # Initialize agent to None for finally block
    try:
        # Instantiate LLM
        llm = get_gemini_flash_llm()

        # --- Browser Configuration for CDP ---
        print("Configuring browser to connect via CDP...")
        browser_config = BrowserConfig(
            # headless=False, # Keep headless=False if you want to see the browser
            cdp_url="http://localhost:9222" # Connect to existing Chrome on port 9222
        )
        browser = Browser(config=browser_config)
        print(f"Browser configured with CDP URL: {browser_config.cdp_url}")
        # -------------------------------------

        # Instantiate Agent with the pre-configured browser
        agent = Agent(task=task_description, llm=llm, browser=browser)

        # Run agent asynchronously
        print(f"Running agent for task: '{task_description}'...")
        agent_result = await agent.run()
        print(f"Agent finished. Result: {agent_result}")

        # Return the actual result
        return TaskResponse(result=str(agent_result))

    except ValueError as ve: # Catch specific error for missing API key
        print(f"Configuration error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print(f"Error running task '{task_description}': {type(e).__name__}: {e}")
        # Consider logging the stack trace for debugging: import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error running agent: {type(e).__name__}: {e}")
    finally:
        # Ensure the browser is closed even if errors occur
        if agent and agent.browser:
            print("Closing browser...")
            try:
                await agent.close()
                print("Browser closed.")
            except Exception as close_err:
                print(f"Error closing browser: {type(close_err).__name__}: {close_err}")

@app.get("/")
async def read_root():
    return {"message": "Browser Agent API is running."}

# --- Server Startup ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000)) # Default to port 8000 if not set
    uvicorn.run(app, host="0.0.0.0", port=port)
    print(f"Server started on port {port}")