from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import models as db_models
from ..db.database import get_db
from .security import get_current_user


async def enforce_api_limit(
    current_user: db_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> db_models.User:
    """
    Dependency to enforce API call limits for the current user.
    Checks if the user has exceeded their monthly API call limit.
    If the limit period has passed, it resets the count.
    Increments the call count if within limits.
    """
    now = datetime.now(timezone.utc)

    # Check if the limit reset period has passed
    if current_user.api_limit_reset_at is None or now >= current_user.api_limit_reset_at:
        current_user.api_call_count = 0
        current_user.api_limit_reset_at = now + timedelta(days=30) # Reset for another 30 days
        # db.commit() # Commit reset separately or together with increment

    # Check if the user has exceeded their limit
    if current_user.api_call_count >= current_user.monthly_api_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"API call limit of {current_user.monthly_api_limit} exceeded. "
                f"Limit will reset on {current_user.api_limit_reset_at.strftime('%Y-%m-%d %H:%M:%S UTC')}."
            ),
        )

    # Increment API call count
    current_user.api_call_count += 1
    db.add(current_user) # Ensure the user object is in the session if it wasn't already or was modified
    db.commit()
    db.refresh(current_user) # Refresh to get the latest state from DB if needed elsewhere
    return current_user