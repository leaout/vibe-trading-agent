# coding: utf-8
"""Internal paper-account and simulated execution API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from trading_v2.api.dependencies import get_paper_service
from trading_v2.paper.models import (
    CreatePaperAccount,
    EnablePaperTrading,
    PaperAccount,
    PaperAccountDetail,
)
from trading_v2.paper.service import PaperTradingService

router = APIRouter(prefix="/paper", tags=["paper-trading"])


@router.get("/accounts", response_model=list[PaperAccount])
async def list_accounts(
    service: Annotated[PaperTradingService, Depends(get_paper_service)],
) -> list[PaperAccount]:
    return await service.list_accounts()


@router.post("/accounts", response_model=PaperAccount, status_code=status.HTTP_201_CREATED)
async def create_account(
    command: CreatePaperAccount,
    service: Annotated[PaperTradingService, Depends(get_paper_service)],
) -> PaperAccount:
    return await service.create_account(command.name, command.initial_cash, command.currency)


@router.get("/accounts/{account_id}", response_model=PaperAccountDetail)
async def account_detail(
    account_id: str,
    service: Annotated[PaperTradingService, Depends(get_paper_service)],
) -> PaperAccountDetail:
    detail = await service.detail(account_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="paper account not found")
    return detail


@router.post("/sessions/{session_id}/enable", response_model=PaperAccount)
async def enable_paper(
    session_id: str,
    command: EnablePaperTrading,
    service: Annotated[PaperTradingService, Depends(get_paper_service)],
) -> PaperAccount:
    try:
        account = await service.enable(session_id, command.account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if account is None:
        raise HTTPException(status_code=404, detail="strategy session not found")
    return account


@router.get("/sessions/{session_id}", response_model=PaperAccountDetail)
async def session_account(
    session_id: str,
    service: Annotated[PaperTradingService, Depends(get_paper_service)],
) -> PaperAccountDetail:
    detail = await service.account_for_session(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="paper account is not bound")
    return detail
