from parsers.axenta import AxentaParser
from parsers.base import GpsParser
from parsers.baltgps_wialon import BaltgpsWialonParser
from parsers.navi39 import Navi39Parser
from parsers.yandex_sharing import YandexSharingParser

PARSERS: list[GpsParser] = [YandexSharingParser(), BaltgpsWialonParser(), AxentaParser(), Navi39Parser()]

def get_parser(url: str | None) -> GpsParser | None:
    if not url:
        return None
    return next((p for p in PARSERS if p.supports(url)), None)
