from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse, Response
from typing import List, Optional
import asyncio
import json
import io
from datetime import datetime
from pydantic import Field, BaseModel

from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.api.deps import get_current_user
from app.db.mongodb import get_gridfs
from bson import ObjectId
from app.services.copilot_service import run_copilot_graph

router = APIRouter()

async def career_copilot_stream(user_input: str, file_content: Optional[bytes] = None, filename: Optional[str] = None):
    """
    Executes LangGraph and streams progress and final results.
    """
    try:
        # For simplicity, we run the graph fully and then stream the response
        # In a more advanced setup, we could stream from each node
        final_state = await run_copilot_graph(user_input, file_content, filename)
        
        if final_state.get("error"):
            yield f"data: {json.dumps({'content': f'Error: {final_state['error']}'})}\n\n"
            return

        # Build a conversational summary based on the graph state
        intent = final_state.get("intent")
        content = ""
        
        if intent == "resume_analysis":
            rd = final_state.get("resume_data") or {}
            sg = final_state.get("skill_gap") or {}
            rm = final_state.get("roadmap") or {}
            
            content = f"# Resume Analysis Summary\n\n"
            content += f"**Experience Level:** {rd.get('experience_level', 'N/A').capitalize()}\n\n"
            
            content += f"### 🛠 Skills Identified\n\n"
            skills = rd.get('skills', [])
            if isinstance(skills, list):
                for skill in skills:
                    content += f"- {skill}\n"
            else:
                content += f"{skills}\n"
            content += "\n"
            
            content += f"### 🎯 Skill Gap Analysis ({sg.get('target_role')})\n\n"
            content += f"✅ **Matched Skills:**\n\n"
            content += ", ".join(sg.get('matched_skills', [])) + "\n\n"
            
            content += f"❌ **Missing Skills:**\n\n"
            content += ", ".join(sg.get('missing_skills', [])) + "\n\n"
            
            content += f"### 🗺 Personalized Roadmap\n\n"
            for step in rm.get("weeks", []):
                content += f"#### Week {step['week']}: {step['topic']}\n\n"
                for task in step['tasks']:
                    content += f"- {task}\n"
                content += "\n"
            
            if rm.get("project_suggestions"):
                content += f"### 🚀 Suggested Projects\n\n"
                for proj in rm.get("project_suggestions"):
                    content += f"- {proj}\n"
            
            # Removed structured JSON block from response to keep it user-friendly
                    
        elif intent == "roadmap_generation":
            sg = final_state.get("skill_gap") or {}
            rm = final_state.get("roadmap") or {}
            content = f"# Career Roadmap: {sg.get('target_role')}\n\n"
            content += f"Based on your goal, here is your customized learning path:\n\n"
            
            for step in rm.get("weeks", []):
                content += f"### 🗓 Week {step['week']}: {step['topic']}\n\n"
                for task in step['tasks']:
                    content += f"- {task}\n"
                content += "\n"
            
            if rm.get("project_suggestions"):
                content += f"### 🚀 Recommended Projects\n\n"
                for proj in rm.get("project_suggestions"):
                    content += f"- {proj}\n"
                    
            # Removed structured JSON block from response to keep it user-friendly
            
            content += f"\n*Keep going! You're making great progress towards your career goals.*"
            
        elif intent == "interview_preparation":
            content = "The **Interview Preparation** module is now live! 🚀\n\nTo start a practice session, please head to the Interview section or use the dedicated `/interview/start` API. I can help you with technical, HR, and rapid-fire rounds tailored to your role and experience."
            
        else:
            content = final_state.get("general_response") or f"I've noted your request: '{user_input}'. How else can I assist with your career today?"

        # Stream the content while preserving newlines and whitespace
        import re
        # This regex matches non-whitespace sequences OR whitespace sequences (including newlines)
        chunks = re.findall(r'\S+|\s+', content)
        
        for chunk in chunks:
            yield f"data: {json.dumps({'content': chunk})}\n\n"
            await asyncio.sleep(0.02) # Faster streaming
            
        # Send completed signal with full data for frontend richness if needed
        yield f"data: {json.dumps({'content': '', 'status': 'completed', 'final_state': {
            'intent': intent,
            'resume_data': final_state.get('resume_data'),
            'skill_gap': final_state.get('skill_gap'),
            'roadmap': final_state.get('roadmap')
        }})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'content': f'An unexpected error occurred: {str(e)}'})}\n\n"

