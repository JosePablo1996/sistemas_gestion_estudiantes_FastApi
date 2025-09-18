from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from urllib.parse import quote_plus
import os
from typing import List
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la base de datos - compatible con Render
DATABASE_URL = os.getenv("DATABASE_URL")

# Si no hay DATABASE_URL (desarrollo local), usar variable alternativa
if not DATABASE_URL:
    DB_PASSWORD = os.getenv("DB_PASSWORD", "uPxBHn]Ag9H~N4'K")
    ENCODED_PASSWORD = quote_plus(DB_PASSWORD)
    DATABASE_URL = f"postgresql://postgres:{ENCODED_PASSWORD}@20.84.99.214:443/mq100216"
    logger.info("Usando configuración de base de datos local")

# Configuración de SQLAlchemy con manejo mejorado de errores
try:
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True, 
        pool_recycle=300,
        pool_size=5,
        max_overflow=10
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base = declarative_base()
    logger.info("Motor de base de datos configurado correctamente")
except Exception as e:
    logger.error(f"Error al conectar con la base de datos: {e}")
    raise

# Modelo de la base de datos
class Estudiante(Base):
    __tablename__ = "estudiantes"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(100), index=True)
    edad = Column(Integer)

# Crear tablas si no existen
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas verificadas/creadas correctamente")
except Exception as e:
    logger.error(f"Error al crear tablas: {e}")

# Esquemas Pydantic
class EstudianteCreate(BaseModel):
    nombre: str
    edad: int

class EstudianteResponse(BaseModel):
    id: int
    nombre: str
    edad: int
    
    class Config:
        from_attributes = True

# Instancia de FastAPI
app = FastAPI(
    title="API de Estudiantes",
    description="API para gestionar estudiantes - Proyecto React",
    version="1.0.0"
)

# Configuración CORS para React - MÁS SEGURA
origins = [
    "http://localhost:3000",    # React desarrollo local
    "http://localhost:5173",    # React desarrollo con Vite
    "https://localhost:3000",   # HTTPS local
    "https://localhost:5173",   # HTTPS local con Vite
]

# Permitir todos los orígenes solo en desarrollo
if os.getenv("RENDER", "").lower() == "true":
    origins.append("https://*.render.com")
else:
    origins.append("*")  # Solo para desarrollo

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Dependencia para la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Error en la conexión de base de datos: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
    finally:
        db.close()

# Rutas de la API
@app.get("/")
async def root():
    return {
        "message": "API de Estudiantes funcionando correctamente",
        "docs": "/docs",
        "health": "/health",
        "environment": "production" if os.getenv("RENDER") else "development"
    }

@app.get("/estudiantes/", response_model=List[EstudianteResponse])
def get_estudiantes(db: Session = Depends(get_db)):
    try:
        estudiantes = db.query(Estudiante).order_by(Estudiante.id).all()
        return estudiantes
    except Exception as e:
        logger.error(f"Error al obtener estudiantes: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estudiantes: {str(e)}")

@app.get("/estudiantes/{id}", response_model=EstudianteResponse)
def get_estudiante(id: int, db: Session = Depends(get_db)):
    try:
        estudiante = db.query(Estudiante).filter(Estudiante.id == id).first()
        if not estudiante:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")
        return estudiante
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener estudiante {id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener estudiante: {str(e)}")

@app.post("/estudiantes/", response_model=EstudianteResponse)
def crear_estudiante(estudiante: EstudianteCreate, db: Session = Depends(get_db)):
    try:
        db_estudiante = Estudiante(nombre=estudiante.nombre, edad=estudiante.edad)
        db.add(db_estudiante)
        db.commit()
        db.refresh(db_estudiante)
        logger.info(f"Estudiante creado: {db_estudiante.id} - {db_estudiante.nombre}")
        return db_estudiante
    except Exception as e:
        db.rollback()
        logger.error(f"Error al crear estudiante: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear estudiante: {str(e)}")

@app.put("/estudiantes/{id}", response_model=EstudianteResponse)
def modificar_estudiante(id: int, estudiante: EstudianteCreate, db: Session = Depends(get_db)):
    try:
        est = db.query(Estudiante).filter(Estudiante.id == id).first()
        if not est:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")
        
        est.nombre = estudiante.nombre
        est.edad = estudiante.edad
        db.commit()
        db.refresh(est)
        logger.info(f"Estudiante actualizado: {id}")
        return est
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al actualizar estudiante {id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar estudiante: {str(e)}")

@app.delete("/estudiantes/{id}")
def eliminar_estudiante(id: int, db: Session = Depends(get_db)):
    try:
        est = db.query(Estudiante).filter(Estudiante.id == id).first()
        if not est:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")
        
        db.delete(est)
        db.commit()
        logger.info(f"Estudiante eliminado: {id}")
        return {"mensaje": "Estudiante eliminado exitosamente", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al eliminar estudiante {id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar estudiante: {str(e)}")

# Health check endpoint para Render
@app.get("/health")
async def health_check():
    try:
        # Verificar conexión a la base de datos
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        
        return {
            "status": "healthy", 
            "message": "API y base de datos funcionando correctamente",
            "database": "connected",
            "environment": "production" if os.getenv("RENDER") else "development"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy", 
            "message": "Error en la conexión a la base de datos",
            "database": "disconnected",
            "error": str(e)[:100]  # Limitar longitud del error
        }, 503

# Info endpoint para debugging (solo en desarrollo)
@app.get("/info")
async def info():
    if os.getenv("RENDER"):
        return {"message": "Info endpoint disabled in production"}
    
    return {
        "database_configured": bool(DATABASE_URL),
        "db_password_set": bool(os.getenv("DB_PASSWORD")),
        "environment": "production" if os.getenv("RENDER") else "development",
        "render_env": os.getenv("RENDER", "false")
    }

# Manejo de excepciones global
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Error no manejado: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor"}
    )