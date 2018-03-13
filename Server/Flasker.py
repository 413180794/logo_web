# -*-coding:utf-8 -*-
import sys
import threading

import os
from flask import Flask, request, Response, send_from_directory
from flask_cors import CORS
from Server import pushToSql

import json
import pickle
import sys
from time import sleep, time

from PyQt5.QtCore import QThread, QReadWriteLock, pyqtSignal, QByteArray, QDataStream, QFile, QIODevice, QObject, \
    QCoreApplication
from PyQt5.QtNetwork import QTcpSocket, QHostAddress, QTcpServer, QAbstractSocket
from PyQt5.QtWidgets import QWidget, QApplication, QPushButton
from resultInfo import resultInfo
from deviceInfo import deviceInfo

PORT = 31200
SIZEOF_UINT16 = 2
SIZEOF_UINT64 = 8

sockeIdToSocketDict = {}  # 保存 socketId 与 socket 的字典
fixIdToSocketIdDict = {}  # 保存设备id与socketID的字典
threadDict = {}


class Thread(QThread, QWidget):  # 这个线程为自动采集所用的。运行这个线程就会启动tcp 允许别人连上
    lock = QReadWriteLock()
    # 该线程内部定义的信号，携带了三个字 用于解决数据库问题
    pushDeviceInfoSignal = pyqtSignal(str, str, str, str)
    popDeviceSignal = pyqtSignal(str)
    pushPictureSizeSignal = pyqtSignal(str, str, str)
    pushFileInfoSignal = pyqtSignal(str, str)
    pushResultInfoSignal = pyqtSignal(str, str, str, str, int)
    sendFileSignal = pyqtSignal(str)

    def __init__(self, socketId, parent):
        super(Thread, self).__init__(parent)
        self.myParent = parent
        self.socketId = socketId  # socketID 可能是为socket编号
        self.hdmi_old_result = ""  # 为自动识别提供的 变量，可防止重复数据不停地输出
        self.av_old_result = ""  # 不共享变量
        self.handleSql = pushToSql.handleSql()
        self.pushDeviceInfoSignal.connect(self.pushDeviceInfo)
        self.pushResultInfoSignal.connect(self.pushResultInfo)
        self.pushPictureSizeSignal.connect(self.pushPictureSize)
        self.pushFileInfoSignal.connect(self.pushFileInfo)
        self.popDeviceSignal.connect(self.popDevice)

    def pushDeviceInfo(self, deviceFixId, regionProvince, regionCity, regionArea):
        self.handleSql.pushDeviceInfo(str(deviceFixId), regionProvince, regionCity, regionArea)

    def pushResultInfo(self, deviceFixId, kind, result, startTime,
                       usedTime):  # (self, deviceFixId, kind, result, startTime, usedTime

        self.handleSql.pushResultInfo(str(deviceFixId), kind, result, startTime, usedTime)

    def pushPictureSize(self, pictureSize, deviceFixId, kind):  # 将图片信息转入数据库
        pictureSizeDict = eval(pictureSize)
        # print(type(pictureSizeDict), pictureSizeDict)
        # print(pictureSizeDict)
        for key, value in pictureSizeDict.items():
            self.handleSql.pushPictureSize(deviceFixId, key, kind, value[0], value[1], value[2], value[3])

    def pushFileInfo(self, fileInfo, deviceFixId):
        fileInfo = eval(fileInfo)
        for fileInfoItem in fileInfo:
            fileAbsolutePath = fileInfoItem['fileAbsolutePath']
            fileSize = fileInfoItem['fileSize']
            lastUpdatedDate = fileInfoItem['lastUpdatedDate']
            self.handleSql.pushFileInfo(deviceFixId, fileAbsolutePath, fileSize,
                                        lastUpdatedDate)

    def popDevice(self, deviceId):
        self.handleSql.updateDeviceStatus(deviceId, 0)

    def run(self):
        print('-----------------------')
        socket = QTcpSocket()

        count = 0

        if not socket.setSocketDescriptor(self.socketId):  # 可能是分配的东西，具体作用不知道
            # self.emit(SIGNAL("error(int)"), socket.error())
            self.error.connect(socket.error)

            return

        while socket.state() == QAbstractSocket.ConnectedState:
            nextBlockSize = 0
            stream = QDataStream(socket)
            stream.setVersion(QDataStream.Qt_5_8)
            sockeIdToSocketDict[self.socketId] = socket
            # print(sockeIdToSocketDict)  # 将所有连接上来的socket保存起来
            # print(fixIdToSocketIdDict)
            aim_ip = socket.peerAddress().toString()  # 获得连上来的IP地址
            # print(aim_ip)

            if (socket.waitForReadyRead() and
                    socket.bytesAvailable() >= SIZEOF_UINT64):
                print('wait')
                nextBlockSize = stream.readUInt64()

            else:
                print('错误')  # 客户端主动断开时，去掉字典中的对应，在这里做一部分操作。
                # 客户端主动断开的时候，要将其从self.myParent.sockeIdToSocketDict   self.myParent.fixIdToSocketIdDict 中删掉
                sockeIdToSocketDict.pop(self.socketId)  # 客户端主动断开的时候删掉。
                fixIdToSocketIdDict.pop(fixID)
                threadDict.pop(self.socketId)
                self.popDeviceSignal.emit(fixID)
                self.sendError(socket, "Cannot read client request")
                return
            if socket.bytesAvailable() < nextBlockSize:
                print("错误2")
                if (not socket.waitForReadyRead(60000) or
                        socket.bytesAvailable() < nextBlockSize):
                    self.sendError(socket, "Cannot read client data")
                    return

            # 这段数据流上 第一个是state 根据state判断接下来的状态，
            # 发送成功的状态，发送来 success    日期  信号类型 识别结果 识别开始时间 识别时间

            state = stream.readQString()  # 读状态

            print('#61    ' + state)
            if state == 'successResult':  # 如果状态是success，说明下一个发来的是识别的结果
                resultBytes = stream.readBytes()
                try:
                    Thread.lock.lockForRead()
                finally:
                    Thread.lock.unlock()
                resultObject = pickle.loads(resultBytes)
                # print(fixID)
                # print(resultObject.dateNow)
                # print(resultObject.kind)
                # print(resultObject.result)
                # print(resultObject.startTime)
                # print(resultObject.usedTime)

                if resultObject.kind == "HDMI" and self.hdmi_old_result != resultObject.result:

                    # 自动采集的不需要时间，他需要 日期 时间识别结果 发走的信息只有 类型 识别结果 ip地址 全是strhandleSql.pushResultInfo('123425','HDMI','北京卫视','2018-12-23 12:23:21',12)
                    self.pushResultInfoSignal.emit(fixID, resultObject.kind, resultObject.result,
                                                   resultObject.startTime,
                                                   int(
                                                       resultObject.usedTime))  # 发射信号，携带了信号类型，识别结果，aim_ip（当做区分控件的id）结果从这里发出去
                    self.hdmi_old_result = resultObject.result

                elif resultObject.kind == 'AV' and self.av_old_result != resultObject.result:
                    self.pushResultInfoSignal.emit(fixID, resultObject.kind, resultObject.result,
                                                   resultObject.startTime,
                                                   int(
                                                       resultObject.usedTime))  # 发射信号，携带了信号类型，识别结果，aim_ip(当做区分空间的id） getMessgetMessageAllTcpageAllTcp
                    self.av_old_result = resultObject.result
            elif state == 'sendImage':  # 如果状态是wait_to_recognize，说明下一端是图片的16位整数# 图片的暂时不考虑，因为还不知道发给谁
                kind = stream.readQString()  # 读台标信号类型
                try:
                    Thread.lock.lockForRead()
                finally:
                    Thread.lock.unlock()
                file = stream.readBytes()
                with open('image.jpg', 'wb') as f:
                    f.write(file)

            elif state == 'deviceInfo':  # 收到deviceInfo对象
                deviceInfoByte = stream.readBytes()
                try:
                    Thread.lock.lockForRead()
                finally:
                    Thread.lock.unlock()
                # pictureSizeByte = stream.readBytes()
                deviceInfo = pickle.loads(deviceInfoByte)
                # pictureSize = pickle.loads(pictureSizeByte)

                fixID = deviceInfo['deviceFixId']
                fixIdToSocketIdDict[fixID] = self.socketId
                print(deviceInfo['pictureSize'])
                self.pushDeviceInfoSignal.emit(deviceInfo['deviceFixId'], deviceInfo['regionProvince'],
                                               deviceInfo['regionCity'],
                                               deviceInfo['regionArea'])
                print("___________________________")
                print(deviceInfo['fileInfo'])
                self.pushPictureSizeSignal.emit(str(deviceInfo['pictureSize']), deviceInfo['deviceFixId'],
                                                deviceInfo['kind'])
                self.pushFileInfoSignal.emit(str(deviceInfo['fileInfo']), deviceInfo['deviceFixId'])



            elif state == 'sendFile':  # 准备接受 文件
                fileName = stream.readQString()  # 读取文件名称
                fileSize = stream.readQString()  # 读取文件大小
                fileBytes = stream.readBytes()  # 读取文件部分字节
                try:
                    Thread.lock.lockForRead()
                finally:
                    Thread.lock.unlock()
                # print(fileSize)
                with open('../TEST/' + fileName, 'ab') as f:
                    f.write(fileBytes)
                count = count + fileBytes.__len__()
                # print(fileBytes.__len__())
                # print(count / int(fileSize))
                # print(count)

    def sendError(self, socket, msg):
        reply = QByteArray()
        stream = QDataStream(reply, QIODevice.WriteOnly)
        stream.setVersion(QDataStream.Qt_5_7)
        stream.writeUInt16(0)
        stream.writeQString("ERROR")
        stream.writeQString(msg)
        stream.device().seek(0)
        stream.writeUInt16(reply.size() - SIZEOF_UINT16)
        socket.write(reply)

    def sendReply(self, socket):  # 用于测试
        reply = QByteArray()
        stream = QDataStream(reply, QIODevice.WriteOnly)
        stream.setVersion(QDataStream.Qt_5_7)
        stream.writeUInt16(0)
        stream.writeQString("test")
        stream.writeQString('收到')
        stream.device().seek(0)
        stream.writeUInt16(reply.size() - SIZEOF_UINT16)
        socket.write(reply)
        socket.waitForBytesWritten()

    def sendBackOrder(self, socket, order):  # 回传一条命令
        reply = QByteArray()
        stream = QDataStream(reply, QIODevice.WriteOnly)
        stream.setVersion(QDataStream.Qt_5_7)
        stream.writeUInt16(0)
        stream.writeQString("ORDER")  # 回传一条命令,命令自己定义。
        stream.writeQString(order)
        stream.device().seek(0)
        stream.writeUInt16(reply.size() - SIZEOF_UINT16)
        socket.write(reply)
        socket.waitForBytesWritten()

    def sendBackFile(self, socket, filePath):  #
        file = QFile(filePath)
        print(file.size())
        count = 0
        with open(filePath, 'rb') as f:
            while 1:
                sleep(0.1)
                filedata = f.read(20480)
                if not filedata:
                    break
                reply = QByteArray()
                stream = QDataStream(reply, QIODevice.WriteOnly)
                stream.setVersion(QDataStream.Qt_5_7)
                stream.writeUInt16(0)

                stream.writeQString('SENDFILE')
                stream.writeQString(file.fileName())
                stream.writeInt(file.size())
                stream.writeBytes(filedata)

                stream.device().seek(0)
                stream.writeUInt16(reply.size() - SIZEOF_UINT16)
                socket.write(reply)
                socket.waitForBytesWritten()
                count = count + filedata.__len__()
                print(count)

    def fileToBytes(self, fileName):  # 将文件转换成二进制
        with open(fileName, 'rb') as f:
            return f.read()


