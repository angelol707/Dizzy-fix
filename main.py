from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
from datetime import datetime
import asyncio
import base64
import cv2
from ultralytics import YOLO

app = FastAPI(title="Cybersickness API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_yolo = YOLO('yolov8n-pose.pt')  # keypoints faciaux : nez, yeux, oreilles

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

            # Inférence YOLOv8-Pose
            results = await loop.run_in_executor(
                None, lambda: _yolo(frame, verbose=False, conf=0.5)
            )

            payload = {"detected": False, "yaw": 0.0, "pitch": 0.0}

            kps_data = results[0].keypoints if results else None
            if kps_data and len(kps_data) > 0:
                # COCO keypoints: 0=nez 1=oeil_g 2=oeil_d 3=oreille_g 4=oreille_d
                kps  = kps_data.xy[0]   # shape (17, 2)
                conf_kps = kps_data.conf[0]  # shape (17,)

                nose    = kps[0];  l_eye = kps[1];  r_eye = kps[2]
                l_ear   = kps[3];  r_ear = kps[4]

                # Dessiner les keypoints faciaux visibles
                face_pts = [(0, (0,255,180)), (1, (130,140,255)), (2, (130,140,255)),
                            (3, (255,160,50)), (4, (255,160,50))]
                for idx, color in face_pts:
                    if conf_kps[idx] > 0.3:
                        cv2.circle(frame, (int(kps[idx][0]), int(kps[idx][1])), 4, color, -1)

                # Label
                box = results[0].boxes
                if box and len(box) > 0:
                    bx1, by1 = map(int, box.xyxy[0][:2])
                    cv2.putText(frame, f"YOLOv8-Pose {float(box.conf[0]):.2f}",
                                (bx1, max(by1 - 6, 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 180), 1)

                # --- Calcul Yaw depuis oreilles (ou yeux si oreilles invisibles) ---
                l_vis = conf_kps[3] > 0.3
                r_vis = conf_kps[4] > 0.3
                if l_vis and r_vis:
                    ear_mid_x = (l_ear[0] + r_ear[0]) / 2
                    ear_width = abs(l_ear[0] - r_ear[0])
                    yaw = float((nose[0] - ear_mid_x) / (ear_width / 2) * 45) if ear_width > 5 else 0.0
                elif conf_kps[1] > 0.3 and conf_kps[2] > 0.3:
                    eye_mid_x = (l_eye[0] + r_eye[0]) / 2
                    yaw = float((nose[0] - eye_mid_x) / (frame.shape[1] / 4) * 45)
                else:
                    yaw = float((nose[0] - frame.shape[1] / 2) / (frame.shape[1] / 2) * 45)

                # --- Calcul Pitch depuis ratio nez/yeux (normalisé par largeur inter-yeux) ---
                if conf_kps[1] > 0.3 and conf_kps[2] > 0.3:
                    eye_mid_y  = (float(l_eye[1]) + float(r_eye[1])) / 2
                    eye_width  = abs(float(l_eye[0]) - float(r_eye[0]))
                    if eye_width > 5:
                        # ratio ≈ 1.0 en frontal ; tête haut → ratio < 1 ; tête bas → ratio > 1
                        ratio = (float(nose[1]) - eye_mid_y) / eye_width
                        pitch = -(ratio - 1.0) * 30
                    else:
                        pitch = 0.0
                else:
                    pitch = float((nose[1] - frame.shape[0] / 2) / (frame.shape[0] / 2) * 30)

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