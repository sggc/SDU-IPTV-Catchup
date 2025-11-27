#!/usr/bin/env python3
import requests
import re
from datetime import datetime, timezone, timedelta

# 配置
SOURCE_URL = "https://raw.githubusercontent.com/plsy1/iptv/refs/heads/main/multicast/multicast-weifang.m3u"
OUTPUT_FILE = "multicast-rtp.m3u"

class MulticastProcessor:
    def __init__(self, source_url, output_file):
        self.source_url = source_url
        self.output_file = output_file
        self.channels = []

    def download_content(self):
        print(f"📥 下载源文件: {self.source_url}")
        resp = requests.get(self.source_url, timeout=10)
        resp.raise_for_status()
        return resp.text

    def parse_m3u(self, content):
        """解析M3U，提取频道信息"""
        lines = content.splitlines()
        self.channels = []
        current_extinf = None

        for line in lines:
            if line.startswith('#EXTINF:') and 'tvg-name=' in line:
                current_extinf = line
            elif not line.startswith('#') and current_extinf and line.strip():
                # 有效URL行
                self.channels.append({
                    'extinf': current_extinf,
                    'url': line.strip(),
                    'name': self._extract_name(current_extinf),
                    'tvg_name': self._extract_attr(current_extinf, 'tvg-name'),
                    'group_title': self._extract_attr(current_extinf, 'group-title')
                })
                current_extinf = None

    def _extract_name(self, extinf):
        match = re.search(r',([^,]*)$', extinf)
        return match.group(1).strip() if match else ""

    def _extract_attr(self, extinf, attr):
        m = re.search(f'{attr}="([^"]*)"', extinf)
        return m.group(1) if m else ""

    def update_group_title(self, channel, new_group):
        old = channel['extinf']
        if 'group-title=' in old:
            new_extinf = re.sub(r'group-title="[^"]*"', f'group-title="{new_group}"', old)
        else:
            new_extinf = old.replace('#EXTINF:-1 ', f'#EXTINF:-1 group-title="{new_group}" ')
        channel['extinf'] = new_extinf
        channel['group_title'] = new_group

    def find_index(self, patterns, exact=False):
        for i, ch in enumerate(self.channels):
            name = ch['name']
            if exact:
                if any(p == name for p in patterns):
                    return i
            else:
                if any(p in name for p in patterns):
                    return i
        return -1

    def find_all_indices(self, patterns, exact=False):
        indices = []
        for i, ch in enumerate(self.channels):
            name = ch['name']
            if exact:
                if any(p == name for p in patterns):
                    indices.append(i)
            else:
                if any(p in name for p in patterns):
                    indices.append(i)
        return indices

    def move_after(self, src_patterns, target_pattern, exact=False):
        target_idx = self.find_index([target_pattern], exact=exact)
        if target_idx == -1:
            print(f"⚠️ 未找到目标频道 '{target_pattern}'")
            return
        src_indices = self.find_all_indices(src_patterns, exact=exact)
        if not src_indices:
            return
        # 从后往前移除，避免索引错乱
        moved = []
        for idx in sorted(src_indices, reverse=True):
            moved.insert(0, self.channels.pop(idx))
        # 插入到目标后
        pos = target_idx + 1
        for ch in moved:
            self.channels.insert(pos, ch)
            pos += 1

    def apply_rules(self):
        print("🔧 应用频道处理规则...")

        # 规则1: CGTN → 其他频道
        for i in self.find_all_indices(['CGTN']):
            self.update_group_title(self.channels[i], "其他频道")

        # 规则2: 复制山东卫视（精确）到CCTV1后，改为央视频道
        sd_idx = self.find_index(['山东卫视'], exact=True)
        cctv1_idx = self.find_index(['CCTV1', 'CCTV-1'])
        if sd_idx != -1 and cctv1_idx != -1:
            copied = self.channels[sd_idx].copy()
            self.update_group_title(copied, "央视频道")
            self.channels.insert(cctv1_idx + 1, copied)

        # 规则3: CCTV4欧洲/美洲 → 山东少儿之后
        self.move_after(['CCTV4欧洲', 'CCTV4美洲'], '山东少儿')

        # 规则4: 山东经济广播 → 广播频道 + 移到末尾
        radio_idx = self.find_index(['山东经济广播'], exact=True)
        if radio_idx != -1:
            self.update_group_title(self.channels[radio_idx], "广播频道")
            radio_ch = self.channels.pop(radio_idx)
            self.channels.append(radio_ch)

    def transform_urls(self):
        """转换直播源和 catchup-source"""
        for ch in self.channels:
            # 修改直播源: 192.168.0.1 → 192.168.100.1
            ch['url'] = re.sub(
                r'^http://192\.168\.0\.1:5140/rtp/',
                r'http://192.168.100.1:5140/rtp/',
                ch['url']
            )

            # 修改 catchup-source: rtsp:// → http://192.168.100.1:5140/rtsp/
            ch['extinf'] = re.sub(
                r'catchup-source="rtsp://',
                r'catchup-source="http://192.168.100.1:5140/rtsp/',
                ch['extinf']
            )

    def generate_output(self):
        beijing_time = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
        header = f"""#EXTM3U
# Generated by GitHub Actions
# Source: {SOURCE_URL}
# Processed at: {beijing_time} (北京时间)
# 处理规则:
# 1. CGTN频道改为"其他频道"
# 2. 复制山东卫视到CCTV1下面并改为"央视频道"
# 3. CCTV4欧洲/美洲移动到山东少儿之后
# 4. 山东经济广播移到末尾并改为"广播频道"
# 5. 直播源 IP 从 192.168.0.1 改为 192.168.100.1
# 6. catchup-source 协议转 HTTP 代理

"""

        lines = [header]
        for ch in self.channels:
            lines.append(ch['extinf'] + '\n')
            lines.append(ch['url'] + '\n')
        return ''.join(lines)

    def run(self):
        content = self.download_content()
        self.parse_m3u(content)
        print(f"✅ 解析完成，共 {len(self.channels)} 个频道")

        self.apply_rules()
        self.transform_urls()

        output = self.generate_output()
        with open(self.output_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(output)

        print(f"✅ 已生成: {self.output_file}")

if __name__ == '__main__':
    processor = MulticastProcessor(SOURCE_URL, OUTPUT_FILE)
    processor.run()
