import os
from gpt.utils.files_utils import read_prompt_template

file_dir_path = os.path.dirname(os.path.abspath(__file__))


###############################  diff改动总结  #####################################
commit_msg_prompt_path = os.path.join(file_dir_path, "prompt", "commit_msg.prompt")
commit_msg_prompt_template = read_prompt_template(commit_msg_prompt_path)