class TcpServer(QTcpServer):

    def __init__(self, parent=None):
        super(TcpServer, self).__init__(parent)
        self.myParent = parent

    def incomingConnection(self, socketId):
        thread = Thread(socketId, self)
        threadDict[socketId] = thread  # 保存此线程对象可以解决回传的问题，
        print(threadDict)
        # thread.havegotmessageall.connect(self.myParent.getMessageAllTcp)  # 因为thread这个对象是内部创建的，只能通过parent得到他内部的信号  绑定
        print('# 151 连接一次')

        thread.finished.connect(thread.deleteLater)
        thread.start()


class BuildingServicesDlg(QObject):
    dosomething = pyqtSignal()

    def __init__(self):
        super(BuildingServicesDlg, self).__init__()
        self.tcpServer = TcpServer(self)

        if not self.tcpServer.listen(QHostAddress("0.0.0.0"), PORT):
            # QMessageBox.critical(self, "Building Services Server",
            #                      "Failed to start server: {0}".format(self.tcpServer.errorString()))

            self.close()
            return

    def dosome(self):
        print('询问客户端是否准备好接受文件')
        fixID = '2sdsaee'
        socketID = fixIdToSocketIdDict[fixID]
        socket = sockeIdToSocketDict[socketID]
        thread = threadDict[socketID]

        thread.sendBackOrder(socket, 'doThing')


