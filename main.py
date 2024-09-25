# main_app.py
import uvicorn
from app.main_app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
