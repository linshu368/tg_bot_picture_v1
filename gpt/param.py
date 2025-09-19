import os
from gpt.utils.files_utils import read_prompt_template

file_dir_path = os.path.dirname(os.path.abspath(__file__))


###############################  diff改动总结  #####################################
commit_process_diff_prompt_path = os.path.join(file_dir_path, "prompt", "commit_process_diff.prompt")
commit_process_diff_prompt_template = read_prompt_template(commit_process_diff_prompt_path)

push_log_title_prompt_path = os.path.join(file_dir_path, "prompt", "push_log_title.prompt")
push_log_title_prompt_template = read_prompt_template(push_log_title_prompt_path)

push_log_arch2pr_prompt_path = os.path.join(file_dir_path, "prompt", "push_log_arch2pr.prompt")
push_log_arch2pr_prompt_template = read_prompt_template(push_log_arch2pr_prompt_path)


