"""Prototype authentication primitives, independent of FastAPI routes.

This is production-oriented application scaffolding, not defence-certified IAM.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import base64, hashlib, hmac, json, secrets, sqlite3
from pathlib import Path
from threading import RLock
from pydantic import BaseModel,Field

class Role(str,Enum):
    ADMIN="ADMIN"; OPERATOR="OPERATOR"; MAINTENANCE_ENGINEER="MAINTENANCE_ENGINEER"; ANALYST="ANALYST"; VIEWER="VIEWER"

class LoginRequest(BaseModel):
    username:str=Field(min_length=1,max_length=64); password:str=Field(min_length=1,max_length=256)
class CreateUserRequest(BaseModel):
    username:str=Field(min_length=3,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$"); password:str=Field(min_length=12,max_length=256); role:Role

class AuthenticationError(Exception): pass
class AuthorizationError(Exception): pass

@dataclass(frozen=True)
class Principal:
    username:str; role:Role; token_id:str

class PasswordHasher:
    algorithm="pbkdf2_sha256"
    def __init__(self,iterations:int=310_000): self.iterations=iterations
    def hash(self,password:str)->str:
        if len(password)<12: raise ValueError("password must contain at least 12 characters")
        salt=secrets.token_bytes(16); digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,self.iterations)
        return f"{self.algorithm}${self.iterations}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"
    def verify(self,password:str,encoded:str)->bool:
        try:
            algorithm,iterations,salt,digest=encoded.split("$")
            if algorithm!=self.algorithm: return False
            actual=hashlib.pbkdf2_hmac("sha256",password.encode(),base64.urlsafe_b64decode(salt),int(iterations))
            return hmac.compare_digest(actual,base64.urlsafe_b64decode(digest))
        except (ValueError,TypeError): return False

class TokenService:
    def __init__(self,secret:str,lifetime_minutes:int=30,issuer="digital-twin-prototype"):
        if len(secret)<32: raise ValueError("token secret must contain at least 32 characters")
        self.secret=secret.encode(); self.lifetime=timedelta(minutes=lifetime_minutes); self.issuer=issuer
    @staticmethod
    def _encode(value:bytes)->str: return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
    @staticmethod
    def _decode(value:str)->bytes: return base64.urlsafe_b64decode(value+"="*(-len(value)%4))
    def issue(self,username:str,role:Role,now:datetime|None=None)->tuple[str,datetime]:
        now=now or datetime.now(timezone.utc); expires=now+self.lifetime
        payload={"sub":username,"role":role.value,"iat":int(now.timestamp()),"exp":int(expires.timestamp()),"iss":self.issuer,"jti":secrets.token_hex(12)}
        body=self._encode(json.dumps(payload,separators=(",",":"),sort_keys=True).encode()); signature=self._encode(hmac.new(self.secret,body.encode(),hashlib.sha256).digest())
        return f"{body}.{signature}",expires
    def verify(self,token:str,now:datetime|None=None)->Principal:
        try:
            body,signature=token.split("."); expected=self._encode(hmac.new(self.secret,body.encode(),hashlib.sha256).digest())
            if not hmac.compare_digest(signature,expected): raise AuthenticationError("invalid token signature")
            payload=json.loads(self._decode(body)); now=now or datetime.now(timezone.utc)
            if payload.get("iss")!=self.issuer or int(payload["exp"])<=int(now.timestamp()): raise AuthenticationError("token expired or issuer invalid")
            return Principal(payload["sub"],Role(payload["role"]),payload["jti"])
        except AuthenticationError: raise
        except Exception as exc: raise AuthenticationError("invalid token") from exc

class AuthRepository:
    def __init__(self,path:Path):
        self.path=path; path.parent.mkdir(parents=True,exist_ok=True); self._lock=RLock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, request_id TEXT NOT NULL, actor TEXT, role TEXT, method TEXT NOT NULL, path TEXT NOT NULL, status INTEGER NOT NULL, event TEXT NOT NULL, detail TEXT, client_ip TEXT)")
            db.execute("CREATE INDEX IF NOT EXISTS ix_audit_time ON audit_events(timestamp DESC)")
    def _connect(self): db=sqlite3.connect(self.path,timeout=10); db.row_factory=sqlite3.Row; return db
    def create_user(self,username,password_hash,role:Role):
        with self._lock,self._connect() as db: db.execute("INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",(username,password_hash,role.value,datetime.now(timezone.utc).isoformat()))
    def user(self,username):
        with self._connect() as db: row=db.execute("SELECT username,password_hash,role,active FROM users WHERE username=?",(username,)).fetchone()
        return dict(row) if row else None
    def count_users(self):
        with self._connect() as db: return int(db.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    def audit(self,**event):
        with self._lock,self._connect() as db: db.execute("INSERT INTO audit_events(timestamp,request_id,actor,role,method,path,status,event,detail,client_ip) VALUES(?,?,?,?,?,?,?,?,?,?)",(datetime.now(timezone.utc).isoformat(),event["request_id"],event.get("actor"),event.get("role"),event["method"],event["path"],event["status"],event["event"],event.get("detail"),event.get("client_ip")))
    def audit_events(self,limit=100):
        with self._connect() as db: return [dict(x) for x in db.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]

class AuthService:
    def __init__(self,repository:AuthRepository,token_service:TokenService,hasher:PasswordHasher|None=None): self.repository=repository; self.tokens=token_service; self.hasher=hasher or PasswordHasher()
    def create_user(self,username:str,password:str,role:Role): self.repository.create_user(username,self.hasher.hash(password),role); return {"username":username,"role":role.value}
    def authenticate(self,username,password):
        record=self.repository.user(username)
        if not record or not record["active"] or not self.hasher.verify(password,record["password_hash"]): raise AuthenticationError("invalid username or password")
        token,expires=self.tokens.issue(username,Role(record["role"])); return {"access_token":token,"token_type":"bearer","expires_at":expires,"role":record["role"]}
    def principal(self,token):
        principal=self.tokens.verify(token); record=self.repository.user(principal.username)
        if not record or not record["active"]: raise AuthenticationError("user is inactive or missing")
        return Principal(principal.username,Role(record["role"]),principal.token_id)
