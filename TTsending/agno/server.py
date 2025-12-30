"""
Agno Multi-Agent Server for White Paper Generator

This server provides a FastAPI backend for the multi-agent white paper system.
Each agent specializes in a different task (research, outline, writing, review, etc.)

Usage:
    cd agno
    source venv/bin/activate
    python server.py
"""

import os
from typing import Optional
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Import Agno components
from agno.agent import Agent
from agno.models.openai import OpenAIChat

# ===========================================
# Configuration
# ===========================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

# ===========================================
# Agent Definitions (Placeholder)
# ===========================================

# These will be defined based on user's workflow requirements
agents = {}

def get_model():
    """Get the configured LLM model"""
    return OpenAIChat(
        id=DEFAULT_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE,
    )

# ===========================================
# Request/Response Models
# ===========================================

class ChatRequest(BaseModel):
    """Chat request from frontend"""
    message: str
    agent_name: Optional[str] = "default"
    context: Optional[dict] = None

class ChatResponse(BaseModel):
    """Chat response to frontend"""
    response: str
    agent_name: str
    metadata: Optional[dict] = None

class OutlineRequest(BaseModel):
    """Request to generate/polish outline"""
    content: str
    config: Optional[dict] = None

class SearchRequest(BaseModel):
    """Search request for knowledge base"""
    query: str
    mode: Optional[str] = "hybrid"
    top_k: Optional[int] = 20

# ===========================================
# FastAPI App Setup
# ===========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    print("🚀 Starting Agno Multi-Agent Server...")
    print(f"   Model: {DEFAULT_MODEL}")
    print(f"   API Base: {OPENAI_API_BASE}")
    
    # Initialize agents here if needed
    yield
    
    print("🛑 Shutting down Agno server...")

app = FastAPI(
    title="White Paper Multi-Agent API",
    description="Agno-powered multi-agent system for white paper generation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================================
# API Endpoints
# ===========================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "framework": "agno",
        "version": "2.3.7",
        "model": DEFAULT_MODEL,
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    General chat endpoint
    Route to appropriate agent based on agent_name
    """
    try:
        # Create a simple agent for now
        agent = Agent(
            name="WhitePaperAssistant",
            model=get_model(),
            description="I am an AI assistant helping with white paper creation.",
            instructions=[
                "You are a professional white paper writing assistant.",
                "Help users with research, outline creation, and content writing.",
                "Always respond in the same language as the user's query.",
                "For Chinese queries, respond in Chinese.",
            ],
        )
        
        # Run the agent
        response = agent.run(request.message)
        
        return ChatResponse(
            response=response.content if hasattr(response, 'content') else str(response),
            agent_name=request.agent_name or "default",
            metadata={"model": DEFAULT_MODEL}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search")
async def search(request: SearchRequest):
    """
    Knowledge base search endpoint
    Will be implemented with RAG capabilities
    """
    # Placeholder - will be implemented with knowledge tools
    return {
        "success": True,
        "query": request.query,
        "response": f"搜索功能正在开发中。查询: {request.query}",
        "references": [],
    }

@app.post("/api/polish-outline")
async def polish_outline(request: OutlineRequest):
    """
    Polish/optimize outline using AI agent
    """
    try:
        agent = Agent(
            name="OutlinePolisher",
            model=get_model(),
            description="Expert at optimizing white paper outlines",
            instructions=[
                "You are a senior energy policy analysis expert.",
                "Review and optimize white paper outlines.",
                "Always respond in Chinese for Chinese input.",
                "Provide structured improvements with clear sections.",
            ],
        )
        
        prompt = f"""请优化以下白皮书大纲，使其更专业、更完整：

{request.content}

请提供：
1. 优化后的章节标题和简要说明
2. 关键分析要点或问题
3. 建议的数据来源或参考类型
4. 改进建议摘要"""

        response = agent.run(prompt)
        
        return {
            "success": True,
            "polishedOutline": response.content if hasattr(response, 'content') else str(response),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-draft")
async def generate_draft(request: OutlineRequest):
    """
    Generate draft content from outline
    """
    try:
        agent = Agent(
            name="DraftWriter",
            model=get_model(),
            description="Professional white paper content writer",
            instructions=[
                "You are an expert white paper writer.",
                "Generate professional, well-researched content.",
                "Use formal academic tone suitable for government or industry.",
                "Always respond in Chinese for Chinese input.",
            ],
        )
        
        prompt = f"""根据以下大纲生成专业的白皮书内容：

{request.content}

请生成完整的白皮书草稿，包括：
- 专业的前言
- 详细的章节内容
- 数据支撑和分析
- 结论与建议"""

        response = agent.run(prompt)
        
        return {
            "success": True,
            "draft": response.content if hasattr(response, 'content') else str(response),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze-whitepaper")
async def analyze_whitepaper(request: OutlineRequest):
    """
    Analyze and provide feedback on white paper content
    """
    try:
        agent = Agent(
            name="WhitePaperReviewer",
            model=get_model(),
            description="Senior white paper quality analyst",
            instructions=[
                "You are a senior white paper quality analyst.",
                "Analyze content for quality, structure, and credibility.",
                "Provide detailed feedback with specific improvements.",
                "Always respond in Chinese.",
            ],
        )
        
        prompt = f"""请分析以下白皮书内容并提供详细反馈：

{request.content}

请从以下方面进行分析：
1. 内容质量评估
2. 结构分析
3. 专业性与可信度
4. 改进建议
5. 总体评分（1-10分）"""

        response = agent.run(prompt)
        
        return {
            "success": True,
            "analysis": response.content if hasattr(response, 'content') else str(response),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===========================================
# Main Entry Point
# ===========================================

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("AGNO_HOST", "0.0.0.0")
    port = int(os.getenv("AGNO_PORT", 8000))
    
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=True,
    )




