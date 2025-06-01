from fastapi import Depends, HTTPException, status
from src.core.security import get_current_user
from src.db.models import User

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user