app1 = Flask(__name__, static_url_path="")
# CORS(app1)

# @app1.route('/')
# def hello_world():
#      return app1.send_static_file('index.html')
def sendBackOrder(deviceFixId, order):
    '''
    :param deviceFixId:
    :param order:
    UpdateInfo
    UpdateModelFile,cetv_tf
    ---先不管下面的---
    RollbackInfo
    RollbackModelFile,cetv_tf
    :return:
    '''
    print('询问客户端是否准备好接受文件')
    try:
        socketID = fixIdToSocketIdDict[deviceFixId]
        socket = sockeIdToSocketDict[socketID]
        thread = threadDict[socketID]
    except Exception as e:
        print("该设备不在线，该设备名称不存在")
        return "该设备不在线，该设备名称不存在"
    thread.sendBackOrder(socket, order)


@app1.route('/exampleData/areaData', methods=['GET'])
def deviceInfo():
    handleSql = pushToSql.handleSql()
    region = request.args.get('data')  # 收到数据
    region = eval(region)  # 将数据转换成list 长度可能为1,2,3
    print(type(region))
    print(region)
    if len(list(region)) == 1:  # 如果长度为1 ，说明要查一个省
        regionProvince = region[0]
        deviceFixIdJson = handleSql.selectDeviceInfo(regionProvince)
    elif len(list(region)) == 2:  # 如果长度为2， 说明要查省市
        regionProvince = region[0]
        regionCity = region[1]
        deviceFixIdJson = handleSql.selectDeviceInfo(regionProvince, regionCity)
    else:  # 如果长度为3， 说明要查省市区
        regionProvince = region[0]
        regionCity = region[1]
        regionArea = region[2]
        deviceFixIdJson = handleSql.selectDeviceInfo(regionProvince, regionCity, regionArea)
    return deviceFixIdJson


