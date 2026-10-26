from parsers._browser import XhrParser

class YandexSharingParser(XhrParser):
    source, host, path_hint = "yandex", "maps.yandex.ru", "location-sharing"
