from app.api.schemas.auth import OtpInDB
from app.api.repo.otp import OtpRepository


class OtpService:
    def __init__(self, otp_repo: OtpRepository):
        self._otp_repo = otp_repo

    def create_otp(self, otp: OtpInDB):
        self._otp_repo.sync_add(entity=otp)
        self._otp_repo.sync_commit()
