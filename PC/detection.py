"""Validated MCU learning telemetry; scores are deviations, not probabilities."""
from dataclasses import dataclass
import re
STATES = ('未学习', '学习中', '滤波预热', '正常', '疑似异常', '异常报警')
_PATTERN = re.compile(r'DETECT state=(\d+) progress=(\d+) score_x100=(\d+) model=(\d+) blocks=(\d+)(?: NVM=-?\d+)?')
@dataclass(frozen=True)
class Detection:
    state: int
    progress: int
    score: float
    model: bool
    blocks: int

def parse_detection(line):
    match = _PATTERN.fullmatch(line.strip())
    if not match:
        return None
    state, progress, score, model, blocks = map(int, match.groups())
    if not (0 <= state < len(STATES) and 0 <= progress <= 100 and
            0 <= score <= 99900 and model in (0, 1) and 0 <= blocks <= 150):
        return None
    return Detection(state, progress, score / 100, bool(model), blocks)
