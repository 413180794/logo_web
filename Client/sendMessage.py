# -*- coding: utf-8 -*-
import json
import pickle
import time
from functools import wraps
from threading import Thread

from PyQt5.QtCore import QByteArray, QDataStream, QIODevice, QDate, QBuffer, QFile, pyqtSignal, QObject
from PyQt5.QtNetwork import QTcpSocket, QAbstractSocket
from deviceInfo import deviceInfo
from resultInfo import resultInfo
from OrderGenerator import generateOrder

'''
专门用于发送信息的类，不用于接受大文件,只能接受简单的命令，比如收到一个台返回收到命令。
IP为目的的IP地址，ID为该设备的固定设备号码，REGION_*  为该设备的所在地 均从deviceInfo.json 读取
创建该类的对象，即自动初始化连接设备，并发送设备信息
PyQt5 --> pip3 install PyQt5

sendResult(self, stream, kind, result, startTime, usedTime): 发送结果函数
    如：sendMessage1.sendResult('HDMI', 'av1' + str(n), '2017-12-21 12:23:23', '78')  # param 信号类型，识别结果，开始时间，使用时间

sendFile(self, filePath): 发送文件函数，用于客户端向服务器端发送小文件
    如：sendMessage1.sendFile('2.jpg')

dowhat()收到某命令后会异步执行还函数，还没有定好规则。



'''

with open("deviceInfo_AV.json", 'r', encoding="GBK") as f:
    deviceInfoJson = f.read()
    deviceInfoJson = json.loads(deviceInfoJson)
IP = deviceInfoJson["ip"]
print(IP)
DEVICE_FIX_ID = deviceInfoJson["deviceFixId"]
REGION_PROVINCE = deviceInfoJson["regionProvince"]
REGION_CITY = deviceInfoJson["regionCity"]
REGION_AREA = deviceInfoJson['regionArea']
PICTURE_SIZE = deviceInfoJson["pictureSize"]
PORT = 31200
SIZEOF_UINT16 = 2
SIZEOF_UINT64 = 8


