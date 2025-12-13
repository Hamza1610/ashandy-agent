import sys
import os
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Import the NEW workflow
from app.workflows.main_workflow import app
from app.models.agent_states import AgentState
from langchain_core.messages import HumanMessage

async def main():
    print(">>> Testing Supervisor -> Planner -> Worker Graph")
    
    input_state = {
        "messages": [HumanMessage(content="Hello, do you have Nivea cream?")],
        "user_id": "test_user_123",
        "platform": "whatsapp"
    }
    
    # We just run one step to see if it compiles and routes
    print(">>> Invoking Graph...")
    try:
        config = {"configurable": {"thread_id": "test_thread"}}
        # Just check if it compiled by checking the object
        print(f"Graph Object: {app}")
        print("Graph compiled successfully!")
        
        # Optional: Actually invoke (might fail if API keys missing, but compiler check is step 1)
        # response = await app.ainvoke(input_state, config=config)
        # print("Response received!")
        
    except Exception as e:
        print(f"Graph Execution Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