@app1.route('/exampleData/detailData', methods=['GET', 'POST'])
def resultInfo():
    handleSql = pushToSql.handleSql()
    deviceNameAndDate = request.args.get('data')
    deviceNameAndDateDict = eval(deviceNameAndDate)  # 字符串转字典
    deviceName = deviceNameAndDateDict['name']
    deviceDate = deviceNameAndDateDict['date']

    x = handleSql.selectResultInfo(deviceName, deviceDate)
    # print(sockeIdToSocketDict)
    # print(fixIdToSocketIdDict)
    # print(threadDict)
    return x


@app1.route('/exampleData/configData', methods=['GET'])
def configureInfo():
    handleSql = pushToSql.handleSql()
    deviceFixIds = request.args.get('data')  # 发来很多设备，说明有很多设备要配置。默认用户知道这一批修改格式相同
    deviceFixIds = eval(deviceFixIds)
    if len(deviceFixIds) != 0:
        deviceFixId = deviceFixIds[0]  # 只查一台设备
    else:
        return "123"
    configJson = handleSql.selectConfigInfo(deviceFixId)
    print(configJson)
    return configJson


@app1.route('/exampleData/sendConfigData', methods=['POST'])
def resetConfigInfo():
    handleSql = pushToSql.handleSql()
    configInfo = request.get_data()  # bytes 类型
    configInfo = str(configInfo, encoding="utf-8")  # bytes类型转字符串
    configInfo = eval(configInfo)  # 字符串转字典
    # print(configInfo)
    # 收到网页端更新数据库的请求 可能更新 deviceList中设备，更新内容为{文件，频道列表} 我需要把文件列表 发给相
    # 应的设备，告诉其应该更新文件了。再发送其命令更新设备信息。 也就是说我需要向回发送两条命令
    # 发送而来的文件名字其实没有什么用，因为我不更新这个东西。
    # 发送而来的channelsList有用，我要更新数据库中图片的大小。

    # --- 更新数据库中图片的大小----
    channelsList = configInfo['channelsList']
    deviceList = configInfo['deviceList']
    for deviceFixId in deviceList:
        for channel in channelsList:
            channelName = channel['name']
            print(channel.keys())
            if "HDMI" in channel.keys():
                kind = "HDMI"
                leftTopX = channel['HDMI']['lt'][0]
                leftTopY = channel['HDMI']['lt'][1]
                rightBottomX = channel['HDMI']['rb'][0]
                rightBottomY = channel['HDMI']['rb'][1]
                handleSql.updatePictureSize(deviceFixId, channelName, kind, leftTopX, leftTopY, rightBottomX,
                                            rightBottomY)
            if "AV" in channel.keys():
                kind = "AV"
                leftTopX = channel['AV']['lt'][0]
                leftTopY = channel['AV']['lt'][1]
                rightBottomX = channel['AV']['rb'][0]
                rightBottomY = channel['AV']['rb'][1]
                handleSql.updatePictureSize(deviceFixId, channelName, kind, leftTopX, leftTopY, rightBottomX,
                                            rightBottomY)

            # handleSql.updatePictureSize(deviceFixId, channelName, leftTopX, leftTopY, rightBottomX, rightBottomY)
    # --  向客户端发送更新文件命令  ----

    print(sockeIdToSocketDict)
    print(fixIdToSocketIdDict)
    print(threadDict)

    filesList = configInfo['filesList']  # 需要更新文件类型
    print(filesList)
    for deviceFixId in deviceList:
        sendBackOrder(deviceFixId, "UpdateInfo,HDMI")
        sendBackOrder(deviceFixId, "UpdateInfo,AV")
        if filesList:
            for file in filesList:
                sendBackOrder(deviceFixId, 'UpdateModelFile,' + file)

    return "123"


