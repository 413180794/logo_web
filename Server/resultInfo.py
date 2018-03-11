class resultInfo(object):  # 结kkkk果信息
    __slots__ = ('_dateNowsa', '_kind', '_result', '_startTime', '_usedTime')

    def __init__(self, dateNow, kind, result, startTime, usedTime):
        self._dateNow = dateNow
        self._kind = kind
        self._result = result
        self._startTime = startTime
        self._usedTime = usedTime

    @property
    def dateNow(self):
        return self._dateNow

    @property
    def kind(self):
        return self._kind

    @property
    def result(self):
        return self._result

    @property
    def startTime(self):
        return self._startTime

    @property
    def usedTime(self):
        return self._usedTime
