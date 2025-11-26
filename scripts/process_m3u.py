#!/usr/bin/env python3
import re
import sys
from datetime import datetime

def fetch_and_process():
    input_url = sys.argv[1]
    import requests
    response = requests.get(input_url)
    response.raise_for_status()
    lines = response.text.splitlines(keepends=True)  # 保留原始换行符

    with open('unicast-catchup.m3u', 'w', encoding='utf-8') as f1, \
         open('unicast-rtp.m3u', 'w', encoding='utf-8') as f2:

        for line in lines:
            # 修改 catchup-source 参数
            modified = re.sub(
                r'catchup-source="([^"]+?)\?tvdr=\{utc:YmdHMS\}GMT-\{utcend:YmdHMS\}GMT"',
                r'catchup-source="\1?tvdr=${(b)yyyyMMddHHmmss}GMT-${(e)yyyyMMddHHmmss}GMT&r2h-seek-offset=-28800"',
                line
            )

            # 写入第一个文件
            f1.write(modified)

            # 转换 RTSP -> HTTP
            rtp_line = re.sub(r'(catchup-source="|)(rtsp://[^"]+)"?', 
                              lambda m: m.group(1) + "http://192.168.100.1:5140/rtsp/" + m.group(2) + '"',
                              modified)
            f2.write(rtp_line)

if __name__ == '__main__':
    try:
        fetch_and_process()
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        sys.exit(1)

