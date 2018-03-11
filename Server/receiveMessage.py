# -*- coding:utf-8 -*-
import pickle
import sys
from functools import wraps
from time import sleep, time

from PyQt5.QtCore import QThread, QReadWriteLock, pyqtSignal, QByteArray, QDataStream, QFile, QIODevice, QObject
from PyQt5.QtGui import QImage
from PyQt5.QtNetwork import QTcpSocket, QHostAddress, QTcpServer, QAbstractSocket
from PyQt5.QtWidgets import QWidget, QMessageBox, QPushButton, QApplication, QMainWindow
from pushToSql import handleSql
from resultInfo import resultInfo
from deviceInfo import deviceInfo

# handleSql.pushDeviceInfo('123452','上海')
# handleSql.pushResultInfo('123452','HDMI','北京卫视','2018-12-23 12:23:21',12)
#
'''
下发命令，发给我想要发给的设备的命令，
发送模型，暂时只写这一个
设备id--->socketID
socketID --> socket    12123=`-04153 
f 
回传命令已经写好
新的想法， socketid --> thread -->thread.send(socket,xxx)  对应的线程调用对象的socket。



2月8号，接收结果到数据库、接收文件、向客户端发送命令、向客户端发送大文件、都已经解决。
接下来学习flask
还需要一个数据库用来保存图片大小 与对应频道

'''
from version1_0 import Ui_MainWindow

PORT = 31200
SIZEOF_UINT16 = 2
SIZEOF_UINT64 = 8


class Thread(QThread, QWidget):  # 这个线程为自动采集所用的。运行这个线程就会启动tcp 允许别人连上
    lock = QReadWriteLock()
    # 该线程内部定义的信号，携带了三个字 用于解决数据库问题
    pushDeviceInfoSignal = pyqtSignal(str, str)
    pushResultInfoSignal = pyqtSignal(str, str, str, str, int)
    sendFileSignal = pyqtSignal(str)

    def __init__(self, socketId, parent):
        super(Thread, self).__init__(parent)
        self.myParent = parent
        self.socketId = socketId  # socketID 可能是为socket编号
        self.hdmi_old_result = ""  # 为自动识别提供的 变量，可防止重复数据不停地输出
        self.av_old_result = ""  # 不共享变量
        self.handleSql = handleSql()
        self.pushDeviceInfoSignal.connect(self.pushDeviceInfo)
        self.pushResultInfoSignal.connect(self.pushResultInfo)

    def pushDeviceInfo(self, fixId, region):
        self.handleSql.pushDeviceInfo(str(fixId), region)

    def pushResultInfo(self, deviceFixId, kind, result, startTime,
                       usedTime):  # (self, deviceFixId, kind, result, startTime, usedTime
        self.handleSql.pushResultInfo(str(deviceFixId), kind, result, startTime, usedTime)


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
            self.myParent.sockeIdToSocketDict[self.socketId] = socket
            print(self.myParent.sockeIdToSocketDict)  # 将所有连接上来的socket保存起来
            print(self.myParent.fixIdToSocketIdDict)
            aim_ip = socket.peerAddress().toString()  # 获得连上来的IP地址
            print(aim_ip)

            if (socket.waitForReadyRead() and
                    socket.bytesAvailable() >= SIZEOF_UINT64):
                print('wait')
                nextBlockSize = stream.readUInt64()

            else:
                print('错误')  # 客户端主动断开时，去掉字典中的对应，在这里做一部分操作。
                # 客户端主动断开的时候，要将其从self.myParent.sockeIdToSocketDict   self.myParent.fixIdToSocketIdDict 中删掉
                self.myParent.sockeIdToSocketDict.pop(self.socketId)  # 客户端主动断开的时候删掉。
                self.myParent.fixIdToSocketIdDict.pop(fixID)
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
                print(fixID)
                print(resultObject.dateNow)
                print(resultObject.kind)
                print(resultObject.result)
                print(resultObject.startTime)
                print(resultObject.usedTime)

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
                deviceInfo = pickle.loads(deviceInfoByte)
                fixID = deviceInfo.fixId
                self.myParent.fixIdToSocketIdDict[fixID] = self.socketId
                self.pushDeviceInfoSignal.emit(deviceInfo.fixId, deviceInfo.region)
                print(deviceInfo.fixId)
                print(deviceInfo.region)

            elif state == 'sendFile':  # 准备接受 文件
                fileName = stream.readQString()  # 读取文件名称
                fileSize = stream.readQString()  # 读取文件大小
                fileBytes = stream.readBytes()  # 读取文件部分字节
                try:
                    Thread.lock.lockForRead()
                finally:
                    Thread.lock.unlock()
                print(fileSize)
                with open('../TEST/' + fileName, 'ab') as f:
                    f.write(fileBytes)
                count = count + fileBytes.__len__()
                print(fileBytes.__len__())
                print(count / int(fileSize))
                print(count)
                # while count < int(fileSize):
                #     stream = QDataStream(socket)
                #     stream.setVersion(QDataStream.Qt_5_7)
                #     x = stream.readUInt16()
                #
                #     print(x)
                #
                #     print(fileBytes)
                #
                #     print(count/int(fileSize))
                #     f.write(fileBytes)




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

    def sendReply(self,socket): # 用于测试
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

    def sendBackOrder(self,socket,order): # 回传一条命令
        reply = QByteArray()
        stream = QDataStream(reply, QIODevice.WriteOnly)
        stream.setVersion(QDataStream.Qt_5_7)
        stream.writeUInt64(0)
        stream.writeQString("ORDER") # 回传一条命令,命令自己定义。
        stream.writeQString(order)
        stream.device().seek(0)
        stream.writeUInt16(reply.size() - SIZEOF_UINT64)
        socket.write(reply)
        socket.waitForBytesWritten()

    def sendBackFile(self,socket,filePath):  #
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
                stream.writeUInt64(0)

                stream.writeQString('SENDFILE')
                stream.writeQString(file.fileName())
                stream.writeInt(file.size())
                stream.writeBytes(filedata)

                stream.device().seek(0)
                stream.writeUInt64(reply.size() - SIZEOF_UINT64)
                socket.write(reply)
                socket.waitForBytesWritten()
                count = count + filedata.__len__()
                print(count)





    def fileToBytes(self, fileName):  # 将文件转换成二进制
        with open(fileName, 'rb') as f:
            return f.read()

