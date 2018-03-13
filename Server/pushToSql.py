# -*-coding:utf-8 -*-
import time
from datetime import datetime
import json
import pypinyin
import sqlalchemy
from flask import jsonify
from sqlalchemy import create_engine, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import sessionmaker, relationship
from collections import namedtuple

engine = create_engine('mysql+mysqlconnector://root:123456@localhost:3306/logoResult?charset=utf8', echo=True)

Base = declarative_base()  # 什么用？what fuck


# 我们看到，在User类中，用__tablename__指定在MySql中表的名字。
# 我们创建了三个基本字段，类中的每一个Column代表数据库中的一列，
# 在Colunm中，指定该列的一些配置。第一个字段代表类的数据类型，上面我们
# 使用String，Integer两个最常用的类型，其他常用的包括
# Text, Boolean,SmallInteger,DateTime
# __slots__ = ('_fixId','_region')
# def __init__(self, dateNow, kind, result, startTime, usedTime):
# nullable=False代表这一列不可以为空，index=True表示在该列创建索引。
class DeviceInfo(Base):
    __tablename__ = 'DeviceInfo'
    id = Column(Integer, primary_key=True, autoincrement=True)
    deviceFixId = Column(String(64), nullable=False, index=True, unique=True, primary_key=True)
    regionProvince = Column(String(64), nullable=False, index=True)
    regionCity = Column(String(64), nullable=False, index=True)
    regionArea = Column(String(64), nullable=False, index=True)
    status = Column(Integer, nullable=False)  # 判断是否在线
    resultInfo = relationship('ResultInfo')
    pictureSize = relationship('PictureSize')
    fileInfo = relationship('FileInfo')


class FileInfo(Base):  # 用于存储每个设备需要修改的文件,设备名,文件绝对路径,文件大小,修改时间
    __tablename__ = 'FileInfo'
    id = Column(Integer, primary_key=True, autoincrement=True)
    deviceFixId = Column(String(64), ForeignKey('DeviceInfo.deviceFixId'), nullable=False, index=True)
    fileAbsolutePath = Column(String(64), nullable=False, index=True)
    fileSize = Column(String(64), nullable=False, index=True)
    lastUpdatedDate = Column(DateTime(64), nullable=False, index=True)


class ResultInfo(Base):
    dateNow = time.strftime("%Y_%m_%d", time.localtime())
    __tablename__ = 'Result_' + dateNow
    id = Column(Integer, primary_key=True, autoincrement=True)
    deviceFixId = Column(String(64), ForeignKey('DeviceInfo.deviceFixId'), nullable=False, index=True)  # 外键
    kind = Column(String(64), nullable=False, index=True)
    result = Column(String(64), nullable=False, index=True)
    startTime = Column(DateTime(64), nullable=False, index=True)
    usedTime = Column(Integer, nullable=False, index=True)

    # deviceInfo = relationship("DeviceInfo", backref=backref('resultInfo', order_by=deviceFixId))

    def __repr__(self):
        return '{0}({1})'.format(self.__class__.__name__, self.username)


class PictureSize(Base):
    __tablename__ = 'PictureSize'
    id = Column(Integer, primary_key=True, autoincrement=True)
    deviceFixId = Column(String(64), ForeignKey('DeviceInfo.deviceFixId'), nullable=False, index=True)
    channel = Column(String(64), nullable=False, index=True)
    kind = Column(String(64), nullable=False, index=True)
    leftTopX = Column(Integer, nullable=False, index=False)
    leftTopY = Column(Integer, nullable=False, index=False)
    rightBottomX = Column(Integer, nullable=False, index=False)
    rightBottomY = Column(Integer, nullable=False, index=False)


