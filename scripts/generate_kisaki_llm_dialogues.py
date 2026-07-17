"""LLM 增强生成月社妃对话数据（通过 vLLM 服务）。

在服务器上执行，调用 localhost:8001 的 vLLM（Qwen3-8B-Instruct-AWQ）。
生成 12 类场景 × 每类 N 条对话，输出 ShareGPT 格式。
"""
import json
import requests
import sys
import time
import re
from pathlib import Path

VLLM_URL = "http://127.0.0.1:8001/v1/chat/completions"
MODEL = "qwen3-8b-instruct-awq"

CHARACTER_DESC = """月社妃，纸上魔法使系列女主角。性格特点：
- 冷静理智，话不多但每句都有分量
- 对克丽索贝莉露有复杂情感
- 内心柔软但不轻易表露
- 喜欢读书，常待在幻想图书馆
- 说话带有一定的文学气质，偶尔引用书本内容
- 不会过度热情，但也不冷漠
- 面对亲近的人会展现温柔一面
- 不会用"嘿嘿""哈哈"等语气词，比较克制"""

SYSTEM_PROMPT = "你正在扮演月社妃。请依据给定角色设定和原作中的语言习惯，自然地回应。"

SCENES = [
    ("日常问候", "打招呼、问好、早晚安、天气"),
    ("闲聊吐槽", "今天发生的事、遇到的人、看到的趣闻"),
    ("书籍讨论", "讨论书籍、安利喜欢的书、吐槽难懂的书"),
    ("情感倾诉", "开心/难过/烦恼/压力、求安慰、分享秘密"),
    ("求助建议", "问问题、求建议、人际关系问题"),
    ("观点讨论", "对某件事的看法、争议话题、立场表达"),
    ("回忆故事", "讲述过去的经历、有趣的故事"),
    ("幽默互怼", "朋友之间开玩笑、相互调侃、冷笑话"),
    ("深度关怀", "一方状态不好时另一方关心、鼓励、陪伴"),
    ("突发奇想", "突然想到的点子、天马行空的对话"),
    ("角色设定", "关于妃的过去、能力、喜好、与克丽索贝莉露的关系"),
    ("幻想图书馆", "在图书馆里的对话、书籍话题、安静的氛围"),
]


def parse_think(text):
    """过滤 Qwen3 thinking 模式的 <think> 标签。"""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def generate_one_dialogue(scene_name, scene_desc, turns=3, max_retries=2):
    """生成一条多轮对话。"""
    turn_guide = {
        1: "单轮对话，用户说一句、妃回复一句",
        2: "两轮对话，用户发起→妃回应→用户追问→妃再回应",
        3: "三轮对话，有起承转合",
        4: "四轮对话，话题有轻微转折",
    }.get(turns, f"{turns}轮对话")

    prompt = f"""请根据以下角色设定和场景，生成一段月社妃的{turn_guide}。

【角色设定】
{CHARACTER_DESC}

【场景】{scene_name}：{scene_desc}

【要求】
1. 妃的回复必须符合角色设定：冷静理智、话不多但有分量、文学气质
2. 妃的每条回复长度不少于 15 字，避免极短回复（如"嗯""好""哦"）
3. 不要让妃使用"嘿嘿""哈哈""哇"等过于活泼的语气词
4. 妃可以偶尔引用书本内容，展现文学气质
5. 直接输出对话内容，用以下格式：

user: 用户的话
assistant: 妃的回复
user: 用户的追问
assistant: 妃的再回复
（以此类推）"""

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(VLLM_URL, json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 1024,
                "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
            }, timeout=60)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            content = parse_think(content)
            conversations = parse_dialogue(content)
            if validate_conversations(conversations, turns):
                return conversations
        except Exception as e:
            if attempt == max_retries:
                print(f"  [WARN] 生成失败 ({scene_name}): {e}", file=sys.stderr)
                return None
            time.sleep(1)
    return None


def parse_dialogue(text):
    """解析 'user: ... / assistant: ...' 格式。"""
    conversations = []
    current_role = None
    current_text = []

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(user|assistant|妃|月社妃)\s*[:：]\s*(.+)", line, re.IGNORECASE)
        if match:
            if current_role and current_text:
                role = "human" if current_role in ("user",) else "gpt"
                conversations.append({"from": role, "value": "\n".join(current_text).strip()})
            speaker = match.group(1).lower()
            current_role = "user" if speaker in ("user",) else "assistant"
            current_text = [match.group(2)]
        else:
            if current_role:
                current_text.append(line)

    if current_role and current_text:
        role = "human" if current_role in ("user",) else "gpt"
        conversations.append({"from": role, "value": "\n".join(current_text).strip()})

    return conversations


def validate_conversations(conversations, expected_turns):
    """校验对话质量。"""
    if len(conversations) < 2:
        return False
    if len(conversations) % 2 != 0:
        conversations = conversations[:-1]  # 去掉最后多余的一条
    # 检查交替
    for i, msg in enumerate(conversations):
        expected = "human" if i % 2 == 0 else "gpt"
        if msg["from"] != expected:
            return False
    # 检查妃的回复长度
    for msg in conversations[1::2]:
        if len(msg["value"]) < 10:
            return False
    return True


def main():
    per_scene = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    output_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/kisaki_llm_generated.json"

    all_dialogues = []
    turn_options = [2, 3, 3, 4, 3, 2, 3, 4, 3, 2, 3, 3]  # 每个场景的轮次

    print(f"开始生成：{len(SCENES)} 场景 × {per_scene} 条 = {len(SCENES) * per_scene} 条")

    for scene_idx, (scene_name, scene_desc) in enumerate(SCENES):
        turns = turn_options[scene_idx % len(turn_options)]
        print(f"\n[{scene_idx+1}/{len(SCENES)}] {scene_name} ({turns}轮, {per_scene}条)")

        for i in range(per_scene):
            convs = generate_one_dialogue(scene_name, scene_desc, turns=turns)
            if convs:
                dialogue = {
                    "id": f"kisaki_llm_{scene_idx:02d}_{i:03d}",
                    "system": SYSTEM_PROMPT,
                    "conversations": convs,
                    "metadata": {
                        "character": "月社妃",
                        "source": "llm_generated",
                        "scene": scene_name,
                        "scene_desc": scene_desc,
                        "turns": turns,
                        "model": MODEL,
                    },
                }
                all_dialogues.append(dialogue)
                print(f"  [{i+1}/{per_scene}] OK ({len(convs)} 条消息)")
            else:
                print(f"  [{i+1}/{per_scene}] FAIL")

    # 写入文件
    output = Path(output_path)
    output.write_text(json.dumps(all_dialogues, ensure_ascii=False, indent=2), encoding="utf-8")

    # 统计
    total_msgs = sum(len(d["conversations"]) for d in all_dialogues)
    assistant_msgs = [m["value"] for d in all_dialogues for m in d["conversations"] if m["from"] == "gpt"]
    avg_len = sum(len(m) for m in assistant_msgs) / max(len(assistant_msgs), 1)

    print(f"\n=== 生成完成 ===")
    print(f"总对话数: {len(all_dialogues)}")
    print(f"总消息数: {total_msgs}")
    print(f"妃回复数: {len(assistant_msgs)}")
    print(f"妃回复平均长度: {avg_len:.1f} 字")
    print(f"输出文件: {output_path}")


if __name__ == "__main__":
    main()
