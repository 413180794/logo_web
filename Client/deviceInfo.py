# -*-coding:utf-8 -*-
class deviceInfo(object):  # 设备信息
    __slots__ = ('_deviceFixId','_regionProvince', '_regionCity', '_regionArea')

    def __init__(self, deviceFixId, regionProvince, regionCity, regionArea):
        self._deviceFixId = deviceFixId
        self._regionProvince = regionProvince
        self._regionCity = regionCity
        self._regionArea = regionArea

    @property
    def deviceFixId(self):
        return self._deviceFixId

    @property
    def regionProvince(self):
        return self._regionProvince

    @property
    def regionCity(self):
        return self._regionCity

    @property
    def regionArea(self):
        return self._regionArea