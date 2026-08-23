# db.py
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
import bcrypt
from dotenv import load_dotenv

# Cargar el .env del proyecto para que db.py sea autocontenido
# (sin esto, y al importarlo aislado, caería a SQLite aunque .env tenga Supabase).
load_dotenv()

# Obtener URL de base de datos desde entorno, por defecto a SQLite local
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app_database.db")

# Ajuste para render/sqlalchemy compatibility con postgres:// vs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Argumentos extras de conexión (solo necesarios para SQLite)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    role = Column(String(20), default="user")  # admin, user
    status = Column(String(20), default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)

class Aprobacion(Base):
    """Entregable crítico que requiere aprobación humana (gate)."""
    __tablename__ = "aprobaciones"

    id = Column(Integer, primary_key=True, index=True)
    arbol_id = Column(String(50), index=True, nullable=False)
    tipo = Column(String(50), nullable=False)      # publicar | enviar | responder | gasto | oferta | datos
    detalle = Column(Text, nullable=False)
    borrador = Column(Text, default="")
    estado = Column(String(20), default="pendiente")  # pendiente | aprobada | rechazada
    feedback = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class ArbolRemoto(Base):
    """Registro de un árbol hijo (instancia remota) que el Comandante controla."""
    __tablename__ = "arboles_remotos"

    id = Column(Integer, primary_key=True, index=True)
    arbol_id = Column(String(50), unique=True, index=True, nullable=False)
    nombre = Column(String(120), default="")
    host = Column(String(200), nullable=False)     # IP o hostname de Tailscale
    puerto = Column(Integer, default=22)           # puerto SSH
    canal = Column(String(20), default="ssh")      # ssh | tailscale
    usuario = Column(String(80), default="root")
    repo_dir = Column(String(300), default=".")    # ruta del repo en el hijo
    estado = Column(String(20), default="desconocido")  # desconocido|online|offline
    ultima_sincronizacion = Column(DateTime, nullable=True)
    ultimo_estado_msg = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

def registrar_arbol(arbol_id: str, host: str, usuario: str = "root", puerto: int = 22,
                    canal: str = "ssh", nombre: str = "", repo_dir: str = ".") -> dict:
    """Registra o actualiza un árbol hijo en el inventario del Comandante."""
    db = SessionLocal()
    try:
        arb = db.query(ArbolRemoto).filter(ArbolRemoto.arbol_id == arbol_id).first()
        if arb is None:
            arb = ArbolRemoto(arbol_id=arbol_id)
            db.add(arb)
        arb.host = host
        arb.usuario = usuario
        arb.puerto = puerto
        arb.canal = canal
        if nombre: arb.nombre = nombre
        if repo_dir: arb.repo_dir = repo_dir
        db.commit()
        db.refresh(arb)
        return {"id": arb.id, "arbol_id": arb.arbol_id, "host": arb.host, "estado": arb.estado}
    finally:
        db.close()

def listar_arboles() -> list:
    """Lista los árboles registrados en el inventario."""
    db = SessionLocal()
    try:
        return [{"id": a.id, "arbol_id": a.arbol_id, "nombre": a.nombre, "host": a.host,
                 "puerto": a.puerto, "canal": a.canal, "usuario": a.usuario, "repo_dir": a.repo_dir,
                 "estado": a.estado, "ultima_sincronizacion":
                     a.ultima_sincronizacion.isoformat() if a.ultima_sincronizacion else None}
                for a in db.query(ArbolRemoto).order_by(ArbolRemoto.id).all()]
    finally:
        db.close()

def buscar_arbol(arbol_id: str) -> dict | None:
    db = SessionLocal()
    try:
        a = db.query(ArbolRemoto).filter(ArbolRemoto.arbol_id == arbol_id).first()
        if not a:
            return None
        return {"id": a.id, "arbol_id": a.arbol_id, "nombre": a.nombre, "host": a.host,
                "puerto": a.puerto, "canal": a.canal, "usuario": a.usuario, "repo_dir": a.repo_dir,
                "estado": a.estado}
    finally:
        db.close()

def marcar_estado(arbol_id: str, estado: str, msg: str = "") -> None:
    db = SessionLocal()
    try:
        a = db.query(ArbolRemoto).filter(ArbolRemoto.arbol_id == arbol_id).first()
        if a:
            a.estado = estado
            a.ultimo_estado_msg = msg
            if estado == "online":
                a.ultima_sincronizacion = datetime.utcnow()
            db.commit()
    finally:
        db.close()

def exportar_inventario() -> list:
    """Devuelve el inventario completo (para que un HEREDERO lo importe en failover)."""
    return listar_arboles()

