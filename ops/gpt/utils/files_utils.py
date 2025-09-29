import json


def read_prompt_template(prompt_path):
    """
    读取指定路径的提示模板文件并返回其内容。

    :param prompt_path: 提示模板文件的路径
    :return: 文件内容字符串
    """
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    return prompt_template


def write_results_to_file(output_file, results):
    """
    将 results（一般是一个列表）以多行缩进 JSON 的形式写到文件里
    """
    with open(output_file, "w", encoding="utf-8") as outfile:
        json.dump(results, outfile, ensure_ascii=False, indent=4)

