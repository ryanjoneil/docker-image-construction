from .most_common import MostCommonHeuristic
from .most_time import MostTimeHeuristic

ALL_SOLVERS = MostCommonHeuristic, MostTimeHeuristic

__all__ = 'ALL_SOLVERS',

