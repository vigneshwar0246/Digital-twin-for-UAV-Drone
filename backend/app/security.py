"""FastAPI authorization dependencies, request IDs, audit, and rate-limit hook."""
from collections import defaultdict,deque
from contextvars import ContextVar
from datetime import datetime,timezone
from typing import Callable
import uuid
from fastapi import Depends,HTTPException,Request
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from .auth import AuthService,AuthenticationError,Principal,Role

request_id_context:ContextVar[str|None]=ContextVar("request_id",default=None)
bearer=HTTPBearer(auto_error=False)

class RateLimiter:
    """Replaceable in-process hook; production deployments should use a shared store."""
    def __init__(self,requests_per_minute:int): self.limit=requests_per_minute; self.events=defaultdict(deque)
    def allow(self,key:str,now:datetime|None=None):
        now=(now or datetime.now(timezone.utc)).timestamp(); queue=self.events[key]
        while queue and queue[0]<=now-60: queue.popleft()
        if len(queue)>=self.limit: return False
        queue.append(now); return True

def authorization_dependency(service_getter:Callable[[],AuthService|None],limiter_getter:Callable[[],RateLimiter|None],allowed:set[Role]):
    def dependency(request:Request,credentials:HTTPAuthorizationCredentials|None=Depends(bearer))->Principal:
        service=service_getter()
        if service is None: raise HTTPException(503,"authentication service unavailable")
        if credentials is None: raise HTTPException(401,"bearer token required",headers={"WWW-Authenticate":"Bearer"})
        try: principal=service.principal(credentials.credentials)
        except AuthenticationError as exc: raise HTTPException(401,str(exc),headers={"WWW-Authenticate":"Bearer"}) from exc
        # Record the authenticated identity before authorization so denied
        # requests remain attributable in the audit trail.
        request.state.principal=principal
        if principal.role not in allowed: raise HTTPException(403,"role is not authorized for this operation")
        limiter=limiter_getter()
        if limiter and not limiter.allow(f"{principal.username}:{request.url.path}"): raise HTTPException(429,"rate limit exceeded",headers={"Retry-After":"60"})
        return principal
    return dependency
