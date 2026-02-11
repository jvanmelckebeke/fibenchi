from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pandas as pd

from app.database import get_db
from app.models.pseudo_etf import PseudoETF, PseudoEtfAnnotation, PseudoEtfThesis, pseudo_etf_constituents
from app.models.asset import Asset
from app.schemas.pseudo_etf import (
    PseudoETFCreate,
    PseudoETFUpdate,
    PseudoETFAddConstituents,
    PseudoETFResponse,
    PerformanceBreakdownPoint,
    ConstituentIndicatorResponse,
)
from app.schemas.thesis import ThesisResponse, ThesisUpdate
from app.schemas.annotation import AnnotationCreate, AnnotationResponse
from app.services.pseudo_etf import calculate_performance
from app.services.indicators import compute_indicators
from app.services.yahoo import batch_fetch_currencies, batch_fetch_history

router = APIRouter(prefix="/api/pseudo-etfs", tags=["pseudo-etfs"])


@router.get("", response_model=list[PseudoETFResponse], summary="List all pseudo-ETFs")
async def list_pseudo_etfs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PseudoETF).order_by(PseudoETF.name))
    return result.scalars().all()


@router.post("", response_model=PseudoETFResponse, status_code=201, summary="Create a pseudo-ETF basket")
async def create_pseudo_etf(data: PseudoETFCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(PseudoETF).where(PseudoETF.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Pseudo-ETF with this name already exists")

    etf = PseudoETF(
        name=data.name,
        description=data.description,
        base_date=data.base_date,
        base_value=data.base_value,
    )
    db.add(etf)
    await db.commit()
    await db.refresh(etf)
    return etf


@router.get("/{etf_id}", response_model=PseudoETFResponse, summary="Get a pseudo-ETF by ID")
async def get_pseudo_etf(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")
    return etf


@router.put("/{etf_id}", response_model=PseudoETFResponse, summary="Update a pseudo-ETF")
async def update_pseudo_etf(etf_id: int, data: PseudoETFUpdate, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(etf, field, value)

    await db.commit()
    await db.refresh(etf)
    return etf


@router.delete("/{etf_id}", status_code=204, summary="Delete a pseudo-ETF")
async def delete_pseudo_etf(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")
    await db.delete(etf)
    await db.commit()


@router.post("/{etf_id}/constituents", response_model=PseudoETFResponse, summary="Add constituent assets to a pseudo-ETF")
async def add_constituents(
    etf_id: int, data: PseudoETFAddConstituents, db: AsyncSession = Depends(get_db)
):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(select(Asset).where(Asset.id.in_(data.asset_ids)))
    assets = result.scalars().all()

    existing_ids = {a.id for a in etf.constituents}
    for asset in assets:
        if asset.id not in existing_ids:
            etf.constituents.append(asset)

    await db.commit()
    await db.refresh(etf)
    return etf


@router.delete("/{etf_id}/constituents/{asset_id}", response_model=PseudoETFResponse, summary="Remove a constituent from a pseudo-ETF")
async def remove_constituent(
    etf_id: int, asset_id: int, db: AsyncSession = Depends(get_db)
):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    asset = next((a for a in etf.constituents if a.id == asset_id), None)
    if not asset:
        raise HTTPException(404, "Asset not in this pseudo-ETF")

    etf.constituents.remove(asset)
    await db.commit()
    await db.refresh(etf)
    return etf


@router.get("/{etf_id}/performance", response_model=list[PerformanceBreakdownPoint], summary="Get indexed performance with per-constituent breakdown")
async def get_performance(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    asset_ids = [a.id for a in etf.constituents]
    if not asset_ids:
        return []

    return await calculate_performance(
        db, asset_ids, etf.base_date, float(etf.base_value), include_breakdown=True
    )


def _bb_position(close: float, upper: float, middle: float, lower: float) -> str:
    if close > upper:
        return "above"
    elif close > middle:
        return "upper"
    elif close > lower:
        return "lower"
    else:
        return "below"


@router.get("/{etf_id}/constituents/indicators", response_model=list[ConstituentIndicatorResponse], summary="Get technical indicators for each constituent")
async def get_constituent_indicators(etf_id: int, db: AsyncSession = Depends(get_db)):
    """Return latest indicator snapshot for each constituent of a pseudo-ETF."""
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    if not etf.constituents:
        return []

    # Get latest performance breakdown for weight calculation
    asset_ids = [a.id for a in etf.constituents]
    perf = await calculate_performance(
        db, asset_ids, etf.base_date, float(etf.base_value), include_breakdown=True
    )
    weight_map: dict[str, float] = {}
    if perf:
        last_point = perf[-1]
        breakdown = last_point.get("breakdown", {})
        total = last_point["value"]
        if total > 0:
            weight_map = {sym: round(val / total * 100, 2) for sym, val in breakdown.items()}

    symbols = [a.symbol for a in etf.constituents]
    symbol_to_name = {a.symbol: a.name for a in etf.constituents}

    histories = batch_fetch_history(symbols, period="3mo")
    currencies = batch_fetch_currencies(symbols)

    results = []
    for sym in symbols:
        currency = currencies.get(sym, "USD")
        df = histories.get(sym)
        if df is None or df.empty or len(df) < 2:
            results.append(ConstituentIndicatorResponse(
                symbol=sym,
                name=symbol_to_name.get(sym),
                currency=currency,
                weight_pct=weight_map.get(sym),
            ))
            continue

        indicators = compute_indicators(df)
        latest = indicators.iloc[-1]
        prev_close = indicators.iloc[-2]["close"] if len(indicators) >= 2 else None

        change_pct = None
        if prev_close and prev_close != 0:
            change_pct = round((latest["close"] - prev_close) / prev_close * 100, 2)

        macd_dir = None
        if pd.notna(latest["macd"]) and pd.notna(latest["macd_signal"]):
            macd_dir = "bullish" if latest["macd"] > latest["macd_signal"] else "bearish"

        bb_pos = None
        if pd.notna(latest["bb_upper"]) and pd.notna(latest["bb_middle"]) and pd.notna(latest["bb_lower"]):
            bb_pos = _bb_position(latest["close"], latest["bb_upper"], latest["bb_middle"], latest["bb_lower"])

        results.append(ConstituentIndicatorResponse(
            symbol=sym,
            name=symbol_to_name.get(sym),
            currency=currency,
            weight_pct=weight_map.get(sym),
            close=round(latest["close"], 2),
            change_pct=change_pct,
            rsi=round(latest["rsi"], 2) if pd.notna(latest["rsi"]) else None,
            sma_20=round(latest["sma_20"], 2) if pd.notna(latest["sma_20"]) else None,
            sma_50=round(latest["sma_50"], 2) if pd.notna(latest["sma_50"]) else None,
            macd_signal_dir=macd_dir,
            bb_position=bb_pos,
        ))

    return results


# --- Thesis ---

@router.get("/{etf_id}/thesis", response_model=ThesisResponse, summary="Get pseudo-ETF investment thesis")
async def get_etf_thesis(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(select(PseudoEtfThesis).where(PseudoEtfThesis.pseudo_etf_id == etf_id))
    thesis = result.scalar_one_or_none()
    if not thesis:
        return ThesisResponse(content="", updated_at=etf.created_at)
    return thesis


@router.put("/{etf_id}/thesis", response_model=ThesisResponse, summary="Create or update pseudo-ETF thesis")
async def update_etf_thesis(etf_id: int, data: ThesisUpdate, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(select(PseudoEtfThesis).where(PseudoEtfThesis.pseudo_etf_id == etf_id))
    thesis = result.scalar_one_or_none()

    if thesis:
        thesis.content = data.content
    else:
        thesis = PseudoEtfThesis(pseudo_etf_id=etf_id, content=data.content)
        db.add(thesis)

    await db.commit()
    await db.refresh(thesis)
    return thesis


# --- Annotations ---

@router.get("/{etf_id}/annotations", response_model=list[AnnotationResponse], summary="List pseudo-ETF chart annotations")
async def list_etf_annotations(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(
        select(PseudoEtfAnnotation)
        .where(PseudoEtfAnnotation.pseudo_etf_id == etf_id)
        .order_by(PseudoEtfAnnotation.date)
    )
    return result.scalars().all()


@router.post("/{etf_id}/annotations", response_model=AnnotationResponse, status_code=201, summary="Create a pseudo-ETF chart annotation")
async def create_etf_annotation(etf_id: int, data: AnnotationCreate, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    annotation = PseudoEtfAnnotation(
        pseudo_etf_id=etf_id,
        date=data.date,
        title=data.title,
        body=data.body,
        color=data.color,
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)
    return annotation


@router.delete("/{etf_id}/annotations/{annotation_id}", status_code=204, summary="Delete a pseudo-ETF chart annotation")
async def delete_etf_annotation(etf_id: int, annotation_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    result = await db.execute(
        select(PseudoEtfAnnotation).where(
            PseudoEtfAnnotation.id == annotation_id,
            PseudoEtfAnnotation.pseudo_etf_id == etf_id,
        )
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(404, "Annotation not found")

    await db.delete(annotation)
    await db.commit()
