def normalize_value(value: str):
    """
    去掉两端空白，保留大小写；空白字符串或非字符串抛 ValueError。
    """
    if not isinstance(value, str):
        raise ValueError("输入必须是字符串")
    value = value.strip()
    if value == "":
        raise ValueError("输入不能为空字符串")
    return value

def format_cents(cents: int) -> str:
    """
    非负整数分转为两位小数的字符串，不带“元”；
    拒绝 bool、float 和负数。用 divmod() 或整数除法与余数处理。
    """
    if not isinstance(cents, int) or isinstance(cents, bool) or cents < 0:
        # 注意 True 和 False 是 int 的子类，需排除
        raise ValueError("输入必须是非负整数")
    yuan, fen = divmod(cents, 100)
    return f"{yuan}.{fen:02d}"

if __name__ == "__main__":
    value = "Alice"
    normalized_value = normalize_value(value)
    print(f"解析后的值: '{normalized_value}'")
    
    value = " "
    try:
        normalize_value(value)
    except ValueError as e:
        print(f"错误: {e}")

        
    cents = 12345
    formatted_value = format_cents(cents)
    print(f"格式化后的金额: {formatted_value}")

    cents = True
    try:
        format_cents(cents)
    except ValueError as e:
        print(f"格式化金额错误: {e}")