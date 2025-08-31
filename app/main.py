import uvicorn
from fastapi import FastAPI
from app.api.v1.letta import router as letta_router
from app.api.v1.conversation import router as conversation_router
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="eq-chat-service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(letta_router, prefix="/v1")
app.include_router(conversation_router, prefix="/v1")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=5002, reload=True)