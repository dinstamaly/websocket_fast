from bson import ObjectId
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi_jwt_auth import AuthJWT
from starlette import status
from starlette.websockets import WebSocket, WebSocketDisconnect

from .. import oauth2
from ..database import Chat, User, Room
from ..schemas import ChatRoom
from ..serializers.roomSerializer import RoomSerializer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=Path(BASE_DIR, 'templates'))

router = APIRouter()


@router.get("/{room_id}")
def get_chat_page(request: Request, room_id, user_id: str = Depends(oauth2.require_user)):
    user = User.find_one({'_id': ObjectId(str(user_id))})
    return templates.TemplateResponse("chat.html", {"request": request, "room_id": room_id, 'user_id': user['_id']})


@router.post("/create_room/")
async def create_room(room: ChatRoom, user_id: str = Depends(oauth2.require_user)):
    chat_room = Room.find_one({'id': room.id})
    if chat_room:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail='Chat Room already exist')
    inserted_room = Room.insert_one(room.dict())

    if not inserted_room.acknowledged:
        raise HTTPException(status_code=500, detail="Failed to create the chat room")
    new_room = RoomSerializer(Room.find_one({'id': room.id}))
    return {"status": "success", "chat_room": new_room}


@router.get("/info_chat/{id}")
async def get_group(id: str, user_id: str = Depends(oauth2.require_user)):
    room = Room.find_one({"id": id})
    if not room:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='No Room')
    else:
        return RoomSerializer(room)


class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, websocket: WebSocket, message: str, add_to_db: bool, room_id: str, client_id: str):
        if add_to_db:
            await self.add_messages_to_database(message, room_id, client_id)
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_text(message)

    @staticmethod
    async def add_messages_to_database(message: str, room_id: str, client_id: str):
        inserted_message = Chat.message.insert_one({
            "sender": client_id,
            "chat_room_id": room_id,
            "message": message
        })

        if not inserted_message.acknowledged:
            raise HTTPException(status_code=500, detail="Failed to create the group")


manager = ConnectionManager()


@router.get("/last_message/{room_id}")
def get_last_message(request: Request, room_id: str, Authorize: AuthJWT = Depends()):
    messages: list = [
        {
            "chat_room_id": i["chat_room_id"],
            "message": i["message"],
            "sender": i["sender"]
        }
        for i in Chat.message.find() if i["chat_room_id"] == room_id]
    return messages


@router.get("/{room_id}")
def get_chat_page(request: Request, room_id: str):
    room = Chat.rooms.find_one({"id": room_id})
    if not room:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No Group'
        )
    return templates.TemplateResponse("chat.html", {"request": request, "group_id": room_id})


@router.websocket("/ws/{id_client}/{room_id}")
async def websocket_endpoint(websocket: WebSocket, id_client: str, room_id: str):
    await manager.connect(websocket, room_id=room_id)
    user = User.find_one({'_id': ObjectId(str(id_client))})
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(websocket, f"{user['name']}: {data}", add_to_db=True, room_id=room_id, client_id=id_client)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id=room_id)
        await manager.broadcast(
            websocket, f"{user['name']} left the chat", add_to_db=False, room_id=room_id, client_id=id_client
        )

