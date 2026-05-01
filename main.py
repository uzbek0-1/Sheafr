from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse , RedirectResponse
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import random
import string

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms = {}

def burn_old_rooms():
    now = datetime.now()
    to_delete = []
    for pin, room in rooms.items():
        if now - room["created_at"] > timedelta(hours=24):
            to_delete.append(pin)
    for pin in to_delete:
        del rooms[pin]
        print(f"Room {pin} burned.")

scheduler = BackgroundScheduler()
scheduler.add_job(burn_old_rooms, "interval", minutes=1)
scheduler.start()

@app.get("/")
def root():
    return  RedirectResponse(url="/chat")

@app.get("/chat")
def get_chat():
    return FileResponse("index.html")

@app.post("/create-room")
def create_room():
    pin = ''.join(random.choices(string.digits, k=6))
    rooms[pin] = {
        "connections": [],
        "messages": [],
        "created_at": datetime.now()
    }
    return {"pin": pin}

@app.get("/join-room/{pin}")
def join_room(pin: str):
    if pin in rooms:
        elapsed = (datetime.now() - rooms[pin]["created_at"]).total_seconds()
        return {"message": "Room found", "pin": pin, "elapsed_seconds": elapsed}
    return {"message": "Room not found"}

@app.websocket("/ws/{pin}")
async def websocket_endpoint(websocket: WebSocket, pin: str):
    if pin not in rooms:
        await websocket.close()
        return

    await websocket.accept()
    rooms[pin]["connections"].append(websocket)

    count = len(rooms[pin]["connections"])
    for conn in rooms[pin]["connections"]:
        await conn.send_text(f"__SYSTEM__:{count} user(s) in room")



    try:
        while True:
            message = await websocket.receive_text()
            rooms[pin]["messages"].append({
                "text": message,
                "timestamp": datetime.now()
            })
            for connection in rooms[pin]["connections"]:
                await connection.send_text(message)
    except WebSocketDisconnect:
        rooms[pin]["connections"].remove(websocket)
        count = len(rooms[pin]["connections"])
        for conn in rooms[pin]["connections"]:
            await conn.send_text(f"__SYSTEM__:{count} user(s) in room")

@app.delete("/burn/{pin}")
async def burn_messages(pin: str, username: str):
    if pin not in rooms:
        return {"message": "Room not found"}
    
    rooms[pin]["messages"] = [
        m for m in rooms[pin]["messages"]
        if not m["text"].startswith(username + ":")
    ]
    
    # Broadcast burn signal to all clients
    for conn in rooms[pin]["connections"]:
        await conn.send_text(f"__BURN__:{username}")
    
    return {"message": "Burned"}