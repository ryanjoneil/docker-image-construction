from collections import defaultdict
from itertools import product
from mosek.fusion import Model, Domain, Expr, ObjectiveSense, AccSolutionStatus
import sys

class CliqueModelMosek(object):
    '''Transformed set packing model over maximal cliques'''
    _slug = 'clique-model-mosek'

    def __init__(self, presol=None, heur=None, time=None):
        self.time = time # in minutes

    def slug(self):
        return CliqueModelMosek._slug

    def solve(self, problem, saver):
        # Construct model.
        self.problem = problem

        # Do recursive maximal clique detection.
        self.clique_data = clique_data = problem.cliques()

        self.model = model = Model()
        if self.time is not None:
            model.setSolverParam('mioMaxTime', 60.0  * int(self.time))

        # x[i] = 1 if clique i is used, 0 otherwise
        self.x = {}
        self._inter = 1
        self._obj = []
        self._update(clique_data)

        model.objective('z', ObjectiveSense.Maximize, Expr.add(self._obj))
        model.setLogHandler(sys.stdout)
        model.acceptedSolutionStatus(AccSolutionStatus.Feasible)
        model.solve()

        # Translate the output of this to a schedule.
        schedule = defaultdict(list)
        self._translate(schedule, clique_data)

        # Add anything that remains, post clique model.
        for img, cmds in schedule.items():
            remain = set(problem.images[img]) - set(cmds)
            schedule[img].extend(remain)

        saver(schedule)

    def _update(self, clique_data, parent=None):
        for c in clique_data['cliques']:
            self.x[c['name']] = v = self.model.variable(
                c['name'],
                Domain.inRange(0.0, 1.0),
                Domain.isInteger()
            )
            self._obj.append(Expr.mul(float(c['cache_use']), v))

            if parent is not None:
                self.model.constraint(
                    'c-%s-%s' % (c['name'], parent['name']),
                    Expr.sub(v, self.x[parent['name']]),
                    Domain.lessThan(0.0)
                )

            for child in c['children']:
                self._update(child, c)

        for inter in clique_data['intersections']:
            self.model.constraint(
                'iter-%d' % self._inter,
                Expr.add([self.x[i] for i in inter]),
                Domain.lessThan(1.0)
            )
            self._inter += 1

    def _translate(self, schedule, data):
        for c in data['cliques']:
            if self.x[c['name']].level()[0] > 0.5:
                for img, cmd in product(c['images'], c['commands']):
                    schedule[img].append(cmd)
                for child in c['children']:
                   self._translate(schedule, c['children'])


