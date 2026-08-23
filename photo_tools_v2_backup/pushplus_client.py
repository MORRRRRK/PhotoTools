"""
pushplus_client.py - PushPlus 推送客户端
用于推送技术报告、评分报告等到微信
"""

import json
from typing import Optional


class PushPlusClient:
    """PushPlus 推送服务封装。"""

    API_URL = "https://www.pushplus.plus/send"

    def __init__(self, token: str):
        self.token = token

    def send(self, title: str, content: str, template: str = "markdown",
             channel: Optional[str] = None) -> dict:
        """
        发送消息到 PushPlus。
        
        Args:
            title: 消息标题
            content: 消息内容（markdown 或 html）
            template: "markdown" | "html" | "txt"
            channel: 可选，指定推送渠道
            
        Returns:
            响应 dict
        """
        import requests

        payload = {
            "token": self.token,
            "title": title,
            "content": content,
            "template": template,
        }
        if channel:
            payload["channel"] = channel

        try:
            resp = requests.post(self.API_URL, json=payload, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"code": 500, "msg": str(e)}

    def send_report(self, title: str, content: str) -> dict:
        """发送报告（markdown 格式的快捷方法）。"""
        return self.send(title=title, content=content, template="markdown")

    @staticmethod
    def build_score_report(scan_results: list) -> str:
        """
        构建评分报告的 markdown 内容。
        预留接口，后续可用于推送评分结果。
        """
        if not scan_results:
            return "暂无评分数据。"

        lines = ["## 照片质量评分报告\n"]
        for item in scan_results:
            lines.append(f"### {item.get('file', '未知')}")
            lines.append(f"- 综合评分: {item.get('total_score', 'N/A')}/100")
            lines.append(f"- 构图: {item.get('composition', 'N/A')}/100")
            lines.append(f"- 曝光: {item.get('exposure', 'N/A')}/100")
            lines.append(f"- 清晰度: {item.get('sharpness', 'N/A')}/100")
            lines.append(f"- 色彩: {item.get('color', 'N/A')}/100")
            lines.append(f"- 噪点: {item.get('noise', 'N/A')}/100")
            lines.append(f"- 建议: {item.get('recommendation', '')}\n")

        return "\n".join(lines)
