from .most_common import MostCommonHeuristic
from .most_time import MostTimeHeuristic
from collections import defaultdict
from itertools import product
from mosek.fusion import Model, Domain, Expr, ObjectiveSense, AccSolutionStatus
import sys

class BIPModelMosek(object):
    '''Reference binary integer program: full model with no decomposition'''
    _slug = 'bip-model-mosek'

    def __init__(self, presol=None, heur=None, time=None):
        self.presol = presol
        self.heur = heur
        self.time = time # in minutes

    def slug(self):
        slug = BIPModelMosek._slug
        if self.presol is not None:
            slug = '%s-presol-%s' % (slug, self.presol)
        if self.heur is not None:
            slug = '%s-heur-%s' % (slug, self.heur)
        return slug

    def solve(self, problem, saver):
        # Construct model.
        self.problem = problem
        self.model = model = Model()
        if self.time is not None:
            model.setSolverParam('mioMaxTime', 60.0  * int(self.time))

        # x[i,s,c] = 1 if image i runs command c during stage s, 0 otherwise.
        self.x = x = {}
        for i, cmds in problem.images.items():
            for s, c in product(problem.stages[i], cmds):
                x[i,s,c] = model.variable(
                    'x[%s,%s,%s]' % (i,s,c), 1,
                    Domain.inRange(0.0, 1.0),
                    Domain.isInteger()
                )

        # y[ip,iq,s,c] = 1 if images ip & iq have a shared path through stage
        #                s by running command c during s, 0 otherwise.
        y = {}
        for (ip, iq), cmds in problem.shared_cmds.items():
            for s, c in product(problem.shared_stages[ip, iq], cmds):
                y[ip,iq,s,c] = model.variable(
                    'y[%s,%s,%s,%s]' % (ip,iq,s,c), 1,
                    Domain.inRange(0.0, 1.0),
                    Domain.isInteger()
                    # Domain.inRange(0.0, 1.0)
                )

        # TODO: need to remove presolved commands so the heuristic doesn't try them.
        # TODO: Add a heuristic initial solution.
        # TODO: Presolving

        # Each image one command per stage, and each command once.
        for i in problem.images:
            for s in problem.stages[i]:
                model.constraint('c1[%s,%s]' % (i,s),
                    Expr.add([x[i,s,c] for c in problem.images[i]]),
                    Domain.equalsTo(1.0)
                )
            for c in problem.images[i]:
                model.constraint('c2[%s,%s]' % (i,c),
                    Expr.add([x[i,s,c] for s in problem.stages[i]]),
                    Domain.equalsTo(1.0)
                )

        # Find shared paths among image pairs.
        for (ip, iq), cmds in problem.shared_cmds.items():
            for s in problem.shared_stages[ip,iq]:
                for c in cmds:
                    model.constraint('c3[%s,%s,%s,%s]' % (ip,iq,s,c),
                        Expr.sub(y[ip,iq,s,c], x[ip,s,c]),
                        Domain.lessThan(0.0)
                    )
                    model.constraint('c4[%s,%s,%s,%s]' % (ip,iq,s,c),
                        Expr.sub(y[ip,iq,s,c], x[iq,s,c]),
                        Domain.lessThan(0.0)
                    )
                if s > 1:
                    lhs = Expr.add([y[ip,iq,s,c] for c in cmds])
                    rhs = Expr.add([y[ip,iq,s-1,c] for c in cmds])
                    model.constraint('c5[%s,%s,%s,%s]' % (ip,iq,s,c),
                        Expr.sub(lhs, rhs), Domain.lessThan(0.0)
                    )

        if y:
            obj = Expr.add(y.values())
        else:
            obj = 0.0
        model.objective('z', ObjectiveSense.Maximize, obj)
        model.setLogHandler(sys.stdout)
        model.acceptedSolutionStatus(AccSolutionStatus.Feasible)
        model.solve()

        # Create optimal schedule.
        schedule = defaultdict(list)
        for i, stages in problem.stages.items():
            for s in stages:
                for c in problem.images[i]:
                    if x[i,s,c].level()[0] > 0.5:
                        schedule[i].append(c)
                        break

        saver(schedule)