def singleton(cls):
    ''' Use class as singleton. '''

    cls.__new_original__ = cls.__new__

    @wraps(cls.__new__)
    def singleton_new(cls, *args, **kw):
        it =  cls.__dict__.get('__it__')
        if it is not None:
            return it

        cls.__it__ = it = cls.__new_original__(cls, *args, **kw)
        it.__init_original__(*args, **kw)
        return it

    cls.__new__ = singleton_new
    cls.__init_original__ = cls.__init__
    cls.__init__ = object.__init__

    return cls

@singleton
class TcpServer(QTcpServer):

    def __init__(self, parent=None):
        super(TcpServer, self).__init__(parent)
        self.myParent = parent
        self.sockeIdToSocketDict = {}  # 保存 socketId 与 socket 的字典
        self.fixIdToSocketIdDict = {}  # 保存设备id与socketID的字典
        self.threadDict = {}

    def incomingConnection(self, socketId):

        thread = Thread(socketId, self)
        self.threadDict[socketId] = thread # 保存此线程对象可以解决回传的问题，
        print(self.threadDict)
        # thread.havegotmessageall.connect(self.myParent.getMessageAllTcp)  # 因为thread这个对象是内部创建的，只能通过parent得到他内部的信号  绑定
        print('# 151 连接一次')
        # with open('{}.txt'.format(socketId), 'wt') as f:
        #     f.write("{}开始连接".format(socketId))
        # self.connect(thread, SIGNAL("finished()"),
        #             thread, SLOT("deleteLater()"))

        thread.finished.connect(thread.deleteLater)
        thread.start()



class BuildingServicesDlg(QObject):


    dosomething = pyqtSignal()

    def __init__(self):
        super(BuildingServicesDlg, self).__init__()
        self.tcpServer = TcpServer(self)
        # self.resetModelButton.clicked.connect(self.dosome)
        # print(self.tcpServer.myParent.)
        if not self.tcpServer.listen(QHostAddress("0.0.0.0"), PORT):
            # QMessageBox.critical(self, "Building Services Server",
            #                      "Failed to start server: {0}".format(self.tcpServer.errorString()))
            self.close()
            return

    def dosome(self):
        print('询问客户端是否准备好接受文件')
        fixID = '2s223'
        socketID=  self.tcpServer.fixIdToSocketIdDict[fixID]
        socket = self.tcpServer.sockeIdToSocketDict[socketID]
        thread = self.tcpServer.threadDict[socketID]

        thread.sendBackFile(socket,'2.jpg')



if __name__ == '__main__':
    app = QApplication(sys.argv)
    dig = BuildingServicesDlg()
    # dig.show()
    sys.exit(app.exec_())
