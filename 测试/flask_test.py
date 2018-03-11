import os
from flask import Flask, Response, send_file, send_from_directory, request
import json

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

@app.route("/cetv_tf/<filename>", methods=['GET'])
def download_file(filename):
    print(request.args.get("deviceFixId"))
    directory = os.getcwd()  # 假设在当前目录
    return send_from_directory(os.path.join(directory, "cetv_tf_source"), filename, as_attachment=True)

@app.route('/')
def root():
    print(request.args.get("deviceFixId"))
    t = {
        "add": "add",
        "deviceFixId": "2sdsaee",
        "ip": "127.0.0.1",
        "regionProvince": "北京",
        "regionCity": "北京",
        "regionArea": "朝阳区",
        "pictureSize": {
          "北京卫视": [
            12,
            23,
            24,
            24
          ],
          "上海卫视": [
            12,
            23,
            42,
            12
          ],
          "安徽卫视": [
            23,
            42,
            12,
            23
          ],
          "湖南卫视": [
            11,
            223,
            12,
            22
          ],
          "重庆卫视": [
            12,
            23,
            23,
            23
          ],
          "湖北卫视": [
            12,
            23,
            21,
            21
          ]
        }
    }
    return Response(json.dumps(t), mimetype='application/json')

if __name__ == '__main__':
    app.debug = True
    app.run(port=5000)