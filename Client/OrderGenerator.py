import os
import json
import shutil
import requests

class Order:
    def run(self, deviceInfo, ip, port, model_type):
        pass

class UpdateInfoOrder(Order):
    def run(self, device_info, ip, port, model_type):
        print("更新配置文件中。。。")
        url = "http://%s:%s/download_deviceInfo/%s" % (ip, port,model_type) # model_type 判断更新是av还是hdmi
        print(url)
        try:
            r =requests.get(url, params={
                "deviceFixId": device_info.deviceFixId
            })
            result_json = r.json()
            print(result_json)
            if result_json.get("deviceFixId") != device_info.deviceFixId:
                return
            else:
                _updateInfoFile(result_json,model_type)
        except Exception as e:
            print(e)

class UpdateModelFileOrder(Order):
    def run(self, deviceInfo, ip, port, model_type): # model_type判断更新什么模型，
        print("更新模型文件%s中。。。" % model_type)
        graph_url = "http://%s:%s/download_file/%s/retrained_graph.pb" % (ip, port, model_type)
        labels_url = "http://%s:%s/download_file/%s/retrained_labels.txt" % (ip, port, model_type)
        if not os.path.exists(model_type):
            os.mkdir(model_type)
        else:
            print("备份上一个版本")
            if os.path.exists(model_type + "_bak"):
                shutil.rmtree(model_type + "_bak")
            os.rename(model_type, model_type + "_bak")
            os.mkdir(model_type)
        _download_file(graph_url, model_type, params={
            "deviceFixId": deviceInfo.deviceFixId
        })
        _download_file(labels_url, model_type, params={
            "deviceFixId": deviceInfo.deviceFixId
        })
        print("更新模型文件完成。。。")
        

class RollbackInfoOrder(Order):
    def run(self, deviceInfo, ip, port, model_type):
        print("回滚配置文件中。。。")
        if not os.path.exists("deviceInfo_"+model_type+".json.bak"):
            return
        os.rename("deviceInfo_"+model_type+".json.bak", "deviceInfo_"+model_type+".json")
        print("回滚配置文件完成。。。")

class RollbackModelFileOrder(Order):
    def run(self, deviceInfo, ip, port, model_type):
        print("回滚配置文件中。。。")
        if not os.path.exists(model_type + "_bak"):
            return
        if os.path.exists(model_type):
            shutil.rmtree(model_type)
            os.rename(model_type + "_bak", model_type)

def generateOrder(order_str):
    if order_str == "UpdateInfo":
        return UpdateInfoOrder()
    elif order_str == "UpdateModelFile":
        return UpdateModelFileOrder()
    elif order_str == "RollbackInfo":
        return RollbackInfoOrder()
    elif order_str == "RollbackModelFile":
        return RollbackModelFileOrder()
    else:
        return Order()


def _updateInfoFile(result_json,model_type):
    if os.path.exists("deviceInfo_"+model_type+".json"):
        os.rename("deviceInfo_"+model_type+".json", "deviceInfo_"+model_type+".json.bak")
    with open("deviceInfo_"+model_type+".json", "w") as f:
        json.dump(result_json, f, ensure_ascii=False) 
        print("更新配置文件完成。。。")

def _download_file(url, path='.', params={}):
    local_filename = url.split('/')[-1]
    # NOTE the stream=True parameter
    with requests.get(url, params=params, stream=True) as r:
        with open(os.path.join(path, local_filename), 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: 
                    f.write(chunk)
    return local_filename

if __name__ == "__main__":
    from deviceInfo import deviceInfo
    device_info = deviceInfo("2sdsaee", "北京", "北京", "朝阳区")
    ip = "115.28.61.129"
    port = 5000
    model_type = "cetv_tf"

    # updateInfoOrder = UpdateInfoOrder()
    # updateInfoOrder.run(device_info, ip, port, model_type)

    # rollbackInfoOrder = RollbackInfoOrder()
    # rollbackInfoOrder.run(device_info, ip, port, model_type)

    updateModelFileOrder = UpdateModelFileOrder()
    updateModelFileOrder.run(device_info, ip, port, model_type)

    # rollbackModelFileOrder = RollbackModelFile()
    # rollbackModelFileOrder.run(device_info, ip, port, model_type)