def startSendMessage(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        request = QByteArray()
        stream = QDataStream(request, QIODevice.WriteOnly)
        stream.setVersion(QDataStream.Qt_5_7)
        stream.writeUInt64(0)
        # time.sleep(0.1)
        result = func(self, stream, *args, **kwargs)
        stream.device().seek(0)
        stream.writeUInt64(request.size() - SIZEOF_UINT64)
        self.socket.write(request)
        self.socket.waitForBytesWritten()
        return result

    return wrapper


class sendMessage(QObject):
    doSomeThing = pyqtSignal(str)  # 收到一条命令去执行

    def __init__(self, parent=None):  # 初始化发送对象，首先要先建立连接
        super(sendMessage, self).__init__(parent)
        self.socket = QTcpSocket()
        self.nextBlockSize = 0
        self.socket.connectToHost(IP, PORT)
        self.deviceInfo = deviceInfo(DEVICE_FIX_ID, REGION_PROVINCE, REGION_CITY, REGION_AREA)  # 保存盒子信息，可从某个文件读取
        self.socket.connected.connect(self.initConnected)  # 初始化连接，第一次连上就发送信息
        self.socket.waitForConnected()  # 等待设备连接完成
        time.sleep(0.1)
        self.socket.readyRead.connect(self.readResponse)
        self.socket.disconnected.connect(self.serverHasStopped)
        self.socket.error.connect(self.serverHasError)
        self.doSomeThing.connect(self.doWhat)  # 收到某条命令要执行的函数

    def doWhat(self,order):  # 收到dosome命令要执行的函数
        if order:
            if ',' in order:
                order, model_type = order.split(",")
            else:
                model_type = None
            order_instance = generateOrder(order)
            t = Thread(target=order_instance.run, args=(self.deviceInfo, IP, 8989, model_type))
            t.start()

    def fileToBytes(self, fileName):  # 将文件转换成二进制
        file = QFile(fileName)
        print(file.size())
        count = 0
        with open(fileName, 'rb') as f:
            while 1:
                filedata = f.read(1024)
                if not filedata:
                    break
                count = count + filedata.__len__()
        print(count)


    @startSendMessage
    def initConnected(self, stream):  # 每次连接上后 发送盒子的设备信息      fixID（固定id） region（所在地区）
        stream.writeQString('deviceInfo')  # 设定信息类型 state
        deviceInfoToByte = pickle.dumps(deviceInfoJson)  # 将设备信息序列化成二进制发送    s = pickle.dumps(sendMessage1.deviceInfo)
        stream.writeBytes(deviceInfoToByte)

        '''
        接下来还有几点
        1、盒子连接建立，发送设备信息。接收端接收一次。
        2、规定好发送文件的格式
        3、设计数据库
        4、与网页交互
        '''

    @startSendMessage
    def sendFileBytes(self, stream, filePath, fileBytes):  # stream 由装饰器传值    状态 文件名 文件字节
        file = QFile(filePath)
        print(filePath)
        stream.writeQString('sendFile')  # 发送文件 状态
        stream.writeQString(file.fileName())  # 发送文件的名字
        print(file.size())
        stream.writeQString(str(file.size()))  # 发送文件的大小

        stream.writeBytes(fileBytes)

    def sendFile(self, filePath):
        with open(filePath, 'rb') as f:
            count = 0
            while 1:  # 循环传输

                filedata = f.read(204800)
                print(filedata.__sizeof__())
                if not filedata:
                    break
                self.sendFileBytes(filePath, filedata)
                count = count + filedata.__sizeof__()
                print(count)

    @startSendMessage
    def sendImage(self, stream, imagePath, kind):  # 传递图片，与图片类型    状态 图片类型 图片
        stream.writeQString('sendImage')
        stream.writeQString(kind)
        stream.writeBytes(self.fileToBytes(imagePath))

    @startSendMessage
    def sendResult(self, stream, kind, result, startTime,
                   usedTime):  # ，发送成功的状态，发送来 success    日期  信号类型 识别结果 识别开始时间 识别时间

        stream.writeQString('successResult')  # 发送成功状态
        dateNow = time.strftime("%Y-%m-%d", time.localtime())
        resultObject = resultInfo(dateNow, kind, result, startTime, usedTime)  # 结果对象 （日期，类型，结果，开始时间，识别用时）
        resultBytes = pickle.dumps(resultObject)
        stream.writeBytes(resultBytes)

    def readResponse(self):  # 收命令，要做的事情，

        stream = QDataStream(self.socket)
        print('--------------------')
        print('服务器响应')
        stream.setVersion(QDataStream.Qt_5_7)

        while True:
            self.nextBlockSize = 0
            if self.nextBlockSize == 0:
                if self.socket.bytesAvailable() < SIZEOF_UINT16:
                    print('没有内容了')
                    break
                self.nextBlockSize = stream.readUInt16()

            else:
                print('错误')  # 客户端主动断开时，去掉字典中的对应，在这里做一部分操作。
                # 客户端主动断开的时候，要将其从self.myParent.sockeIdToSocketDict   self.myParent.fixIdToSocketIdDict 中删掉

                break
            if self.socket.bytesAvailable() < self.nextBlockSize:
                print("错误2")
                if (not self.socket.waitForReadyRead(60000) or
                        self.socket.bytesAvailable() < self.nextBlockSize):
                    break
            state = stream.readQString()  # 读命令         sendModel
            print('state==' + state)
            if state == 'SENDFILE':
                filename = stream.readQString()  # 读文件名
                fileSize = stream.readInt()  # 读文件大小
                with open('../TEST/' + filename, 'ab') as f:
                    while self.nextBlockSize > 0:
                        fileBytes = stream.readBytes()  # 读文件部分字节
                        f.write(fileBytes)

                        print(fileBytes.__len__())
                        self.nextBlockSize = stream.readUInt64()
                        print('self.nextBlockSize:' + str(self.nextBlockSize))
                        state = stream.readQString()
                        filename = stream.readQString()  # 读文件名
                        fileSize = stream.readInt()  # 读文件大小
                        print('filename:' + filename)
                        print('fileSize:' + str(fileSize))

            elif state == 'test':
                print(stream.readQString())

            elif state == 'ORDER':  # 收到一条命令      要执行的命令
                order = stream.readQString()  # 读是什么命令
                if order:  # shou dao doThing
                    self.doSomeThing.emit(order)

    def serverHasStopped(self):
        print('连接断开')
        self.socket.close()
        self.socket = QTcpSocket()
        print(self.socket.state())
        while self.socket.state() == 0:
            print("重新连接")
            time.sleep(5)
            self.socket.connectToHost(IP, PORT)
            self.socket.waitForConnected()

        # self.socket.close()

    def serverHasError(self, error):
        self.socket.close()


if __name__ == '__main__':
    sendMessage1 = sendMessage()
    n = 0

    # x = pickle.dumps(sendMessage1.deviceInfo)
    # print(x)
    # x1 = pickle.loads(x)
    # print(x1)
    # sendMessage1.sendResult('HDMI', 'anshu123' + str(n), '2017-12-21 12:23:23', '78')  # param 信号类型，识别结果，开始时间，使用时间

    # sendMessage1.sendFile('logo_detect.tar')

    # sendMessage1.sendResult('HDMI', 'anshu1213' + str(n), '2017-12-21 12:23:23', '78')
    #
    # sendMessage1.sendResult('AV', 'anshu123' + str(n), '2017-12-21 12:23:23', '78')
    # sendMessage1.sendResult('AV', 'anshu123' + str(n), '2017-12-21 12:23:23', '78')
    # sendMessage1.sendResult('AV', 'anshu123' + str(n), '2017-12-21 12:23:23', '78')
    # sendMessage1.sendResult('AV', 'anshu123' + str(n), '2017-12-21 12:23:23', '78')
    # sendMessage1.sendResult('HDMI', 'av1' + str(n), '2017-12-21 12:23:23', '78')  # param 信号类型，识别结果，开始时间，使用时间
    # sendMessage1.sendResult('AV', 'av2' + str(n), '2017-12-21 12:23:23', '78')  # param 信号类型，识别结果，开始时间，使用

    # sendMessage1.sendFile('2.jpg')
    # sendMessage1.receiveFile()
    while (1):
        n = n + 1
        # sendMessage1.sendFile('retrained_graph.pb')
        # sendMessage1.sendResult('HDMI', 'anshu123' + str(n),'2017-12-21 12:23:23','78')    # param 信号类型，识别结果，开始时间，使用时间
        time.sleep(20)
        sendMessage1.sendResult('AV', 'shanghai23' + str(n), '2018-03-10 12:23:23', '7')  # param 信号类型，识别结果，开始时间，使用时间
    # #     print(sendMessage1.socket.state())
    #     print(sendMessage1.socket.currentReadChannel())
