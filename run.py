import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


# To quit existing server:  lsof -ti:8000 | xargs kill -9
# Then run python run.py

# First run python run.py
# Then run the agents
# Cuz this scripts starts the API endpoints