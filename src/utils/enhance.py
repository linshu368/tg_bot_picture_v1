import os
from typing import Tuple, Optional

def enhance_user_input(original_content: str, instruction_type: str, user_context: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    根据指令类型对用户输入进行增强，返回 (增强后的内容, 实际使用的指令文本或 None)
    
    instruction_type: "system"（前3轮）或 "ongoing"（第4轮及以后）
    user_context: 若为空则使用 original_content 作为用户信息段
    """
    if user_context is None:
        user_context = original_content or ""
    
    if instruction_type == "system":
        template = (
            "##系统指令：以下为最高优先级指令。\n"
            "{system_instructions}"
            "##用户指令:{user_context}\n"
        )
        instructions = os.getenv('SYSTEM_INSTRUCTIONS', '') or ''
        enhanced_content = template.format(
            user_context=user_context,
            system_instructions=instructions
        )
        return enhanced_content, (instructions or None)
    elif instruction_type == "ongoing":
        template = (

            "##系统指令：\n"
            "{ongoing_instructions}"
            "##用户指令:{user_context}\n"
        )
        instructions = os.getenv('ONGOING_INSTRUCTIONS', '') or ''
        enhanced_content = template.format(
            user_context=user_context,
            ongoing_instructions=instructions
        )
        return enhanced_content, (instructions or None)
    else:
        raise ValueError(f"不支持的指令类型: {instruction_type}")


