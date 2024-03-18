import json
import os
import subprocess
import uuid
from http.client import HTTPException
from threading import Thread, Event

from flask import Flask, request, send_from_directory, after_this_request
from werkzeug.utils import secure_filename

import backend.main
# # 初次运行检查运行环境是否正常
# from paddle import fluid
#
# fluid.install_check.run_check()

# Assuming your backend.db and backend.main modules are compatible with Flask or don't need specific adaptations.
from backend.db import db_api
# import backend.main

# import torch
# # 确保 CUDA 可用
# if torch.cuda.is_available():
#     # 创建一个随机张量并将其移到 GPU 上，以触发 CUDA 初始化
#     x = torch.rand(5, 5).cuda()
#     print(f"手动初始化CUDA {x}")

app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*"}})  # 仅用于示例，实际部署时应限制为真实的前端地址

UPLOAD_FOLDER = db_api.get_temp_dir()
ALLOWED_EXTENSIONS = {'mp4', 'mov'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 设置上传文件大小限制为500MB
app.config['MAX_CONTENT_LENGTH'] = 1500 * 1024 * 1024  # 1500MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/extractor', methods=['POST'])
def extractor():
    """
    :param file 视频
    :param area 区域 (startY, endY, startX, endX)
    """
    print("start inference")
    if 'file' not in request.files:
        raise HTTPException(400, 'No selected file')
    file = request.files['file']
    area = request.form['area']
    print(area)

    if file.filename == '':
        raise HTTPException(400, 'No selected file')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"temp_{uuid.uuid4()}.{filename.rsplit('.', 1)[1].lower()}"
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        # file.save(temp_filepath)
        # 使用流式写入文件
        with open(temp_filepath, 'wb') as f:
            chunk_size = 4096  # 可以根据需要调整块的大小
            while True:
                chunk = file.stream.read(chunk_size)
                if len(chunk) == 0:
                    break
                f.write(chunk)

        area_list = json.loads(area)
        subtitle_area = (area_list[0], area_list[1], area_list[2], area_list[3])

        # 构建命令行命令
        command = [
            'python3', './backend/main.py',
            '--video-path', temp_filepath,
            '--y-min', str(subtitle_area[0]),
            '--y-max', str(subtitle_area[1]),
            '--x-min', str(subtitle_area[2]),
            '--x-max', str(subtitle_area[3]),
            '--gpu_mem', str(2048),
            '--max_batch_size', str(32),
            # '--cls_batch_num', str(32),
        ]

        try:

            # 手动打印命令
            print("Executing command:", " ".join(command))

            subprocess.run(command, check=True)
            srt_path = os.path.join(os.path.splitext(temp_filepath)[0] + '.srt')
            output_file = srt_path

            @after_this_request
            def remove_file(response):
                os.remove(temp_filepath)
                return response
            print(f"output_file={output_file}")
            return send_from_directory(directory=os.path.dirname(output_file),
                                       path=os.path.basename(output_file),
                                       as_attachment=True)
        except Exception as e:
            print(e)
            raise HTTPException(500, str(e))
    else:
        raise HTTPException(500, "Invalid file type.")

@app.route('/')
def main():
    return {"message": "Welcome to the watermark removal API!"}

if __name__ == "__main__":
    print(f"run in port 8003 start")
    app.run(host='0.0.0.0', port=8003, debug=False)