def importar_inventario(registros: list) -> dict:
    """Reemplaza el inventario local con el del comandante primario (failover).
    Cada registro: {arbol_id, host, usuario, puerto, canal, nombre, repo_dir}."""
    db = SessionLocal()
    try:
        db.query(ArbolRemoto).delete(synchronize_session=False)
        for r in registros:
            db.add(ArbolRemoto(
                arbol_id=r["arbol_id"],
                host=r.get("host", ""),
                usuario=r.get("usuario", "root"),
                puerto=r.get("puerto", 22),
                canal=r.get("canal", "ssh"),
                nombre=r.get("nombre", ""),
                repo_dir=r.get("repo_dir", "."),
            ))
        db.commit()
        return {"importados": len(registros)}
    finally:
        db.close()

def crear_aprobacion(arbol_id: str, tipo: str, detalle: str, borrador: str = "") -> dict:
    """Registra un entregable en la cola de aprobación humana. Retorna dict."""
    db = SessionLocal()
    try:
        ap = Aprobacion(arbol_id=arbol_id, tipo=tipo, detalle=detalle, borrador=borrador)
        db.add(ap)
        db.commit()
        db.refresh(ap)
        return {"id": ap.id, "estado": ap.estado, "tipo": ap.tipo,
                "detalle": ap.detalle, "arbol_id": ap.arbol_id}
    finally:
        db.close()

def listar_aprobaciones(arbol_id: str, estado: str | None = None) -> list:
    """Lista aprobaciones de un árbol, opcionalmente filtradas por estado."""
    db = SessionLocal()
    try:
        q = db.query(Aprobacion).filter(Aprobacion.arbol_id == arbol_id)
        if estado:
            q = q.filter(Aprobacion.estado == estado)
        return [{"id": a.id, "arbol_id": a.arbol_id, "tipo": a.tipo, "detalle": a.detalle,
                 "borrador": a.borrador, "estado": a.estado, "feedback": a.feedback,
                 "created_at": a.created_at.isoformat() if a.created_at else None}
                for a in q.order_by(Aprobacion.created_at.desc()).all()]
    finally:
        db.close()

def resolver_aprobacion(aprobacion_id: int, decision: str, feedback: str = "") -> dict | None:
    """Aprueba/rechaza una aprobación pendiente. Retorna dict o None si no existe."""
    if decision not in ("aprobada", "rechazada"):
        raise ValueError("decision debe ser 'aprobada' o 'rechazada'")
    db = SessionLocal()
    try:
        ap = db.query(Aprobacion).filter(Aprobacion.id == aprobacion_id).first()
        if not ap:
            return None
        ap.estado = decision
        ap.feedback = feedback
        ap.resolved_at = datetime.utcnow()
        db.commit()
        db.refresh(ap)
        return {"id": ap.id, "tipo": ap.tipo, "estado": ap.estado, "feedback": ap.feedback}
    finally:
        db.close()

def init_db():
    # Crear las tablas si no existen
    Base.metadata.create_all(bind=engine)
    
    # Crear administrador por defecto si no hay usuarios en la base de datos.
    # Las credenciales NUNCA van hardcodeadas en código: se leen de .env y, si faltan,
    # se generan temporales seguras (se imprimen una sola vez).
    db = SessionLocal()
    try:
        admin_count = db.query(User).filter(User.role == "admin").count()
        if admin_count == 0:
            import secrets as _sec
            admin_user = os.getenv("ADMIN_USERNAME") or "admin"
            admin_email = os.getenv("ADMIN_EMAIL", "admin@marketing.com").strip()
            admin_pass = os.getenv("ADMIN_PASSWORD", "").strip()
            autogenerated = not admin_pass
            if autogenerated:
                admin_pass = _sec.token_urlsafe(18)
            if not admin_email:
                admin_email = f"{admin_user}@colmena.local"

            hashed_pw = bcrypt.hashpw(admin_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            db_admin = User(
                username=admin_user,
                email=admin_email,
                hashed_password=hashed_pw,
                role="admin",
                status="approved"
            )
            db.add(db_admin)
            db.commit()
            if autogenerated:
                print(f"[ADMIN] Administrador inicial: user='{admin_user}' email='{admin_email}'. "
                      f"PASSWORD TEMPORAL (define ADMIN_PASSWORD en .env y recrea el admin): {admin_pass}")
            else:
                print(f"[ADMIN] Usuario administrador inicial creado: {admin_user}")
    except Exception as e:
        print(f"[ERROR] Error al inicializar la base de datos: {e}")
    finally:
        db.close()

# Dependency para FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
