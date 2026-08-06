from .course_outline import Lesson
from .workflow_plan import WorkflowTask
R_CODE_SCHEMA = '{"code":"complete executable R script","expected_outputs":["relative/path"],"knowledge_ids":["DOC-..."]}'
SYSTEM_PROMPT = (
    'You are a senior R developer creating reproducible teaching examples. '
    'Return one complete executable R script. Do not install packages or access the network. '
    'Do not use system(), shell(), unlink(), file.remove(), download.file(), or external commands. '
    'Use relative paths only and set.seed(12345) when randomness is involved.'
)
def build_r_code_prompt(*,lesson:Lesson,task:WorkflowTask,knowledge:list[dict]):
    user = f'LESSON:\n{lesson.model_dump_json(indent=2)}\n\nTASK:\n{task.model_dump_json(indent=2)}\n\nKNOWLEDGE:\n{knowledge}'
    return SYSTEM_PROMPT, user, R_CODE_SCHEMA
