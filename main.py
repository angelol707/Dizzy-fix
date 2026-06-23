from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
from datetime import datetime
import asyncio
import base64
import cv2

app = FastAPI(title="Cybersickness API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
_eye_cascade  = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

# Configuration de la connexion MySQL (XAMPP)
db_config = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "", 
    "database": "cybersickness"
}

# --- MODELES DE DONNEES ---
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str

class SymptomReport(BaseModel):
    session_id: int
    symptom_id: int
    severity: int

# --- ROUTES ---

@app.get("/")
def read_root():
    return {"status": "L'API Cybersickness fonctionne correctement"}

# 1. ROUTE DE LOGIN
@app.post("/api/login")
def login(data: LoginRequest):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT id, username, full_name, ai_sensitivity_score FROM users WHERE username = %s AND password_hash = %s"
        cursor.execute(query, (data.username, data.password))
        user = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if user:
            return {"success": True, "message": "Connexion réussie", "user": user}
        else:
            raise HTTPException(status_code=401, detail="Identifiants incorrects")
            
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Erreur DB : {err}")

# 2. ROUTE D'INSCRIPTION (REGISTER)
@app.post("/api/register")
def register(data: RegisterRequest):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        # On vérifie si le pseudo existe déjà
        cursor.execute("SELECT id FROM users WHERE username = %s", (data.username,))
        if cursor.fetchone():
            cursor.close()
            connection.close()
            raise HTTPException(status_code=400, detail="Ce nom d'utilisateur est déjà pris.")
            
        # Insertion du nouveau joueur avec un score de sensibilité par défaut (5/10)
        query = """
            INSERT INTO users (username, email, password_hash, full_name, ai_sensitivity_score) 
            VALUES (%s, %s, %s, %s, 5)
        """
        cursor.execute(query, (data.username, data.email, data.password, data.full_name))
        connection.commit()
        
        cursor.close()
        connection.close()
        return {"success": True, "message": "Compte créé avec succès !"}
        
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Erreur DB : {err}")

# 3. ROUTE DU QUESTIONNAIRE
class AntecedentsRequest(BaseModel):
    username: str
    motion_sickness: int  # Note de 1 à 5 (sensibilité transports)
    vr_experience: int     # Note de 1 à 5 (habitude de la VR)

# 3. ROUTE DES ANTECEDENTS : Matrice de score personnalisée
@app.post("/api/antecedents")
def save_antecedents(data: AntecedentsRequest):
    try:
        # Lignes = Sensibilité transports (1 à 5)
        # Colonnes = Expérience VR (1 à 5)
        # On définit EXACTEMENT le score pour chaque situation
        score_matrix = {
            # --- Pas du tout sensible (1) ---
            1: {1: 4, 2: 3, 3: 2, 4: 1, 5: 1},
            
            # --- Légèrement sensible (2) ---
            # Pour ton test : ligne 2 (Légèrement), colonne 2 (Quelques fois) -> ça donnera 7 ! (Donc Orange bloqué !)
            2: {1: 8, 2: 7, 3: 5, 4: 3, 5: 2},
            
            # --- Moyennement sensible (3) ---
            3: {1: 9, 2: 8, 3: 6, 4: 5, 5: 3},
            
            # --- Assez sensible (4) ---
            4: {1: 10, 2: 9, 3: 8, 4: 7, 5: 5},
            
            # --- Très sensible (5) ---
            5: {1: 10, 2: 10, 3: 9, 4: 8, 5: 6}
        }
        
        # On récupère le score parfait dans notre tableau
        # Si jamais une valeur sort de nulle part, on met 5 par défaut
        calculated_score = score_matrix.get(data.motion_sickness, {}).get(data.vr_experience, 5)
        
        # Connexion et mise à jour en BDD
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        query = "UPDATE users SET ai_sensitivity_score = %s WHERE username = %s"
        cursor.execute(query, (calculated_score, data.username))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return {"success": True, "score": calculated_score}

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Erreur DB : {err}")


# 4. WEBSOCKET HEAD TRACKING
@app.websocket("/ws/head-tracking")
async def head_tracking_ws(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_event_loop()
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    try:
        while True:
            ret, frame = await loop.run_in_executor(None, cap.read)
            if not ret:
                await asyncio.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = _face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

            payload = {"detected": False, "yaw": 0.0, "pitch": 0.0}

            if len(faces) > 0:
                fx, fy, fw, fh = faces[0]

                # Draw face rectangle
                cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (0, 255, 180), 2)

                # Detect and draw eyes
                roi_gray = gray[fy:fy+fh, fx:fx+fw]
                eyes = _eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=5)
                for (ex, ey, ew, eh) in eyes[:2]:
                    cv2.rectangle(frame, (fx+ex, fy+ey), (fx+ex+ew, fy+ey+eh), (130, 140, 255), 1)

                # Estimate head pose from face center offset
                frame_cx = frame.shape[1] / 2
                frame_cy = frame.shape[0] / 2
                face_cx  = fx + fw / 2
                face_cy  = fy + fh / 2

                yaw   = (face_cx - frame_cx) / (frame.shape[1] / 2) * 45
                pitch = (face_cy - frame_cy) / (frame.shape[0] / 2) * 30

                payload = {"detected": True, "yaw": round(yaw, 1), "pitch": round(pitch, 1)}

            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 55])
            payload["frame"] = base64.b64encode(buf).decode("utf-8")

            await websocket.send_json(payload)
            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[head-tracking] {e}")
    finally:
        cap.release()