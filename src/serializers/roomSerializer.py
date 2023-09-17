def RoomSerializer(room) -> dict:
    return {
        "id": room["id"],
        "name": room["name"],
        "members": room["members"]
    }