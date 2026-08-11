"""FastAPI provider assembling the forecast use case from repositories +
services, mirroring ``dependencies.connector_use_cases``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from quantix_api.application.use_cases.generate_forecast import GenerateForecastUseCase
from quantix_api.interface.api.v1.dependencies.repositories import DatasetRepo, ForecastRepo
from quantix_api.interface.api.v1.dependencies.services import AuditLoggerDep, DatasetStorageDep


def get_generate_forecast_use_case(
    dataset_repo: DatasetRepo,
    dataset_storage: DatasetStorageDep,
    forecast_repo: ForecastRepo,
    audit_logger: AuditLoggerDep,
) -> GenerateForecastUseCase:
    return GenerateForecastUseCase(
        dataset_repo=dataset_repo,
        dataset_storage=dataset_storage,
        forecast_repo=forecast_repo,
        audit_logger=audit_logger,
    )


GenerateForecastUseCaseDep = Annotated[
    GenerateForecastUseCase, Depends(get_generate_forecast_use_case)
]
