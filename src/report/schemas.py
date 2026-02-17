"""Report API 스키마."""

from pydantic import BaseModel, Field


class TypeCount(BaseModel):
    """경험 타입별 개수."""

    type: str = Field(..., description="경험 타입")
    count: int = Field(..., ge=0, description="개수")


class CategoryCount(BaseModel):
    """경험 카테고리별 개수."""

    category: str = Field(..., description="경험 카테고리")
    count: int = Field(..., ge=0, description="개수")


class TagCount(BaseModel):
    """경험 태그별 개수."""

    tag: str = Field(..., description="경험 태그")
    count: int = Field(..., ge=0, description="개수")


class TypeCountResponse(BaseModel):
    """경험 타입별 개수 응답."""

    data: list[TypeCount] = Field(..., description="타입별 개수 목록")
    total: int = Field(..., ge=0, description="전체 경험 개수")


class CategoryCountResponse(BaseModel):
    """경험 카테고리별 개수 응답."""

    data: list[CategoryCount] = Field(..., description="카테고리별 개수 목록")
    total: int = Field(..., ge=0, description="전체 경험 개수")


class TagCountResponse(BaseModel):
    """경험 태그별 개수 응답."""

    data: list[TagCount] = Field(..., description="태그별 개수 목록")
    total: int = Field(..., ge=0, description="전체 경험 개수")


class ExperienceSummaryResponse(BaseModel):
    """경험 요약 응답 (타입, 카테고리, 태그 모두 포함)."""

    type_counts: list[TypeCount] = Field(..., description="타입별 개수 목록")
    category_counts: list[CategoryCount] = Field(..., description="카테고리별 개수 목록")
    tag_counts: list[TagCount] = Field(..., description="태그별 개수 목록")
    total: int = Field(..., ge=0, description="전체 경험 개수")