@router.get("/sessions", response_model=List[dict])
async def get_sessions(current_user: User = Depends(get_current_user)):
    """Retrieve all chat sessions for the current user."""
    sessions = await ChatSession.find(ChatSession.user_id == str(current_user.id)).sort("-updated_at").to_list()
    return [{
        "id": str(s.id),
        "title": s.title,
        "has_files": any(getattr(m, 'file_id', None) for m in s.messages),
        "created_at": s.created_at,
        "updated_at": s.updated_at
    } for s in sessions]

@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str, current_user: User = Depends(get_current_user)):
    """Retrieve history for a specific session."""
    session = await ChatSession.get(session_id)
    if not session or session.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/chat/stream")
async def chat_stream(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    """
    Handle chat messages with SSE streaming.
    Supports file uploads (PDF, Word, etc.) stored in GridFS.
    """
    # 1. Handle File Upload if present
    file_info = {}
    if file:
        file_content = await file.read()
        if len(file_content) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Resume size must be under 2 MB")
            
        fs = get_gridfs()
        file_id = await fs.upload_from_stream(
            file.filename,
            io.BytesIO(file_content),
            metadata={"contentType": file.content_type, "user_id": str(current_user.id)}
        )
        file_info = {
            "file_id": str(file_id),
            "file_name": file.filename,
            "file_type": file.content_type
        }

    # 2. Handle Session
    if session_id:
        session = await ChatSession.get(session_id)
        if not session or session.user_id != str(current_user.id):
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        # Create new session
        session = ChatSession(
            user_id=str(current_user.id),
            title=message[:30] + "..." if len(message) > 30 else message
        )
        await session.insert()
        session_id = str(session.id)

    # 3. Add User Message to History
    user_msg = ChatMessage(
        role="user", 
        content=message,
        **file_info
    )
    session.messages.append(user_msg)
    
    # 4. Define Generator for SSE
    async def event_generator():
        # First event: send the session_id back
        yield f"data: {json.dumps({'session_id': session_id, 'status': 'started', 'file_info': file_info})}\n\n"
        
        # Get raw file bytes if needed for graph
        file_bytes = None
        if file:
            await file.seek(0)
            file_bytes = await file.read()
            
        full_ai_response = ""
        # Get the real AI stream via LangGraph
        async for chunk_data in career_copilot_stream(message, file_bytes, file.filename if file else None):
            yield chunk_data
            
            try:
                json_str = chunk_data.replace("data: ", "").strip()
                if json_str:
                    data_obj = json.loads(json_str)
                    if "content" in data_obj:
                        full_ai_response += data_obj["content"]
            except Exception as e:
                print(f"Error parsing stream chunk: {e}")

        # 5. Save AI Message and everything to DB after streaming completes
        if full_ai_response:
            ai_msg = ChatMessage(role="ai", content=full_ai_response)
            session.messages.append(ai_msg)
            
        session.updated_at = datetime.utcnow()
        await session.save()

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/chat/download/{file_id}")
async def download_file(file_id: str, current_user: User = Depends(get_current_user)):
    """Download a file from GridFS."""
    try:
        fs = get_gridfs()
        grid_out = await fs.open_download_stream(ObjectId(file_id))
        
        # Verify ownership via metadata
        if grid_out.metadata.get("user_id") != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to access this file")

        content = await grid_out.read()
        return Response(
            content=content,
            media_type=grid_out.metadata.get("contentType"),
            headers={
                "Content-Disposition": f"attachment; filename={grid_out.filename}"
            }
        )
    except Exception as e:
        print(f"Download error: {e}")
        raise HTTPException(status_code=404, detail="File not found")

class UpdateSessionRequest(BaseModel):
    title: str

@router.put("/sessions/{session_id}")
async def update_session(
    session_id: str, 
    req: UpdateSessionRequest, 
    current_user: User = Depends(get_current_user)
):
    """Update session title."""
    session = await ChatSession.get(session_id)
    if not session or session.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.title = req.title
    session.updated_at = datetime.utcnow()
    await session.save()
    return {"message": "Session updated successfully"}

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, current_user: User = Depends(get_current_user)):
    """Delete a specific session and any associated files from GridFS."""
    session = await ChatSession.get(session_id)
    if not session or session.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Clean up associated files from GridFS
    fs = get_gridfs()
    for msg in session.messages:
        if getattr(msg, "file_id", None):
            try:
                # Beanie or Pydantic might store it as a string
                file_oid = ObjectId(msg.file_id)
                await fs.delete(file_oid)
            except Exception as e:
                # Log the error but continue deleting the session
                print(f"Error deleting file {msg.file_id} from GridFS: {e}")
    
    await session.delete()
    return {"message": "Session and associated files deleted successfully"}
