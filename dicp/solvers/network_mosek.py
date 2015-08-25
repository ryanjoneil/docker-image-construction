from .most_common import MostCommonHeuristic
from .most_time import MostTimeHeuristic
from collections import defaultdict
from itertools import product
from mosek.fusion import Model, Domain, Expr, ObjectiveSense, AccSolutionStatus
import sys

class NetworkMosek(object):
    '''Network binary integer program: full model with no decomposition'''
    _slug = 'network-mosek'

    def __init__(self, presol=None, heur=None, time=None):
        self.presol = presol
        self.heur = heur
        self.time = time # in minutes

    def slug(self):
        return NetworkMosek._slug

    def solve(self, problem, saver):
        # Construct model.
        self.problem = problem
        self.model = model = Model()
        if self.time is not None:
            model.setSolverParam('mioMaxTime', 60.0  * int(self.time))

        # x[1,c] = 1 if the master schedule has (null, c) in its first stage
        # x[s,c1,c2] = 1 if the master schedule has (c1, c2) in stage s > 1
        x = {}
        for s in problem.all_stages:
            if s == 1:
                # First arc in the individual image path.
                for c in problem.commands:
                    x[1,c] = model.variable(
                        'x[1,%s]' % c, 1,
                        Domain.inRange(0.0, 1.0),
                        Domain.isInteger()
                    )

            else:
                # Other arcs.
                for c1, c2 in product(problem.commands, problem.commands):
                    if c1 == c2:
                        continue
                    x[s,c1,c2] = model.variable(
                        'x[%s,%s,%s]' % (s,c1,c2), 1,
                        Domain.inRange(0.0, 1.0),
                        Domain.isInteger()
                    )

        smax = max(problem.all_stages)
        obj = [0.0]

        # TODO: deal with images that do not have the same number of commands.
        # t[s,c] is the total time incurred at command c in stage s
        t = {}
        for s in problem.all_stages:
            for c in problem.commands:
                t[s,c] = model.variable(
                    't[%s,%s]' % (c,s), 1,
                    Domain.greaterThan(0.0)
                )
                if s == 1:
                    model.constraint('t[1,%s]' % c,
                        Expr.sub(t[1,c], Expr.mul(float(problem.commands[c]), x[1,c])),
                        Domain.greaterThan(0.0)
                    )
                else:
                    rhs = [0.0]
                    for c1, coeff in problem.commands.items():
                        if c1 == c:
                            continue
                        else:
                            rhs = Expr.add(rhs, Expr.mulElm(t[s-1,c1], x[s,c1,c]))
                    model.constraint('t[%s,%s]' % (s,c),
                        Expr.sub(t[1,c], rhs),
                        Domain.greaterThan(0.0)
                    )

                    # Objective function = sum of aggregate  comand times
                    if s == smax:
                        obj = Expr.add(obj, t[s,c])

        # y[i,1,c] = 1 if image i starts by going to c
        # y[i,s,c1,c2] = 1 if image i goes from command c1 to c2 in stage s > 1
        y = {}
        for i, cmds in problem.images.items():
            for s in problem.stages[i]:
                if s == 1:
                    # First arc in the individual image path.
                    for c in cmds:
                        y[i,1,c] = model.variable(
                            'y[%s,1,%s]' % (i,c), 1,
                            Domain.inRange(0.0, 1.0),
                            Domain.isInteger()
                        )
                        model.constraint('x_y[i%s,1,c%s]' % (i,c),
                            Expr.sub(x[1,c], y[i,1,c]),
                            Domain.greaterThan(0.0)
                        )

                else:
                    # Other arcs.
                    for c1, c2 in product(cmds, cmds):
                        if c1 == c2:
                            continue
                        y[i,s,c1,c2] = model.variable(
                            'y[%s,%s,%s,%s]' % (i,s,c1,c2), 1,
                            Domain.inRange(0.0, 1.0),
                            Domain.isInteger()
                        )
                        model.constraint('x_y[i%s,s%s,c%s,c%s]' % (i,s,c1,c2),
                            Expr.sub(x[s,c1,c2], y[i,s,c1,c2]),
                            Domain.greaterThan(0.0)
                        )

            for c in cmds:
                # Each command is an arc destination exactly once.
                arcs = [y[i,1,c]]
                for c1 in cmds:
                    if c1 == c:
                        continue
                    arcs.extend([y[i,s,c1,c] for s in problem.stages[i][1:]])

                model.constraint('y[i%s,c%s]' % (i,c),
                    Expr.add(arcs),
                    Domain.equalsTo(1.0)
                )

                # Network balance equations (stages 2 to |stages|-1).
                # Sum of arcs in = sum of arcs out.
                for s in problem.stages[i][:len(problem.stages[i])-1]:
                    if s == 1:
                        arcs_in = [y[i,1,c]]
                    else:
                        arcs_in = [y[i,s,c1,c] for c1 in cmds if c1 != c]

                    arcs_out = [y[i,s+1,c,c2] for c2 in cmds if c2 != c]

                    model.constraint('y[i%s,s%s,c%s]' % (i,s,c),
                        Expr.sub(Expr.add(arcs_in), Expr.add(arcs_out)),
                        Domain.equalsTo(0.0)
                    )


        model.objective('z', ObjectiveSense.Minimize, Expr.add(x.values()))
#        model.objective('z', ObjectiveSense.Minimize, obj)
        model.setLogHandler(sys.stdout)
        model.acceptedSolutionStatus(AccSolutionStatus.Feasible)
        model.solve()

        # Create optimal schedule.
        schedule = defaultdict(list)
        for i, cmds in problem.images.items():
            for s in problem.stages[i]:
                if s == 1:
                    # First stage starts our walk.
                    for c in cmds:
                        if y[i,s,c].level()[0] > 0.5:
                            schedule[i].append(c)
                            break
                else:
                    # After that we know what our starting point is.
                    for c2 in cmds:
                        if c2 == c:
                            continue
                        if y[i,s,c,c2].level()[0] > 0.5:
                            schedule[i].append(c2)
                            c = c2
                            break

        saver(schedule)
