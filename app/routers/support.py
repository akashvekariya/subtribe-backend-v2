"""Support ticket endpoints for help and issue resolution."""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import NotFoundError
from app.models.support import SupportMessage, SupportTicket
from app.schemas.common import PaginationMeta
from app.schemas.support import (
    SupportMessageCreate,
    SupportMessageResponse,
    SupportMessagesResponse,
    SupportTicketCreate,
    SupportTicketCreated,
    SupportTicketDetail,
    SupportTicketListItem,
    SupportTicketListResponse,
    SupportTicketUpdate,
)

router = APIRouter()


@router.post("/tickets", response_model=SupportTicketCreated, tags=["Support"])
async def create_support_ticket(
    data: SupportTicketCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new support ticket.

    Creates a support ticket for the authenticated user's company.
    In the future, this will also create a Discord thread for two-way sync.

    Args:
        data: Ticket creation data (subject, description, priority)
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Created ticket ID and success message
    """
    company_id: UUID = current_user["company_id"]
    user_id: UUID = current_user["user_id"]

    # Create the ticket
    ticket = SupportTicket(
        company_id=company_id,
        user_id=user_id,
        subject=data.subject,
        description=data.description,
        priority=data.priority,
        status="open",
    )

    db.add(ticket)
    await db.flush()

    # Get user for Discord notification
    from app.services.support_service import SupportService

    support_service = SupportService(db)
    user = await support_service.get_user_by_id(user_id)

    await db.commit()
    await db.refresh(ticket)

    # Create Discord thread (async, non-blocking)
    await support_service.create_ticket_discord_thread(ticket, user)

    return SupportTicketCreated(id=ticket.id)


@router.get("/tickets", response_model=SupportTicketListResponse, tags=["Support"])
async def list_support_tickets(
    status: str | None = Query(
        None,
        description="Filter by status",
        pattern="^(open|in_progress|resolved|closed)$",
    ),
    priority: str | None = Query(
        None,
        description="Filter by priority",
        pattern="^(low|medium|high|urgent)$",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List support tickets for the authenticated company.

    Returns paginated list of tickets with optional filtering by status and priority.

    Args:
        status: Optional status filter
        priority: Optional priority filter
        page: Page number (1-indexed)
        limit: Number of items per page
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Paginated list of support tickets
    """
    company_id: UUID = current_user["company_id"]

    # Build base query
    base_query = select(SupportTicket).where(SupportTicket.company_id == company_id)

    # Apply filters
    if status:
        base_query = base_query.where(SupportTicket.status == status)
    if priority:
        base_query = base_query.where(SupportTicket.priority == priority)

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate pagination
    total_pages = math.ceil(total / limit) if total > 0 else 0
    offset = (page - 1) * limit

    # Get tickets with message count
    tickets_query = (
        base_query.options(selectinload(SupportTicket.messages))
        .order_by(SupportTicket.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(tickets_query)
    tickets = result.scalars().all()

    # Build response
    ticket_items = [
        SupportTicketListItem(
            id=t.id,
            subject=t.subject,
            status=t.status,
            priority=t.priority,
            created_at=t.created_at,
            updated_at=t.updated_at,
            message_count=len(t.messages) if t.messages else 0,
        )
        for t in tickets
    ]

    return SupportTicketListResponse(
        data=ticket_items,
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
            has_more=page < total_pages,
        ),
    )


@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetail, tags=["Support"])
async def get_support_ticket(
    ticket_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a support ticket.

    Returns full ticket details including all messages.

    Args:
        ticket_id: UUID of the ticket
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Full ticket details with messages
    """
    company_id: UUID = current_user["company_id"]

    # Get ticket with messages and user info
    query = (
        select(SupportTicket)
        .options(
            selectinload(SupportTicket.messages).selectinload(SupportMessage.user),
            selectinload(SupportTicket.user),
        )
        .where(
            SupportTicket.id == ticket_id,
            SupportTicket.company_id == company_id,
        )
    )

    result = await db.execute(query)
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise NotFoundError(
            message="Support ticket not found",
            code="ticket_not_found",
        )

    # Build response with messages
    messages = [
        SupportMessageResponse(
            id=m.id,
            content=m.content,
            source=m.source,
            discord_message_id=m.discord_message_id,
            created_at=m.created_at,
            user={
                "id": m.user.id,
                "first_name": m.user.first_name,
                "last_name": m.user.last_name,
            }
            if m.user
            else None,
        )
        for m in sorted(ticket.messages, key=lambda x: x.created_at)
    ]

    return SupportTicketDetail(
        id=ticket.id,
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        discord_channel_id=ticket.discord_channel_id,
        discord_thread_id=ticket.discord_thread_id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        resolved_at=ticket.resolved_at,
        user={
            "id": ticket.user.id,
            "first_name": ticket.user.first_name,
            "last_name": ticket.user.last_name,
        }
        if ticket.user
        else None,
        messages=messages,
    )


@router.patch("/tickets/{ticket_id}", response_model=SupportTicketDetail, tags=["Support"])
async def update_support_ticket(
    ticket_id: UUID,
    data: SupportTicketUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a support ticket's status or priority.

    Args:
        ticket_id: UUID of the ticket
        data: Update data (status and/or priority)
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Updated ticket details
    """
    from datetime import datetime, timezone

    company_id: UUID = current_user["company_id"]

    # Get ticket
    query = (
        select(SupportTicket)
        .options(
            selectinload(SupportTicket.messages).selectinload(SupportMessage.user),
            selectinload(SupportTicket.user),
        )
        .where(
            SupportTicket.id == ticket_id,
            SupportTicket.company_id == company_id,
        )
    )

    result = await db.execute(query)
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise NotFoundError(
            message="Support ticket not found",
            code="ticket_not_found",
        )

    # Update fields
    if data.status is not None:
        ticket.status = data.status
        # Set resolved_at when status changes to resolved or closed
        if data.status in ("resolved", "closed") and ticket.resolved_at is None:
            ticket.resolved_at = datetime.now(timezone.utc)
        # Clear resolved_at if reopened
        elif data.status in ("open", "in_progress"):
            ticket.resolved_at = None

    if data.priority is not None:
        ticket.priority = data.priority

    # Send status update to Discord
    from app.services.support_service import SupportService

    support_service = SupportService(db)
    if data.status is not None and data.status != ticket.status:
        user = await support_service.get_user_by_id(current_user["user_id"])
        await support_service.send_status_update_to_discord(
            ticket, ticket.status, data.status, user
        )

    await db.commit()
    await db.refresh(ticket)

    # Build response
    messages = [
        SupportMessageResponse(
            id=m.id,
            content=m.content,
            source=m.source,
            discord_message_id=m.discord_message_id,
            created_at=m.created_at,
            user={
                "id": m.user.id,
                "first_name": m.user.first_name,
                "last_name": m.user.last_name,
            }
            if m.user
            else None,
        )
        for m in sorted(ticket.messages, key=lambda x: x.created_at)
    ]

    return SupportTicketDetail(
        id=ticket.id,
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        discord_channel_id=ticket.discord_channel_id,
        discord_thread_id=ticket.discord_thread_id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        resolved_at=ticket.resolved_at,
        user={
            "id": ticket.user.id,
            "first_name": ticket.user.first_name,
            "last_name": ticket.user.last_name,
        }
        if ticket.user
        else None,
        messages=messages,
    )


@router.get("/tickets/{ticket_id}/messages", response_model=SupportMessagesResponse, tags=["Support"])
async def get_ticket_messages(
    ticket_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a support ticket.

    Args:
        ticket_id: UUID of the ticket
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        List of messages for the ticket
    """
    company_id: UUID = current_user["company_id"]

    # Verify ticket exists and belongs to company
    ticket_query = select(SupportTicket).where(
        SupportTicket.id == ticket_id,
        SupportTicket.company_id == company_id,
    )
    ticket_result = await db.execute(ticket_query)
    ticket = ticket_result.scalar_one_or_none()

    if not ticket:
        raise NotFoundError(
            message="Support ticket not found",
            code="ticket_not_found",
        )

    # Get messages
    messages_query = (
        select(SupportMessage)
        .options(selectinload(SupportMessage.user))
        .where(SupportMessage.ticket_id == ticket_id)
        .order_by(SupportMessage.created_at.asc())
    )

    result = await db.execute(messages_query)
    messages = result.scalars().all()

    return SupportMessagesResponse(
        data=[
            SupportMessageResponse(
                id=m.id,
                content=m.content,
                source=m.source,
                discord_message_id=m.discord_message_id,
                created_at=m.created_at,
                user={
                    "id": m.user.id,
                    "first_name": m.user.first_name,
                    "last_name": m.user.last_name,
                }
                if m.user
                else None,
            )
            for m in messages
        ]
    )


@router.post("/tickets/{ticket_id}/messages", response_model=SupportMessageResponse, tags=["Support"])
async def add_ticket_message(
    ticket_id: UUID,
    data: SupportMessageCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a message to a support ticket.

    Args:
        ticket_id: UUID of the ticket
        data: Message content
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Created message
    """
    company_id: UUID = current_user["company_id"]
    user_id: UUID = current_user["user_id"]

    # Verify ticket exists and belongs to company
    ticket_query = select(SupportTicket).where(
        SupportTicket.id == ticket_id,
        SupportTicket.company_id == company_id,
    )
    ticket_result = await db.execute(ticket_query)
    ticket = ticket_result.scalar_one_or_none()

    if not ticket:
        raise NotFoundError(
            message="Support ticket not found",
            code="ticket_not_found",
        )

    # Create message
    message = SupportMessage(
        ticket_id=ticket_id,
        user_id=user_id,
        content=data.content,
        source="dashboard",
    )

    db.add(message)
    await db.flush()

    await db.commit()
    await db.refresh(message)

    # Send message to Discord thread
    from app.services.support_service import SupportService

    support_service = SupportService(db)
    user = await support_service.get_user_by_id(user_id)
    await support_service.send_message_to_discord(ticket, message, user)

    # Get user info
    from app.models.user import User

    user_query = select(User).where(User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()

    return SupportMessageResponse(
        id=message.id,
        content=message.content,
        source=message.source,
        discord_message_id=message.discord_message_id,
        created_at=message.created_at,
        user={
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
        if user
        else None,
    )
