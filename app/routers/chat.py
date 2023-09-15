import uuid

from bson import ObjectId
from fastapi import APIRouter, Request, HTTPException
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocket, WebSocketDisconnect

from app import oauth2
from app.database import User, Room
from app.schemas import ChatRoom

# from app import oauth2
# from app.database import Chat, Room, User
# from app.schemas import ChatRoom

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()


@router.get("/")
def get_chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@router.post("/create_room/", response_model=ChatRoom)
async def create_group(room: ChatRoom, user_id: str = Depends(oauth2.require_user)):
    room_id = str(uuid.uuid4())
    room.id = room_id
    inserted_group = Room.insert_one(room.dict())
    if not inserted_group.acknowledged and user_id:
        raise HTTPException(status_code=500, detail="Failed to create the room")
    return room


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    # append for save messages into db


manager = ConnectionManager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    user = User.find_one({"_id": ObjectId(client_id)})
    if not user:
        await websocket.close()
        return

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"{user['name']} : {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{user['name']} left the chat")