class handleSql(object):

    def __init__(self):
        # 命名元组的使用方法，便于操作数据库
        self.SubscriberResultInfo = namedtuple('ResultInfo',
                                               ['id', 'deviceFixId', 'kind', 'result', 'startTime', 'usedTime'])

        self.SubscriberPictureSize = namedtuple('PictureSize',
                                                ['id', 'deviceFixId', 'channel', 'leftTopX', 'leftTopY', 'rightBottomX',
                                                 'rightBottomY'])

        self.SubscriberDeveiceInfo = namedtuple('DeviceInfo',
                                                ['deviceFixId', 'regionProvince', 'regionCity', 'regionArea', 'status'])

    def pushFileInfo(self, deviceFixId, fileAbsolutePath, fileSize, lastUpdatedDate):
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        Base.metadata.create_all(engine)  # 创建表，如果不存在
        # 根据设备号和名字，判断是否存在
        x = session.query(FileInfo).filter(FileInfo.deviceFixId == deviceFixId,
                                           FileInfo.fileAbsolutePath == fileAbsolutePath)
        count = 0
        for x1 in x:
            count += 1
        if count == 0:  # 不存在该数据，直接添加
            fileInfo = FileInfo(deviceFixId=deviceFixId, fileAbsolutePath=fileAbsolutePath, fileSize=fileSize,
                                lastUpdatedDate=lastUpdatedDate)
            session.add(fileInfo)
        else:
            fileInfo1 = session.query(FileInfo).filter(FileInfo.deviceFixId == deviceFixId,
                                                       FileInfo.fileAbsolutePath == fileAbsolutePath).first()
            fileInfo1.fileSize = fileSize
            fileInfo1.lastUpdatedDate = lastUpdatedDate
        session.commit()
        session.close()

    def updatePictureSize(self, deviceFixId, channel, kind, leftTopX, leftTopY, rightBottomX, rightBottomY):
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        pictureSize = session.query(PictureSize).filter(PictureSize.deviceFixId == deviceFixId,
                                                        PictureSize.channel == channel,
                                                        PictureSize.kind == kind).first()
        print(pictureSize, "___________________________")
        if not pictureSize:  # 如果不存在该频道，就什么也不做
            session.close()
            return
        pictureSize.leftTopX = leftTopX
        pictureSize.leftTopY = leftTopY
        pictureSize.rightBottomX = rightBottomX
        pictureSize.rightBottomY = rightBottomY
        session.add(pictureSize)
        session.commit()
        session.close()

    def pushPictureSize(self, deviceFixId, channel, kind, leftTopX, leftTopY, rightBottomX, rightBottomY):
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        Base.metadata.create_all(engine)  # 创建表，如果不存在
        x = session.query(PictureSize).filter(PictureSize.deviceFixId == deviceFixId, PictureSize.channel == channel,
                                              PictureSize.kind == kind)
        count = 0
        for x1 in x:  # 用于判断设备是否存在
            count += 1
        if count == 0:  # 不存在该数据，直接添加

            pictureSize = PictureSize(deviceFixId=deviceFixId, channel=channel, kind=kind, leftTopX=leftTopX,
                                      leftTopY=leftTopY,
                                      rightBottomX=rightBottomX,
                                      rightBottomY=rightBottomY)  # 要先判断fixId与channel是否存在，如果存在，就是更新，如果不存在才是添加
            session.add(pictureSize)
            session.commit()
            session.close()
        else:  # 已经存在该数据，更新该数据
            session.close()
            self.updatePictureSize(deviceFixId, channel, kind, leftTopX, leftTopY, rightBottomX, rightBottomY)

    def updateDeviceStatus(self, deviceFixId, status):  # 更新设备状态
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        updateDeviceStatus = session.query(DeviceInfo).filter(DeviceInfo.deviceFixId == deviceFixId).first()
        updateDeviceStatus.status = status
        session.commit()
        session.close()

    def pushDeviceInfo(self, deviceFixId, regionProvince, regionCity, regionArea):
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        Base.metadata.create_all(engine)  # 创建表，如果不存在的情况下
        x = session.query(DeviceInfo).filter(DeviceInfo.deviceFixId == deviceFixId,
                                             DeviceInfo.regionProvince == regionProvince,
                                             DeviceInfo.regionCity == regionCity, DeviceInfo.regionArea == regionArea)
        # 按要求向数据库插入设备信息
        count = 0
        for x1 in x:  # 用于判断是否存在该设备
            count += 1
        if count == 0:  # 如果不存在该设备
            deviceInfo = DeviceInfo(deviceFixId=deviceFixId, regionProvince=regionProvince, regionCity=regionCity,
                                    regionArea=regionArea, status=1)

            session.add(deviceInfo)
            try:
                session.commit()
            except sqlalchemy.exc.IntegrityError as e:  # 设备已经存在，键冲突
                print('重复插入')
                session.rollback()
            except sqlalchemy.exc.ProgrammingError as e:  # 设备信息表示已经存在的，这个异常基本不会存在
                Base.metadata.create_all(engine)
                session.rollback()
        else:  # 如果存在该设备，则代表设备重新上线
            self.updateDeviceStatus(deviceFixId, 1)

        session.close()

    def pushResultInfo(self, deviceFixId, kind, result, startTime, usedTime):
        tableData = startTime.split(' ')[0].replace("-", '_')
        ResultInfo.__table__.name = 'Result_' + tableData  # 根据数据上传的日期来创建新表
        ResultInfo.__tablename__ = 'Result_' + tableData
        Base.metadata.create_all(engine)
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        session.execute(
            'Insert into {} (`deviceFixId`, `kind`, `result`, `startTime`, usedTime) VALUES ("{}","{}","{}","{}",{})'.format(
                'Result_' + tableData, deviceFixId, kind, result, startTime, usedTime))
        session.commit()
        session.close()

    def selectDeviceInfo(self, regionProvince, regionCity=None, regionArea=None):
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        dataDict = {}
        dataDict["titles"] = ["设备ID"]
        dataDict["data"] = []
        # 查一个省的，
        if regionCity == None and regionArea == None:

            for x in session.query(DeviceInfo.deviceFixId, DeviceInfo.status).filter(
                    DeviceInfo.regionProvince == regionProvince):
                dataDict["data"].append({"fixedID": str(x[0]), "state": int(x[1])})
                # print(x)
        # 查省市
        elif regionArea == None:
            for x in session.query(DeviceInfo.deviceFixId, DeviceInfo.status).filter(
                    DeviceInfo.regionProvince == regionProvince,
                    DeviceInfo.regionCity == regionCity):
                dataDict["data"].append({"fixedID": str(x[0]), "state": int(x[1])})
                # print(x)
        # 查省市区
        else:
            for x in session.query(DeviceInfo.deviceFixId, DeviceInfo.status).filter(
                    DeviceInfo.regionProvince == regionProvince,
                    DeviceInfo.regionCity == regionCity,
                    DeviceInfo.regionArea == regionArea):
                dataDict["data"].append({"fixedID": str(x[0]), "state": int(x[1])})
                # print(x)
        return json.dumps(dataDict)

    def selectRegion(self, deviceFixId):
        DBSession =  sessionmaker(bind=engine)
        session = DBSession()
        x = session.query(DeviceInfo).filter(DeviceInfo.deviceFixId==deviceFixId).first()
        pinyin = pypinyin.slug(x.regionProvince,separator="")
        session.close()
        return pinyin


    def selectConfigInfo(self, deviceFixId):
        configJson = {}
        havePustList = []
        configJson["filesList"] = []
        configJson["channelsList"] = []
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        FileInfo = session.query(DeviceInfo).filter(DeviceInfo.deviceFixId == deviceFixId).first()  # 查询指定设备名的所有fileInfo
        for fileInfo in FileInfo.fileInfo:
            fileAbsolutePath = fileInfo.fileAbsolutePath
            fileSize = fileInfo.fileSize
            lastUpdatedDate = fileInfo.lastUpdatedDate
            configJson["filesList"].append(fileAbsolutePath)

        for pictureSize in FileInfo.pictureSize:

            channelName = pictureSize.channel
            kind = pictureSize.kind
            leftTopX = pictureSize.leftTopX
            leftTopY = pictureSize.leftTopY
            rightBottomX = pictureSize.rightBottomX
            rightBottomY = pictureSize.rightBottomY
            # x = session.query(PictureSize).filter(PictureSize.channel == channelName,
            #                                       PictureSize.deviceFixId == deviceFixId).all()
            # for x in x:
            #     print(x.channel,x.kind)
            # print(channelName,kind)
            # print(havePustList)
            if channelName in havePustList:
                channelIndex = havePustList.index(channelName)
                # print(channelIndex)
                configJson['channelsList'][channelIndex][kind] = {
                    "lt": [leftTopX, leftTopY],
                    "rb": [rightBottomX, rightBottomY]
                }
            else:
                configJson["channelsList"].append({"name": channelName,
                                                   kind: {
                                                       "lt": [leftTopX, leftTopY],
                                                       "rb": [rightBottomX, rightBottomY]
                                                   }
                                                   })
                havePustList.append(channelName)
        # print(configJson)
        session.close()
        return jsonify(configJson)

    def selectResultInfo(self, deviceName, deviceDate):
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        ResultInfo.__table__.name = "Result_" + str(deviceDate).replace("-", '_')  # 根据日期选择要查询的表
        print(deviceName)
        print(deviceDate)
        resultDict = {}
        resultDict['titles'] = ["序号", "设备名称", "信号类型", "识别结果", "识别时间", "耗时"]
        resultDict['data'] = []
        try:
            for result in session.query(ResultInfo.id, ResultInfo.deviceFixId, ResultInfo.kind, ResultInfo.result,
                                        ResultInfo.startTime, ResultInfo.usedTime).filter(
                DeviceInfo.deviceFixId == deviceName):
                result = self.SubscriberResultInfo(*result)
                resultDict['data'].append(
                    {"id": result.id, "fixId": result.deviceFixId, "kind": result.kind, "result": result.result,
                     "date": result.startTime.strftime("%Y-%m-%d %H:%M:%S"), "usedTime": result.usedTime})
            print("结果是:")
            print(resultDict)
            return json.dumps(resultDict)

        except sqlalchemy.exc.ProgrammingError as e:
            print(e)
            print('没有这一天的日期')
            return json.dumps(resultDict)
        finally:
            session.close()

    def returnDeviceInfo(self, deviceFixId, kind):
        deviceInfoJson = {}
        deviceInfoJson["deviceFixId"] = deviceFixId
        deviceInfoJson["ip"] = "127.0.0.1"
        deviceInfoJson["fileInfo"] = []
        deviceInfoJson['pictureSize'] = {}
        deviceInfoJson['kind'] = kind
        DBSession = sessionmaker(bind=engine)
        session = DBSession()
        deviceInfo = session.query(DeviceInfo).filter(
            DeviceInfo.deviceFixId == deviceFixId).first()  # 查询指定设备名的所有fileInfo

        deviceInfoJson['regionProvince'] = deviceInfo.regionProvince
        deviceInfoJson['regionCity'] = deviceInfo.regionCity
        deviceInfoJson['regionArea'] = deviceInfo.regionArea

        for fileInfo in deviceInfo.fileInfo:
            fileAbsolutePath = fileInfo.fileAbsolutePath
            fileSize = fileInfo.fileSize
            lastUpdatedDate = fileInfo.lastUpdatedDate
            lastUpdatedDate = datetime.strftime(lastUpdatedDate, '%Y-%m-%d %H:%M:%S')
            deviceInfoJson["fileInfo"].append(
                {"fileAbsolutePath": fileAbsolutePath, "fileSize": fileSize, "lastUpdatedDate": lastUpdatedDate})
        for pictureSize in deviceInfo.pictureSize:
            if pictureSize.kind == kind:
                channelName = pictureSize.channel
                leftTopX = pictureSize.leftTopX
                leftTopY = pictureSize.leftTopY
                rightBottomX = pictureSize.rightBottomX
                rightBottomY = pictureSize.rightBottomY
                deviceInfoJson["pictureSize"][channelName] = [leftTopX, leftTopY, rightBottomX, rightBottomY]
        session.close()
        return deviceInfoJson


if __name__ == '__main__':
    handleSql = handleSql()
    handleSql.pushDeviceInfo('31', '安徽' ,'安徽','利辛')
    handleSql.pushResultInfo('31','AV','bei','2018-12-24 21:12:21')
    #
    # # x = handleSql.selectDeviceInfo('上海')
    # handleSql.selectResultInfo("2zs23", "2018_01_21")
    # handleSql.updatePictureSize('2sdsaee',"北京卫视1","HDMI",12,23,24,12)
    # handleSql.returnDeviceInfo('2sdsaee', 'HDMI')
    # handleSql.selectRegion('2sdsaee')