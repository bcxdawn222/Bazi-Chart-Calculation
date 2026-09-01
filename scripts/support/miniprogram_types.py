from __future__ import annotations

from typing import TypedDict


class AppConfig(TypedDict):
    pages: list[str]


class SolarDate(TypedDict):
    year: int
    month: int
    day: int


class Correction(TypedDict):
    longitudeMinutes: float
    equationOfTimeMinutes: float
    totalCorrectionMinutes: float
    crossedDateBoundary: bool


class CrossDateCorrection(TypedDict):
    solar: SolarDate
    totalCorrectionMinutes: float
    crossedDateBoundary: bool


class ElementCounts(TypedDict):
    wood: int
    fire: int
    earth: int
    metal: int
    water: int


class SampleResult(TypedDict):
    roundTripCases: int
    leapRoundTripCases: int
    boundaryRejectCount: int
    ziHourDiffers: bool
    invalidInputRejectCount: int
    unsupportedSolarTermYearRejected: bool
    solar: SolarDate
    hour: int
    minute: int
    correction: Correction
    crossDateCorrection: CrossDateCorrection
    pillars: list[str]
    tenGods: list[str]
    hiddenStemCount: int
    nayinCount: int
    elementCounts: ElementCounts
    palaceCount: int
    mainStarCount: int
    auxiliaryStarCount: int
    brightnessCount: int
    relatedPalaceCount: int
    transformationCount: int
    bureau: str
    lifePalace: str
    ziweiPosition: str
    analysisCount: int
    lifeDaxian: str
    ziweiLiunianCount: int
    solarTermBoundaryCount: int
    dayunVaries: bool
    resultPageLiunianBound: bool
    resultPageDetailsBound: bool
    invalidResultHandled: bool
    indexFlowValidated: bool
    featureNavigationValidated: bool
    dailyFortuneValidated: bool
    yearFortuneValidated: bool
    divinationValidated: bool
    compatibilityValidated: bool
    namingValidated: bool