@app1.route('/download_deviceInfo/<model_type>')
def UpdateDeviceInfo(model_type):
    handleSql = pushToSql.handleSql()
    print("****************!!!!!!!!********************************")
    print(model_type)
    deviceFixId = request.args.get("deviceFixId")
    t = handleSql.returnDeviceInfo(deviceFixId, model_type)
    print(t)
    print(type(t))
    print(request.args.get("deviceFixId"))
    return Response(json.dumps(t), mimetype='application/json')


@app1.route("/download_file/<kindname>/<filename>", methods=['GET'])
def download_file(kindname, filename):
    handleSql = pushToSql.handleSql()
    deviceFixId = request.args.get("deviceFixId")
    deviceProvince = handleSql.selectRegion(deviceFixId)
    directory = os.getcwd()  # 假设在当前目录
    print(os.path.join(directory, "download", kindname + "_" + deviceProvince))
    print(filename)
    return send_from_directory(os.path.join(directory, "download", kindname + "_" + deviceProvince), filename,
                               as_attachment=True)

if __name__ == '__main__':
    t = threading.Thread(target=app1.run,args=('127.0.0.1',5000))
    t.start()
    # app1.run()
    app = QCoreApplication(sys.argv)
    dig = BuildingServicesDlg()
    sys.exit(app.exec_())

